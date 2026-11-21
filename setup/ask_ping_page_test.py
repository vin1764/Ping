"""Ask Ping, tested the way a person uses it: open the dashboard page in a real browser,
sign in, type the questions in the chat, and read the replies on the screen.

Runs on GitHub (Actions > Admin > ask-ping-page) where the keys are: it builds the page
with SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY, signs in with REVIEWER_EMAIL / REVIEWER_PASSWORD
(the read-only demo login; the owner's password isn't stored anywhere) and asks each question
given on the command line. The answer comes from the same ask-ping function the owner uses.
"""

from __future__ import annotations

import functools
import http.server
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def serve(folder: Path) -> str:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_address[1]}/"


def main(questions: list[str]) -> int:
    from playwright.sync_api import sync_playwright
    subprocess.run(["bash", str(ROOT / "dashboard" / "build.sh")], check=True, cwd=ROOT)
    url = serve(ROOT / "_site")
    failures = 0
    with sync_playwright() as p:
        page = p.chromium.launch().new_page(viewport={"width": 390, "height": 844})
        calls = []
        page.on("response", lambda r: "/functions/v1/ask-ping" in r.url and calls.append(r.status))
        page.on("pageerror", lambda e: print(f"  page error: {e}"))
        page.goto(url)
        page.fill("#login-email", os.environ["REVIEWER_EMAIL"])
        page.fill("#login-pw", os.environ["REVIEWER_PASSWORD"])
        page.click("form.login button.btn")
        page.wait_for_selector("#ask-input", timeout=30000)
        print(f"signed in on the page as {os.environ['REVIEWER_EMAIL']} ({page.inner_text('#mode-badge')})")
        for q in questions:
            before = page.locator(".msg.ping:not(.typing)").count()
            page.fill("#ask-input", q)
            page.press("#ask-input", "Enter")
            # "Ping is typing…" is replaced by the reply bubble when the answer arrives
            page.wait_for_function(
                "n => !document.querySelector('.msg.typing') && "
                "document.querySelectorAll('.msg.ping:not(.typing)').length > n", arg=before, timeout=200000)
            reply = page.locator(".msg.ping:not(.typing)").last.locator(".text").inner_text()
            status = calls[-1] if calls else None
            bad = status != 200 or "AI not reachable" in reply
            failures += bad
            print(f"\nQ: {q}\n   ask-ping answered HTTP {status}{'  <-- PROBLEM' if bad else ''}\nA: {reply}")
    print(f"\n{'all answers came from the AI' if not failures else f'{failures} question(s) fell back to rules'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["slice ctc breakdown", "what's due tomorrow"]))
