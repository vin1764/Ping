"""Setting up a Supabase project without opening Supabase's screens.

- SQL (tables, permissions) needs a personal access token: the project's
  secret key can read and write rows but cannot create tables.
- The dashboard user is created with the secret key (Auth admin API),
  already confirmed, and added to allowed_users.
- The check signs in exactly like the dashboard does (publishable key +
  email + password) and asks the database whether that login is the owner.
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

API = os.environ.get("PING_SUPABASE_API", "https://api.supabase.com")
SCHEMA = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


class SetupError(Exception):
    pass


def project_ref(url: str) -> str:
    host = url.split("//", 1)[-1].split("/", 1)[0]
    if os.environ.get("PING_SUPABASE_REF"):          # tests: a local fake has no ref in its host
        return os.environ["PING_SUPABASE_REF"]
    return host.split(".", 1)[0]


def _check(r: requests.Response, what: str):
    if r.status_code >= 400:
        raise SetupError(f"{what} failed: HTTP {r.status_code} {r.text[:300]}")
    return r


def run_sql(url: str, token: str, sql: str) -> list:
    r = requests.post(f"{API}/v1/projects/{project_ref(url)}/database/query",
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                      json={"query": sql}, timeout=120)
    if r.status_code in (401, 403):
        raise SetupError("Supabase didn't accept the access token (create a new one: Supabase > Account > Access Tokens)")
    _check(r, "creating the tables")
    try:
        return r.json()
    except ValueError:
        return []


def create_database(url: str, token: str) -> None:
    run_sql(url, token, SCHEMA.read_text(encoding="utf-8"))
    run_sql(url, token, "notify pgrst, 'reload schema';")  # the data API caches the table list


def api_keys(url: str, token: str) -> dict:
    """Publishable and secret keys of the project, so nobody has to copy them by hand."""
    r = requests.get(f"{API}/v1/projects/{project_ref(url)}/api-keys", params={"reveal": "true"},
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    _check(r, "reading the project's keys")
    out = {}
    for k in r.json():
        kind = k.get("type") or ""
        key = k.get("api_key") or ""
        if kind in ("publishable", "secret") and key and kind not in out:
            out[kind] = key
    return out


def _admin_headers(secret: str) -> dict:
    return {"apikey": secret, "Authorization": f"Bearer {secret}", "Content-Type": "application/json"}


def ensure_dashboard_user(url: str, secret: str, email: str, password: str) -> str:
    """Create the dashboard login (confirmed), or reset its password if it exists. Returns 'created'/'updated'."""
    base = url.rstrip("/") + "/auth/v1/admin/users"
    email = email.strip().lower()
    r = requests.post(base, headers=_admin_headers(secret), timeout=30,
                      json={"email": email, "password": password, "email_confirm": True})
    if r.status_code < 300:
        return "created"
    if r.status_code not in (400, 409, 422) or "exist" not in r.text.lower() and "registered" not in r.text.lower():
        _check(r, "creating the dashboard login")
    users = _check(requests.get(base, headers=_admin_headers(secret), params={"per_page": 1000}, timeout=30),
                   "finding the existing dashboard login").json().get("users", [])
    user = next((u for u in users if (u.get("email") or "").lower() == email), None)
    if not user:
        raise SetupError(f"Supabase says {email} exists but it isn't in the user list")
    _check(requests.put(f"{base}/{user['id']}", headers=_admin_headers(secret), timeout=30,
                        json={"password": password, "email_confirm": True}), "updating the dashboard login")
    return "updated"


def allow(url: str, secret: str, email: str) -> None:
    r = requests.post(url.rstrip("/") + "/rest/v1/allowed_users", params={"on_conflict": "email"},
                      headers={**_admin_headers(secret), "Prefer": "resolution=merge-duplicates,return=minimal"},
                      json=[{"email": email.strip().lower()}], timeout=30)
    _check(r, "adding the login to the allowed list")


def sign_in_check(url: str, publishable: str, email: str, password: str) -> None:
    """Sign in exactly like the dashboard, then ask the database if this login may see Ping's data."""
    base = url.rstrip("/")
    r = requests.post(f"{base}/auth/v1/token", params={"grant_type": "password"}, timeout=30,
                      headers={"apikey": publishable, "Content-Type": "application/json"},
                      json={"email": email.strip().lower(), "password": password})
    if r.status_code != 200:
        raise SetupError(f"signing in as {email} failed: {r.text[:200]}")
    token = r.json()["access_token"]
    hdrs = {"apikey": publishable, "Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    owner = requests.post(f"{base}/rest/v1/rpc/is_ping_owner", headers=hdrs, json={}, timeout=30)
    if owner.status_code != 200 or owner.json() is not True:
        raise SetupError(f"signed in, but the database doesn't let this login see Ping's data ({owner.text[:200]})")
    items = requests.get(f"{base}/rest/v1/items", headers=hdrs, params={"select": "id", "limit": "1"}, timeout=30)
    _check(items, "reading the feed as the dashboard login")
