"""Deadline digests: one message per batch, one reminder, updates instead of repeats.

Each test runs the feed builder the way the hourly runs do: the items of the last run (with the first_seen the
database gave them) are passed back in as `previous`.
"""

from datetime import datetime, timedelta

from ping.config import IST
from ping.items import build_items

PROFILE = {"roll": "22XY10042", "name": "Demo Student", "cgpa": 8.0, "department": "COMPUTER SCIENCE AND ENGINEERING",
           "degree": "B.TECH"}
T0 = datetime(2026, 11, 14, 9, 41, tzinfo=IST)          # when Ping first saw the roles (its own message then)
DUE = datetime(2026, 11, 21, 20, 0, tzinfo=IST)


def role(i, company, due=DUE, applied=False, seen=T0):
    return {"id": f"r{i}", "company": company, "designation": f"Role {i}", "applied": applied,
            "apply_end": due.isoformat(), "first_seen": seen.isoformat(), "erp_messages": [],
            "allowed": [{"degree": "B.TECH", "department": "COMPUTER SCIENCE AND ENGINEERING"}]}


def run(roles, now, previous=None, profile=None):
    items = build_items(roles, [], {}, {**PROFILE, **(profile or {})}, now, previous=previous or {})
    for it in items:   # what the database keeps: first_seen from the run that first wrote the row
        it["first_seen"] = (previous or {}).get(it["id"], {}).get("first_seen") or it.get("first_seen") or now.isoformat()
    return {it["id"]: it for it in items}


def visible(items):
    return {k: v for k, v in items.items() if v["level"] != "hidden" and v["category"] not in ("apply", "reminder")}


def hourly(roles, start, end, profile=None, previous=None):
    """Every hourly run from start to end; returns the final items and the messages each run added."""
    prev, sent = previous or {}, []
    t = start
    while t <= end:
        cur = run(roles, t, prev, profile)
        new = sorted(k for k in visible(cur) if k not in visible(prev) and k not in prev)
        sent.append((t, new))
        prev = cur
        t += timedelta(hours=1)
    return prev, sent


def test_same_deadline_becomes_one_digest():
    roles = [role(1, "Alpha"), role(2, "Beta"), role(3, "Gamma", applied=True),
             role(4, "Delta", due=DUE + timedelta(days=3))]
    now = DUE - timedelta(hours=20)
    items = run(roles, now)
    digests = [v for v in visible(items).values() if v["category"] == "digest"]
    assert len(digests) == 1, [d["title"] for d in digests]
    d = digests[0]
    assert d["title"].startswith("3 applications close tomorrow, Sat 21 Nov 20:00 — you've applied to 1 of them")
    rows = [r["text"] for g in d["details"]["list"] for r in g["rows"]]
    assert rows == ["Alpha — Role 1", "Beta — Role 2", "Gamma — Role 3"]
    # this check is 4 hours late for it (the batch came within 24 hours at Fri 20:00): the digest is dated then
    assert d["details"]["source"] == "ERP check 20:00 · companies list"
    assert d["first_seen"] == (DUE - timedelta(hours=24)).isoformat()
    # no per-role "Reminder: X closes" cards left
    assert not [v for v in items.values() if v["category"] == "reminder" and v["level"] != "hidden"]
    assert all(items[f"role:r{i}:apply"]["level"] == "hidden" for i in (1, 2, 4))
    # Delta closes in 3+ days: no digest yet
    assert not any("Delta" in str(v["details"].get("list")) for v in digests)


def test_digest_once_reminder_once_nothing_else():
    roles = [role(1, "Alpha"), role(2, "Beta")]
    final, sent = hourly(roles, DUE - timedelta(hours=30), DUE + timedelta(hours=2))
    messages = [(t, ids) for t, ids in sent if ids]
    assert [ids for _, ids in messages] == [["digest:application:20261121T2000"],
                                           ["digest:application:20261121T2000:reminder"]]
    # the digest when the batch came within 24 hours, the reminder 2 hours before it closes
    assert DUE - timedelta(hours=24) <= messages[0][0] < DUE - timedelta(hours=23)
    assert DUE - timedelta(hours=2) <= messages[1][0] < DUE - timedelta(hours=1)
    rem = final["digest:application:20261121T2000:reminder"]
    assert rem["title"] == "Reminder: 2 applications you haven't applied to close tonight, Sat 21 Nov 20:00"
    # after the deadline both stay in the history, marked as past
    assert final["digest:application:20261121T2000"]["details"]["hidden_because"] == "deadline gone"


def test_reminder_lists_only_unapplied_and_follows_the_profile_setting():
    roles = [role(1, "Alpha"), role(2, "Beta")]
    prev, _ = hourly(roles, DUE - timedelta(hours=30), DUE - timedelta(hours=10), profile={"reminder_hours": 5})
    roles[1]["applied"] = True
    final, sent = hourly(roles, DUE - timedelta(hours=9), DUE - timedelta(minutes=30), profile={"reminder_hours": 5},
                         previous=prev)
    when = [t for t, ids in sent if "digest:application:20261121T2000:reminder" in ids]
    assert len(when) == 1 and DUE - timedelta(hours=5) <= when[0] < DUE - timedelta(hours=4)
    rem = final["digest:application:20261121T2000:reminder"]
    assert [r["text"] for g in rem["details"]["list"] for r in g["rows"]] == ["Alpha — Role 1"]
    assert rem["title"].startswith("Reminder: 1 application you haven't applied to closes tonight")


def test_no_reminder_when_everything_is_applied():
    roles = [role(1, "Alpha", applied=True), role(2, "Beta", applied=True)]
    final, sent = hourly(roles, DUE - timedelta(hours=26), DUE - timedelta(minutes=30))
    assert not any(ids for _, ids in sent)


def test_batch_change_is_one_update_not_a_new_digest():
    roles = [role(1, "Alpha"), role(2, "Beta")]
    prev, _ = hourly(roles, DUE - timedelta(hours=23), DUE - timedelta(hours=21))
    # a notice extends Beta's deadline to Monday; a role that was due earlier now closes with Alpha
    later = DUE + timedelta(days=2)
    roles[1]["apply_end"] = later.isoformat()
    roles.append(role(3, "Gamma", due=DUE - timedelta(days=1)))
    prev2, sent = hourly(roles, DUE - timedelta(hours=20), DUE - timedelta(hours=18), previous=prev)
    roles[2]["apply_end"] = DUE.isoformat()
    final, sent2 = hourly(roles, DUE - timedelta(hours=17), DUE - timedelta(hours=15), previous=prev2)
    new = [ids for _, ids in sent + sent2 if ids]
    flat = [i for ids in new for i in ids]
    # Beta's move: one "update" for the old batch, no full digest for the new one
    moved = [i for i in flat if ":moved:" in i]
    assert len(moved) == 1
    assert final[moved[0]]["title"].startswith("Update: 1 application that closed Sat 21 Nov 20:00 now closes Mon 23 Nov 20:00")
    assert final["digest:application:20261123T2000"]["level"] == "hidden"
    # Gamma joining Alpha's batch: one update, sent once
    upd = [i for i in flat if ":upd:" in i]
    assert len(upd) == 1 and final[upd[0]]["title"].startswith("Update: 1 more application now closes")
    # and nothing more after that
    _, sent3 = hourly(roles, DUE - timedelta(hours=14), DUE - timedelta(hours=12), previous=final)
    assert not any(ids for _, ids in sent3)


def test_new_roles_of_one_run_are_one_message():
    seen = DUE - timedelta(days=2)
    roles = [role(1, "Alpha", seen=seen), role(2, "Beta", seen=seen), role(3, "Beta", seen=seen,
                                                                        due=DUE + timedelta(days=1))]
    items = run(roles, seen + timedelta(minutes=5))
    msgs = visible(items)
    assert list(msgs) == ["listing:20261119T2000"]
    m = msgs["listing:20261119T2000"]
    assert m["title"] == "3 new roles listed at 2 companies; the first closes Sat 21 Nov 20:00."
    assert [g["head"] for g in m["details"]["list"]] == ["Close Sat 21 Nov 20:00", "Close Sun 22 Nov 20:00"]
    # when the batch then comes within 24 hours, its digest says it once more; listed in the same run -> no digest
    roles2 = [role(4, "Epsilon", seen=DUE - timedelta(hours=10)), role(5, "Zeta", seen=DUE - timedelta(hours=10))]
    items2 = run(roles2, DUE - timedelta(hours=10) + timedelta(minutes=5))
    assert [k for k in visible(items2)] == ["listing:20261121T1000"]


def test_eligibility_note_counts_only_roles_without_criteria():
    roles = [role(1, "Alpha"), role(2, "Beta"), role(3, "Gamma")]
    roles[2].pop("allowed")                                   # the ERP hasn't given Gamma's criteria yet
    roles[2]["details_fetched"] = False
    for r in roles[:2]:
        r["details_fetched"] = True
    items = run(roles, DUE - timedelta(hours=20))
    d = [v for v in visible(items).values() if v["category"] == "digest"][0]
    assert d["details"]["note"] == "Eligibility not verified for Gamma Role 3 (the ERP gives no criteria yet)."
    # a profile without department/degree: one line, no count
    items2 = run(roles[:2], DUE - timedelta(hours=20), profile={"department": None, "degree": None})
    d2 = [v for v in visible(items2).values() if v["category"] == "digest"][0]
    assert d2["details"]["note"] == "Add your degree and department on the Profile page to check eligibility."
