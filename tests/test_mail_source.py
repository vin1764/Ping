"""The mailbox as a source (ping/mail_source.py), against the 20-mail fixture mailbox (evals/mail/fixture.py)."""

import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals" / "mail"))

from fixture import NAME, NOW, OTP_CODE, ROLES, ROLL, mailbox, mails  # noqa: E402

from ping import mail_source  # noqa: E402
from ping.mailbox import Head  # noqa: E402
from ping.matching import CompanyIndex  # noqa: E402


@pytest.fixture(scope="module")
def scanned():
    fx = mails()
    mb, fake = mailbox(fx)
    rows, st = mail_source.scan(mb, NOW - timedelta(days=14), CompanyIndex(ROLES), ROLL, NAME)
    return fx, fake, rows, st


def test_noise_is_never_read_beyond_headers(scanned):
    fx, fake, rows, st = scanned
    noise = {m["uid"] for m in fx if not m["placement"]}
    assert sorted(fake.headers_read, key=int) == [m["uid"] for m in fx]       # every mail: headers only first
    assert not noise & set(fake.bodies_read)                                    # no noise body, ever
    assert set(fake.bodies_read) == {m["uid"] for m in fx if m["placement"]}
    assert fake.writes == []                                                    # read-only
    assert st.headers_seen == 20 and st.kept == 10 and st.bodies_read == 10


def test_nothing_of_the_noise_or_the_otp_is_stored(scanned):
    fx, _, rows, st = scanned
    stored = repr(rows)
    for m in fx:
        if not m["placement"]:
            assert m["subject"] not in stored
    assert OTP_CODE not in stored and "OTP" not in stored and st.otp_skipped == 1


def test_why_each_noise_mail_was_dropped(scanned):
    fx, *_ = scanned
    from ping.mailbox import parse_head
    index = CompanyIndex(ROLES)
    for m in fx:
        v = mail_source.scope(parse_head(m["uid"], m["raw"], None), index)
        assert v.keep == m["placement"], m["label"]
        if not m["placement"]:
            assert v.because == m["expect"]["because"], m["label"]


def test_otp_found_only_in_the_body_is_still_not_stored():
    from ping.mailbox import Mail
    mail = Mail("1", NOW, "CDC <cdc@institute.example>", "Login help", "Your one time password is 123456")
    v = mail_source.Verdict(True, "placement_office")
    assert mail_source.read(mail, [], v, CompanyIndex(ROLES), ROLL) is None


@pytest.mark.parametrize("sender,subject,keep", [
    ("Pine Labs <hr@pinelabs.example>", "Welcome", True),                    # company by domain
    ("x <a@b.example>", "Your PineLabs application", True),                  # name written together
    ("x <a@b.example>", "Feedback form for course CS101", False),            # "form" without a hiring word
    ("x <a@b.example>", "Internship form: last date Friday", True),          # "form" next to a hiring word
    ("Training & Placement Cell <tnp@inst.example>", "Notice", True),        # placement office
    ("x <a@b.example>", "Global summit", False),                             # a common word isn't a company
])
def test_scope_examples(sender, subject, keep):
    assert mail_source.scope(Head("1", NOW, sender, subject), CompanyIndex(ROLES)).keep is keep


def test_extraction(scanned):
    fx, _, rows, _ = scanned
    for m, r in zip([m for m in fx if m["placement"]], rows):
        for k, want in m["expect"].items():
            if k == "pdf":
                assert (r["pdf"] or {}).get("status") == want, m["label"]
            elif k != "twin":
                assert r.get(k) == want, (m["label"], k, r.get(k))
    shortlist = rows[0]["pdf"]
    assert shortlist["my_row"] and ROLL in " ".join(shortlist["my_row"]) and shortlist["header"]


# ---------------------------------------------------------------- the feed: ERP twins and mail-only messages
@pytest.fixture(scope="module")
def feed(scanned):
    from fixture import NOTICES, PROFILE
    from ping.items import build_items
    from ping.notices import analyze
    _, _, rows, _ = scanned
    index = CompanyIndex(ROLES)
    notices = [dict(n) for n in NOTICES]
    for n in notices:
        n["analysis"] = analyze(n, n["text"], index, ROLL, NAME)
    roles = [dict(r) for r in ROLES]
    stats = {}
    items = build_items(roles, notices, {}, PROFILE, NOW, rows, {}, stats=stats)
    return {it["id"]: it for it in items}, stats, roles


def test_the_erp_duplicate_only_adds_also_mailed(feed, scanned):
    items, stats, _ = feed
    assert stats["mail_twins"] == 1 and stats["mail_only"] == 9
    groww = next(it for it in items.values() if it["id"].startswith("notice:2026-2027:901"))
    assert groww["details"]["mail"]["note"] == "also mailed to you"
    assert groww["details"]["mail"]["link"] == "https://www.hackerrank.com/tests/groww-pa-2026"
    dup = next(r for r in scanned[2] if r["subject"].startswith("Groww online test"))
    assert f"mail:{dup['id']}" not in items                     # no second message for it


def test_mail_only_items_are_feed_items_via_email(feed):
    items, _, _ = feed
    mail = [it for it in items.values() if it["id"].startswith("mail:")]
    assert len(mail) == 9 and all(it["details"]["via"] == "email" for it in mail)
    form = next(it for it in mail if "Pine Labs" in it["title"])
    assert form["category"] == "todo" and form["details"]["todo"]["action"] == "fill_form"
    assert form["due_at"] == "2026-11-22T17:00:00+05:30" and form["details"]["todo"]["link"] == "https://forms.gle/PineLabsPre2026"
    gs = next(it for it in mail if "Goldman" in it["title"])
    assert gs["level"] == "always" and gs["pdf_status"] == "yes" and "You're on it" in gs["title"]
    navi = next(it for it in mail if "Navi" in it["title"])
    assert navi["category"] == "test" and navi["event_at"] == "2026-11-24T11:00:00+05:30"


def test_mail_never_changes_applied(feed):
    _, _, roles = feed
    assert [r["applied"] for r in roles] == [r["applied"] for r in ROLES]      # the offer mail and "thanks for applying"


def test_eligibility_and_interests_apply_to_mail_items(scanned):
    from fixture import PROFILE
    from ping.items import build_items
    _, _, rows, _ = scanned
    prof = {**PROFILE, "not_interested_companies": ["Pine Labs Private Limited"]}
    items = {it["id"]: it for it in build_items(ROLES, [], {}, prof, NOW, rows, {})}
    pine = next(it for it in items.values() if it["id"].startswith("mail:") and "Pine Labs" in it["title"])
    assert pine["level"] == "hidden" and pine["details"]["hidden_because"] == "marked not interested"


def test_old_mail_rows_are_deleted_when_the_rules_change():
    from ping.store import MemoryStore
    st = MemoryStore()
    st.upsert("emails", [{"id": "old", "subject": "Mess menu", "rules_version": None, "is_sample": False},
                         {"id": "demo", "subject": "x", "rules_version": None, "is_sample": True},
                         {"id": "new", "subject": "Groww test", "rules_version": 1, "is_sample": False}])
    st.delete("emails", {"rules_version": "is.null", "is_sample": "is.false"})
    assert sorted(r["id"] for r in st.select("emails")) == ["demo", "new"]
