"""The hourly-run guard (same rule as supabase/functions/kick-run/guard.ts): never two runs within 50 minutes."""

from datetime import datetime, timedelta, timezone

from ping.schedule_guard import decide

NOW = datetime(2026, 11, 21, 13, 41, tzinfo=timezone.utc)


def run(i, status, mins_ago):
    return {"id": i, "status": status, "created_at": (NOW - timedelta(minutes=mins_ago)).isoformat()}


def test_starts_after_50_minutes():
    assert decide([run(1, "completed", 60)], NOW)[0]


def test_skips_a_recent_or_running_run():
    assert not decide([run(1, "completed", 20)], NOW)[0]
    assert not decide([run(1, "in_progress", 90)], NOW)[0]
    assert not decide([run(2, "queued", 1)], NOW)[0]


def test_ignores_itself():
    assert decide([run(7, "in_progress", 0), run(1, "completed", 61)], NOW, ignore_id=7)[0]


def test_the_students_own_schedule_decides():
    from datetime import timedelta, timezone as tz
    from ping.schedule_guard import decide
    ist = tz(timedelta(hours=5, minutes=30))
    t = datetime(2026, 11, 21, 10, 11, tzinfo=ist)
    done = lambda mins: [{"id": 1, "status": "completed", "created_at": (t - timedelta(minutes=mins)).isoformat()}]
    assert decide(done(30), t, schedule={"every_minutes": 30})[0]
    assert not decide(done(30), t, schedule={"every_minutes": 60})[0]
    assert not decide(done(60), t, schedule={"every_minutes": 120})[0]
    assert decide(done(120), t, schedule={"every_minutes": 120})[0]
    assert not decide([], datetime(2026, 11, 21, 7, 41, tzinfo=ist), schedule={"from": "08:00", "to": "22:00"})[0]
    assert decide([], datetime(2026, 11, 21, 0, 41, tzinfo=ist), schedule={"from": "06:00", "to": "01:00"})[0]
    assert not decide([], datetime(2026, 11, 21, 3, 11, tzinfo=ist), schedule={"from": "06:00", "to": "01:00"})[0]
