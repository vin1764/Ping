"""Is it really new? Repeats collapse; real changes become one Update message."""

from datetime import datetime, timedelta

from ping.config import IST
from ping.dedupe import changes_since_last_run, dedupe

NOW = datetime(2026, 11, 21, 9, 0, tzinfo=IST)


def item(i, cat, company, t, due=None, event=None, venue=None, pdf=None, roles=("r1",), profiles=(), todo=None, title=None):
    return {"id": f"notice:2026:{i}:0", "level": "always", "category": cat, "company": company,
            "title": title or f"{company} {cat} {i}", "due_at": due and due.isoformat(),
            "event_at": event and event.isoformat(), "pdf_status": pdf, "role_ids": list(roles),
            "details": {"notice_time": t.isoformat(), "venue": venue, "profiles": list(profiles),
                        **({"todo": {"action": todo}} if todo else {})}}


def shown(items):
    return [i for i in items if i["level"] != "hidden"]


def test_reposted_notice_is_not_sent_again():
    t = NOW - timedelta(days=1)
    a = item(1, "test", "Eternal", t, event=NOW + timedelta(hours=5), venue="Nalanda")
    b = item(2, "test", "ETERNAL", t + timedelta(hours=2), event=NOW + timedelta(hours=5), venue="Nalanda")
    out, st = dedupe([a, b], NOW)
    assert st["duplicates_merged"] == 1 and len(shown(out)) == 1
    assert out[0]["details"]["merged"][0]["id"] == b["id"]


def test_deadline_extension_becomes_one_update():
    t = NOW - timedelta(days=2)
    a = item(1, "deadline", "Groww", t, due=NOW + timedelta(days=1))
    b = item(2, "deadline", "Groww", t + timedelta(days=1), due=NOW + timedelta(days=3))
    out, st = dedupe([a, b], NOW)
    upd = [i for i in out if ":update:" in i["id"]]
    assert st["updates"] == 1 and len(upd) == 1
    assert "deadline moved from" in upd[0]["title"]
    assert a["details"]["hidden_because"] == "updated by a later message"   # stays in the thread as 'Updated below'
    assert b["level"] == "hidden"


def test_now_shortlisted_and_venue_change_are_updates():
    t = NOW - timedelta(days=1)
    a = item(1, "test", "Pine Labs", t, event=NOW + timedelta(days=1), venue="Nalanda", pdf="no")
    b = item(2, "test", "Pine Labs", t + timedelta(hours=3), event=NOW + timedelta(days=1), venue="Vikramshila", pdf="yes")
    out, _ = dedupe([a, b], NOW)
    upd = [i for i in out if ":update:" in i["id"]][0]
    assert "venue changed to Vikramshila" in upd["title"] and "you're now on the list" in upd["title"]


def test_different_profiles_are_different_things():
    t = NOW - timedelta(days=1)
    a = item(1, "test", "Prodigal", t, event=NOW.replace(hour=2), profiles=["Applied AI"])
    b = item(2, "test", "Prodigal", t, event=NOW.replace(hour=4), profiles=["Associate Consultant"])
    out, st = dedupe([a, b], NOW)
    assert st["duplicates_merged"] == 0 and st["updates"] == 0 and len(shown(out)) == 2


def test_far_apart_in_time_is_new():
    a = item(1, "deadline", "Groww", NOW - timedelta(days=10), due=NOW - timedelta(days=9))
    b = item(2, "deadline", "Groww", NOW - timedelta(days=1), due=NOW + timedelta(days=1))
    out, st = dedupe([a, b], NOW)
    assert st["updates"] == 0 and len(shown(out)) == 2


def test_unsure_counts_as_same_with_a_note():
    t = NOW - timedelta(days=1)
    a = item(1, "test", "IQVIA", t, event=NOW + timedelta(hours=8), roles=())
    b = item(2, "test", "IQVIA", t + timedelta(hours=1), event=NOW + timedelta(hours=8))
    out, st = dedupe([a, b], NOW)
    assert st["duplicates_merged"] == 1 and st["unsure_merges"] == 1
    assert "doesn't say which role" in out[0]["details"]["merged"][0]["note"]


def test_email_repeating_a_notice_is_merged():
    t = NOW - timedelta(hours=5)
    a = item(1, "test", "Eternal", t, event=NOW + timedelta(hours=5))
    mail = {"id": "mail:1", "level": "always", "category": "email", "company": "Eternal", "title": "Eternal emailed you",
            "role_ids": [], "details": {"received_at": (t + timedelta(hours=1)).isoformat(), "links": ["https://x.test/l"]}}
    out, st = dedupe([a, mail], NOW)
    assert st["emails_merged"] == 1 and mail["level"] == "hidden"
    assert a["details"]["mail_links"] == ["https://x.test/l"]


def test_flip_flop_is_not_an_update():
    t = NOW - timedelta(days=1)
    e1, e2 = NOW.replace(hour=2), NOW.replace(hour=4)
    a = item(1, "test", "X", t, event=e1)
    b = item(2, "test", "X", t + timedelta(hours=1), event=e2)
    c = item(3, "test", "X", t + timedelta(hours=2), event=e1)
    out, st = dedupe([a, b, c], NOW)
    assert st["updates"] == 1 and st["duplicates_merged"] == 1


def test_deadline_moved_between_runs():
    prev = {"role:1:apply": {"id": "role:1:apply", "due_at": (NOW + timedelta(days=1)).isoformat()}}
    cur = [{"id": "role:1:apply", "level": "show", "category": "apply", "company": "Accordion",
            "due_at": (NOW + timedelta(days=2)).isoformat(), "details": {}}]
    upd = changes_since_last_run(prev, cur, NOW)
    assert len(upd) == 1 and "deadline moved from" in upd[0]["title"]
