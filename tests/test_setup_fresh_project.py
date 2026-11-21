"""A brand-new student, an empty Supabase project, one command.

Runs setup/new_student_setup.py against a fake but realistic Supabase (real
Postgres with Supabase's roles, RLS and the newer 'no automatic grants'
default), then checks that Ping can save a run and the dashboard login can
read it, without anyone touching Supabase's SQL editor or auth screens.
Needs root + a local Postgres 16; skipped otherwise.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
import requests

import fake_supabase as fs

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not fs.available() or os.geteuid() != 0, reason="needs root and Postgres 16")

STUDENT = {
    "ERP_USER_ID": "22XY10042", "ERP_PASSWORD": "pw",
    "ERP_SECQ_1": "What is the name of your first pet?::Bruno", "ERP_SECQ_2": "In which city were you born?::Patna",
    "ERP_SECQ_3": "What is your favourite food?::Dosa",
    "MAIL_ADDRESS": "Student@Example.com", "MAIL_APP_PASSWORD": "abcd efgh ijkl mnop",
    "SUPABASE_ACCESS_TOKEN": fs.TOKEN, "GEMINI_API_KEY": "", "PING_GITHUB_TOKEN": "",
    "DASHBOARD_PASSWORD": "correct horse battery", "GITHUB_REPO": "student/ping",
}


@pytest.fixture()
def project(tmp_path):
    fake = fs.FakeSupabase().start()
    env = {**os.environ, **STUDENT, "SUPABASE_URL": fake.url, "PING_SUPABASE_API": fake.url,
           "PING_SUPABASE_REF": fs.REF, "PING_SETUP_TEST": "1", "DASHBOARD_EMAIL": "Student@Example.com",
           "PING_SETUP_ENV_FILE": str(tmp_path / ".env")}
    yield fake, env, tmp_path
    fake.stop()


def setup(env, *extra):
    return subprocess.run([sys.executable, str(ROOT / "setup" / "new_student_setup.py"), "--skip-erp-test", "--no-gh",
                           *extra], env=env, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)


def sign_in(fake, email, password):
    r = requests.post(f"{fake.url}/auth/v1/token", params={"grant_type": "password"},
                      headers={"apikey": fs.PUBLISHABLE}, json={"email": email, "password": password})
    return r


def test_one_command_setup_on_an_empty_project(project):
    fake, env, tmp = project
    out = setup(env)
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-2000:]
    text = out.stdout
    assert "tables, permissions and database rules: OK" in text
    assert "login student@example.com: created, confirmed, on the allowed list" in text
    assert "Done in" in text and "Open https://student.github.io/ping/ and sign in with student@example.com" in text
    # the student was told every GitHub secret, by name, including the keys the script fetched itself
    for name in ("ERP_USER_ID", "SUPABASE_SERVICE_KEY", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ACCESS_TOKEN"):
        assert f"    {name}" in text
    assert fs.SECRET in text and fs.PUBLISHABLE in text
    # .env saved, readable only by the student
    envfile = tmp / ".env"
    assert oct(envfile.stat().st_mode)[-3:] == "600"
    assert 'MAIL_APP_PASSWORD="abcdefghijklmnop"' in envfile.read_text()

    # a brand-new student starts with an EMPTY profile: nothing about anyone is pre-filled
    from ping.store import SupabaseStore as _S
    prof = _S(fake.url, fs.SECRET).select("profile")
    assert [r["id"] for r in prof] == [1]
    assert all(prof[0].get(k) in (None, [], "") for k in ("roll", "name", "department", "degree", "cgpa", "targets", "cvs"))

    # Ping can now save a whole run with the secret key ...
    from fake_erp import FakeErp
    import ping.erp as erp_mod
    from ping.config import IST, Secrets, SecurityAnswer
    from ping.gate import Gate
    from ping.run import Runner
    from ping.store import SupabaseStore
    erp_mod.MIN_OTP_TO_LOGIN = 0
    store = SupabaseStore(fake.url, fs.SECRET)
    assert store.ready() == (True, "ok")
    erp = FakeErp(datetime(2026, 11, 21, 9, 0, tzinfo=IST))
    secrets = Secrets("22XY10042", "pw", [SecurityAnswer("What is the name of your first pet?", "Bruno")],
                      "student@example.com", "x", fake.url, fs.SECRET, {})
    rec = Runner(secrets, store, store_ok=True, gate=Gate(erp), mailbox=erp.mail,
                 now=datetime(2026, 11, 21, 9, 0, tzinfo=IST), pause=0).run()
    assert rec["status"] == "ok", rec["problems"]
    assert not any("saving" in p for p in rec["problems"]), rec["problems"]

    # ... and the dashboard login reads it, exactly like the dashboard does
    r = sign_in(fake, "student@example.com", "correct horse battery")
    assert r.status_code == 200, r.text
    user = {"apikey": fs.PUBLISHABLE, "Authorization": f"Bearer {r.json()['access_token']}"}
    items = requests.get(f"{fake.url}/rest/v1/items", headers=user, params={"select": "*"}).json()
    assert len(items) > 3 and any("Pine Labs" in i["title"] for i in items)
    assert requests.post(f"{fake.url}/rest/v1/rpc/is_ping_owner", headers=user, json={}).json() is True
    # it may edit the profile and write to the chat ...
    ok = requests.patch(f"{fake.url}/rest/v1/profile", headers=user, params={"id": "eq.1"}, json={"cgpa": 8.4})
    assert ok.status_code == 204, ok.text
    # ... including what a first chat message saves ("only show me ...", "remind me 3 hours before")
    prefs = {"targets": "roles a new student describes", "reminder_hours": 3, "list_other_roles": False}
    ok = requests.patch(f"{fake.url}/rest/v1/profile", headers=user, params={"id": "eq.1"}, json=prefs)
    assert ok.status_code == 204, ok.text
    assert {k: store.select("profile", {"id": "eq.1"})[0][k] for k in prefs} == prefs
    # onboarding step (f) as the student: check every 30 minutes, 08:00-22:00 IST; the scheduler's guard reads exactly
    # that (ping/schedule_guard.py, the mirror of kick-run's guard) and follows it
    sched = {"check_every_minutes": 30, "check_from": "08:00", "check_to": "22:00", "onboarding_step": "reminders"}
    ok = requests.patch(f"{fake.url}/rest/v1/profile", headers=user, params={"id": "eq.1"}, json=sched)
    assert ok.status_code == 204, ok.text
    import os
    from datetime import timedelta as _td, timezone as _tz
    from ping import schedule_guard
    saved_env = {k: os.environ.get(k) for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")}
    os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"] = fake.url, fs.SECRET
    try:
        plan = schedule_guard.owner_schedule()
    finally:
        for k, v in saved_env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    assert plan == {"every_minutes": 30, "from": "08:00", "to": "22:00"}
    ist = _tz(_td(hours=5, minutes=30))
    t10 = datetime(2026, 11, 21, 10, 11, tzinfo=ist)
    last = [{"id": 1, "status": "completed", "created_at": (t10 - _td(minutes=30)).isoformat()}]
    assert schedule_guard.decide(last, t10, schedule=plan)[0]                                  # 30 min later: runs
    assert not schedule_guard.decide([], datetime(2026, 11, 21, 23, 11, tzinfo=ist), schedule=plan)[0]  # after 22:00
    chat = requests.post(f"{fake.url}/rest/v1/chat_messages", headers=user, json=[{"role": "me", "text": "hi"}])
    assert chat.status_code == 201, chat.text
    # ... but not change what Ping found, and someone without a login sees nothing
    bad = requests.patch(f"{fake.url}/rest/v1/items", headers=user, params={"id": f"eq.{items[0]['id']}"},
                         json={"title": "hacked"})
    assert bad.status_code == 403
    anon = requests.get(f"{fake.url}/rest/v1/items", headers={"apikey": fs.PUBLISHABLE}, params={"select": "*"})
    assert anon.status_code == 403 or anon.json() == []


def test_running_it_again_is_safe_and_fixes_the_password(project):
    fake, env, _ = project
    assert setup(env).returncode == 0
    again = setup({**env, "DASHBOARD_PASSWORD": "a new password 123"})
    assert again.returncode == 0, again.stdout[-2000:]
    assert "updated, confirmed, on the allowed list" in again.stdout
    assert sign_in(fake, "student@example.com", "a new password 123").status_code == 200
    assert sign_in(fake, "student@example.com", "correct horse battery").status_code == 400


def test_wrong_access_token_stops_with_a_clear_message(project):
    fake, env, _ = project
    out = setup({**env, "SUPABASE_ACCESS_TOKEN": "sbp_wrong"})
    assert out.returncode == 1
    assert "STOPPED" in out.stdout and "token" in out.stdout.lower()


def _anonymous(fake):
    """What the dashboard's "View demo" button does: supabase.auth.signInAnonymously()."""
    r = requests.post(f"{fake.url}/auth/v1/signup", headers={"apikey": fs.PUBLISHABLE}, json={})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    return {"apikey": fs.PUBLISHABLE, "Authorization": f"Bearer {tok}"}, r.json()["user"]["id"]


def test_demo_session_reads_only_demo_rows_and_writes_only_its_own_chat(project):
    fake, env, _ = project
    assert setup(env).returncode == 0
    from fake_erp import FakeErp
    import ping.erp as erp_mod
    from ping.config import IST, Secrets, SecurityAnswer
    from ping.demo_from_real import build_from_store, load_to_db, verify
    from ping.gate import Gate
    from ping.run import Runner
    from ping.store import SupabaseStore
    erp_mod.MIN_OTP_TO_LOGIN = 0
    store = SupabaseStore(fake.url, fs.SECRET)
    erp = FakeErp(datetime(2026, 11, 21, 9, 0, tzinfo=IST))
    secrets = Secrets("22XY10042", "pw", [SecurityAnswer("What is the name of your first pet?", "Bruno")],
                      "student@example.com", "x", fake.url, fs.SECRET, {})
    assert Runner(secrets, store, store_ok=True, gate=Gate(erp), mailbox=erp.mail,
                  now=datetime(2026, 11, 21, 9, 0, tzinfo=IST), pause=0).run()["status"] == "ok"
    data = build_from_store(store, "22AB99999", "student@example.com")
    assert verify(data, "22AB99999", "student@example.com", None) == []
    load_to_db(store, data)
    real = {t: len(store.select(t, {"is_sample": "not.is.true"})) for t in ("items", "roles", "notices", "runs")}
    assert all(real.values()), real

    demo, demo_uid = _anonymous(fake)
    get = lambda h, t, **q: requests.get(f"{fake.url}/rest/v1/{t}", headers=h, params={"select": "*", **q})
    # reads: demo rows only in the five demo tables, nothing at all elsewhere
    for t in ("profile", "roles", "notices", "pdf_checks", "items"):
        rows = get(demo, t).json()
        assert rows and all(r["is_sample"] for r in rows), t
    assert [r["id"] for r in get(demo, "profile").json()] == [2]
    for t in ("runs", "state", "contacts", "emails", "allowed_users", "corrections", "demo_questions"):
        r = get(demo, t)
        assert r.status_code == 403 or r.json() == [], (t, r.status_code, r.text[:100])
    assert requests.post(f"{fake.url}/rest/v1/rpc/is_ping_owner", headers=demo, json={}).json() is False

    # writes: nothing except its own chat
    some_item = store.select("items", {"is_sample": "is.true"})[0]
    requests.patch(f"{fake.url}/rest/v1/items", headers=demo, params={"id": f"eq.{some_item['id']}"}, json={"done": True})
    requests.patch(f"{fake.url}/rest/v1/profile", headers=demo, params={"id": "eq.2"}, json={"cgpa": 9.9})
    requests.delete(f"{fake.url}/rest/v1/items", headers=demo, params={"id": f"eq.{some_item['id']}"})
    assert store.select("items", {"id": f"eq.{some_item['id']}"})[0]["done"] is not True
    assert store.select("profile", {"id": "eq.2"})[0]["cgpa"] != 9.9
    for t, row in (("items", {"id": "x", "title": "x", "is_sample": True}), ("corrections", {"notice_id": "x"}),
                   ("runs", {"id": "x", "is_sample": True}), ("allowed_users", {"email": "me@x.in"})):
        assert requests.post(f"{fake.url}/rest/v1/{t}", headers=demo, json=[row]).status_code == 403, t
    chat = lambda h, row: requests.post(f"{fake.url}/rest/v1/chat_messages", headers=h, json=[row]).status_code
    assert chat(demo, {"role": "me", "text": "slice ctc?", "is_sample": True}) == 201
    assert chat(demo, {"role": "me", "text": "not a demo row"}) == 403            # demo chat must be a demo row
    other, other_uid = _anonymous(fake)
    assert chat(demo, {"role": "me", "text": "x", "is_sample": True, "owner_id": other_uid}) == 403  # not someone else's
    assert [m["text"] for m in get(demo, "chat_messages").json()] == ["slice ctc?"]

    # preferences: a demo session keeps its own (session_prefs), never the owner's profile, never another session's
    owner_targets = store.select("profile", {"id": "eq.1"})[0].get("targets")
    pref = lambda h, row: requests.post(f"{fake.url}/rest/v1/session_prefs", headers=h, json=[row]).status_code
    assert pref(demo, {"owner_id": demo_uid, "targets": "only analyst roles"}) == 201
    assert pref(demo, {"owner_id": other_uid, "targets": "x"}) == 403
    requests.patch(f"{fake.url}/rest/v1/profile", headers=demo, params={"id": "eq.1"}, json={"targets": "hijack"})
    assert store.select("profile", {"id": "eq.1"})[0].get("targets") == owner_targets
    assert [r["targets"] for r in get(demo, "session_prefs").json()] == ["only analyst roles"]
    assert get(other, "session_prefs").json() == []
    # the "For you" cache is server-only
    r = get(demo, "role_marks")
    assert r.status_code == 403 or r.json() == []
    assert get(other, "chat_messages").json() == []                                # sessions don't see each other
    me = sign_in(fake, "student@example.com", "correct horse battery").json()["access_token"]
    owner = {"apikey": fs.PUBLISHABLE, "Authorization": f"Bearer {me}"}
    assert not any(m["text"] == "slice ctc?" for m in get(owner, "chat_messages").json())  # nor does the owner
    assert len(get(owner, "items").json()) == real["items"]                       # owner: real rows, as before

    # Ask Ping's demo limit: 15 per session per hour, counted without the question text
    take = lambda h: requests.post(f"{fake.url}/rest/v1/rpc/demo_take_question", headers=h, json={}).json()
    assert all(take(demo)["ok"] for _ in range(15)) and take(demo) == {"ok": False, "why": "session", "session": 15, "all": 15}
    assert take(other)["ok"] and take(owner) == {"ok": True}

    # daily cleanup: only the service key may run it; it removes week-old anonymous users and their chat
    assert requests.post(f"{fake.url}/rest/v1/rpc/cleanup_demo_sessions", headers=demo, json={"days": 7}).status_code == 403
    with fake.conn() as c:
        c.execute("update auth.users set created_at = now() - interval '8 days' where id = %s", (demo_uid,))
    done = requests.post(f"{fake.url}/rest/v1/rpc/cleanup_demo_sessions", headers={"apikey": fs.SECRET}, json={"days": 7}).json()
    assert done["anonymous_users"] == 1 and done["chat_messages"] == 1
    with fake.conn() as c:
        assert c.execute("select count(*) from auth.users where is_anonymous").fetchone()[0] == 1   # the newer one
