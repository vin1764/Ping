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
