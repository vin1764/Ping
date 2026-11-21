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
