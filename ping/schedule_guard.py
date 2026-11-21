"""Should a scheduled Ping run go ahead? Mirrors supabase/functions/kick-run/guard.ts.

Two things can start a scheduled run: Supabase's pg_cron (through the kick-run function, every 30 minutes) and
GitHub's own cron line in ping.yml, kept as a backup. Both follow the student's own schedule (profile:
check_every_minutes, check_from, check_to in IST; default every hour, 06:00-01:00): a run starts only inside those
hours, once the last run is at least (every - 10) minutes old, and never while another one is going.

    python -m ping.schedule_guard     # on GitHub: prints skip=true/false to $GITHUB_OUTPUT
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import requests

DEFAULT = {"every_minutes": 60, "from": "06:00", "to": "01:00"}
MIN_GAP_MINUTES = DEFAULT["every_minutes"] - 10
BUSY = {"queued", "in_progress", "waiting", "requested", "pending"}


def _mins(hhmm: str) -> int:
    h, m = (hhmm.split(":") + ["0"])[:2]
    return (int(h) % 24) * 60 + int(m or 0)


def in_window(now: datetime, start: str, end: str) -> bool:
    ist = now.astimezone(timezone(timedelta(hours=5, minutes=30)))
    m, f, t = ist.hour * 60 + ist.minute, _mins(start), _mins(end)
    if f == t:
        return True
    return f <= m < t if f < t else (m >= f or m < t)


def decide(runs: list[dict], now: datetime, ignore_id: int | None = None, schedule: dict | None = None) -> tuple[bool, str]:
    s = {**DEFAULT, **{k: v for k, v in (schedule or {}).items() if v is not None}}
    if not in_window(now, s["from"], s["to"]):
        return False, f"outside your hours ({s['from']}-{s['to']} IST)"
    gap = max(20, int(s["every_minutes"]) - 10)
    others = [r for r in runs if r.get("id") != ignore_id]
    busy = next((r for r in others if r.get("status") in BUSY), None)
    if busy:
        return False, f"a Ping run is {busy['status'].replace('_', ' ')} (run {busy['id']})"
    times = sorted((datetime.fromisoformat((r.get("run_started_at") or r["created_at"]).replace("Z", "+00:00"))
                    for r in others), reverse=True)
    if times and (now - times[0]).total_seconds() < gap * 60:
        return False, f"a Ping run started {round((now - times[0]).total_seconds() / 60)} min ago (every {s['every_minutes']} min)"
    return True, f"last run started {round((now - times[0]).total_seconds() / 60)} min ago" if times else "no earlier runs"


def owner_schedule() -> dict:
    url, key = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return {}
    try:
        r = requests.get(f"{url}/rest/v1/profile", timeout=20, headers={"apikey": key, "Authorization": f"Bearer {key}"},
                         params={"select": "check_every_minutes,check_from,check_to", "id": "eq.1"})
        p = (r.json() or [{}])[0] if r.status_code == 200 else {}
    except Exception:
        p = {}
    return {"every_minutes": p.get("check_every_minutes"), "from": p.get("check_from"), "to": p.get("check_to")}


def main() -> int:
    repo, token, me = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"], int(os.environ["GITHUB_RUN_ID"])
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/workflows/ping.yml/runs", params={"per_page": 10},
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=30)
    r.raise_for_status()
    start, why = decide(r.json().get("workflow_runs", []), datetime.now(timezone.utc), ignore_id=me,
                        schedule=owner_schedule())
    print(("going ahead: " if start else "standing down: ") + why)
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as out:
        out.write(f"skip={'false' if start else 'true'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
