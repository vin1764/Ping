"""Push from the run (ping/push.py): one notification per run for the most urgent new for-you message, its label
and first line, nothing for other roles only, test-day reminders, the optional email. Made-up items."""
from datetime import datetime

from ping import push
from ping.config import IST

NOW = datetime(2026, 11, 21, 13, 0, tzinfo=IST)
DIGEST_MINE = {"id": "d1", "category": "digest", "level": "show", "due_at": "2026-11-21T20:00:00+05:30",
               "title": "Reminder: 38 applications you haven't applied to close tonight, Sat 21 Nov 20:00 — 8 for you",
               "details": {"kind": "application", "role": "reminder", "list": [{"head": "For you", "rows": [{"id": "r1"}]},
                                                                                {"head": "Others (30)", "rows": [{"id": "r2"}]}]}}
DIGEST_OTHERS = {"id": "d2", "category": "digest", "level": "show", "due_at": "2026-11-22T20:00:00+05:30",
                 "title": "Reminder: 3 applications close tomorrow — 0 for you",
                 "details": {"kind": "application", "list": [{"head": "Others (3)", "rows": [{"id": "r3"}]}]}}
TEST_MINE = {"id": "t1", "company": "Groww", "category": "test", "level": "always", "event_at": "2026-11-21T15:00:00+05:30",
             "title": "Groww test (APM) Sat 21 Nov 15:00.", "details": {"kind": "test", "pdf": {"status": "yes", "details": {"room": "304"}}}}
TEST_NOT = {"id": "t2", "company": "Pine Labs", "category": "test", "level": "show", "event_at": "2026-11-21T16:00:00+05:30",
            "title": "I couldn't find your roll number in the Pine Labs test room list. Please check the list yourself.", "details": {"kind": "test_rooms", "pdf": {"status": "no"}}}


def test_for_you_or_not():
    assert push.is_for_you(DIGEST_MINE) and push.is_for_you(TEST_MINE)
    assert not push.is_for_you(DIGEST_OTHERS)          # other roles only: no push
    assert not push.is_for_you(TEST_NOT)               # a list you're not on: no push
    assert not push.is_for_you({**DIGEST_MINE, "level": "hidden"})


def test_one_push_per_run_the_most_urgent_with_the_count_of_others():
    assert push.pick([], NOW) is None
    assert push.pick([DIGEST_OTHERS, TEST_NOT], NOW) is None    # "nothing new for you": nothing sent
    it, others = push.pick([DIGEST_MINE, DIGEST_OTHERS, TEST_MINE], NOW)
    assert it["id"] == "t1" and others == 1
    p = push.payload(it, others, NOW)
    assert p == {"mode": "notify", "id": "t1", "title": "Test · today 15:00", "body": "Groww test (APM) Sat 21 Nov 15:00. (+1 more for you)",
                 "url": "./#m-t1", "tag": "t1"}
    assert push.label(DIGEST_MINE, NOW) == "Reminder · closes tonight 20:00"


def test_reminders_for_tests_you_are_on():
    rows = push.reminders([TEST_MINE, TEST_NOT, DIGEST_MINE], {"reminder_hours": 2}, NOW)
    assert rows == [{"id": "reminder:t1", "kind": "reminder", "title": "Test · today 15:00", "body": "Groww test at 15:00 · room 304",
                     "url": "./#m-t1", "tag": "reminder:t1", "event_at": "2026-11-21T15:00:00+05:30",
                     "send_at": "2026-11-21T13:00:00+05:30"}]
    # already inside the lead time: due now; a test that has started: none
    late = push.reminders([TEST_MINE], {"reminder_hours": 3}, NOW)
    assert late[0]["send_at"] == NOW.isoformat()
    assert push.reminders([TEST_MINE], {}, datetime(2026, 11, 21, 15, 5, tzinfo=IST)) == []


def test_email_digest_text():
    subject, body = push.email_text([DIGEST_MINE, TEST_MINE, DIGEST_OTHERS], NOW, "https://x.github.io/ping-dashboard/")
    assert subject == "Ping · Reminder · closes tonight 20:00 (+1 more)"
    assert "Test · today 15:00: Groww test (APM)" in body and "0 for you" not in body
    assert push.email_text([DIGEST_OTHERS], NOW, "") is None
