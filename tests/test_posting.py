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


def test_re_reads_are_silent_for_past_and_already_announced_but_a_new_future_todo_gets_its_card():
    later = "2026-11-25T20:00:00+05:30"
    # a future to-do you've never been shown, found by a re-scan: one card, drawn now (25 Nov: RISA Labs, BlueStone)
    shown, out, store = run([form(1, later)], silent=["re-scan"])
    assert [it["id"] for it in shown] == [form(1)["id"]] and out[0]["details"]["posted_at"] == NOW.isoformat()
    # past: silent
    shown, out, _ = run([form(2)], silent=["re-scan"])
    assert shown == [] and out[0]["level"] == "hidden"
    # already announced (same company, task, deadline and link under a new id): silent
    prev = {**FIRST, form(1, later)["id"]: dict(form(1, later), details={**form(1, later)["details"], "posted_at": NOW.isoformat()})}
    shown, out, _ = run([form(1, later), form(3, later)], prev, store, silent=["re-scan"])
    assert shown == [] and "re-scan" in out[1]["details"]["hidden_because"]
    # not a to-do (a notice update) found by a re-scan: silent
    info = {"id": "notice:2026-2027:1799:0", "level": "show", "category": "update", "company": "Diageo", "title": "Diageo update",
            "details": {"notice_time": "2026-11-24T22:00:00+05:30"}}
    shown, out, _ = run([info], silent=["re-scan"])
    assert shown == []


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
    assert len(shown) == 1 and shown[0]["id"].startswith("batch:") and shown[0]["title"] == "Co0, Co1 +5 more — see Today"
    assert len(shown[0]["details"]["list"][0]["rows"]) == 7          # the items themselves, never only a count
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


def test_a_new_message_about_something_days_old_is_saved_not_posted_unless_its_a_future_todo():
    later = "2026-11-28T20:00:00+05:30"
    # a notice update days old, found again: saved, not posted
    info = {"id": "notice:2026-2027:1798:0", "level": "show", "category": "update", "company": "Diageo", "title": "Diageo update",
            "details": {"notice_time": "2026-11-20T10:00:00+05:30"}}
    shown, out, _ = run([info])
    assert shown == [] and "older message" in out[0]["details"]["hidden_because"]
    # a form still open, from a notice days old, never shown: its card, at the bottom (posted now, not 20 Nov)
    old = dict(form(1, later), details={"notice_time": "2026-11-20T10:00:00+05:30", "todo": {"action": "fill_form", "link": "https://forms.gle/abc"}})
    shown, out, _ = run([old])
    assert len(shown) == 1 and posting.chat_time(shown[0]) == NOW.isoformat()


def test_a_future_todo_held_back_by_an_earlier_run_is_posted_on_the_next_one_and_only_once():
    later = "2026-11-27T23:59:00+05:30"
    a = dict(form(1, later, company="RISA Labs", link="https://forms.gle/risa"), details={"todo": {"action": "submit", "link": "https://forms.gle/risa"}, "notice_time": "2026-11-24T17:49:00+05:30"})
    store = MemoryStore()
    # the earlier, old-rule run held it back (a re-read): hidden, in silenced_ids
    store.set_state("posted_keys", ["seed"])
    store.set_state("silenced_ids", [a["id"]])
    prev = {**FIRST, a["id"]: dict(a, level="hidden", details={**a["details"], "hidden_because": "found by a mail rules re-read: saved, not posted"})}
    shown, out, store = run([a], prev, store)
    got = next(it for it in out if it["id"] == a["id"])
    assert got["level"] == "show" and got["details"]["posted_at"] == NOW.isoformat()
    # the run after: it stays (not posted again, not hidden)
    prev2 = {**FIRST, **{it["id"]: it for it in out}}
    out2 = posting.guard([dict(a, details=dict(a["details"]))], prev2, store, NOW + timedelta(hours=1), log=lambda *_: None)
    assert out2[0]["level"] == "show" and a["id"] not in (store.get_state("silenced_ids") or [])
    # a past one held back stays held back
    b = dict(form(2, "2026-11-20T20:00:00+05:30"), details={"todo": {"action": "fill_form", "link": "x"}})
    store.set_state("silenced_ids", [b["id"]])
    out3 = posting.guard([dict(b, details=dict(b["details"]))], {**FIRST, b["id"]: dict(b, level="hidden")}, store, NOW, log=lambda *_: None)
    assert out3[0]["level"] == "hidden"


def test_more_than_five_rescued_todos_are_one_grouped_message_and_their_reminders_open_it():
    later = "2026-11-27T23:59:00+05:30"
    many = [form(i, later, company=f"Co{i}", link=f"https://forms.gle/{i}") for i in range(7)]
    store = MemoryStore()
    store.set_state("posted_keys", ["seed"])
    store.set_state("silenced_ids", [it["id"] for it in many])
    prev = {**FIRST, **{it["id"]: dict(it, level="hidden") for it in many}}
    shown, out, store = run(many, prev, store)
    batch = [it for it in out if it["id"].startswith("batch:")]
    assert len(batch) == 1 and all(it["details"].get("grouped_in") == batch[0]["id"] for it in out if it["id"] in {m["id"] for m in many})
    # the next run doesn't post them one by one
    out2 = posting.guard([dict(m, details=dict(m["details"])) for m in many], {**FIRST, **{it["id"]: it for it in out}}, store,
                         NOW + timedelta(hours=1), log=lambda *_: None)
    assert all(it["level"] == "hidden" for it in out2 if not it["id"].startswith("batch:"))


def test_a_which_company_question_is_never_a_repeat():
    q = lambda n: {"id": f"notice:2026-2027:{n}:unsure0", "level": "show", "category": "review", "needs_review": True, "company": None,
                   "title": 'A cv submission notice says "DELOITTE". Which company is that?', "details": {}}
    items = [q(1705), q(1870)]
    assert posting.collapse_repeats(items) == 0
