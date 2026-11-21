"""Ask Ping evals: ask the deployed ask-ping function every question in cases.json, exactly as the dashboard's
one-click demo does (an anonymous "View demo" session, which sees only the anonymised demo), with the snapshot
time fixed so "today" and "tomorrow" never move. Score the deterministic checks and write REPORT.md.

Run it:
  - on GitHub: Actions > Admin > ask-ping-evals, or
  - locally:   SUPABASE_URL=... SUPABASE_PUBLISHABLE_KEY=... python evals/ask_ping/run_ask_ping_evals.py
               (a .env file with those names works too)

A demo session may ask 15 questions an hour, so the runner opens a new session every 7 questions (a retry counts too). With
SUPABASE_SERVICE_KEY set (as in Admin), it removes its own question counts afterwards, so an eval run doesn't
use up the hour's demo allowance for visitors.

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


class DemoSessions:
    """One-click demo sessions, a fresh one before the per-session limit (15 an hour) is reached."""
    PER_SESSION = 7   # each question may be sent twice (one retry), and both count towards the 15

    def __init__(self, url: str, key: str):
        from ping.supabase_admin import demo_session
        self.url, self.key, self._new, self.ids, self.used = url, key, demo_session, [], self.PER_SESSION
        self.token = ""

    def fresh(self) -> str:
        """A new session of its own (an empty chat thread), e.g. for one multi-turn conversation."""
        hdr, uid = self._new(self.url, self.key)
        self.ids.append(uid)
        self.used = self.PER_SESSION  # the next single question gets a new session too
        return hdr["Authorization"].removeprefix("Bearer ")

    def next_token(self) -> str:
        if self.used >= self.PER_SESSION:
            hdr, uid = self._new(self.url, self.key)
            self.token, self.used = hdr["Authorization"].removeprefix("Bearer "), 0
            self.ids.append(uid)
        self.used += 1
        return self.token

    def forget_counts(self) -> str:
        """Remove this run's rows from the demo question counter (needs the service key)."""
        secret = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not secret or not self.ids:
            return "question counts kept (no SUPABASE_SERVICE_KEY here)"
        r = requests.delete(f"{self.url}/rest/v1/demo_questions", timeout=30,
                            headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
                            params={"session_id": f"in.({','.join(self.ids)})"})
        return f"removed this run's demo question counts (HTTP {r.status_code}, {len(self.ids)} sessions)"


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
    if not (url and key):
        print("needs SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY")
        return 2
    spec = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    demo = (ROOT / "dashboard" / "demo-data.json").read_bytes()
    demo_ok = hashlib.sha256(demo).hexdigest() == spec["demo_data_sha256"]
    if not demo_ok:
        print("WARNING: dashboard/demo-data.json changed since the expected answers were written; "
              "rebuilding the demo can change the right answers")
    sessions = DemoSessions(url, key)
    results = []
    for c in spec["cases"]:
        status, answer, model, secs = ask(url, key, sessions.next_token(), c["question"],
                                          c.get("as_of") or spec["snapshot_as_of"])
        failed = score(answer, c["checks"]) if status == 200 else [f"no answer (HTTP {status})"]
        results.append({**c, "status": status, "answer": answer, "model": model, "seconds": round(secs, 1),
                        "failed": failed})
        print(f"{c['id']:3} {'PASS' if not failed else 'FAIL'} {secs:5.1f}s {model:26} {c['question']}"
              + ("" if not failed else f"  -> {'; '.join(failed)}"), flush=True)

    convs = []
    for conv in spec.get("conversations", []):
        token = sessions.fresh()
        turns = []
        for t in conv["turns"]:
            # exactly like the dashboard: your message goes into the thread, then Ping answers, then its reply goes in
            post_chat(url, key, token, "me", t["question"])
            status, answer, model, secs = ask(url, key, token, t["question"], conv.get("as_of") or spec["snapshot_as_of"])
            post_chat(url, key, token, "ping", answer)
            failed = score(answer, t["checks"]) if status == 200 else [f"no answer (HTTP {status})"]
            turns.append({**t, "status": status, "answer": answer, "model": model, "seconds": round(secs, 1),
                          "failed": failed})
            print(f"{conv['id']:3} turn {len(turns)} {'PASS' if not failed else 'FAIL'} {secs:5.1f}s {model:26} "
                  f"{t['question']}" + ("" if not failed else f"  -> {'; '.join(failed)}"), flush=True)
        convs.append({"id": conv["id"], "why": conv["why"], "turns": turns, "passed": all(not t["failed"] for t in turns)})
    print(sessions.forget_counts())
    report = write_report(spec, results, demo_ok, convs)
    (HERE / "results.json").write_text(json.dumps({"single_turn": results, "conversations": convs}, indent=1,
                                                  ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for r in results if not r["failed"])
    print(f"\nsingle-turn: {passed} of {len(results)} passed; conversations: {sum(c['passed'] for c in convs)} of "
          f"{len(convs)} fully passed. Wrote {report.relative_to(ROOT)}")
    return 0


def post_chat(url: str, key: str, token: str, role: str, text: str) -> None:
    """A message in the demo session's own thread (a demo row, as the dashboard writes it)."""
    r = requests.post(f"{url}/rest/v1/chat_messages", timeout=30, json=[{"role": role, "text": text, "is_sample": True}],
                      headers={"apikey": key, "Authorization": f"Bearer {token}", "Prefer": "return=minimal"})
    if r.status_code >= 300:
        print(f"  (couldn't save the {role} message to the thread: HTTP {r.status_code} {r.text[:120]})")


def write_report(spec: dict, results: list[dict], demo_ok: bool, convs: list[dict] | None = None) -> Path:
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
        f"from one-click demo sessions (anonymised demo data), snapshot time fixed at {spec['snapshot_as_of']} (cases marked 'as_of' use their own). "
        "Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._", "",
        "## In short", "",
        f"- **Single questions: {passed} of {len(results)} passed all their checks ({pct([not r['failed'] for r in results])}).**",
        (f"- **Conversations (follow-ups in one thread): {sum(c['passed'] for c in convs)} of {len(convs)} passed every turn; "
         f"{sum(not t['failed'] for c in convs for t in c['turns'])} of {sum(len(c['turns']) for c in convs)} turns passed.**"
         if convs else "- Conversations: none in this run."),
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
    if convs:
        lines += ["", "## Conversations (multi-turn)", "",
                  "Each conversation runs in one fresh demo session; the function reads the thread from the database "
                  "itself. A conversation passes only if every turn passes.", "",
                  "| id | turns | first question | follow-up(s) | result |", "|---|---|---|---|---|"]
        for c in convs:
            qs = [t["question"].replace("|", "/") for t in c["turns"]]
            res = "pass" if c["passed"] else "FAIL (turn " + ", ".join(str(i + 1) for i, t in enumerate(c["turns"]) if t["failed"]) + ")"
            lines.append(f"| {c['id']} | {len(qs)} | {qs[0]} | {' / '.join(qs[1:])} | {res} |")
        cfails = [(c, i, t) for c in convs for i, t in enumerate(c["turns"]) if t["failed"]]
        lines += ["", "### Conversation failures", ""] + (["None."] if not cfails else [])
        for c, i, t in cfails:
            prev = c["turns"][i - 1] if i else None
            lines += [f"#### {c['id']} turn {i + 1}: {t['question']}", "",
                      f"- failed: {'; '.join(t['failed'])}", f"- expected: {c['why']}",
                      (f"- previous turn: \"{prev['question']}\" → \"{prev['answer'][:200]}\"" if prev else ""),
                      f"- model {t['model']}, {t['seconds']} s", "", "> " + t["answer"].replace("\n", "\n> "), ""]
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
