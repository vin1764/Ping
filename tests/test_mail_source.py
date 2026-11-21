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
