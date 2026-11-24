"""The posting guard (ping/posting.py): paused, silent re-reads, past deadlines, the same message under a new id,
one digest a run, more than 5 new messages grouped. Made-up items shaped like the 24 Nov Diageo repeats."""

from datetime import datetime, timedelta, timezone

from ping import posting
from ping.store import MemoryStore

NOW = datetime(2026, 11, 24, 23, 47, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def form(i, due="2026-11-23T20:00:00+05:30", company="Diageo", link="https://forms.gle/abc"):
    return {"id": f"notice:2026-2027:{1700 + i}:0:todo{i}", "level": "show", "category": "todo", "company": company,
            "due_at": due, "title": f"{company}: fill the form", "details": {"todo": {"action": "fill_form", "link": link}}}


FIRST = {"seed": {"id": "seed", "level": "show", "category": "update", "company": "Seed"}}   # not the first run


def run(items, previous=None, store=None, **kw):
    store = store or MemoryStore()
    previous = previous if previous is not None else dict(FIRST)
    out = posting.guard([dict(it, details=dict(it.get("details") or {})) for it in items], previous or {}, store, NOW, log=lambda *_: None, **kw)
    shown = [it for it in out if it.get("level") != "hidden" and it["id"] not in (previous or {})]
    return shown, out, store


def test_a_past_deadline_is_never_posted():
    shown, out, _ = run([form(1)])
    assert shown == [] and out[0]["details"]["hidden_because"].startswith("its time had already passed")


def test_the_same_message_under_new_ids_is_posted_once():
    later = "2026-11-25T20:00:00+05:30"
    shown, _, store = run([form(1, later)])
    assert len(shown) == 1
    # the next run: four copies of the same form under new ids (a re-read changed the ids): none posted
    prev = {**FIRST, form(1, later)["id"]: form(1, later)}
    shown2, out2, _ = run([form(1, later), form(2, later), form(3, later), form(4, later), form(5, later)], prev, store)
    assert shown2 == []
    assert sum(1 for it in out2 if "already posted" in (it["details"].get("hidden_because") or "")) == 4


def test_re_reads_are_silent():
    shown, out, _ = run([form(1, "2026-11-25T20:00:00+05:30")], silent=["re-scan"])
    assert shown == [] and "re-scan" in out[0]["details"]["hidden_because"]


def test_paused_holds_back_then_posts_once_posting_is_on():
    later = "2026-11-25T20:00:00+05:30"
    shown, out, store = run([form(1, later)], paused=True)
    assert shown == [] and out[0]["details"]["hidden_because"] == "posting paused"
    prev = {**FIRST, **{it["id"]: it for it in out}}
    out2 = posting.guard([form(1, later)], prev, store, NOW, paused=False, log=lambda *_: None)
    assert out2[0]["level"] == "show"                  # held, then posted once posting is back


def test_more_than_five_new_messages_are_one_grouped_message_and_one_digest_a_run():
    later = "2026-11-25T20:00:00+05:30"
    many = [form(i, later, company=f"Co{i}", link=f"https://forms.gle/{i}") for i in range(7)]
    shown, out, _ = run(many)
    assert len(shown) == 1 and shown[0]["id"].startswith("batch:") and "7 new updates" in shown[0]["title"]
    digests = [{"id": f"digest:{i}", "level": "show", "category": "digest", "company": None, "due_at": later,
                "title": f"digest {i}", "details": {"kind": "application"}} for i in range(3)]
    shown, _, _ = run(digests)
    assert len([it for it in shown if it["category"] == "digest"]) == 1


def test_held_back_messages_stay_held_back_on_the_next_run():
    shown, out, store = run([form(1)])                  # past: held back
    prev = {**FIRST, **{it["id"]: it for it in out}}
    again = form(1)                                     # the next run rebuilds it as visible
    out2 = posting.guard([again], prev, store, NOW, log=lambda *_: None)
    assert out2[0]["level"] == "hidden"


def test_the_first_run_builds_the_thread_with_its_history():
    shown, out, _ = run([form(1)], previous={})
    assert out[0]["level"] == "show"                  # the starting thread, not a new post


# ---- the 24 Nov Diageo case: one multi-company notice (22 Nov 23:47) gave every section a copy of one company's
# form. The copies were hidden for another reason; when their deadline passed, a later run gave them "deadline gone",
# and the page (which keeps a past message in the history when Ping posted it while it mattered) drew 7 identical cards.
NOTICE_AT = "2026-11-22T23:47:00+05:30"


def copy(section, why, due="2026-11-23T20:00:00+05:30"):
    return {"id": f"notice:2026-2027:1830:{section}:todo7", "level": "hidden", "category": "todo", "company": "Diageo",
            "due_at": due, "first_seen": "2026-11-23T00:41:00+05:30", "title": "Diageo (GBS MANAGEMENT TRAINEE): fill the form by Mon 23 Nov 20:00.",
            "details": {"notice_time": NOTICE_AT, "hidden_because": why, "todo": {"action": "fill_form", "link": "https://forms.gle/x"}}}


def test_a_message_hidden_for_another_reason_never_reappears_as_a_past_one():
    prev = {**FIRST, **{copy(s, "another company's form in the same notice")["id"]: copy(s, "another company's form in the same notice") for s in range(2, 9)}}
    now = [copy(s, "deadline gone") for s in range(2, 9)]
    assert all(posting.in_chat(it) for it in now)            # what the page would have drawn: 7 cards
    out = posting.guard(now, prev, MemoryStore(), NOW, log=lambda *_: None)
    assert not any(posting.in_chat(it) for it in out)


def test_copies_of_a_message_folded_elsewhere_are_none_and_plain_repeats_are_one():
    items = [copy(1, "in the form digest")] + [copy(s, "deadline gone") for s in range(2, 9)]
    assert posting.collapse_repeats(items) == 7 and not any(posting.in_chat(it) for it in items)
    items = [copy(s, "deadline gone") for s in range(2, 9)]
    assert posting.collapse_repeats(items) == 6 and sum(posting.in_chat(it) for it in items) == 1


def test_a_new_message_already_past_never_enters_the_history():
    # a re-scan found an old test again under a new id: hidden 'already happened', which the page would draw
    old_test = {"id": "notice:2026-2027:1350:19", "level": "hidden", "category": "test", "company": "Capital One",
                "event_at": "2026-11-02T18:00:00+05:30", "title": "Capital One test", "details": {"notice_time": "2026-11-01T21:27:00+05:30",
                "hidden_because": "already happened", "kind": "test"}}
    assert posting.in_chat(old_test)
    shown, out, _ = run([old_test])
    assert not any(posting.in_chat(it) for it in out)


def test_a_new_message_about_something_days_old_is_saved_not_posted():
    later = "2026-11-28T20:00:00+05:30"
    old = dict(form(1, later), details={"notice_time": "2026-11-20T10:00:00+05:30", "todo": {"action": "fill_form", "link": "https://forms.gle/abc"}})
    shown, out, _ = run([old])
    assert shown == [] and "older message" in out[0]["details"]["hidden_because"]
