"""One-off maintenance tasks, run on GitHub (Actions > Admin) where the secrets live.

  apply-sql        create/update all tables, permissions and rules (sql/schema.sql) with the access token
  create-reviewer  create the read-only reviewer login (demo data only) and prove what it can see
  build-demo       build the anonymised demo from your real data, check it, save it for the static demo
                   (dashboard/demo-data.json) and load it as the rows the reviewer login sees
  gemini-check     call Gemini once and show exactly what comes back, plus retry the notices the rules missed
  functions-check  the Ask Ping / Check now functions on Supabase: deployed versions, which secrets they have
                   (names only), their logs from the last 24 hours, and two test questions as the reviewer
  ask-ping-page    open the dashboard page in a real browser, sign in as the reviewer, type the two test
                   questions into the chat and print the replies shown on screen
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from . import ai, supabase_admin as sa
from .config import IST, load_secrets
from .demo_from_real import REAL, build_from_store, load_to_db, verify
from .store import SupabaseStore

ROOT = Path(__file__).resolve().parent.parent


def say(msg=""):
    print(msg, flush=True)


def apply_sql(secrets) -> int:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        say("SUPABASE_ACCESS_TOKEN is not set in the repo secrets")
        return 2
    sa.create_database(secrets.supabase_url, token)
    # The data API caches the list of tables; ask it to reload, then confirm from the database itself.
    sa.run_sql(secrets.supabase_url, token, "notify pgrst, 'reload schema';")
    rows = sa.run_sql(secrets.supabase_url, token,
                      "select t, to_regclass('public.' || t) is not null as present from unnest(array["
                      "'chat_messages','reviewer_users','allowed_users','items','profile']) t")
    say("  in the database: " + ", ".join(f"{r['t']}={'yes' if r['present'] else 'NO'}" for r in rows))
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    for t in ("chat_messages", "reviewer_users", "items", "profile"):
        for attempt in range(10):
            try:
                store.select(t, {"limit": "1"})
                say(f"  {t}: reachable through the data API")
                break
            except Exception as e:
                if attempt == 9:
                    raise
                time.sleep(3)
    say("schema.sql applied (tables, permissions, owner/reviewer rules, chat). Your data was not touched.")
    return 0


def create_reviewer(secrets) -> int:
    email = os.environ.get("REVIEWER_EMAIL", "").strip().lower()
    password = os.environ.get("REVIEWER_PASSWORD", "")
    publishable = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    if not email or len(password) < 8 or not publishable:
        say("need REVIEWER_EMAIL, REVIEWER_PASSWORD (8+ characters) and SUPABASE_PUBLISHABLE_KEY")
        return 2
    if email == secrets.mail_address.strip().lower():
        say("the reviewer email must not be your own")
        return 2
    url, secret = secrets.supabase_url, secrets.supabase_key
    how = sa.ensure_dashboard_user(url, secret, email, password)
    store = SupabaseStore(url, secret)
    store.upsert("reviewer_users", [{"email": email}], key="email")
    store.delete("allowed_users", {"email": f"eq.{email}"})
    say(f"reviewer login {email}: {how}, confirmed, on the reviewer list (not the owner list)")
    r = requests.post(f"{url}/auth/v1/token", params={"grant_type": "password"}, timeout=30,
                      headers={"apikey": publishable}, json={"email": email, "password": password})
    r.raise_for_status()
    hdr = {"apikey": publishable, "Authorization": f"Bearer {r.json()['access_token']}"}
    owner = requests.post(f"{url}/rest/v1/rpc/is_ping_owner", headers=hdr, json={}, timeout=30).json()
    rev = requests.post(f"{url}/rest/v1/rpc/is_ping_reviewer", headers=hdr, json={}, timeout=30).json()
    items = requests.get(f"{url}/rest/v1/items", headers=hdr, params={"select": "id,is_sample"}, timeout=30).json()
    real_seen = [i for i in items if not i.get("is_sample")] if isinstance(items, list) else ["error"]
    profile = requests.get(f"{url}/rest/v1/profile", headers=hdr, params={"select": "id"}, timeout=30).json()
    write = requests.patch(f"{url}/rest/v1/profile", headers=hdr, params={"id": "eq.2"}, json={"cgpa": 1}, timeout=30)
    chk = requests.get(f"{url}/rest/v1/profile", params={"select": "cgpa", "id": "eq.2"},
                       headers={"apikey": secret}, timeout=30).json()
    say(f"  signed in as the reviewer: owner={owner}, reviewer={rev}")
    say(f"  rows it can see: {len(items) if isinstance(items, list) else items} items, "
        f"{len(real_seen)} of them real (must be 0); profile rows {[p.get('id') for p in profile] if isinstance(profile, list) else profile}")
    say(f"  tried to change the demo profile: HTTP {write.status_code}; stored CGPA afterwards: {chk}")
    ok = owner is False and rev is True and not real_seen and not (chk and chk[0].get("cgpa") == 1)
    say("reviewer login: OK, read-only and demo-only" if ok else "reviewer login: PROBLEM (see above)")
    return 0 if ok else 1


def build_demo(secrets) -> int:
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    data = build_from_store(store, secrets.erp_user_id, secrets.mail_address)
    real_name = (store.select("profile", {"id": "eq.1"}) or [{}])[0].get("name")
    problems = verify(data, secrets.erp_user_id, secrets.mail_address, real_name)
    if problems:
        say("NOT written, anonymising left something behind:")
        for p in problems:
            say(f"  - {p}")
        return 1
    out = ROOT / "dashboard" / "demo-data.json"
    out.write_text(json.dumps(data, default=str, ensure_ascii=False), encoding="utf-8")
    counts = load_to_db(store, data)
    visible = sum(1 for i in data["items"] if i["level"] != "hidden")
    say(f"demo built from the real data: {counts}; {visible} items shown in the chat")
    say(f"anonymising check: passed (no real roll, email or name; no other rolls/phones). Wrote {out.name}, "
        f"{out.stat().st_size // 1024} KB")
    return 0


def gemini_check(secrets) -> int:
    cfg = secrets.ai
    if not cfg.get("provider"):
        say("no GEMINI_API_KEY in the secrets")
        return 2
    test = "The CV submission of Northwind (made-up) closes at five in the evening on the twenty-second of November, 2026."
    res = ai.refine_notice(test, datetime(2026, 11, 20, tzinfo=IST), ["Northwind"], cfg)
    say(f"models tried in order: {[cfg.get('model')] + list(cfg.get('fallback_models', []))}")
    say(f"test call: {'answered' if res else 'FAILED'}; {res}")
    for a in ai.stats["attempts"]:
        say(f"  model said: {a}")
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    missed = [n for n in store.select("notices", REAL) if (n.get("analysis") or {}).get("rule_misses")]
    say(f"notices the rules couldn't read: {len(missed)}")
    for n in missed[:5]:
        ai.stats["last_error"] = None
        res = ai.refine_notice(n.get("text") or n.get("preview") or "", datetime.fromisoformat(n["notice_time"]),
                               [r["company"] for r in store.select("roles", REAL)], cfg)
        say(f"  notice {n['notice_id']} ({n['subject']} / {n['company']}): misses {n['analysis']['rule_misses']} -> "
            f"{'Gemini answered: ' + json.dumps(res)[:300] if res else 'no answer; ' + str(ai.stats['last_error'])}")
    return 0 if res is not None or not missed else 1


API = "https://api.supabase.com"


def _logs(ref: str, token: str, sql: str, hours: int = 24) -> list:
    from datetime import timedelta, timezone
    end = datetime.now(timezone.utc)
    r = requests.get(f"{API}/v1/projects/{ref}/analytics/endpoints/logs.all", timeout=60,
                     headers={"Authorization": f"Bearer {token}"},
                     params={"sql": sql, "iso_timestamp_start": (end - timedelta(hours=hours)).isoformat(),
                             "iso_timestamp_end": end.isoformat()})
    if r.status_code >= 400:
        say(f"  (logs query failed: HTTP {r.status_code} {r.text[:300]})")
        return []
    body = r.json()
    if body.get("error"):
        say(f"  (logs query error: {str(body['error'])[:300]})")
    return body.get("result") or []


def ask_as_reviewer(url: str, question: str) -> tuple[int, float, str]:
    """Ask Ping exactly like the dashboard does: signed-in token + publishable key, POST {question}."""
    publishable = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    r = requests.post(f"{url.rstrip('/')}/auth/v1/token", params={"grant_type": "password"}, timeout=30,
                      headers={"apikey": publishable},
                      json={"email": os.environ.get("REVIEWER_EMAIL", ""), "password": os.environ.get("REVIEWER_PASSWORD", "")})
    if r.status_code != 200:
        return r.status_code, 0.0, f"reviewer sign-in failed: {r.text[:200]}"
    tok = r.json()["access_token"]
    t = time.monotonic()
    a = requests.post(f"{url.rstrip('/')}/functions/v1/ask-ping", timeout=180, json={"question": question},
                      headers={"apikey": publishable, "Authorization": f"Bearer {tok}"})
    return a.status_code, time.monotonic() - t, a.text[:1500]


def functions_check(secrets) -> int:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        say("SUPABASE_ACCESS_TOKEN is not set in the repo secrets")
        return 2
    ref = sa.project_ref(secrets.supabase_url)
    hdr = {"Authorization": f"Bearer {token}"}
    fns = requests.get(f"{API}/v1/projects/{ref}/functions", headers=hdr, timeout=30).json()
    ids = {}
    say("deployed functions:")
    for f in fns if isinstance(fns, list) else []:
        ids[f.get("id")] = f.get("slug")
        say(f"  {f.get('slug')}: status {f.get('status')}, version {f.get('version')}, "
            f"updated {datetime.fromtimestamp((f.get('updated_at') or 0) / 1000, IST):%d %b %H:%M IST}, "
            f"verify_jwt {f.get('verify_jwt')}")
    names = sorted(x.get("name", "") for x in requests.get(f"{API}/v1/projects/{ref}/secrets", headers=hdr,
                                                            timeout=30).json())
    say(f"secrets the functions can read on Supabase (names only): {', '.join(names)}")
    say(f"  GEMINI_API_KEY on the Supabase side: {'yes' if 'GEMINI_API_KEY' in names else 'NO'}")
    ask_id = next((i for i, slug in ids.items() if slug == "ask-ping"), None)

    say("\nask-ping requests, last 24 h (newest first):")
    rows = _logs(ref, token, f"""
        select timestamp, response.status_code as status, request.method as method, m.execution_time_ms as ms,
               m.version as version
        from function_edge_logs
        cross join unnest(metadata) as m
        cross join unnest(m.response) as response
        cross join unnest(m.request) as request
        where m.function_id = '{ask_id}'
        order by timestamp desc
        limit 40""")
    for x in rows:
        ts = datetime.fromtimestamp(int(x["timestamp"]) / 1e6, IST)
        say(f"  {ts:%d %b %H:%M:%S} {x.get('method')} -> HTTP {x.get('status')} in {x.get('ms')} ms (v{x.get('version')})")
    say("\nask-ping messages (errors, crashes, shutdown reasons), last 24 h:")
    rows = _logs(ref, token, f"""
        select timestamp, event_message, m.level as level, m.event_type as event_type
        from function_logs
        cross join unnest(metadata) as m
        where m.function_id = '{ask_id}'
        order by timestamp desc
        limit 60""")
    for x in rows:
        ts = datetime.fromtimestamp(int(x["timestamp"]) / 1e6, IST)
        msg = " ".join(str(x.get("event_message") or "").split())[:400]
        say(f"  {ts:%d %b %H:%M:%S} [{x.get('level')}/{x.get('event_type')}] {msg}")

    if os.environ.get("REVIEWER_PASSWORD") and os.environ.get("SUPABASE_PUBLISHABLE_KEY"):
        say("\ntest questions, asked as the reviewer login (demo data, same function):")
        for q in ("slice ctc breakdown", "what's due tomorrow"):
            code, secs, body = ask_as_reviewer(secrets.supabase_url, q)
            say(f"  Q: {q}\n  -> HTTP {code} in {secs:.1f}s: {body}")
    return 0


def ask_ping_page(secrets) -> int:
    import subprocess
    return subprocess.run([sys.executable, str(ROOT / "setup" / "ask_ping_page_test.py"),
                           "slice ctc breakdown", "what's due tomorrow"]).returncode


def main() -> int:
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    secrets = load_secrets(require_erp=False, require_store=True)
    tasks = {"apply-sql": apply_sql, "create-reviewer": create_reviewer, "build-demo": build_demo,
             "gemini-check": gemini_check, "functions-check": functions_check, "ask-ping-page": ask_ping_page}
    if task not in tasks:
        say(f"unknown task {task!r}; choose from {', '.join(tasks)}")
        return 2
    return tasks[task](secrets)


if __name__ == "__main__":
    sys.exit(main())
