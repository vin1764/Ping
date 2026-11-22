"""22 Nov, FirstClub shortlist (anonymised): Ping said "You're not on it" to a student who was on the list.

What happened: the profile table holds the student's row (id 1) and, since the anonymised demo was built, the demo's
made-up profile (id 2, is_sample: fake roll, "Demo Student"). The run read "the first profile row" and got the demo's,
so a 2-page, 117-roll shortlist was searched for the demo roll. The demo roll and the student's share the first digit
and the last five digits, so nothing looked odd. The file itself was read in full.

The rolls below are made up; the shape of the case is the real one: 2 pages, one table, 117 rolls (106 of one
pattern, 11 of another), the student on page 2, the demo roll not in the file.
"""

from datetime import datetime

from attachment_fixtures import table_pdf
from ping.config import IST, Secrets
from ping.pdfs import check_attachment
from ping.run import Runner
from ping.store import MemoryStore

STUDENT = "23QR10042"         # made up: same first digit and last five digits as the demo roll
DEMO = "22XY10042"


def shortlist() -> bytes:
    rows = [["S.No", "Roll No", "Profile"]]
    for i in range(1, 107):
        rows.append([str(i), f"2{i % 4 + 1}AB{20000 + i * 7:05d}", "Product Management"])
    for i in range(107, 118):
        rows.append([str(i), f"2{i % 4 + 1}C{i % 9}AB{i % 90 + 10:02d}", "Product Management"])
    rows.insert(95, ["95a", STUDENT, "Product Management"])      # page 2
    rows.pop(96)
    return table_pdf(rows, title="FirstClub - Shortlist (Product Management)")


def store_with_demo_first() -> MemoryStore:
    s = MemoryStore()
    s.upsert("profile", [{"id": 2, "roll": DEMO, "name": "Demo Student", "cgpa": 7.0, "targets": "demo targets",
                          "is_sample": True}])
    s.upsert("profile", [{"id": 1, "roll": None, "name": None, "cgpa": 8.4, "targets": "my targets", "is_sample": False}])
    return s


def runner(store):
    return Runner(Secrets(STUDENT, "pw", [], "me@example.com", "app", ai={}), store, store_ok=True,
                  now=datetime(2026, 11, 22, 12, 41, tzinfo=IST), mailbox=object())


def test_the_run_reads_your_own_profile_not_the_demo_one():
    p = runner(store_with_demo_first()).profile()
    assert p["roll"] == STUDENT and p["targets"] == "my targets" and p["cgpa"] == 8.4


def test_the_firstclub_shortlist_finds_you():
    pdf = shortlist()
    res = check_attachment(pdf, STUDENT)
    assert res["pages"] >= 2 and res["roll_like_count"] >= 100
    assert res["status"] == "yes" and res["matched_by"] == "roll", res
    # even with a wrong roll in the profile, your ERP login id is looked for too
    res = check_attachment(pdf, DEMO, also=[STUDENT])
    assert res["status"] == "yes", res
    # and a file read in full that doesn't list you is "not found", which the feed words as "couldn't find" (below)
    assert check_attachment(pdf, "24ZZ99999")["status"] == "no"


def test_never_you_are_not_on_it():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    for f in [*root.glob("ping/*.py"), *root.glob("dashboard/*.js"), *root.glob("supabase/functions/**/*.ts"),
              *root.glob("supabase/functions/**/*.js")]:
        text = f.read_text(encoding="utf-8", errors="ignore")
        assert "You're not on it" not in text and "you're not on the list" not in text.lower(), f


def test_rescan_reads_lists_again_and_reports_what_changed(monkeypatch):
    """ping.recheck.rescan (the 14-day re-scan and the chat's 'check X again'): files read again from the (fake) ERP
    with the fixed code, verdicts saved, the feed rebuilt, every change listed."""
    import ping.erp as erp_mod
    from fake_erp import FakeErp
    from ping.gate import Gate
    from ping.recheck import rescan
    from test_end_to_end import NOW, run, secrets
    monkeypatch.setattr(erp_mod, "MIN_OTP_TO_LOGIN", 0)
    fake = FakeErp(NOW)
    _, store = run(fake)
    # the 22 Nov state: the demo profile read first, and a stored "no"
    store.tables["profile"] = {2: {"id": 2, "roll": "99ZZ00000", "name": "Demo Student", "is_sample": True}, **store.tables["profile"]}
    for c in store.tables["pdf_checks"].values():
        c["status"] = "no"
    r = Runner(secrets(), store, store_ok=True, gate=Gate(fake), mailbox=fake.mail, now=NOW, pause=0)
    changes = rescan(r, days=14)
    assert [(c["old"], c["new"]) for c in changes] == [("no", "yes")]
    item = next(i for i in store.select("items") if i.get("pdf_status"))
    assert item["title"].startswith("You're on the Pine Labs test room list")
    assert not any(x.startswith("POST") and "Action" in x for x in fake.calls)
