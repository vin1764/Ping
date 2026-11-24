"""'Not for me' on forms (ping/forms.py not_for_me_items, ping/items.py): a dismissed form never posts, pushes or
counts; restoring it brings it back as before; a demo session's dismissals never touch the owner's feed; the
company's roles are never touched."""

from datetime import datetime, timedelta

from ping import forms, posting, push
from ping.config import IST
from ping.items import build_items

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=IST)
DUE = (NOW + timedelta(hours=8)).isoformat()


def notice(nid, company, link):
    return {"id": f"2026-2027:{nid}", "notice_id": nid, "year": "2026-2027", "company": company, "subject": "Additional requirement form",
            "notice_time": (NOW - timedelta(hours=2)).isoformat(), "text": f"Students applying to {company} must fill {link} by tonight 20:00.",
            "analysis": {"kind": "form", "todos": [{"action": "fill_form", "link": link, "due": DUE}],
                         "targets": [{"name": company, "company": company, "profiles": [], "score": 1.0}]}}


ROLES = [{"id": f"r{i}", "company": c, "designation": d, "applied": False, "apply_end": DUE, "first_seen": NOW.isoformat(),
          "erp_messages": [], "allowed": [{"degree": "B.TECH", "department": "X"}]}
         for i, (c, d) in enumerate([("Diageo", "GBS Management Trainee"), ("Groww", "Product Analyst")])]
PROFILE = {"roll": "22XY10042", "cgpa": 8.0, "department": "X", "degree": "B.TECH"}


def build(not_for_me=frozenset()):
    ns = [notice(1900, "Diageo", "https://forms.gle/diageo1"), notice(1901, "Groww", "https://forms.gle/groww1")]
    items = build_items(ROLES, ns, {}, PROFILE, NOW, not_for_me=set(not_for_me))
    rows = forms.build(items, now=NOW)
    return items, rows


def form_items(items, company):
    return [it for it in items if it.get("category") == "todo" and company.lower() in str(it.get("company")).lower()]


def test_a_dismissed_form_never_posts_pushes_or_counts():
    items, rows = build()
    diageo = form_items(items, "Diageo")
    assert diageo, "the fixture makes a Diageo form to-do"
    key = next(r["key"] for r in rows if set(r["item_ids"]) & {it["id"] for it in diageo})
    status = [{"form_key": key, "not_for_me": True, "is_demo": False}]
    ids = forms.not_for_me_items(status, rows, ROLES)
    assert ids >= {it["id"] for it in diageo}
    items2, _ = build(ids)
    gone = form_items(items2, "Diageo")
    assert all(it["level"] == "hidden" and not posting.in_chat(it) for it in gone)                 # no message
    assert not any("Diageo" in str(it.get("title")) for it in items2 if it.get("category") == "digest" and it["level"] != "hidden")
    assert push.compose(gone, {r["id"]: r for r in ROLES}, NOW) in (None, {}, [])                    # no push
    for it in gone:
        it.setdefault("details", {})["via"] = "email"
    assert push.mail_reminders(gone, {"reminder_hours": 9}, NOW) == []                              # no reminder
    # the other company's form is untouched, and so are Diageo's roles
    assert any(it["level"] != "hidden" for it in form_items(items2, "Groww"))
    assert [r for r in ROLES if r["company"] == "Diageo"][0].get("applied") is False


def test_restoring_brings_it_back_exactly_as_before():
    before, _ = build()
    items, rows = build()
    key = next(r["key"] for r in rows if any("Diageo" in str(i) for i in r.get("companies") or [r.get("company")]))
    hidden, _ = build(forms.not_for_me_items([{"form_key": key, "not_for_me": True, "is_demo": False}], rows, ROLES))
    restored, _ = build(forms.not_for_me_items([{"form_key": key, "not_for_me": False, "is_demo": False}], rows, ROLES))
    strip = lambda its: sorted((it["id"], it["level"], it.get("title"), (it.get("details") or {}).get("hidden_because")) for it in its)
    assert strip(restored) == strip(before) != strip(hidden)


def test_a_demo_sessions_dismissals_never_touch_the_owners_feed():
    _, rows = build()
    key = rows[0]["key"]
    assert forms.not_for_me_items([{"form_key": key, "not_for_me": True, "is_demo": True}], rows, ROLES) == set()


def test_a_kind_you_said_yes_to_covers_that_companys_or_role_types_forms():
    _, rows = build()
    by_co = forms.not_for_me_items([{"form_key": "kind:company:diageo", "not_for_me": True, "is_demo": False}], rows, ROLES)
    diageo_rows = [r for r in rows if "diageo" in str(r.get("company")).lower()]
    assert diageo_rows and by_co == {i for r in diageo_rows for i in r["item_ids"]}
    assert forms.role_type("GBS MANAGEMENT TRAINEE") == "management trainee"
    assert forms.not_for_me_items([{"form_key": "asked:company:diageo", "not_for_me": False, "is_demo": False}], rows, ROLES) == set()


def test_a_today_item_with_no_form_can_be_dismissed_on_its_own():
    assert forms.not_for_me_items([{"form_key": "item:mail:m1", "not_for_me": True, "is_demo": False}], [], []) == {"mail:m1"}


def test_the_role_types_match_the_pages_list():
    import json, subprocess
    out = subprocess.run(["node", "-e", "const F=require('./dashboard/forms.js');console.log(JSON.stringify(F.ROLE_TYPES.map(([t,re])=>[t,re.source])))"],
                         capture_output=True, text=True, check=True).stdout
    page = json.loads(out)
    assert [t for t, _ in page] == [t for t, _ in forms.ROLE_TYPES]
    assert [rx.replace("\\\\", "\\") for _, rx in page] == [rx for _, rx in forms.ROLE_TYPES]
