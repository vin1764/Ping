"""Tasks with a deadline (ping/items.py, ping/mail_source.py): the 24 Nov BlueStone case, made up in the same shape.
A Placecom mail '[URGENT] | BLUESTONE | ASSIGNMENT SUBMISSION' (17:47) with the brief's link and 'submit by 27 Nov
23:59'; the ERP notice saying the same appeared on the notice board hours later, with no link."""

from datetime import datetime, timedelta

from ping import mail_source, posting
from ping.config import IST
from ping.items import build_items

NOW = datetime(2026, 11, 24, 18, 11, tzinfo=IST)
DUE = "2026-11-27T23:59:00+05:30"
LINK = "https://drive.example.com/bluestone-assignment-brief"
ROLES = [{"id": "b1", "company": "BLUESTONE", "designation": "Management Trainee (Marketing)", "applied": True,
          "apply_end": "2026-11-23T20:00:00+05:30", "first_seen": "2026-11-22T11:41:00+05:30", "erp_messages": [],
          "allowed": [{"degree": "B.TECH", "department": "X"}]}]
PROFILE = {"roll": "22XY10042", "cgpa": 8.0, "department": "X", "degree": "B.TECH"}
MAIL = {"id": "m-bluestone", "received_at": "2026-11-24T17:47:00+05:30", "sender": "Placecom_IIT Kharagpur <placecom@inst.example>",
        "subject": "[URGENT] | BLUESTONE | ASSIGNMENT SUBMISSION", "snippet": "Assignment · BLUESTONE · 2026-11-27 23:59",
        "company": "BLUESTONE", "links": [LINK], "kind": "assignment", "main_link": LINK, "due_at": DUE, "event_at": None,
        "when_text": "by 27 Nov 23:59", "pdf": None, "kept_because": "placement_office", "rules_version": 3,
        "source": "mail from BLUESTONE"}
NOTICE = {"id": "2026-2027:1872", "notice_id": 1872, "year": "2026-2027", "company": "BLUESTONE", "subject": "Urgent",
          "notice_time": "2026-11-24T17:49:00+05:30", "type": "PLACEMENT",
          "text": "All students who are eligible and have applied for the Management Trainee (Marketing) role must submit the assignment by 27 Nov 23:59.",
          "analysis": {"kind": "info", "todos": [{"action": "submit", "due": DUE}],
                       "targets": [{"name": "BLUESTONE", "company": "BLUESTONE", "profiles": [], "score": 1.0}]}}


def test_the_mail_is_an_assignment():
    assert mail_source.classify(MAIL["subject"], "Please submit the assignment by 27 Nov.", [LINK], False) == "assignment"


def test_a_mail_only_assignment_is_a_todo_with_its_link_and_is_posted():
    items = build_items(ROLES, [], {}, PROFILE, NOW, [MAIL])
    it = next(i for i in items if i["id"] == "mail:m-bluestone")
    assert it["category"] == "todo" and it["due_at"] == DUE and it["level"] != "hidden"
    assert it["details"]["todo"] == {"action": "submit", "task": "assignment", "due": DUE, "link": LINK}
    assert it["details"]["source"] == "mail from BLUESTONE" and "submit the assignment" in it["title"]
    assert posting.in_chat(it)
    shown, = [x for x in posting.guard([dict(it)], {"seed": {"id": "seed", "level": "show"}}, _Store(), NOW, log=lambda *_: None)
              if x["id"] == it["id"]]
    assert shown["level"] != "hidden"                                   # new, not past: posted


def test_the_notice_saying_the_same_gets_the_mails_link_and_type():
    items = build_items(ROLES, [NOTICE], {}, PROFILE, NOW + timedelta(hours=6), [MAIL])
    todo = next(i for i in items if i["id"] == "notice:2026-2027:1872:0:todo0")
    assert todo["details"]["todo"]["link"] == LINK and todo["details"]["todo"]["task"] == "assignment"
    assert "submit the assignment" in todo["title"] and todo["level"] == "always"   # applied: never "Others"
    assert not any(i["id"] == "mail:m-bluestone" for i in items)        # one message, not two


class _Store:
    def __init__(self):
        self.s = {}

    def get_state(self, k, default=None):
        return self.s.get(k, default)

    def set_state(self, k, v):
        self.s[k] = v


def test_an_assignment_is_pushed_and_the_push_opens_its_message():
    from ping import push
    it = next(i for i in build_items(ROLES, [], {}, PROFILE, NOW, [MAIL]) if i["id"] == "mail:m-bluestone")
    note = push.compose([it], {r["id"]: r for r in ROLES}, NOW)
    assert note and "Submit the assignment by" in note["title"] and note["url"] == "./#m-mail%3Am-bluestone"


def test_a_push_held_back_by_quiet_hours_is_queued_for_the_check_window():
    from datetime import datetime, timezone
    from ping.push import window_start
    at = window_start(datetime(2026, 11, 24, 20, 47, tzinfo=timezone.utc), None)          # 02:17 IST, window 06:00
    assert at.isoformat() == "2026-11-25T06:00:00+05:30"
    at = window_start(datetime(2026, 11, 25, 1, 0, tzinfo=timezone.utc), "07:30")         # 06:30 IST: later today
    assert at.isoformat() == "2026-11-25T07:30:00+05:30"
    at = window_start(datetime(2026, 11, 25, 3, 0, tzinfo=timezone.utc), "07:30")         # 08:30 IST: tomorrow
    assert at.isoformat() == "2026-11-26T07:30:00+05:30"


# ---------------------------------------------------------------- 25 Nov: a re-scan's future to-do gets a card + reminder
def _guarded(items, previous, store, now, **kw):
    return posting.guard(items, previous, store, now, log=lambda *_: None, **kw)


def test_a_rescan_finds_a_future_assignment_one_card_and_a_reminder_that_opens_it():
    from ping import push
    from ping.store import MemoryStore
    store = MemoryStore()
    store.set_state("posted_keys", ["seed"])
    prev = {"seed": {"id": "seed", "level": "show", "category": "update"}}
    items = _guarded(build_items(ROLES, [], {}, PROFILE, NOW, [MAIL]), prev, store, NOW, silent=["mail rules re-read"])
    card = next(i for i in items if i["id"] == "mail:m-bluestone")
    assert card["level"] != "hidden" and posting.in_chat(card)                     # one card, even in a silent run
    assert card["details"]["posted_at"] == NOW.isoformat()                         # drawn now, at the bottom
    # its reminder (2 h before) opens that card
    later = datetime(2026, 11, 27, 21, 0, tzinfo=IST)
    rows, first = push.with_cards(push.mail_reminders(items, PROFILE, NOW), items, NOW)
    assert first == [] and [r["url"] for r in rows if r["id"] == "reminder:mail:m-bluestone"] == ["./#m-mail%3Am-bluestone"]
    # the next run (a re-scan again): the same card, not posted twice
    prev2 = {it["id"]: it for it in items}
    again = _guarded(build_items(ROLES, [], {}, PROFILE, later - timedelta(hours=60), [MAIL]), prev2, store,
                     later - timedelta(hours=60), silent=["re-scan"])
    assert sum(1 for i in again if i["id"] == "mail:m-bluestone" and i["level"] != "hidden") == 1


def test_a_rescan_stays_silent_for_a_past_or_an_already_announced_todo():
    from ping import push
    from ping.store import MemoryStore
    prev = {"seed": {"id": "seed", "level": "show", "category": "update"}}
    # past: its deadline went before Ping found it
    store = MemoryStore()
    store.set_state("posted_keys", ["seed"])
    after = datetime(2026, 11, 28, 9, 0, tzinfo=IST)
    items = _guarded(build_items(ROLES, [], {}, PROFILE, after, [MAIL]), prev, store, after, silent=["re-scan"])
    assert all(not posting.in_chat(i) or i.get("level") == "hidden" for i in items if i["id"] == "mail:m-bluestone")
    assert push.with_cards(push.mail_reminders(items, PROFILE, after), items, after)[0] == []
    # already announced (its company, task, deadline and link posted before)
    store = MemoryStore()
    first = build_items(ROLES, [], {}, PROFILE, NOW, [MAIL])
    store.set_state("posted_keys", [posting.post_key(next(i for i in first if i["id"] == "mail:m-bluestone"))])
    items = _guarded(first, prev, store, NOW, silent=["re-scan"])
    it = next(i for i in items if i["id"] == "mail:m-bluestone")
    assert it["level"] == "hidden" and "re-scan" in it["details"]["hidden_because"]


def test_a_reminder_without_a_card_gets_one_first_and_one_you_hid_gets_none():
    from ping import push
    base = {"category": "todo", "company": "Acme", "due_at": DUE, "details": {"via": "email", "todo": {"action": "submit", "link": "x"}}}
    rows = [{"id": "reminder:a", "url": "./#m-a"}, {"id": "reminder:b", "url": "./#m-b"}, {"id": "reminder:c", "url": "./#m-c"}]
    items = [{**base, "id": "a", "level": "hidden", "details": {**base["details"], "hidden_because": "an older message found again: saved, not posted"}},
             {**base, "id": "b", "level": "hidden", "details": {**base["details"], "hidden_because": "marked not interested"}},
             {**base, "id": "c", "level": "hidden", "details": {**base["details"], "hidden_because": "grouped into one message", "grouped_in": "batch:1"}}]
    keep, first = push.with_cards(rows, items, NOW)
    assert [i["id"] for i in first] == ["a"]                                  # its card is posted first
    assert {r["id"]: r["url"] for r in keep} == {"reminder:a": "./#m-a", "reminder:c": "./#m-batch%3A1"}   # b: you hid it
