"""Feedback evals against the deployed ask-ping function: the 12 live cases of evals/feedback/cases.json, in order, in
one demo session (anonymised demo data), with the model on and with it off (no_ai). Feedback is decided by rules, so
both runs must give the same answers. Also checks that a hide is saved (the session's lists, read back) and that a
reply's quoted message travels apart from the question. Uses the evals keys (never the live ones).

    python evals/feedback/run_feedback_evals.py      -> evals/feedback/REPORT.md
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))


def run(url: str, publishable: str, cases: list[dict], reply: dict, no_ai: bool, headers: dict) -> list[dict]:
    from ping.supabase_admin import demo_session
    hdr, _ = demo_session(url, publishable)
    out = []
    for c in cases:
        body = {"question": c["message"], **({"reply": reply} if c.get("reply") else {}), **({"no_ai": True} if no_ai else {})}
        t = time.monotonic()
        r = requests.post(f"{url}/functions/v1/ask-ping", json=body, headers={**hdr, **headers}, timeout=120)
        secs = time.monotonic() - t
        j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        ans, why = j.get("answer") or j.get("error") or r.text[:200], []
        w = c["want"]
        if r.status_code != 200:
            why.append(f"HTTP {r.status_code}")
        elif "line" in w:
            if not ans.startswith(w["line"]):
                why.append("wrong line")
            if w["line"].startswith("Got it") and "[Undo](#ask:undo)" not in ans:
                why.append("no Undo button")
        elif "ask" in w:
            if not ans.startswith(w["ask"]) or "#ask:" not in ans:
                why.append("no question with buttons")
            if any(x in ans.lower() for x in ("deadline", "applied", "notice", "closes")):
                why.append("a status dump")
        elif w.get("not_feedback") and (j.get("route") == "feedback" or ans.startswith("Got it")):
            why.append("taken as feedback")
        out.append({"id": c["id"], "case": c["case"], "message": c["message"], "answer": ans, "ok": not why, "why": why,
                    "model": j.get("model"), "secs": round(secs, 1)})
        if c["id"] == "L1" and r.status_code == 200:
            # saved: the session's lists, read back the way the page reads them
            m = requests.post(f"{url}/functions/v1/ask-ping", json={"marks": True}, headers={**hdr, **headers}, timeout=60).json()
            saved = "Navi Limited" in ((m.get("lists") or {}).get("not_interested_companies") or [])
            out[-1]["saved"] = saved
            if not saved:
                out[-1]["ok"] = False
                out[-1]["why"].append("not saved")
    return out


def main() -> int:
    from ping.config import load_dotenv
    load_dotenv()
    from ping.evals_key import eval_headers
    url = os.environ["SUPABASE_URL"].rstrip("/")
    pub = os.environ["SUPABASE_PUBLISHABLE_KEY"]
    spec = json.loads((HERE / "cases.json").read_text())
    headers = eval_headers()
    on = run(url, pub, spec["live"], spec["live_reply"], False, headers)
    off = run(url, pub, spec["live"], spec["live_reply"], True, headers)
    same = sum(a["answer"] == b["answer"] for a, b in zip(on, off))
    lines = ["# Feedback evals", "",
             f"Run {datetime.now().astimezone():%a %d %b %H:%M %Z} against the deployed `ask-ping` function, one demo session per "
             "run (anonymised demo data), the evals keys. Feedback is decided by rules, never by a model.", "",
             f"- **Model on: {sum(r['ok'] for r in on)}/{len(on)}. Model off (no_ai): {sum(r['ok'] for r in off)}/{len(off)}.** "
             f"Same answer both ways: {same}/{len(on)}.",
             f"- The hide is saved (read back from the session's lists): {'yes' if on[0].get('saved') else 'NO'} (model on), "
             f"{'yes' if off[0].get('saved') else 'NO'} (model off).", "",
             "| case | message | model on | model off | answer (model on) |", "|---|---|---|---|---|"]
    for a, b in zip(on, off):
        res = lambda r: "ok" if r["ok"] else "FAIL: " + "; ".join(r["why"])  # noqa: E731
        lines.append(f"| {a['id']} {a['case']} | `{a['message']}` | {res(a)} | {res(b)} | {a['answer'][:140].replace('|', '/')} |")
    (HERE / "REPORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if all(r["ok"] for r in on + off) else 1


if __name__ == "__main__":
    sys.exit(main())
