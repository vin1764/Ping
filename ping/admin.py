"""One-off maintenance tasks, run on GitHub (Actions > Admin) where the secrets live.

  apply-sql        create/update all tables, permissions and rules (sql/schema.sql) with the access token
  build-demo       build the anonymised demo from your real data, check it, save it for the static demo
                   (dashboard/demo-data.json) and load it as the rows a demo session sees
  gemini-check     call Gemini once and show exactly what comes back, plus retry the notices the rules missed
  functions-check  the Ask Ping / Check now functions on Supabase: deployed versions, which secrets they have
                   (names only), their logs from the last 24 hours, and two test questions from a demo session
  auth-config      Supabase Auth settings for the live dashboard: Site URL and redirect allow-list point at
                   https://<owner>.github.io/ping-dashboard/ (localhost kept for development), anonymous
                   sign-ins on (the one-click demo), and the old reviewer login deleted
  cleanup-demo     delete one-click demo sessions (anonymous users) older than 7 days and their chat messages
                   (also runs daily inside Supabase, see schedule-setup)
  schedule-setup   schedule the hourly Ping run and the daily demo cleanup inside Supabase (pg_cron + the kick-run
                   function), with a new shared secret; then a dry-run call to prove it's wired up
  schedule-status  the Supabase jobs, their last runs and calls, and the latest Ping runs on GitHub
  ask-ping-evals   run evals/ask_ping (questions against the deployed function from demo sessions) and save the report
  rearm-schedule   switch the Ping workflow off and on through GitHub's API, which makes GitHub register its
                   hourly schedule again, then show what GitHub reports about it
  ask-ping-page    open the live dashboard in a real browser, click "View demo", type the two test
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
from .demo_from_real import REAL, build_from_store, final_check, load_to_db, verify
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
                      "'chat_messages','demo_questions','allowed_users','items','profile']) t")
    say("  in the database: " + ", ".join(f"{r['t']}={'yes' if r['present'] else 'NO'}" for r in rows))
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    for t in ("chat_messages", "items", "profile"):
        for attempt in range(10):
            try:
                store.select(t, {"limit": "1"})
                say(f"  {t}: reachable through the data API")
                break
            except Exception as e:
                if attempt == 9:
                    raise
                time.sleep(3)
    say("schema.sql applied (tables, permissions, owner and demo rules, chat). Your data was not touched.")
    return 0


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
    say(f"anonymising check: passed (no real roll, email or name; no other rolls, phones, ten-digit numbers, "
        f"'+91', meeting links or real names from the denylist). Wrote {out.name}, {out.stat().st_size // 1024} KB")
    # read back exactly what a demo session now sees and check it again
    live = {t: store.select(t, {"is_sample": "is.true"}) for t in
            ("profile", "roles", "notices", "pdf_checks", "items", "runs", "contacts", "emails")}
    left = final_check(live)
    say(f"demo rows in the database, read back ({', '.join(f'{t} {len(r)}' for t, r in live.items())}): "
        + ("clean" if not left else "NOT CLEAN: " + "; ".join(left)))
    file_left = final_check(out.read_text(encoding="utf-8"))
    say(f"{out.name} as written: " + ("clean" if not file_left else "NOT CLEAN: " + "; ".join(file_left)))
    return 0 if not left and not file_left else 1


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


def _z(t) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")  # the logs API accepts only this shape


def _logs(ref: str, token: str, sql: str, hours: int = 23) -> list:
    from datetime import timedelta, timezone
    end = datetime.now(timezone.utc)
    r = requests.get(f"{API}/v1/projects/{ref}/analytics/endpoints/logs", timeout=60,
                     headers={"Authorization": f"Bearer {token}"},
                     params={"sql": sql, "iso_timestamp_start": _z(end - timedelta(hours=hours)),
                             "iso_timestamp_end": _z(end)})
    _logs.last_error = None
    if r.status_code >= 400:
        _logs.last_error = f"HTTP {r.status_code} {r.text[:300]}"
        say(f"  (logs query failed: {_logs.last_error})")
        return []
    body = r.json()
    if body.get("error"):
        _logs.last_error = str(body["error"])[:300]
        say(f"  (logs query error: {_logs.last_error})")
    return body.get("result") or []


def _when(ts) -> str:
    try:
        v = float(ts)
        v = v / 1e6 if v > 1e14 else v / 1e3 if v > 1e11 else v
        return f"{datetime.fromtimestamp(v, IST):%d %b %H:%M:%S}"
    except (TypeError, ValueError):
        try:
            return f"{datetime.fromisoformat(str(ts).replace('Z', '+00:00').replace(' ', 'T')).astimezone(IST):%d %b %H:%M:%S}"
        except ValueError:
            return str(ts)


def _source_logs(ref: str, token: str, source: str, function_id, fields: str, limit: int) -> list:
    """Supabase's logs API (ClickHouse SQL): one `logs` table, filtered by source; its docs name the
    column both source_name and source, so try both."""
    for col in ("source_name", "source"):
        rows = _logs(ref, token, f"""
            SELECT timestamp, {fields}
            FROM logs
            WHERE {col} = '{source}' AND log_attributes['function_id'] = '{function_id}'
            ORDER BY timestamp DESC
            LIMIT {limit}""")
        if rows or not _logs.last_error:
            return rows
    return []


def ask_as_demo(url: str, questions: list[str]) -> list[tuple[str, int, float, str]]:
    """Ask Ping exactly like the dashboard's demo does: a one-click (anonymous) session, POST {question}."""
    hdr, _ = sa.demo_session(url, os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""))
    out = []
    for q in questions:
        t = time.monotonic()
        a = requests.post(f"{url.rstrip('/')}/functions/v1/ask-ping", timeout=180, json={"question": q}, headers=hdr)
        out.append((q, a.status_code, time.monotonic() - t, a.text[:1500]))
    return out

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

    say("\nask-ping requests, last 23 h (newest first):")
    rows = _source_logs(ref, token, "function_edge_logs", ask_id, """
        log_attributes['response.status_code'] AS status, log_attributes['request.method'] AS method,
        log_attributes['execution_time_ms'] AS ms, log_attributes['version'] AS version""", 40)
    for x in rows:
        say(f"  {_when(x.get('timestamp'))} {x.get('method')} -> HTTP {x.get('status')} in {x.get('ms')} ms "
            f"(version {x.get('version')})")
    say("\nask-ping messages (errors, crashes, shutdown reasons), last 23 h:")
    rows = _source_logs(ref, token, "function_logs", ask_id, """
        event_message, severity_text AS severity, log_attributes['level'] AS level,
        log_attributes['event_type'] AS event_type""", 60)
    for x in rows:
        msg = " ".join(str(x.get("event_message") or "").split())[:400]
        say(f"  {_when(x.get('timestamp'))} [{x.get('level') or x.get('severity')}/{x.get('event_type')}] {msg}")

    if os.environ.get("SUPABASE_PUBLISHABLE_KEY"):
        say("\ntest questions from a one-click demo session (demo data, same function):")
        try:
            for q, code, secs, body in ask_as_demo(secrets.supabase_url, ["slice ctc breakdown", "what's due tomorrow"]):
                say(f"  Q: {q}\n  -> HTTP {code} in {secs:.1f}s: {body}")
        except sa.SetupError as e:
            say(f"  {e}")
    return 0


def ask_ping_page(secrets) -> int:
    import subprocess
    return subprocess.run([sys.executable, str(ROOT / "setup" / "ask_ping_page_test.py"),
                           "slice ctc breakdown", "what's due tomorrow"]).returncode


def auth_config(secrets) -> int:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    if not token or not owner:
        say("needs SUPABASE_ACCESS_TOKEN and GITHUB_REPOSITORY_OWNER (run it on GitHub: Actions > Admin)")
        return 2
    live = f"https://{owner.lower()}.github.io/ping-dashboard/"
    url = f"{API}/v1/projects/{sa.project_ref(secrets.supabase_url)}/config/auth"
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    cur = requests.get(url, headers=hdr, timeout=30)
    if cur.status_code >= 300:
        say(f"reading the Auth settings failed: HTTP {cur.status_code} {cur.text[:200]}")
        return 1
    cur = cur.json()
    before_site, before_list = cur.get("site_url") or "", [u for u in (cur.get("uri_allow_list") or "").split(",") if u]
    keep = list(before_list)  # nothing already there is removed
    if ("localhost" in before_site or "127.0.0.1" in before_site) and before_site != live:
        keep.append(before_site)  # the old local Site URL stays allowed for development
    if not any("localhost" in u or "127.0.0.1" in u for u in keep):
        keep += ["http://localhost:8000/**", "http://127.0.0.1:8000/**"]  # python -m http.server, for development
    wanted = [live, live + "**"] + keep
    new_list = list(dict.fromkeys(wanted))
    say(f"before: site_url = {before_site or '(empty)'}; redirect allow-list = {before_list or '(empty)'}")
    say(f"before: anonymous sign-ins {'on' if cur.get('external_anonymous_users_enabled') else 'off'}, "
        f"new sign-ups {'off' if cur.get('disable_signup') else 'on'}, "
        f"email confirmation {'off' if cur.get('mailer_autoconfirm') else 'required'}")
    # An anonymous sign-in is a sign-up to Supabase, so sign-ups must be allowed for the demo. That's safe for the
    # data: the owner rules only let emails in allowed_users read anything, the demo rules only anonymous
    # sessions, and email sign-ups must confirm their address first (no automatic confirmation).
    r = requests.patch(url, headers=hdr, timeout=30, json={"site_url": live, "uri_allow_list": ",".join(new_list),
                                                           "external_anonymous_users_enabled": True,
                                                           "disable_signup": False, "mailer_autoconfirm": False})
    if r.status_code >= 300:
        say(f"updating the Auth settings failed: HTTP {r.status_code} {r.text[:200]}")
        return 1
    after = requests.get(url, headers=hdr, timeout=30).json()
    say(f"after:  site_url = {after.get('site_url')}; redirect allow-list = {(after.get('uri_allow_list') or '').split(',')}")
    say(f"after:  anonymous sign-ins {'on' if after.get('external_anonymous_users_enabled') else 'OFF'}, "
        f"new sign-ups {'off' if after.get('disable_signup') else 'on'}, "
        f"email confirmation {'off' if after.get('mailer_autoconfirm') else 'required'}")
    # the reviewer login the one-click demo replaces
    base = secrets.supabase_url.rstrip("/") + "/auth/v1/admin/users"
    admin_hdr = {"apikey": secrets.supabase_key, "Authorization": f"Bearer {secrets.supabase_key}"}
    users = requests.get(base, headers=admin_hdr, params={"per_page": 1000}, timeout=30).json().get("users", [])
    old = [u for u in users if (u.get("email") or "").lower() == "reviewer@ping-demo.example"]
    for u in old:
        d = requests.delete(f"{base}/{u['id']}", headers=admin_hdr, timeout=30)
        say(f"old reviewer login deleted: HTTP {d.status_code}")
    if not old:
        say("old reviewer login: not there")
    ok = after.get("site_url") == live and after.get("external_anonymous_users_enabled") and not after.get("disable_signup")
    return 0 if ok and not after.get("mailer_autoconfirm") else 1


def cleanup_demo(secrets) -> int:
    r = requests.post(secrets.supabase_url.rstrip("/") + "/rest/v1/rpc/cleanup_demo_sessions", timeout=60,
                      headers={"apikey": secrets.supabase_key, "Authorization": f"Bearer {secrets.supabase_key}",
                               "Content-Type": "application/json"}, json={"days": 7})
    if r.status_code >= 300:
        say(f"cleanup failed: HTTP {r.status_code} {r.text[:200]}")
        return 1
    say(f"demo cleanup (older than 7 days): {r.json()}")
    return 0


def _function_url(secrets, name: str) -> str:
    return f"{secrets.supabase_url.rstrip('/')}/functions/v1/{name}"


def schedule_setup(secrets) -> int:
    import secrets as pysecrets
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        say("SUPABASE_ACCESS_TOKEN is not set in the repo secrets")
        return 2
    ref = sa.project_ref(secrets.supabase_url)
    shared = pysecrets.token_urlsafe(32)
    r = requests.post(f"{API}/v1/projects/{ref}/secrets", timeout=30, json=[{"name": "PING_CRON_SECRET", "value": shared}],
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    say(f"kick-run's shared secret set as a function secret: HTTP {r.status_code}")
    if r.status_code >= 300:
        return 1
    lit = shared.replace("'", "''")
    sa.run_sql(secrets.supabase_url, token, f"""
        do $$ begin
          if exists (select 1 from vault.secrets where name = 'ping_cron_secret') then
            perform vault.update_secret((select id from vault.secrets where name = 'ping_cron_secret'), '{lit}');
          else
            perform vault.create_secret('{lit}', 'ping_cron_secret', 'shared secret for the kick-run function');
          end if;
        end $$;""")
    say("the same secret stored in the database's Vault as ping_cron_secret")
    sql = (ROOT / "sql" / "schedule.sql").read_text(encoding="utf-8").replace("{{FUNCTION_URL}}", _function_url(secrets, "kick-run"))
    sa.run_sql(secrets.supabase_url, token, sql)
    jobs = sa.run_sql(secrets.supabase_url, token, "select jobname, schedule, active from cron.job order by jobname")
    for j in jobs:
        say(f"  job {j['jobname']}: '{j['schedule']}' (UTC), active {j['active']}")
    time.sleep(5)  # a new function secret takes a moment to reach the function
    for attempt in range(6):
        c = requests.post(_function_url(secrets, "kick-run"), json={"task": "check"}, timeout=60,
                          headers={"x-ping-cron": shared, "Content-Type": "application/json"})
        if c.status_code == 200:
            break
        time.sleep(10)
    say(f"dry run of kick-run (doesn't start anything): HTTP {c.status_code} {c.text[:300]}")
    return 0 if c.status_code == 200 and len(jobs) >= 2 else 1


def schedule_status(secrets) -> int:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    q = lambda sql: sa.run_sql(secrets.supabase_url, token, sql)  # noqa: E731
    for j in q("select jobid, jobname, schedule, active from cron.job order by jobname"):
        say(f"job {j['jobname']}: '{j['schedule']}' UTC, active {j['active']}")
        for d in q(f"select status, start_time, return_message from cron.job_run_details where jobid = {int(j['jobid'])} "
                   "order by start_time desc limit 3"):
            say(f"   ran {d['start_time']}: {d['status']} {str(d['return_message'])[:80]}")
    for h in q("select created, status_code, left(content::text, 160) as body from net._http_response order by created desc limit 4"):
        say(f"call to kick-run {h['created']}: HTTP {h['status_code']} {h['body']}")
    gh = os.environ.get("GITHUB_TOKEN", "")
    r = requests.get(f"https://api.github.com/repos/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/workflows/ping.yml/runs",
                     params={"per_page": 5}, headers={"Authorization": f"Bearer {gh}"}, timeout=30)
    for run in r.json().get("workflow_runs", []) if r.ok else []:
        say(f"Ping run {run['id']}: {run['event']}, started {run['run_started_at']}, {run['status']} {run.get('conclusion') or ''}")
    return 0


def ask_ping_evals(secrets) -> int:
    import subprocess
    return subprocess.run([sys.executable, str(ROOT / "evals" / "ask_ping" / "run_ask_ping_evals.py")]).returncode


def rearm_schedule(secrets) -> int:
    """GitHub registers a workflow's cron when it sees the file on the default branch. ping.yml has been there
    since the repo was created and never fired, so the registration was lost; disable + enable re-registers it."""
    token, repo = os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        say("needs GITHUB_TOKEN and GITHUB_REPOSITORY (run this on GitHub: Actions > Admin)")
        return 2
    gh = requests.Session()
    gh.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                       "X-GitHub-Api-Version": "2022-11-28"})
    base = f"https://api.github.com/repos/{repo}"
    info = gh.get(f"{base}", timeout=30).json()
    wf = gh.get(f"{base}/actions/workflows/ping.yml", timeout=30).json()
    say(f"repo: default branch {info.get('default_branch')}, private {info.get('private')}, "
        f"archived {info.get('archived')}, pushed {info.get('pushed_at')}")
    say(f"Ping workflow before: state {wf.get('state')}, updated {wf.get('updated_at')}")
    runs = gh.get(f"{base}/actions/workflows/ping.yml/runs", params={"event": "schedule", "per_page": 1}, timeout=30).json()
    say(f"scheduled runs so far: {runs.get('total_count')}")
    for action in ("disable", "enable"):
        r = gh.put(f"{base}/actions/workflows/ping.yml/{action}", timeout=30)
        say(f"{action}: HTTP {r.status_code}{'' if r.status_code < 300 else ' ' + r.text[:200]}")
        if r.status_code >= 300:
            return 1
        time.sleep(3)
    wf = gh.get(f"{base}/actions/workflows/ping.yml", timeout=30).json()
    say(f"Ping workflow after: state {wf.get('state')}, updated {wf.get('updated_at')}")
    from datetime import timedelta, timezone
    now = datetime.now(timezone.utc)
    nxt = now.replace(minute=41, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(hours=1)
    while not 0 <= nxt.hour <= 19:
        nxt += timedelta(hours=1)
    say("GitHub's API does not report a 'next run' time for schedules; from the cron '41 0-19 * * *' the next "
        f"tick is {nxt:%H:%M} UTC ({nxt.astimezone(IST):%H:%M} IST). GitHub may start it a few minutes late.")
    return 0 if wf.get("state") == "active" else 1


def main() -> int:
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    secrets = load_secrets(require_erp=False, require_store=True)
    tasks = {"apply-sql": apply_sql, "build-demo": build_demo,
             "gemini-check": gemini_check, "functions-check": functions_check, "ask-ping-page": ask_ping_page, "rearm-schedule": rearm_schedule, "ask-ping-evals": ask_ping_evals, "auth-config": auth_config, "cleanup-demo": cleanup_demo, "schedule-setup": schedule_setup, "schedule-status": schedule_status}
    if task not in tasks:
        say(f"unknown task {task!r}; choose from {', '.join(tasks)}")
        return 2
    return tasks[task](secrets)


if __name__ == "__main__":
    sys.exit(main())
