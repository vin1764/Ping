"""A brand-new Supabase project, faked closely enough to test first-time setup.

Real Postgres (initdb in a temp folder) with Supabase's roles (anon,
authenticated, service_role with BYPASSRLS), an auth schema with
auth.jwt(), and NO automatic grants on new public tables (the newer
Supabase default that caused 'permission denied' for real). In front of it,
a small HTTP server that answers like Supabase's:
  - Management API: POST /v1/projects/<ref>/database/query, GET .../api-keys
  - Auth: /auth/v1/settings, /auth/v1/admin/users, /auth/v1/token
  - Data API (a small PostgREST): GET / POST (upsert) / PATCH / DELETE on
    /rest/v1/<table>, POST /rest/v1/rpc/<fn>; every request runs as the
    role the key/token maps to, so grants and RLS are really enforced.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

import psycopg

PG_BIN = "/usr/lib/postgresql/16/bin"
TOKEN = "sbp_test_access_token"
PUBLISHABLE = "sb_publishable_testkey123"
SECRET = "sb_secret_testkey456"
REF = "fakeprojectref"

BOOT = """
create role anon nologin noinherit;
create role authenticated nologin noinherit;
create role service_role nologin noinherit bypassrls;
grant usage on schema public to anon, authenticated, service_role;
create schema auth;
create table auth.users (id uuid primary key default gen_random_uuid(), email text unique,
  pw text, email_confirmed_at timestamptz, created_at timestamptz default now(), last_sign_in_at timestamptz);
create function auth.jwt() returns jsonb language sql stable as
  $$ select coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb $$;
grant usage on schema auth to anon, authenticated, service_role;
"""


def available() -> bool:
    return os.path.exists(f"{PG_BIN}/initdb") and shutil.which("runuser") is not None


class FakeSupabase:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="fake-supabase-")
        os.chmod(self.dir, 0o777)
        self.data = os.path.join(self.dir, "data")
        self.sock = self.dir
        self.port = 54000 + os.getpid() % 1000

    # ---------------------------------------------------------------- postgres
    def _pg(self, *args):
        subprocess.run(["runuser", "-u", "postgres", "--", *args], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def start(self):
        self._pg(f"{PG_BIN}/initdb", "-D", self.data, "-A", "trust", "-U", "postgres")
        self._pg(f"{PG_BIN}/pg_ctl", "-D", self.data, "-w", "-o",
                 f"-k {self.sock} -p {self.port} -c listen_addresses=''", "start")
        with self.conn() as c:
            c.execute(BOOT)
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), _handler(self))
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        return self

    def stop(self):
        try:
            self.http.shutdown()
        except Exception:
            pass
        subprocess.run(["runuser", "-u", "postgres", "--", f"{PG_BIN}/pg_ctl", "-D", self.data, "-m", "immediate",
                        "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.rmtree(self.dir, ignore_errors=True)

    def conn(self):
        return psycopg.connect(host=self.sock, port=self.port, user="postgres", dbname="postgres", autocommit=True)

    def as_role(self, role: str, claims: dict, sql: str, params=()):
        with self.conn() as c:
            with c.transaction():
                c.execute(f"set local role {role}")
                c.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
                cur = c.execute(sql, params)
                return cur.fetchall() if cur.description else []


def _token_for(email: str) -> str:
    claims = {"email": email, "role": "authenticated"}
    return "fakejwt." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode()


def _claims(token: str) -> dict | None:
    if token.startswith("fakejwt."):
        return json.loads(base64.urlsafe_b64decode(token[8:]))
    return None


def _handler(fake: FakeSupabase):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body):
            data = json.dumps(body, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"null") if n else None

        def _role(self):
            auth = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            claims = _claims(auth)
            if claims:
                return "authenticated", claims
            key = self.headers.get("apikey")
            if key == SECRET:
                return "service_role", {"role": "service_role"}
            if key == PUBLISHABLE:
                return "anon", {"role": "anon"}
            return None, None

        def do_GET(self):
            self._route("GET")

        def do_POST(self):
            self._route("POST")

        def do_PATCH(self):
            self._route("PATCH")

        def do_PUT(self):
            self._route("PUT")

        def do_DELETE(self):
            self._route("DELETE")

        def _route(self, method):
            parts = urlsplit(self.path)
            path, q = parts.path, dict(parse_qsl(parts.query, keep_blank_values=True))
            try:
                if path.startswith("/v1/projects/"):
                    return self._management(method, path, q)
                if path.startswith("/auth/v1/"):
                    return self._auth(method, path, q)
                if path.startswith("/rest/v1/"):
                    return self._rest(method, path, q)
                self._send(404, {"message": "not found"})
            except psycopg.Error as e:
                code = getattr(e, "sqlstate", "") or ""
                status = 403 if code == "42501" else 404 if code == "42P01" else 400
                self._send(status, {"code": code, "message": str(e).splitlines()[0]})

        # ------------------------------------------------------ management API
        def _management(self, method, path, q):
            if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                return self._send(401, {"message": "Unauthorized"})
            if not path.startswith(f"/v1/projects/{REF}/"):
                return self._send(404, {"message": "project not found"})
            if path.endswith("/database/query") and method == "POST":
                with fake.conn() as c:
                    cur = c.execute(self._body()["query"])
                    rows = cur.fetchall() if cur.description else []
                    cols = [d.name for d in cur.description] if cur.description else []
                return self._send(201, [dict(zip(cols, r)) for r in rows])
            if path.endswith("/api-keys"):
                return self._send(200, [{"name": "default", "type": "publishable", "api_key": PUBLISHABLE},
                                        {"name": "default", "type": "secret", "api_key": SECRET}])
            self._send(404, {"message": "not found"})

        # ------------------------------------------------------ auth
        def _auth(self, method, path, q):
            role, claims = self._role()
            if path == "/auth/v1/settings":
                return self._send(200 if role else 401, {"external": {"email": True}, "disable_signup": True,
                                                         "mailer_autoconfirm": False})
            if path.startswith("/auth/v1/admin/users"):
                if role != "service_role":
                    return self._send(401, {"message": "not admin"})
                with fake.conn() as c:
                    if method == "GET":
                        rows = c.execute("select id, email, email_confirmed_at, last_sign_in_at from auth.users").fetchall()
                        return self._send(200, {"users": [dict(id=str(r[0]), email=r[1], email_confirmed_at=r[2],
                                                               last_sign_in_at=r[3], identities=[{"provider": "email"}])
                                                          for r in rows]})
                    b = self._body()
                    pw = hashlib.sha256(b.get("password", "").encode()).hexdigest() if b.get("password") else None
                    if method == "POST":
                        if c.execute("select 1 from auth.users where email=%s", (b["email"],)).fetchone():
                            return self._send(422, {"code": "email_exists",
                                                    "msg": "A user with this email address has already been registered"})
                        uid = uuid.uuid4()
                        c.execute("insert into auth.users (id, email, pw, email_confirmed_at) values (%s,%s,%s, case when %s then now() end)",
                                  (uid, b["email"], pw, bool(b.get("email_confirm"))))
                        return self._send(200, {"id": str(uid), "email": b["email"]})
                    if method == "PUT":
                        uid = path.rsplit("/", 1)[-1]
                        c.execute("update auth.users set pw=coalesce(%s, pw), email_confirmed_at=coalesce(email_confirmed_at, now()) where id=%s",
                                  (pw, uid))
                        return self._send(200, {"id": uid})
            if path == "/auth/v1/token" and q.get("grant_type") == "password":
                if role != "anon":
                    return self._send(401, {"message": "Invalid API key"})
                b = self._body()
                with fake.conn() as c:
                    row = c.execute("select pw, email_confirmed_at from auth.users where email=%s",
                                    (b["email"].lower(),)).fetchone()
                    ok = row and row[0] == hashlib.sha256(b["password"].encode()).hexdigest() and row[1]
                    if not ok:
                        return self._send(400, {"error": "invalid_grant", "error_description": "Invalid login credentials"})
                    c.execute("update auth.users set last_sign_in_at=now() where email=%s", (b["email"].lower(),))
                return self._send(200, {"access_token": _token_for(b["email"].lower()), "token_type": "bearer"})
            self._send(404, {"message": "not found"})

        # ------------------------------------------------------ data API (tiny PostgREST)
        def _rest(self, method, path, q):
            role, claims = self._role()
            if not role:
                return self._send(401, {"message": "Invalid API key"})
            name = path[len("/rest/v1/"):]
            if name.startswith("rpc/"):
                fn = re.sub(r"[^a-z_]", "", name[4:])
                rows = fake.as_role(role, claims, f"select to_jsonb({fn}())")
                return self._send(200, rows[0][0])
            table = re.sub(r"[^a-z_]", "", name)
            exists = fake.as_role("postgres", {}, "select to_regclass(%s) is not null", (f"public.{table}",))[0][0]
            if not exists:
                return self._send(404, {"code": "PGRST205", "message": f"Could not find the table 'public.{table}'"})
            where, params = self._filters(q)
            if method == "GET":
                limit = f" limit {int(q['limit'])}" if "limit" in q else ""
                rng = self.headers.get("Range")
                if rng and "-" in rng:
                    a, b = (int(x) for x in rng.split("-"))
                    limit = f" limit {b - a + 1} offset {a}"
                order = ""
                if "order" in q:
                    col, _, dirn = q["order"].partition(".")
                    order = f" order by {re.sub(r'[^a-z_]', '', col)} {'desc' if dirn.startswith('desc') else 'asc'}"
                rows = fake.as_role(role, claims, f"select coalesce(jsonb_agg(t), '[]') from (select * from public.{table}"
                                    f"{where}{order}{limit}) t", params)
                return self._send(200, rows[0][0])
            if method == "POST":
                body = self._body()
                body = body if isinstance(body, list) else [body]
                cols = [c for c in (q.get("columns") or ",".join(sorted({k for r in body for k in r}))).split(",") if c]
                cols = [re.sub(r"[^a-z_]", "", c) for c in cols]
                key = re.sub(r"[^a-z_]", "", q.get("on_conflict", ""))
                sets = ", ".join(f"{c}=excluded.{c}" for c in cols if c != key)
                conflict = f" on conflict ({key}) do update set {sets}" if key and sets else \
                    f" on conflict ({key}) do nothing" if key else ""
                collist = ", ".join(cols)
                fake.as_role(role, claims, f"insert into public.{table} ({collist}) select {collist} from "
                             f"jsonb_populate_recordset(null::public.{table}, %s::jsonb){conflict}",
                             (json.dumps(body, default=str),))
                return self._send(201, [])
            if method == "PATCH":
                body = self._body()
                sets = ", ".join(f"{re.sub(r'[^a-z_]', '', k)} = (jsonb_populate_record(null::public.{table}, %s::jsonb)).{re.sub(r'[^a-z_]', '', k)}"
                                 for k in body)
                fake.as_role(role, claims, f"update public.{table} set {sets}{where}",
                             [json.dumps(body, default=str)] * len(body) + params)
                return self._send(204, [])
            if method == "DELETE":
                fake.as_role(role, claims, f"delete from public.{table}{where}", params)
                return self._send(204, [])
            self._send(405, {"message": "method"})

        @staticmethod
        def _filters(q):
            conds, params = [], []
            for k, v in q.items():
                if k in ("select", "limit", "order", "on_conflict", "columns"):
                    continue
                col = re.sub(r"[^a-z_]", "", k)
                op, _, val = v.partition(".")
                if op == "eq":
                    conds.append(f"{col}::text = %s")
                    params.append(val)
                elif op == "gte":
                    conds.append(f"{col}::text >= %s")
                    params.append(val)
                elif op == "is" and val in ("true", "false", "null"):
                    conds.append(f"{col} is {val}")
                elif v == "not.is.true":
                    conds.append(f"{col} is not true")
            return (" where " + " and ".join(conds) if conds else ""), params

    return H
