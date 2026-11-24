"""20 open-ended questions to the deployed ask-ping function, as a demo visitor (anonymised demo data) on the LIVE
keys, the way a visitor's questions go: Groq -> Gemini flash-lite -> rules. Not an eval (evals never use the live
Groq key): it measures each provider from the 'tried' list every answer carries (status and time of each try).

    python evals/ask_ping/live_providers.py      -> evals/ask_ping/PROVIDERS.md
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

QUESTIONS = [
    "why should I prioritise the Groww APM role?", "compare the Navi and slice roles for me",
    "which of tonight's roles fit a product person best and why?", "explain what the Accordion data role involves",
    "should I apply to Axis Bank BIU?", "give me a plan for today's deadlines",
    "what's the difference between the IDFC FIRST Bank roles?", "tips to prepare for the Groww test",
    "is the BlackBuck leadership program worth it?", "summarise this week for me in three lines",
    "which role closing tonight pays best, and why would I pick it?", "what do you think about Cars24's roles for a data person?",
    "help me decide between Eternal and Porter", "what should I do first tonight?", "why is Auro Group a fit for me?",
    "compare Moneyview's two roles", "explain the Waterfly management consultant role", "how should I prepare for HPCL's CV submission?",
    "recommend three roles for me this week", "what are the pros and cons of the Arihant Capital roles?",
]


def provider(name: str) -> str:
    return "groq" if name.startswith("groq/") else "gemini flash-lite" if "flash-lite" in name else name


def main() -> int:
    from ping.config import load_dotenv
    from ping.supabase_admin import demo_session
    load_dotenv()
    url, pub = os.environ["SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_PUBLISHABLE_KEY"]
    as_of = json.loads((HERE / "cases.json").read_text()).get("snapshot_as_of")
    tries, answered, rows = defaultdict(list), defaultdict(int), []
    hdr = None
    for i, q in enumerate(QUESTIONS):
        if i % 10 == 0:
            hdr, _ = demo_session(url, pub)          # the demo's limit is 15 questions a session
        t = time.monotonic()
        r = requests.post(f"{url}/functions/v1/ask-ping", json={"question": q, "as_of": as_of}, headers=hdr, timeout=120)
        secs = time.monotonic() - t
        j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        model = j.get("model") or f"HTTP {r.status_code}"
        for tr in j.get("tried") or []:
            parts = str(tr).split(":")
            name = parts[0]
            ok = len(parts) > 1 and parts[1] == "200"
            ms = int(parts[2][:-2]) if len(parts) > 2 and parts[2].endswith("ms") and parts[2][:-2].isdigit() else None
            tries[provider(name)].append((ok, ms))
        who = provider(model) if model not in ("rules", "jd-summary") else "rules"
        answered[who] += 1
        rows.append((q, who, round(secs, 1), j.get("tried") or [], (j.get("answer") or j.get("error") or "")[:110].replace("\n", " ")))
        time.sleep(2)
    lines = ["# Providers on the live keys", "",
             f"Run {datetime.now().astimezone():%a %d %b %H:%M %Z}: {len(QUESTIONS)} open-ended questions as a demo visitor "
             "(anonymised demo data, live keys), chain Groq -> Gemini flash-lite -> rules. A try succeeds when the provider "
             "answered (HTTP 200 with text); latency is that try's own time.", "",
             "| provider | tried | answered | success | median latency |", "|---|---|---|---|---|"]
    for p in ("groq", "gemini flash-lite"):
        ts = tries.get(p, [])
        ok = [ms for good, ms in ts if good and ms is not None]
        lines.append(f"| {p} | {len(ts)} | {sum(g for g, _ in ts)} | {f'{100 * sum(g for g, _ in ts) / len(ts):.0f}%' if ts else 'n/a'} | "
                     f"{f'{statistics.median(ok) / 1000:.1f} s' if ok else 'n/a'} |")
    lines.append(f"| rules (fallback or FACT) | - | {answered.get('rules', 0)} | - | - |")
    lines += ["", "Answered by: " + ", ".join(f"{k} {v}" for k, v in sorted(answered.items(), key=lambda kv: -kv[1])), "",
              "| question | answered by | seconds | tries | answer (start) |", "|---|---|---|---|---|"]
    lines += [f"| {q} | {w} | {s} | {', '.join(t) or '-'} | {a.replace('|', '/')} |" for q, w, s, t, a in rows]
    (HERE / "PROVIDERS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
