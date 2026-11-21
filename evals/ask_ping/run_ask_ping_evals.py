"""Ask Ping evals: ask the deployed ask-ping function every question in cases.json, exactly as the dashboard
does (signed in as the reviewer login, which sees the anonymised demo), with the snapshot time fixed so
"today" and "tomorrow" never move. Score the deterministic checks and write REPORT.md.

Run it:
  - on GitHub: Actions > Admin > ask-ping-evals (type the reviewer password), or
  - locally:   SUPABASE_URL=... SUPABASE_PUBLISHABLE_KEY=... REVIEWER_EMAIL=... REVIEWER_PASSWORD=... \
               python evals/ask_ping/run_ask_ping_evals.py
               (a .env file with those names works too)

Checks never call a model: must_contain / must_not_contain (case-insensitive; 'a|b' = either),
numbers_present (2800000 = 28,00,000 = 28 L = 28 LPA ...), max_words.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

UNITS = {"l": 1e5, "lpa": 1e5, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "cr": 1e7, "crore": 1e7,
         "crores": 1e7, "k": 1e3}
NUM_RE = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(lpa|lakhs?|lacs?|crores?|cr|l|k)?(?![a-z])", re.I)


def norm(text: str) -> str:
    text = text.replace("**", "").replace("`", "").replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def numbers_in(text: str) -> list[float]:
    out = []
    for m in NUM_RE.finditer(text):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        out.append(v * UNITS.get(unit, 1))
    return out


def has_number(text: str, expected: str) -> bool:
    want = float(expected)
    for v in numbers_in(text):
        if want >= 1e5:
            if abs(v - want) <= want * 0.005:
                return True
        elif abs(v - want) < 1e-9:
            return True
    return False


def score(answer: str, checks: dict) -> list[str]:
    """The failed checks, as readable strings (empty = passed)."""
    a = norm(answer)
    failed = []
    for item in checks.get("must_contain", []):
        if not any(alt.strip().lower() in a for alt in item.split("|")):
            failed.append(f"must_contain '{item[:80]}'")
    for item in checks.get("must_not_contain", []):
        if item.lower() in a:
            failed.append(f"must_not_contain '{item}'")
    for n in checks.get("numbers_present", []):
        if not has_number(answer, n):
            failed.append(f"numbers_present {n}")
    if "max_words" in checks and len(answer.split()) > checks["max_words"]:
        failed.append(f"max_words {checks['max_words']} (had {len(answer.split())})")
    return failed


def sign_in(url: str, key: str, email: str, password: str) -> str:
    r = requests.post(f"{url}/auth/v1/token", params={"grant_type": "password"}, headers={"apikey": key},
                      json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def ask(url: str, key: str, token: str, question: str, as_of: str) -> tuple[int, str, str, float]:
    """(HTTP status, answer or error, model, seconds). One retry if Gemini is busy or the call fails."""
    for attempt in (1, 2):
        t = time.monotonic()
        try:
            r = requests.post(f"{url}/functions/v1/ask-ping", timeout=170,
                              headers={"apikey": key, "Authorization": f"Bearer {token}"},
                              json={"question": question, "as_of": as_of})
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            secs = time.monotonic() - t
            if r.status_code == 200:
                return 200, body.get("answer", ""), body.get("model", "?"), secs
            err = body.get("error") or r.text[:200]
        except requests.RequestException as e:
            secs, err, r = time.monotonic() - t, f"{type(e).__name__}: {e}", None
        if attempt == 1:
            time.sleep(20)
    return (r.status_code if r is not None else 0), f"(no answer: {err})", "-", secs


def main() -> int:
    from ping.config import load_dotenv
    load_dotenv()
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    email = os.environ.get("REVIEWER_EMAIL", "reviewer@ping-demo.example")
    password = os.environ.get("REVIEWER_PASSWORD", "")
    if not (url and key and password):
        print("needs SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY and REVIEWER_PASSWORD (and REVIEWER_EMAIL)")
        return 2
    spec = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    demo = (ROOT / "dashboard" / "demo-data.json").read_bytes()
    demo_ok = hashlib.sha256(demo).hexdigest() == spec["demo_data_sha256"]
    if not demo_ok:
        print("WARNING: dashboard/demo-data.json changed since the expected answers were written; "
              "rebuilding the demo can change the right answers")
    token = sign_in(url, key, email, password)
    results = []
    for c in spec["cases"]:
        status, answer, model, secs = ask(url, key, token, c["question"], spec["snapshot_as_of"])
        failed = score(answer, c["checks"]) if status == 200 else [f"no answer (HTTP {status})"]
        results.append({**c, "status": status, "answer": answer, "model": model, "seconds": round(secs, 1),
                        "failed": failed})
        print(f"{c['id']:3} {'PASS' if not failed else 'FAIL'} {secs:5.1f}s {model:26} {c['question']}"
              + ("" if not failed else f"  -> {'; '.join(failed)}"), flush=True)
    (HERE / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    report = write_report(spec, results, demo_ok)
    passed = sum(1 for r in results if not r["failed"])
    print(f"\n{passed} of {len(results)} cases passed. Wrote {report.relative_to(ROOT)}")
    return 0


def write_report(spec: dict, results: list[dict], demo_ok: bool) -> Path:
    by_cat = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(not r["failed"])
    passed = sum(1 for r in results if not r["failed"])
    pct = lambda xs: f"{100 * sum(xs) / len(xs):.0f}%"  # noqa: E731
    models = defaultdict(int)
    for r in results:
        models[r["model"]] += 1
    lat = sorted(r["seconds"] for r in results if r["status"] == 200)
    lines = [
        "# Ask Ping evals", "",
        f"_Run on {datetime.now().astimezone().strftime('%d %b %Y, %H:%M %Z')} against the deployed `ask-ping` function, "
        f"signed in as the reviewer login (anonymised demo data), snapshot time fixed at {spec['snapshot_as_of']}. "
        "Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._", "",
        "## In short", "",
        f"- **{passed} of {len(results)} questions passed all their checks ({pct([not r['failed'] for r in results])}).**",
        f"- Models that answered: " + ", ".join(f"{m} ({n})" for m, n in sorted(models.items(), key=lambda x: -x[1])),
        (f"- Latency: median {lat[len(lat) // 2]:.1f} s, slowest {lat[-1]:.1f} s" if lat else "- Latency: no answers"),
        "- Checks are deterministic (no model grades another model): required words or phrases, forbidden ones, "
        "numbers in any common format (28,00,000 = 28 L = 28 LPA), and a word limit.",
    ]
    if not demo_ok:
        lines.append("- **Warning:** the demo data changed after the expected answers were written.")
    lines += ["", "## By category", "", "| category | passed | out of | score |", "|---|---|---|---|"]
    for cat, xs in by_cat.items():
        lines.append(f"| {cat} | {sum(xs)} | {len(xs)} | {pct(xs)} |")
    fails = [r for r in results if r["failed"]]
    lines += ["", "## Failures", ""]
    if not fails:
        lines.append("None.")
    for r in fails:
        lines += [f"### {r['id']} ({r['category']}): {r['question']}", "",
                  f"- failed: {'; '.join(r['failed'])}", f"- expected: {r['why']}",
                  f"- model {r['model']}, {r['seconds']} s", "", "> " + r["answer"].replace("\n", "\n> "), ""]
    lines += ["", "## Every case", "", "| id | category | question | result | model | seconds |", "|---|---|---|---|---|---|"]
    for r in results:
        q = r["question"].replace("|", "/")
        lines.append(f"| {r['id']} | {r['category']} | {q} | {'pass' if not r['failed'] else 'FAIL'} | "
                     f"{r['model']} | {r['seconds']} |")
    lines += ["", "The questions, checks and the data each expected answer comes from are in "
              "[`cases.json`](cases.json); every answer is in `results.json`."]
    out = HERE / "REPORT.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    sys.exit(main())
