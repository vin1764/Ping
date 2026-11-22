"""The forms list (ping/forms.py): one row per form whatever the notice or mail around it says, reposts and extensions
merged with their history, ticks that silence reminders."""

from datetime import datetime, timedelta

from ping import forms, push
from ping.config import IST

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=IST)
G = "https://docs.google.com/forms/d/e/1FAIpQLSdTestForm0123456789/viewform"


def todo(iid, company, link, due, *, notice=None, mail=None, subject="Additional requirement form", level="show"):
    d = {"todo": {"action": "fill_form", "link": link, "due": due}, "subject": subject}
    if link:
        d["forms"] = [link]
    if notice:
        d["notice_time"] = notice[1]
    if mail:
        d["mail"] = {"id": mail[0], "received_at": mail[1], "link": link}
        d["via"] = "email" if not notice else None
    return {"id": iid, "category": "todo", "company": company, "title": f"{company}: fill the form by {due}.",
            "due_at": due, "level": level, "notice_id": notice[0] if notice else None, "role_ids": [], "details": d}


def test_canonical_keys_whatever_the_wrapping():
    assert forms.key_of(G + "?usp=sf_link") == forms.key_of(G) == forms.key_of(G.replace("viewform", "formResponse"))
    assert forms.key_of("https://docs.google.com/forms/d/1AbCdEfGhIjKlMnOp/edit#responses") == "gform:1AbCdEfGhIjKlMnOp"
    assert forms.key_of("https://forms.office.com/Pages/ResponsePage.aspx?id=AbC123xyz&embed=true") == "msform:AbC123xyz"
    assert forms.key_of("https://forms.zohopublic.in/acme/form/Reg/formperma/aBcDeFgHiJkL?x=1") == "zoho:aBcDeFgHiJkL"
    assert forms.key_of("https://acme.typeform.com/to/AbC123?utm=x") == "typeform:AbC123"
    assert forms.key_of("https://form.jotform.com/231234567890123") == "jotform:231234567890123"
    assert forms.key_of("mailto:cdc@example.com") is None
    # a short link is followed to the form it points to (no cookies, nothing submitted)
    final, key = forms.resolve("https://forms.gle/AbCdEf123", fetch=lambda u: G + "?usp=send_form")
    assert key == forms.key_of(G)


def test_the_same_form_by_notice_and_by_mail_is_one_row_with_both_sources():
    items = [todo("notice:1791:todo0", "Groww", G, "2026-11-21T20:00:00+05:30", notice=("1791", "2026-11-20T10:00:00+05:30")),
             todo("mail:m1", "Groww", G + "?usp=sf_link", "2026-11-21T20:00:00+05:30", mail=("m1", "2026-11-20T11:00:00+05:30"))]
    rows = forms.build(items, now=NOW)
    assert len(rows) == 1
    r = rows[0]
    assert [s["type"] for s in r["sources"]] == ["notice", "mail"]
    assert r["item_ids"] == ["notice:1791:todo0", "mail:m1"]
    assert r["purpose"] == "additional requirement"


def test_a_repost_with_a_later_deadline_moves_it_and_keeps_the_history():
    items = [todo("notice:1791:todo0", "Groww", G, "2026-11-21T20:00:00+05:30", notice=("1791", "2026-11-20T10:00:00+05:30")),
             todo("notice:1796:todo0", "Groww", G, "2026-11-22T20:00:00+05:30", notice=("1796", "2026-11-21T09:00:00+05:30"))]
    r = forms.build(items, now=NOW)[0]
    assert r["due_at"] == "2026-11-22T20:00:00+05:30"
    assert r["deadline_history"] == [{"from": "2026-11-21T20:00:00+05:30", "to": "2026-11-22T20:00:00+05:30",
                                      "at": "2026-11-21T09:00:00+05:30", "source": {"type": "notice", "id": "1796", "at": "2026-11-21T09:00:00+05:30"}}]
    assert [s["id"] for s in r["sources"]] == ["1791", "1796"]
    # a later run keeps the history and the first-seen time
    again = forms.build(items[1:], previous={r["key"]: r}, now=NOW + timedelta(hours=1))[0]
    assert again["deadline_history"] == r["deadline_history"] and again["first_seen"] == r["first_seen"]
    assert {s["id"] for s in again["sources"]} == {"1791", "1796"}


def test_two_different_forms_from_one_company_stay_apart():
    other = "https://docs.google.com/forms/d/e/1FAIpQLSdOtherForm987654321/viewform"
    items = [todo("n1:todo0", "Groww", G, "2026-11-21T20:00:00+05:30", notice=("1", "2026-11-20T10:00:00+05:30"), subject="Registration form"),
             todo("n2:todo0", "Groww", other, "2026-11-21T20:00:00+05:30", notice=("2", "2026-11-20T11:00:00+05:30"), subject="Test slot preference form")]
    rows = forms.build(items, now=NOW)
    assert len(rows) == 2
    assert {r["purpose"] for r in rows} == {"registration", "test slot"}


def test_a_ticked_form_gets_no_mail_reminder_and_the_queue_row_carries_its_key():
    due = (NOW + timedelta(hours=5)).isoformat()
    it = todo("mail:m9", "Axon", "https://example.com/forms/axon", due, mail=("m9", NOW.isoformat()))
    it["details"]["via"] = "email"
    rows = forms.build([it], now=NOW)
    forms.mark_items([it], rows, filled=set())
    q = push.mail_reminders([it], {"reminder_hours": 2}, NOW)
    assert len(q) == 1 and q[0]["form_key"] == rows[0]["key"]          # send-push re-checks the tick at send time
    forms.mark_items([it], rows, filled={rows[0]["key"]})
    assert it["details"]["form"]["filled"] is True
    assert push.mail_reminders([it], {"reminder_hours": 2}, NOW) == []


def test_only_your_own_ticks_count():
    assert forms.filled_keys([{"form_key": "a", "filled": True, "is_demo": False}, {"form_key": "b", "filled": True, "is_demo": True},
                              {"form_key": "c", "filled": False, "is_demo": False}]) == {"a"}


def test_purposes():
    assert forms.purpose_of("Registration form for Groww") == "registration"
    assert forms.purpose_of("PPT RSVP: Slice") == "PPT RSVP"
    assert forms.purpose_of("CV Submission", "submit your CV") == "CV submission"
    assert forms.purpose_of("Test slot booking") == "test slot"
    assert forms.purpose_of("Fill the form") == "form"
