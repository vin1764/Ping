"""Where results go. SupabaseStore talks to your own Supabase project over its
REST API; MemoryStore keeps everything in memory (tests, offline replay)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import requests


class StoreNotReady(Exception):
    pass


class MemoryStore:
    def __init__(self, path: str | None = None):
        self.tables: dict[str, dict[str, dict]] = {}
        self.path = Path(path) if path else None
        if self.path and self.path.exists():
            self.tables = json.loads(self.path.read_text())

    def ready(self) -> tuple[bool, str]:
        return True, "memory"

    def select(self, table: str, filters: dict | None = None, columns: str = "*") -> list[dict]:
        rows = list(self.tables.get(table, {}).values())
        for k, v in (filters or {}).items():
            op, _, val = v.partition(".")
            if op == "eq":
                rows = [r for r in rows if str(r.get(k)).lower() == val.lower()]
            elif op == "gte":
                rows = [r for r in rows if (r.get(k) or "") >= val]
            elif op == "is" and val == "true":
                rows = [r for r in rows if r.get(k) is True]
            elif v == "not.is.true":
                rows = [r for r in rows if r.get(k) is not True]
        return copy.deepcopy(rows)

    def upsert(self, table: str, rows: list[dict], key: str = "id") -> int:
        t = self.tables.setdefault(table, {})
        for r in rows:
            k = str(r[key])
            if k in t:
                t[k].update(copy.deepcopy(r))
            else:
                new = copy.deepcopy(r)
                new.setdefault("first_seen", datetime.now(timezone.utc).isoformat())
                t[k] = new
        return len(rows)

    def delete(self, table: str, filters: dict) -> None:
        keep = {}
        for k, r in self.tables.get(table, {}).items():
            if all(str(r.get(f)).lower() == v.partition(".")[2].lower() for f, v in filters.items()):
                continue
            keep[k] = r
        self.tables[table] = keep

    def get_state(self, key: str, default=None):
        row = self.tables.get("state", {}).get(key)
        return row["value"] if row else default

    def set_state(self, key: str, value) -> None:
        self.upsert("state", [{"key": key, "value": value}], key="key")

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.tables, indent=1, default=str))


class SupabaseStore:
    def __init__(self, url: str, key: str, timeout: float = 40):
        self.base = url.rstrip("/") + "/rest/v1"
        self.key = key
        self.timeout = timeout
        self.session = requests.Session()
        # New-style secret keys (sb_secret_...) go in the apikey header only.
        self.session.headers.update({"apikey": key, "Content-Type": "application/json"})
        if not key.startswith("sb_"):
            self.session.headers["Authorization"] = f"Bearer {key}"

    def _req(self, method: str, table: str, **kw) -> requests.Response:
        r = self.session.request(method, f"{self.base}/{table}", timeout=self.timeout, **kw)
        if r.status_code == 401 and "Authorization" not in self.session.headers:
            self.session.headers["Authorization"] = f"Bearer {self.key}"
            r = self.session.request(method, f"{self.base}/{table}", timeout=self.timeout, **kw)
        if r.status_code >= 400:
            body = r.text[:300]
            if r.status_code == 404 or "PGRST205" in body or "42P01" in body:
                raise StoreNotReady(f"table '{table}' missing - run sql/schema.sql in Supabase ({body})")
            if "42501" in body:
                raise StoreNotReady(f"no permission on table '{table}' - run sql/fix_grants.sql in Supabase")
            raise RuntimeError(f"Supabase {method} {table} failed: {r.status_code} {body}")
        return r

    def ready(self) -> tuple[bool, str]:
        try:
            for t in ("profile", "roles", "notices", "pdf_checks", "items", "runs", "state", "corrections",
                      "emails", "contacts"):
                self._req("GET", t, params={"select": "*", "limit": "1"})
            return True, "ok"
        except StoreNotReady as e:
            return False, str(e)
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def select(self, table: str, filters: dict | None = None, columns: str = "*") -> list[dict]:
        out, start, page = [], 0, 1000
        while True:
            params = {"select": columns, **(filters or {})}
            r = self._req("GET", table, params=params, headers={"Range-Unit": "items",
                                                                 "Range": f"{start}-{start + page - 1}"})
            rows = r.json()
            out += rows
            if len(rows) < page:
                return out
            start += page

    def upsert(self, table: str, rows: list[dict], key: str = "id") -> int:
        # A bulk upsert needs every row to carry the same columns, and a column
        # sent as null overwrites what is stored. So send rows in groups that
        # share exactly the same columns; columns a row doesn't carry stay as they are.
        groups: dict[tuple, list[dict]] = {}
        for r in rows:
            groups.setdefault(tuple(sorted(r)), []).append(r)
        for cols, group in groups.items():
            for i in range(0, len(group), 300):
                chunk = group[i:i + 300]
                self._req("POST", table, params={"on_conflict": key, "columns": ",".join(cols)},
                          data=json.dumps(chunk, default=str),
                          headers={"Prefer": "resolution=merge-duplicates,return=minimal"})
        return len(rows)

    def delete(self, table: str, filters: dict) -> None:
        self._req("DELETE", table, params=filters)

    def get_state(self, key: str, default=None):
        rows = self.select("state", {"key": f"eq.{key}"})
        return rows[0]["value"] if rows else default

    def set_state(self, key: str, value) -> None:
        self.upsert("state", [{"key": key, "value": value,
                               "updated_at": datetime.now(timezone.utc).isoformat()}], key="key")

    def save(self) -> None:
        pass
