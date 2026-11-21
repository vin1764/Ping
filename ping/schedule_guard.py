"""Should a scheduled Ping run go ahead? Mirrors supabase/functions/kick-run/guard.ts.

Two things can start the hourly run: Supabase's pg_cron (through the kick-run function) and GitHub's own cron
line in ping.yml, kept as a backup. Whichever comes second must stand down, so: skip if another Ping run is in
progress or queued, or one started less than 50 minutes ago.

    python -m ping.schedule_guard     # on GitHub: prints skip=true/false to $GITHUB_OUTPUT
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import requests

MIN_GAP_MINUTES = 50
BUSY = {"queued", "in_progress", "waiting", "requested", "pending"}


def decide(runs: list[dict], now: datetime, ignore_id: int | None = None) -> tuple[bool, str]:
    others = [r for r in runs if r.get("id") != ignore_id]
    busy = next((r for r in others if r.get("status") in BUSY), None)
    if busy:
        return False, f"a Ping run is {busy['status'].replace('_', ' ')} (run {busy['id']})"
    times = sorted((datetime.fromisoformat((r.get("run_started_at") or r["created_at"]).replace("Z", "+00:00"))
                    for r in others), reverse=True)
    if times and (now - times[0]).total_seconds() < MIN_GAP_MINUTES * 60:
        return False, f"a Ping run started {round((now - times[0]).total_seconds() / 60)} min ago"
    return True, f"last run started {round((now - times[0]).total_seconds() / 60)} min ago" if times else "no earlier runs"


def main() -> int:
    repo, token, me = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"], int(os.environ["GITHUB_RUN_ID"])
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/workflows/ping.yml/runs", params={"per_page": 10},
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=30)
    r.raise_for_status()
    start, why = decide(r.json().get("workflow_runs", []), datetime.now(timezone.utc), ignore_id=me)
    print(("going ahead: " if start else "standing down: ") + why)
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as out:
        out.write(f"skip={'false' if start else 'true'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
