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
    assert "more for you" not in push.payload(it, others, NOW)["body"]          # the '+N more for you' suffix is gone
    assert push.label(DIGEST_MINE, NOW) == "Reminder · closes tonight 20:00"


def test_reminders_for_tests_you_are_on():
    rows = push.reminders([TEST_MINE, TEST_NOT, DIGEST_MINE], {"reminder_hours": 2}, NOW)
    assert rows == [{"id": "reminder:t1", "kind": "reminder", "title": "Groww · Test at 15:00 · Room 304", "body": "APM",
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


# ---------------------------------------------------------------- 23 Nov: who and what to do, never "Others"
ROLES = {"r1": {"id": "r1", "company": "ZS ASSOCIATES INDIA PRIVATE LIMITED", "designation": "Business Analyst",
                "effective_deadline": "2026-11-22T20:00:00+05:30", "relevance": {"best_cv": "Consulting CV"}},
         "r2": {"id": "r2", "company": "Other Co", "designation": "SDE", "effective_deadline": "2026-11-22T20:00:00+05:30"},
         "r3": {"id": "r3", "company": "BLUESTONE", "designation": "APM", "effective_deadline": "2026-11-25T20:00:00+05:30",
                "relevance": {"best_cv": "Product CV"}},
         "r4": {"id": "r4", "company": "Meesho", "designation": "PM", "effective_deadline": "2026-11-26T14:00:00+05:30"}}
APPLY = {"id": "d9", "category": "digest", "level": "show", "due_at": "2026-11-22T20:00:00+05:30", "title": "x",
         "details": {"kind": "application", "list": [{"head": "For you", "rows": [{"id": "r1", "text": "ZS — BA", "cv": "Consulting CV"}]},
                                                     {"head": "Others (1)", "collapsed": True, "rows": [{"id": "r2", "text": "Other Co — SDE"}]}]}}
NEW = {"id": "l1", "category": "listing", "level": "show", "title": "x",
       "details": {"kind": "listing", "list": [{"head": "For you", "rows": [{"id": "r3", "text": "BLUESTONE — APM"}]}]}}
FORM = {"id": "f1", "category": "todo", "level": "show", "company": "Piramal Finance", "due_at": "2026-11-21T20:00:00+05:30",
        "title": "Piramal Finance: fill the form by 20:00.", "details": {"todo": {"action": "fill_form"}, "form": {"key": "k1", "filled": False}}}
MOVED = {"id": "a4:update:202611261400", "category": "apply", "level": "show", "company": "Meesho", "role_ids": ["r4"],
         "due_at": "2026-11-26T14:00:00+05:30", "title": "Update - Meesho: deadline moved", "details": {}}
SHORT = {"id": "s1", "category": "shortlist", "level": "always", "company": "FirstClub", "role_ids": [], "pdf_status": "yes",
         "title": "You're on the FirstClub shortlist (Product Management).", "details": {"kind": "shortlist", "pdf": {"status": "yes"}}}


def c(items, roles=ROLES, now=NOW):
    return push.compose(items, roles, now)


def test_titles_say_who_and_what_to_do():
    p = c([APPLY])
    assert (p["title"], p["body"]) == ("ZS Associates India · Apply by tomorrow 20:00", "Business Analyst · Apply with Consulting CV · in 1 day")
    assert "Other" not in p["title"] + p["body"] and p["url"].startswith("./#sheet/apply/")
    assert (c([FORM])["title"], c([FORM])["body"]) == ("Piramal Finance · Fill form by 20:00", "in 7 h")
    assert c([FORM])["url"].startswith("./#sheet/form/")
    assert c([{**FORM, "details": {**FORM["details"], "form": {"key": "k1", "filled": True}}}]) is None     # ticked: nothing
    assert c([MOVED])["title"] == "Meesho · Deadline extended to Thu 14:00"
    assert c([MOVED], {**ROLES, "r4": {**ROLES["r4"], "applied": True}}) is None                       # applied: nothing
    assert c([TEST_MINE])["title"] == "Groww · Test at 15:00 · Room 304" and c([TEST_MINE])["url"] == "./#m-t1"
    assert (c([SHORT])["title"], c([SHORT])["body"]) == ("FirstClub · You're on the shortlist", "Product Management")
    assert c([NEW])["title"] == "Bluestone · New role for you: APM"
    assert c([DIGEST_OTHERS]) is None                                  # other roles only: no notification


def test_same_deadline_grouped_and_capped():
    roles = {f"g{i}": {"id": f"g{i}", "company": f"Co {i}", "designation": "Analyst", "effective_deadline": "2026-11-22T20:00:00+05:30"}
             for i in range(5)}

    def dig(n):
        return {**APPLY, "details": {"kind": "application", "list": [{"head": "For you", "rows": [{"id": f"g{i}", "text": "x"} for i in range(n)]}]}}
    two = c([dig(2)], roles)
    assert two["title"] == "2 to apply by tomorrow 20:00" and two["body"].split("\n")[:2] == ["Co 0 — Analyst", "Co 1 — Analyst"]
    five = c([dig(5)], roles)
    assert five["title"] == "5 to apply by tomorrow 20:00" and five["body"].split("\n")[3] == "and 2 more"
    assert "more for you" not in five["body"]


def test_display_names():
    assert push.display_name("Auro Group(www.AuroIM.com)") == "Auro Group"
    assert push.display_name("ICICI LOMBARD GENERAL INSURANCE") == "ICICI Lombard General Insurance"
    assert push.display_name("BLUESTONE") == "Bluestone"
