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


def test_reviewer_sees_only_the_anonymised_demo_and_cannot_change_it(project):
    fake, env, _ = project
    assert setup(env).returncode == 0
    from fake_erp import FakeErp
    import ping.erp as erp_mod
    from ping import admin
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
    real_items = len(store.select("items"))
    # build the demo from the real rows, check it, load it as demo rows
    data = build_from_store(store, "22AB99999", "student@example.com")
    assert verify(data, "22AB99999", "student@example.com", None) == []
    load_to_db(store, data)
    # create the reviewer exactly like Actions > Admin > create-reviewer
    os.environ.update({"REVIEWER_EMAIL": "reviewer@ping-demo.example", "REVIEWER_PASSWORD": "review-me-123",
                       "SUPABASE_PUBLISHABLE_KEY": fs.PUBLISHABLE})
    assert admin.create_reviewer(secrets) == 0
    rev = sign_in(fake, "reviewer@ping-demo.example", "review-me-123").json()["access_token"]
    me = sign_in(fake, "student@example.com", "correct horse battery").json()["access_token"]
    see = lambda tok: requests.get(f"{fake.url}/rest/v1/items", params={"select": "id,is_sample"},
                                   headers={"apikey": fs.PUBLISHABLE, "Authorization": f"Bearer {tok}"}).json()
    assert see(rev) and all(i["is_sample"] for i in see(rev))
    assert len(see(me)) == real_items and not any(i["is_sample"] for i in see(me))
    hdr = {"apikey": fs.PUBLISHABLE, "Authorization": f"Bearer {rev}"}
    assert requests.post(f"{fake.url}/rest/v1/chat_messages", headers=hdr, json=[{"role": "me", "text": "x"}]).status_code == 403
    # a later Ping run never mixes the demo rows into the real feed
    erp2 = FakeErp(datetime(2026, 11, 21, 10, 0, tzinfo=IST))
    Runner(secrets, store, store_ok=True, gate=Gate(erp2), mailbox=erp2.mail,
           now=datetime(2026, 11, 21, 10, 0, tzinfo=IST), pause=0).run()
    assert not any(i["id"].startswith("sample:") and not i.get("is_sample") for i in store.select("items"))
