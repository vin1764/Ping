"""Ask Ping, tested the way a person uses it: open the LIVE dashboard in a real browser, sign in, type the
questions in the chat, and read the replies on the screen.

By default it opens the published site, https://<owner>.github.io/ping-dashboard/ (PING_DASHBOARD_URL
overrides it; --local builds dashboard/ and serves it on this machine instead). Runs on GitHub as
Actions > Admin > ask-ping-page.

1. Owner sign-in screen: a fresh browser sees the email + password form, and a made-up email with a wrong
   password gets Supabase's "Invalid login credentials" back, which proves the live page reaches Supabase Auth
   from its own address. It never signs in as the owner.
2. The one-click demo: clicks "View demo", lands on the chat with the demo's messages and the demo chip, checks
   with that session's own token that the database gives it 0 real rows, then asks each question; every
   answer must come back from ask-ping with HTTP 200 and not be the rules fallback.
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


def live_url() -> str:
    if os.environ.get("PING_DASHBOARD_URL"):
        return os.environ["PING_DASHBOARD_URL"].rstrip("/") + "/"
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    if not owner:
        remote = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, cwd=ROOT).stdout
        owner = remote.rstrip("/").split("/")[-2].split(":")[-1] if "/" in remote else ""
    return f"https://{owner.lower()}.github.io/ping-dashboard/"


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright
    local = "--local" in argv
    questions = [a for a in argv if not a.startswith("--")] or ["slice ctc breakdown", "what's due tomorrow"]
    if local:
        subprocess.run(["bash", str(ROOT / "dashboard" / "build.sh")], check=True, cwd=ROOT)
        url = serve(ROOT / "_site")
    else:
        url = live_url()
    print(f"dashboard: {url}")
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # 1. the owner's sign-in screen, without signing in as the owner
        page = browser.new_page(viewport={"width": 390, "height": 844})
        resp = page.goto(url)
        print(f"page: HTTP {resp.status if resp else '?'}, build {page.evaluate('window.PING_BUILD || null')}")
        page.wait_for_selector("form.login", timeout=30000)
        has_email, has_pw = page.locator("#login-email").count(), page.locator("#login-pw").count()
        page.fill("#login-email", "owner-check@example.invalid")
        page.fill("#login-pw", "not-the-password-0")
        page.click("form.login button.btn")
        page.wait_for_function("() => /invalid|credentials|error/i.test(document.querySelector('form.login p.muted')?.innerText || '')",
                               timeout=30000)
        msg = page.locator("form.login p.muted").first.inner_text()
        owner_ok = has_email == 1 and has_pw == 1 and "invalid login credentials" in msg.lower()
        failures += not owner_ok
        print(f"owner sign-in screen: email field {has_email}, password field {has_pw}; a wrong password gets "
              f"'{msg}' from Supabase Auth{'' if owner_ok else '  <-- PROBLEM'}")
        page.close()

        # 2. the one-click demo: View demo, the chat, 0 real rows, then the questions
        page = browser.new_page(viewport={"width": 390, "height": 844})
        calls = []
        page.on("response", lambda r: "/functions/v1/ask-ping" in r.url and calls.append(r.status))
        page.on("pageerror", lambda e: print(f"  page error: {e}"))
        page.goto(url)
        page.click("#view-demo")
        # a fresh demo session starts with the onboarding; its first bubble offers the demo profile in one tap
        page.wait_for_selector("[data-onboarding]", timeout=30000)
        first = page.locator(".chips .chip").first.inner_text()
        onb_ok = first == "Use the demo profile" and page.get_attribute("[data-onboarding]", "data-onboarding") == "welcome"
        failures += not onb_ok
        print(f"onboarding: first question shown, first chip '{first}'{'' if onb_ok else '  <-- PROBLEM'}")
        page.click(".chips .chip:has-text('Use the demo profile')")
        page.wait_for_selector("#ask-input", timeout=30000)
        chip = page.inner_text("#mode-badge")
        bubbles = page.locator(".msg.item").count()
        print(f"View demo: landed on {page.evaluate('location.pathname + location.hash')}, chip '{chip}', "
              f"{bubbles} messages from Ping in the chat")
        failures += not (chip.startswith("Demo") and bubbles > 0)
        # the session the page holds (supabase-js keeps it in localStorage)
        token = page.evaluate("""() => { for (const k of Object.keys(localStorage)) if (/^sb-.*-auth-token$/.test(k))
                                   return JSON.parse(localStorage.getItem(k)).access_token; return null; }""")
        cfg = page.evaluate("window.PING_CONFIG")
        import requests
        hdr = {"apikey": cfg["supabaseKey"], "Authorization": f"Bearer {token}"}
        import base64, json as _json
        own_id = _json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "==")).get("sub")
        real = {}
        # every table: a demo session must see 0 real rows (tables it may not read at all answer with an error or
        # nothing; role_marks, demo_questions, allowed_users and state have no policy for it)
        for t in ("items", "roles", "notices", "pdf_checks", "profile", "runs", "emails", "contacts", "chat_messages",
                  "corrections", "state", "allowed_users", "role_marks", "demo_questions", "session_prefs"):
            has_sample = t not in ("state", "allowed_users", "role_marks", "demo_questions", "session_prefs", "corrections")
            params = {"select": "is_sample", "is_sample": "not.is.true", "limit": "5"} if has_sample else {"select": "*", "limit": "5"}
            if t == "session_prefs":
                # the onboarding saves this session's own row ("Use the demo profile"): it may see that one, no other
                params = {"select": "owner_id", "limit": "5"}
            r = requests.get(f"{cfg['supabaseUrl']}/rest/v1/{t}", headers=hdr, timeout=30, params=params)
            if t == "session_prefs" and r.status_code == 200:
                real[t] = sum(1 for row in r.json() if row.get("owner_id") != own_id)
                continue
            real[t] = len(r.json()) if r.status_code == 200 else f"HTTP {r.status_code}"
        demo_rows = requests.get(f"{cfg['supabaseUrl']}/rest/v1/items", headers=hdr, timeout=30,
                                 params={"select": "id", "limit": "1000"}).json()
        zero = all(v == 0 or str(v).startswith("HTTP 4") for v in real.values())
        failures += not zero or not demo_rows
        print(f"demo session in the database: {len(demo_rows)} demo items readable; real rows per table: {real}"
              f"{'' if zero else '  <-- PROBLEM'}")
        # the CV bucket: a demo session can neither list nor download anything in it
        lst = requests.post(f"{cfg['supabaseUrl']}/storage/v1/object/list/cvs", headers=hdr, timeout=30,
                            json={"prefix": "", "limit": 100})
        listed = lst.json() if lst.status_code == 200 else []
        dl = requests.get(f"{cfg['supabaseUrl']}/storage/v1/object/cvs/cv1.pdf", headers=hdr, timeout=30)
        bucket_ok = not listed and dl.status_code >= 400
        failures += not bucket_ok
        print(f"CV bucket from the demo session: list HTTP {lst.status_code}, {len(listed)} objects; download cv1.pdf "
              f"HTTP {dl.status_code}{'' if bucket_ok else '  <-- PROBLEM'}")
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
        browser.close()
    print(f"\n{'all checks passed on ' + url if not failures else f'{failures} problem(s) on ' + url}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
