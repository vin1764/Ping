"""A whole run against the fake ERP: login, companies, popups, notices, PDF, mail, feed."""

from datetime import datetime

import pytest

from fake_erp import QUESTIONS, ROLL, FakeErp
from ping.config import IST, Secrets, SecurityAnswer
from ping.gate import Gate
from ping.run import Runner
from ping.store import MemoryStore

NOW = datetime(2026, 11, 21, 9, 0, tzinfo=IST)


def secrets(answers=None):
    answers = answers or [SecurityAnswer(q.upper() + "  ", a) for q, a in QUESTIONS.items()]
    return Secrets(ROLL, "pw", answers, "me@kgpian.iitkgp.ac.in", "app", ai={})


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    import ping.erp as erp_mod
    monkeypatch.setattr(erp_mod, "MIN_OTP_TO_LOGIN", 0)


def run(fake, store=None, s=None):
    store = store or MemoryStore()
    store.upsert("profile", [{"id": 1, "department": "Computer Science and Engineering", "degree": "B.Tech",
                              "cgpa": 8.1, "name": "Demo Student"}])
    r = Runner(s or secrets(), store, store_ok=True, gate=Gate(fake), mailbox=fake.mail, now=NOW, pause=0)
    return r.run(), store


def test_full_run():
    fake = FakeErp(NOW)
    rec, store = run(fake)
    assert rec["status"] == "ok", rec["problems"]
    c = rec["counts"]
    assert c["roles_seen"] == 5 and c["roles_new"] == 5
    assert c["notices_seen"] == 3 and c["notices_new"] == 2   # 30-day-old notice skipped on first run
    assert c["pdf_yes"] == 1
    # logged out at the end, and never touched anything outside the allow list
    assert fake.calls[-1] == "GET /IIT_ERP3/logout.htm"
    assert not any("Action" in x or "TPFile" in x for x in fake.calls)
    items = {i["id"]: i for i in store.select("items")}
    titles = [i["title"] for i in items.values() if i["level"] != "hidden"]
    assert any("You're on the Pine Labs test room list" in t and "room V2" in t for t in titles), titles
    assert any("Accordion" in t and "fill the form" in t for t in titles), titles
    # notice deadline (3 days) beats the companies list (2 days) for the role it names
    role = next(r for r in store.select("roles") if r["designation"] == "Data & AI Analyst")
    assert role["deadline_source"].startswith("notice")
    other = next(r for r in store.select("roles") if r["designation"] == "Business Analyst")
    assert other["deadline_source"] == "companies list"
    # Sakura: ERP says CGPA cut-off above yours -> not eligible -> hidden
    sak = next(i for i in items.values() if i["company"] == "Sakura KK")
    assert sak["level"] == "hidden"
    # every title fits on one line
    assert all(len(i["title"]) <= 160 for i in items.values())
    # only my row is stored from the PDF, never other students
    chk = store.select("pdf_checks")[0]
    assert chk["my_row"] == ["17", ROLL, "DEMO STUDENT", "V2"]
    assert "Student 3" not in str(chk)


def test_second_run_only_reads_new_things():
    fake = FakeErp(NOW)
    _, store = run(fake)
    fake2 = FakeErp(NOW)
    rec, _ = run(fake2, store)
    assert rec["counts"]["roles_new"] == 0
    assert rec["counts"]["notices_new"] == 1  # the old notice is now 'new' since only 14 days were read first
    assert not any("TPJNFView" in x for x in fake2.calls)


def test_unknown_security_question_stops_and_says_which():
    fake = FakeErp(NOW, question="What was your childhood nickname?")
    rec, _ = run(fake)
    assert rec["status"] == "failed: unknown_question"
    assert "childhood nickname" in rec["problems"][0]
    assert not any("getEmilOTP" in x for x in fake.calls)


def test_wrong_answer_is_reported():
    s = secrets([SecurityAnswer(q, "wrong") for q in QUESTIONS])
    rec, _ = run(FakeErp(NOW), s=s)
    assert rec["status"] == "failed: otp_refused"


@pytest.mark.parametrize("shown,stored,ok", [
    ("What is the name of your first pet?", "what is the name of your FIRST pet", True),
    ("What is the name of your first pet ?", "What is the name of your first pet?", True),
    ("In which city were you born?", "In which city was you born", False),  # a changed word is not a typo
    ("What is the name of your first pet?", "What is the name of your first pets", True),
    ("What is your favourite food?", "What is your favourite colour?", False),
])
def test_question_matching(shown, stored, ok):
    from ping.erp import match_question
    assert (match_question(shown, [SecurityAnswer(stored, "x")]) is not None) == ok


def test_login_failure_after_otp_is_retried_once(monkeypatch):
    import ping.erp as erp_mod
    monkeypatch.setattr(erp_mod.time, "sleep", lambda s: None)
    fake = FakeErp(NOW)
    real_send = fake.send
    state = {"auth": 0}

    def flaky(method, url, data, headers):
        if url.endswith("/SSOAdministration/auth.htm"):
            state["auth"] += 1
            if state["auth"] == 1:
                from ping.gate import Reply
                return Reply(200, url, {"content-type": "text/html"},
                             b"<div class='x'>Invalid OTP. Please try again.</div>")
        return real_send(method, url, data, headers)

    fake.send = flaky
    rec, _ = run(fake)
    assert rec["status"] == "ok", rec["problems"]
    assert state["auth"] == 2


def _failing(fake, how):
    """Make the fake ERP fail the way the real one does: 'blank' = login page without its form (ERP down),
    'refused' = the ERP won't send an OTP (password or security answer wrong)."""
    from ping.gate import Reply
    real_send = fake.send

    def send(method, url, data, headers):
        if how == "blank" and "/SSOAdministration/login.htm" in url:
            return Reply(200, url, {"content-type": "text/html"}, b"<html><body></body></html>")
        if how == "refused" and url.endswith("/SSOAdministration/getEmilOTP.htm"):
            return Reply(200, url, {"content-type": "application/json"}, b'{"msg": "Unable to send OTP"}')
        return real_send(method, url, data, headers)
    fake.send = send
    return fake


def _chat(store):
    return [m["text"] for m in store.select("chat_messages")]


@pytest.fixture()
def emails(monkeypatch):
    sent = []
    import ping.notify as notify
    monkeypatch.setattr(notify, "send_self", lambda addr, pw, subject, body: sent.append(subject) or True)
    return sent


def test_erp_unreachable_never_pauses_and_alerts_once_per_streak(emails):
    from ping.run import BACK_ONLINE_MSG, UNREACHABLE_MSG, credentials_pause
    store = MemoryStore()
    for i in range(1, 6):  # five hourly runs where the ERP shows a blank login page
        rec, store = run(_failing(FakeErp(NOW), "blank"), store)
        assert rec["status"] == "failed: page_changed"
        assert credentials_pause(store) is None  # never paused: the next hourly run tries again
        expected = 1 if i >= 3 else 0
        assert _chat(store).count(UNREACHABLE_MSG) == expected, (i, _chat(store))
        assert len(emails) == expected, (i, emails)
    assert store.get_state("erp_failures_in_a_row") == 5
    # the ERP is back: one "back online" message, no email, and the streak starts over
    rec, store = run(FakeErp(NOW), store)
    assert rec["status"] == "ok", rec["problems"]
    assert _chat(store)[-1] == BACK_ONLINE_MSG.format(n=5)
    assert len(emails) == 1 and store.get_state("erp_failures_in_a_row") == 0
    # a new streak alerts again after 3, once
    for _ in range(4):
        rec, store = run(_failing(FakeErp(NOW), "blank"), store)
    assert _chat(store).count(UNREACHABLE_MSG) == 2 and len(emails) == 2


def test_two_failures_then_success_says_nothing(emails):
    store = MemoryStore()
    for _ in range(2):
        run(_failing(FakeErp(NOW), "blank"), store)
    rec, store = run(FakeErp(NOW), store)
    assert rec["status"] == "ok" and _chat(store) == [] and emails == []


def test_refused_credentials_alert_at_once_and_pause_until_a_manual_run(emails, monkeypatch):
    from ping import run as run_mod
    store = MemoryStore()
    rec, store = run(_failing(FakeErp(NOW), "refused"), store)
    assert rec["status"] == "failed: otp_refused"
    assert len(emails) == 1 and "Login refused" in emails[0]          # immediately, first failure
    assert len(_chat(store)) == 1 and "refused the login" in _chat(store)[0]
    assert run_mod.credentials_pause(store)["kind"] == "otp_refused"
    assert store.get_state("erp_failures_in_a_row", 0) == 0           # not an "ERP down" streak

    # scheduled runs now skip without touching the ERP; a run started by hand still goes ahead
    started = []
    monkeypatch.setattr(run_mod, "Runner", lambda *a, **k: started.append(k["trigger"]) or
                        type("R", (), {"run": lambda self: {"status": "ok"}})())
    monkeypatch.setattr(run_mod, "MemoryStore", lambda *a: store)
    for key, val in {"ERP_USER_ID": ROLL, "ERP_PASSWORD": "pw", "ERP_SECQ_1": "q?::a", "ERP_SECQ_2": "q2?::b",
                     "ERP_SECQ_3": "q3?::c", "MAIL_ADDRESS": "me@x.in", "MAIL_APP_PASSWORD": "app"}.items():
        monkeypatch.setenv(key, val)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    assert run_mod.main(["--memory", "unused.json"]) == 0 and started == []
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    run_mod.main(["--memory", "unused.json"])
    assert started == ["workflow_dispatch"]


def test_a_manual_run_that_logs_in_resumes_the_schedule(emails):
    from ping.run import credentials_pause
    store = MemoryStore()
    run(_failing(FakeErp(NOW), "refused"), store)
    assert credentials_pause(store)
    rec, store = run(FakeErp(NOW), store)  # you fixed the secret and pressed Check now
    assert rec["status"] == "ok"
    assert credentials_pause(store) is None
    assert _chat(store)[-1] == "Logged in again; hourly checks are back on."
    assert len(emails) == 1  # only the original alert


def test_a_run_reports_its_progress_for_the_dashboard(monkeypatch):
    """The dashboard listens to the runs table: each step updates the run's own row (the one Check now created when
    there is one), the last update says done and how many new messages the chat got."""
    monkeypatch.setenv("PING_RUN_ROW", "20261121T090000-check")
    store = MemoryStore()
    stages = []
    orig = store.upsert

    def spy(table, rows, *a, **k):
        if table == "runs":
            stages.extend((r["id"], r.get("stage")) for r in rows)
        return orig(table, rows, *a, **k)
    monkeypatch.setattr(store, "upsert", spy)
    rec, store = run(FakeErp(NOW), store)
    assert {i for i, _ in stages} == {"20261121T090000-check"}
    assert [s for _, s in stages] == ["logging in", "reading companies", "reading notices", "reading PDFs", "saving", "done"]
    row = store.select("runs")[0]
    assert row["status"] == "ok" and row["new_items"] > 0 and row["note"] is None
    # the next run finds nothing new
    monkeypatch.delenv("PING_RUN_ROW")
    rec2, store = run(FakeErp(NOW), store)
    latest = next(r for r in store.select("runs") if r["id"] == rec2["id"])
    assert latest["stage"] == "done" and latest["new_items"] == 0


def test_a_failed_run_says_why_in_the_chat_words(monkeypatch):
    fake = FakeErp(NOW)
    rec, store = run(fake, s=secrets(answers=[SecurityAnswer("no such question", "x")] * 3))
    row = next(r for r in store.select("runs") if r["id"] == rec["id"])
    assert row["stage"] == "failed" and row["note"], row


def test_job_descriptions_found_off_the_companies_list(monkeypatch):
    """'Find Attached' + Download -> the ERP's JD file; a JD inline stays as it is; a Drive link is read (public);
    a placeholder with nothing behind it is 'none'. Found once, not again while the role doesn't change."""
    import ping.jd as jd
    from fake_erp import JD_FILE
    from ping.relevance import cache_key, needs
    monkeypatch.setattr(jd, "from_link", lambda url, session=None: {
        "jd_text": "Associate, Accordion. Work across client analytics engagements; " * 6, "jd_source": "link", "jd_url": url})
    fake = FakeErp(NOW)
    rec, store = run(fake)
    roles = {r["designation"]: r for r in store.select("roles")}
    a, b, c, p = roles["Data & AI Analyst"], roles["Business Analyst"], roles["Associate"], roles["Software Development Engineer"]
    assert a["jd_source"] == "attachment" and "Build dashboards" in a["jd_text"]
    assert a["jd_url"].endswith("AdmFilePDF.htm?type=JNF&year=2026-2027&jnf_id=1&com_id=501")
    assert b["jd_source"] == "inline" and b["jd_text"].startswith("As a Business Analyst")
    assert c["jd_source"] == "link" and c["jd_url"].startswith("https://drive.google.com/")
    assert p["jd_source"] == "none" and p["jd_text"] is None
    # the summary of the file: from its own lines (no model in this test)
    s = a["jd_summary"]
    assert s["model"] == "rules" and s["location"] == "Gurugram"
    assert any("SQL" in x for x in s["must_have"]) and any("service agreement" in x for x in s["unusual"])
    # a role that got a JD is marked again (its cache key changed); one whose JD was inline keeps its key
    before = dict(a, jd_text=None)
    old = {"relevance": {"key": cache_key("analytics roles", before)}}
    assert needs({**a, **old}, "analytics roles")
    assert cache_key("analytics roles", b) == cache_key("analytics roles", dict(b, jd_text=None))
    # the next run doesn't fetch it again
    files = lambda: sum("AdmFilePDF" in x for x in fake.calls)  # noqa: E731
    before_files = files()
    rec2, store = run(fake, store)
    assert files() == before_files, "no file fetched again (no new notice, the role's JD inputs unchanged)"


def test_the_run_builds_the_forms_list_and_a_tick_carries_to_the_next_run():
    fake = FakeErp(NOW)
    rec, store = run(fake)
    assert rec["status"] == "ok", rec["problems"]
    fs = store.select("forms")
    assert len(fs) == 1 and fs[0]["company"] == "Accordion" and fs[0]["link"] == "https://forms.gle/abc123"
    item = next(i for i in store.select("items") if (i.get("details") or {}).get("form"))
    assert item["details"]["form"] == {"key": fs[0]["key"], "filled": False, "sources": 1, "extended": False, "closed": False}
    # you tick it; the next run knows (only your own ticks count, never a demo session's)
    store.upsert("form_status", [{"owner_id": "me", "form_key": fs[0]["key"], "filled": True, "is_demo": False}],
                 key="owner_id,form_key")
    rec2, store = run(fake, store)
    assert rec2["counts"]["forms"]["filled"] == 1
    item = next(i for i in store.select("items") if (i.get("details") or {}).get("form"))
    assert item["details"]["form"]["filled"] is True
