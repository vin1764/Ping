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

try:
    import psycopg
except ImportError:  # GitHub's test machine: these tests are skipped there
    psycopg = None

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
  pw text, email_confirmed_at timestamptz, created_at timestamptz default now(), last_sign_in_at timestamptz,
  is_anonymous boolean not null default false);
create function auth.jwt() returns jsonb language sql stable as
  $$ select coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb $$;
create function auth.uid() returns uuid language sql stable as
  $$ select nullif(auth.jwt() ->> 'sub', '')::uuid $$;
grant usage on schema auth to anon, authenticated, service_role;
"""


def available() -> bool:
    return psycopg is not None and os.path.exists(f"{PG_BIN}/initdb") and shutil.which("runuser") is not None



# ---------------------------------------------------------------- the data API's query language (a small PostgREST)
MAX_ROWS = 1000                 # Supabase's default: the most rows one request returns
_ID = re.compile(r"^[a-z_][a-z0-9_]*$")


def _colsql(expr: str, types: dict) -> str:
    """A column or a JSON path ("details->>posted_at", "details->pdf") as SQL; anything else is refused."""
    parts = re.split(r"(->>|->)", expr.strip())
    col = parts[0]
    if not _ID.match(col):
        raise ValueError(f"bad column {expr!r}")
    out = f'"{col}"'
    for i in range(1, len(parts), 2):
        key = parts[i + 1]
        if not re.match(r"^[A-Za-z0-9_]+$", key):
            raise ValueError(f"bad path {expr!r}")
        out += f"{parts[i]}'{key}'"
    return out


def _selsql(select: str, types: dict) -> str:
    """'*', or columns and JSON paths, each optionally renamed ("alias:details->>kind"); "count" isn't a column."""
    if select.strip() in ("", "*"):
        return "*"
    out = []
    for term in select.split(","):
        term = term.strip()
        if not term:
            continue
        alias, _, expr = term.rpartition(":") if ":" in term and not term.startswith(":") else ("", "", term)
        if "::" in term:                      # a cast ("x::text"): left as it is
            alias, expr = "", term
        name = alias or re.split(r"->>|->", expr)[-1]
        if not _ID.match(name):
            raise ValueError(f"bad select {term!r}")
        out.append(f'{_colsql(expr, types)} as "{name}"')
    return ", ".join(out)


def _cast(col: str, types: dict) -> str:
    """The parameter's cast to the column's own type (JSON text paths compare as text, as in PostgREST)."""
    if "->>" in col:
        return "%s"
    if "->" in col:
        return "%s::jsonb"
    t = types.get(col)
    return f"cast(%s as {t})" if t else "%s"


def _cond(col: str, v: str, types: dict, neg: bool = False):
    """One filter ("due_at", "gte.2026-11-25T00:00:00Z") as SQL and its parameters."""
    op, _, val = v.partition(".")
    if op == "not":
        return _cond(col, val, types, not neg)
    c = _colsql(col, types)
    p = _cast(col, types)
    ops = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
    if op in ops:
        sql, ps = f"{c} {ops[op]} {p}", [val]
    elif op in ("like", "ilike"):
        sql, ps = f"{c}::text {op} %s", [val.replace("*", "%")]
    elif op == "in":
        vals = [x.strip().strip('"') for x in _split(val.strip("()"))]
        sql, ps = f"{c}::text = any(%s)", [vals]
    elif op == "is" and val in ("true", "false", "null"):
        sql, ps = f"{c} is {val}", []
    else:
        return "", []
    return (f"not ({sql})" if neg else sql), ps


def _split(s: str) -> list[str]:
    """Split on commas outside parentheses and quotes."""
    out, depth, cur, q = [], 0, "", False
    for ch in s:
        if ch == '"':
            q = not q
        if ch == "(" and not q:
            depth += 1
        if ch == ")" and not q:
            depth -= 1
        if ch == "," and depth == 0 and not q:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def _logic(kind: str, v: str, types: dict):
    """or=(a.gte.1,b.is.null,and(c.eq.2,d.lt.3)) as SQL."""
    parts, params = [], []
    for term in _split(v.strip()[1:-1] if v.strip().startswith("(") else v):
        term = term.strip()
        m = re.match(r"^(not\.)?(or|and)\((.*)\)$", term)
        if m:
            sql, ps = _logic(m.group(2), "(" + m.group(3) + ")", types)
            sql = f"not {sql}" if m.group(1) else sql
        else:
            # "col.op.value" where col may be a JSON path with dots in no part
            m2 = re.match(r"^([a-z_][a-z0-9_]*(?:->>?[A-Za-z0-9_]+)*)\.(.*)$", term)
            if not m2:
                raise ValueError(f"bad filter {term!r}")
            sql, ps = _cond(m2.group(1), m2.group(2), types)
        if sql:
            parts.append(sql)
            params += ps
    joiner = " or " if kind == "or" else " and "
    return "(" + joiner.join(parts or ["true"]) + ")", params

class FakeSupabase:
    def __init__(self):
        self.anonymous_enabled = True
        # sessions like Supabase Auth's: an access token that expires, single-use refresh tokens that rotate; a used
        # one is accepted again only within the reuse window, after that the whole session is revoked
        self.jwt_exp = 3600
        self.reuse_seconds = 10
        self.refresh = {}           # refresh token -> {"session": id, "email", "uid", "anonymous", "used_at"}
        self.revoked = set()        # session ids
        self.auth_log = []          # ("refresh", token, outcome) / ("logout", scope) for the tests
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

    max_rows = MAX_ROWS

    def column_types(self, table: str) -> dict:
        """{column: its type} (for typed comparisons in filters), read once per table."""
        cache = self.__dict__.setdefault("_types", {})
        if table not in cache:
            rows = self.as_role("postgres", {}, "select column_name, udt_name from information_schema.columns "
                                "where table_schema = 'public' and table_name = %s", (table,))
            cache[table] = {c: t for c, t in rows}
        return cache[table]

    def as_role(self, role: str, claims: dict, sql: str, params=()):
        with self.conn() as c:
            with c.transaction():
                c.execute(f"set local role {role}")
                c.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
                cur = c.execute(sql, params)
                return cur.fetchall() if cur.description else []


def _token_for(email: str, uid: str = "", anonymous: bool = False, session_id: str = "", exp: int = 0) -> str:
    claims = {"email": email, "role": "authenticated", "sub": uid, "is_anonymous": anonymous, "session_id": session_id,
              "exp": exp or int(time.time()) + 3600}
    return "fakejwt." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode()


def _claims(token: str) -> dict | None:
    if token.startswith("fakejwt."):
        return json.loads(base64.urlsafe_b64decode(token[8:]))
    return None


def _handler(fake: FakeSupabase):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, headers=None):
            data = b"" if code == 204 else json.dumps(body, default=str).encode()   # 204 has no body (as Supabase)
            self.send_response(code)
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"null") if n else None

        def _role(self):
            auth = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            claims = _claims(auth)
            if claims:
                if claims.get("exp", 1e12) < time.time():
                    fake.auth_log.append(("expired token used", self.path.split("?")[0]))
                    return None, None                 # PostgREST: 401 JWT expired
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
                    uid = c.execute("update auth.users set last_sign_in_at=now() where email=%s returning id",
                                    (b["email"].lower(),)).fetchone()[0]
                return self._send(200, self._session(b["email"].lower(), str(uid), False, uuid.uuid4().hex))
            if path == "/auth/v1/token" and q.get("grant_type") == "refresh_token":
                if role != "anon" and role != "authenticated":
                    return self._send(401, {"message": "Invalid API key"})
                tok = (self._body() or {}).get("refresh_token", "")
                rec = fake.refresh.get(tok)
                now = time.time()
                if not rec or rec["session"] in fake.revoked:
                    fake.auth_log.append(("refresh", tok, "invalid"))
                    return self._send(400, {"error": "invalid_grant", "error_description": "Invalid Refresh Token: Refresh Token Not Found"})
                if rec["used_at"] and now - rec["used_at"] > fake.reuse_seconds:
                    fake.revoked.add(rec["session"])          # reuse outside the window: the session is revoked
                    fake.auth_log.append(("refresh", tok, "reused"))
                    return self._send(400, {"error": "invalid_grant", "error_description": "Invalid Refresh Token: Already Used"})
                rec["used_at"] = rec["used_at"] or now
                fake.auth_log.append(("refresh", tok, "ok"))
                return self._send(200, self._session(rec["email"], rec["uid"], rec["anonymous"], rec["session"]))
            if path == "/auth/v1/logout" and method == "POST":
                if not claims:
                    return self._send(401, {"message": "not signed in"})
                scope = q.get("scope", "global")
                fake.auth_log.append(("logout", scope, claims.get("sub")))
                sid = claims.get("session_id")
                for rec in fake.refresh.values():
                    if (scope == "global" and rec["uid"] == claims.get("sub")) or rec["session"] == sid:
                        fake.revoked.add(rec["session"])
                return self._send(204, None)
            if path == "/auth/v1/user" and method == "GET":
                if role != "authenticated" or not claims:
                    return self._send(401, {"message": "not signed in"})
                return self._send(200, {"id": claims.get("sub"), "email": claims.get("email"), "aud": "authenticated",
                                        "role": "authenticated", "is_anonymous": bool(claims.get("is_anonymous"))})
            if path == "/auth/v1/signup" and method == "POST" and not (self._body() or {}).get("email"):
                # supabase-js signInAnonymously(): a new user with no email, is_anonymous = true
                if role != "anon":
                    return self._send(401, {"message": "Invalid API key"})
                if not fake.anonymous_enabled:
                    return self._send(422, {"code": "anonymous_provider_disabled", "msg": "Anonymous sign-ins are disabled"})
                with fake.conn() as c:
                    uid = c.execute("insert into auth.users (is_anonymous) values (true) returning id").fetchone()[0]
                return self._send(200, self._session("", str(uid), True, uuid.uuid4().hex))
            self._send(404, {"message": "not found"})

        def _session(self, email, uid, anonymous, session_id):
            """A session as supabase-js expects it, with a fresh single-use refresh token."""
            rt = uuid.uuid4().hex
            fake.refresh[rt] = {"session": session_id, "email": email, "uid": uid, "anonymous": anonymous, "used_at": None}
            user = {"id": uid, "email": email or None, "aud": "authenticated", "role": "authenticated", "is_anonymous": anonymous}
            return {"access_token": _token_for(email, uid, anonymous, session_id, int(time.time()) + fake.jwt_exp), "token_type": "bearer",
                    "expires_in": fake.jwt_exp, "expires_at": int(time.time()) + fake.jwt_exp, "refresh_token": rt,
                    "user": user}

        # ------------------------------------------------------ data API (tiny PostgREST)
        def _rest(self, method, path, q):
            role, claims = self._role()
            if not role:
                return self._send(401, {"message": "Invalid API key"})
            name = path[len("/rest/v1/"):]
            if name.startswith("rpc/"):
                fn = re.sub(r"[^a-z_]", "", name[4:])
                args = self._body() if method == "POST" else None
                named = ", ".join(f"{re.sub(r'[^a-z_]', '', k)} => %s" for k in (args or {}))
                rows = fake.as_role(role, claims, f"select to_jsonb({fn}({named}))", list((args or {}).values()))
                return self._send(200, rows[0][0])
            table = re.sub(r"[^a-z_]", "", name)
            exists = fake.as_role("postgres", {}, "select to_regclass(%s) is not null", (f"public.{table}",))[0][0]
            if not exists:
                return self._send(404, {"code": "PGRST205", "message": f"Could not find the table 'public.{table}'"})
            types = fake.column_types(table)
            where, params = self._filters(q, types)
            if method == "GET":
                # like Supabase's API: at most MAX_ROWS rows a request, whatever limit or range is asked
                n, off = fake.max_rows, 0
                if "limit" in q:
                    n = min(n, int(q["limit"]))
                if "offset" in q:
                    off = int(q["offset"])
                rng = self.headers.get("Range")
                if rng and "-" in rng:
                    a, b = (int(x) for x in rng.split("-"))
                    off, n = a, min(fake.max_rows, b - a + 1)
                order = ""
                if "order" in q:
                    parts = []
                    for term in q["order"].split(","):
                        col, _, dirn = term.partition(".")
                        nulls = " nulls first" if "nullsfirst" in dirn else " nulls last" if "nullslast" in dirn else ""
                        parts.append(f"{_colsql(col, types)} {'desc' if dirn.startswith('desc') else 'asc'}{nulls}")
                    order = " order by " + ", ".join(parts)
                sel = _selsql(q.get("select", "*"), types)
                rows = fake.as_role(role, claims, f"select coalesce(jsonb_agg(t), '[]') from (select {sel} from public.{table}"
                                    f"{where}{order} limit {n} offset {off}) t", params)
                out = rows[0][0]
                headers = {}
                if "count=exact" in (self.headers.get("Prefer") or ""):
                    total = fake.as_role(role, claims, f"select count(*) from public.{table}{where}", params)[0][0]
                    headers["Content-Range"] = f"{off}-{off + len(out) - 1 if out else off}/{total}"
                return self._send(200, out, headers)
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
        def _filters(q, types=None):
            conds, params = [], []
            for k, v in q.items():
                if k in ("select", "limit", "offset", "order", "on_conflict", "columns"):
                    continue
                if k in ("or", "and"):
                    sql, ps = _logic(k, v, types or {})
                    conds.append(sql)
                    params += ps
                    continue
                sql, ps = _cond(k, v, types or {})
                if sql:
                    conds.append(sql)
                    params += ps
            return (" where " + " and ".join(conds) if conds else ""), params

    return H
