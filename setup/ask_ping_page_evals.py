"""Ask Ping's single-question evals, asked through the page the way a person asks them (Admin > ask-ping-page).

Seven cases share a one-click demo session ("View demo", "Use the demo profile", the "For you" marks loaded), as in the
API evals: Supabase allows about 30 new anonymous sign-ins an hour from one address. The question is typed into the chat and
the reply read off the screen. Per case it records who answered (the page itself, or the ask-ping function), how
long from Enter to the reply on screen, whether the typing bubble showed, and the same checks as the API evals.

OPEN questions go to the function. With GEMINI_API_KEY_EVALS they carry the evals proof (the model answers on the
evals key); without it they are sent with no_ai, so the function answers by rules and no model is called (the
live key is never used by an Admin task). The report says which.

    python setup/ask_ping_page_evals.py [url]   -> evals/ask_ping/PAGE_RUN.md and evals/ask_ping/page_results.json
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals" / "ask_ping"))

WATCH = """() => { window.__typing = false;
  new MutationObserver(() => { if (document.querySelector('.msg.typing')) window.__typing = true; })
    .observe(document.body, { childList: true, subtree: true }); }"""


def median(xs):
    return round(statistics.median(xs)) if xs else None


PER_SESSION = 7    # Supabase allows about 30 new anonymous sign-ins an hour from one address; 7 a session, as the API evals


def run(url: str, cases: list[dict], proof: dict | None) -> list[dict]:
    from playwright.sync_api import sync_playwright
    from run_ask_ping_evals import score
    out = []
    with sync_playwright() as p:
        # PING_CHROMIUM: a Chromium binary to use instead of Playwright's own download (a machine with its own)
        browser = p.chromium.launch(executable_path=os.environ.get("PING_CHROMIUM") or None)
        for k in range(0, len(cases), PER_SESSION):
            ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            calls = []

            def on_route(route):
                req = route.request
                hdr = dict(req.headers)
                if proof:
                    hdr.update(proof)
                    return route.continue_(headers=hdr)
                try:
                    data = json.loads(req.post_data or "{}")
                except ValueError:
                    data = {}
                if data.get("question"):
                    data["no_ai"] = True                 # no evals key here: rules only, never the live key
                return route.continue_(headers=hdr, post_data=json.dumps(data))

            page.route("**/functions/v1/ask-ping", on_route)
            page.on("response", lambda r: "/functions/v1/ask-ping" in r.url and calls.append(
                {"status": r.status, "marks": "marks" in (r.request.post_data or "")}))
            page.goto(url)
            page.click("#view-demo")
            page.wait_for_selector("[data-onboarding], #ask-input", timeout=60000)
            if page.locator(".chips .chip:has-text('Use the demo profile')").count():
                page.click(".chips .chip:has-text('Use the demo profile')")
            page.wait_for_selector("#ask-input", timeout=30000)
            # the "For you" marks (one call to the function, cache only): local answers split For you / Others
            for _ in range(100):
                if any(x["marks"] for x in calls):
                    break
                page.wait_for_timeout(100)
            page.wait_for_timeout(400)
            page.evaluate(WATCH)
            for c in cases[k:k + PER_SESSION]:
                page.evaluate("() => { window.__typing = false; }")
                before = page.locator(".msg.ping:not(.typing)").count()
                n_calls = len(calls)
                page.fill("#ask-input", c["question"])
                t0 = time.perf_counter()
                page.press("#ask-input", "Enter")
                page.wait_for_function("n => !document.querySelector('.msg.typing') && "
                                       "document.querySelectorAll('.msg.ping:not(.typing)').length > n", arg=before, timeout=60000)
                wall = (time.perf_counter() - t0) * 1000
                last = page.locator(".msg.ping:not(.typing)").last
                answer = last.locator(".text").inner_text()
                by = last.get_attribute("data-answered-by") or "?"
                page_ms = int(last.get_attribute("data-ms") or 0)
                typing = page.evaluate("window.__typing")
                server = [x for x in calls[n_calls:] if not x["marks"]]
                status = server[-1]["status"] if server else None
                failed = score(answer, c["checks"])
                out.append({"id": c["id"], "question": c["question"], "answered_by": by, "ms_on_screen": round(wall),
                            "ms_in_page": page_ms, "typing_bubble": typing, "server_status": status, "failed": failed,
                            "answer": answer})
                print(f"{c['id']:5} {'PASS' if not failed else 'FAIL'} {by:6} {wall:7.0f} ms  typing={'yes' if typing else 'no '}  "
                      f"{c['question'][:60]}" + (f"  -> {'; '.join(failed)}" if failed else ""), flush=True)
                page.wait_for_timeout(300)
            ctx.close()
        browser.close()
    return out


def report(rows: list[dict], url: str, mode: str, build: str) -> str:
    page_rows = [r for r in rows if r["answered_by"] == "page"]
    srv = [r for r in rows if r["answered_by"] == "server"]
    fact_fast = sum(1 for r in page_rows if r["ms_on_screen"] < 300)
    lines = ["# Ask Ping through the page: single-question evals", "",
             f"{len(rows)} single-question cases from `evals/ask_ping/cases.json`, each typed into the live page "
             f"({url}, build `{build}`), 7 to a one-click demo session, by `setup/ask_ping_page_evals.py` "
             f"(Actions > Admin > ask-ping-page). Time = from Enter to the reply on screen.", "",
             f"OPEN questions: {mode}.", "",
             "| | cases | median on screen | slowest | typing bubble | pass |", "|---|---|---|---|---|---|",
             f"| FACT (answered in the page) | {len(page_rows)} | {median([r['ms_on_screen'] for r in page_rows])} ms | "
             f"{max([r['ms_on_screen'] for r in page_rows], default=0)} ms | {sum(r['typing_bubble'] for r in page_rows)} of {len(page_rows)} | "
             f"{sum(not r['failed'] for r in page_rows)}/{len(page_rows)} |",
             f"| OPEN and preferences (the function) | {len(srv)} | {median([r['ms_on_screen'] for r in srv])} ms | "
             f"{max([r['ms_on_screen'] for r in srv], default=0)} ms | {sum(r['typing_bubble'] for r in srv)} of {len(srv)} | "
             f"{sum(not r['failed'] for r in srv)}/{len(srv)} |", "",
             f"FACT answers under 300 ms: {fact_fast} of {len(page_rows)} (median work inside the page "
             f"{median([r['ms_in_page'] for r in page_rows])} ms).", "",
             "| id | by | ms | typing | result | question |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['id']} | {r['answered_by']} | {r['ms_on_screen']} | {'yes' if r['typing_bubble'] else 'no'} | "
                     f"{'pass' if not r['failed'] else 'FAIL: ' + '; '.join(r['failed']).replace('|', '/')} | {r['question']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    from ask_ping_page_test import live_url
    url = argv[0] if argv and not argv[0].startswith("--") else live_url()
    spec = json.loads((ROOT / "evals" / "ask_ping" / "cases.json").read_text(encoding="utf-8"))
    cases = spec["cases"]
    if "--only" in argv:
        want = argv[argv.index("--only") + 1].split(",")
        cases = [c for c in cases if any(c["id"] == w or c["id"].startswith(w) for w in want)]
    proof = None
    if os.environ.get("GEMINI_API_KEY_EVALS", "").strip():
        from ping.evals_key import eval_headers
        proof = eval_headers()
        mode = "the model, on the evals key (GEMINI_API_KEY_EVALS)"
    else:
        mode = ("sent with no_ai: GEMINI_API_KEY_EVALS isn't set, and an Admin task never uses the live key, so the "
                "function answered them by rules; their times are the function's own path without a model call")
    import requests
    build = (requests.get(url + "config.js", timeout=30).text.split('PING_BUILD = "')[-1].split('"')[0]
             if url.startswith("http") else "?")
    rows = run(url, cases, proof)
    md = report(rows, url, mode, build)
    (ROOT / "evals" / "ask_ping" / "PAGE_RUN.md").write_text(md, encoding="utf-8")
    (ROOT / "evals" / "ask_ping" / "page_results.json").write_text(json.dumps(
        {"url": url, "build": build, "open_mode": mode, "rows": rows}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n" + md.split("| id |")[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
