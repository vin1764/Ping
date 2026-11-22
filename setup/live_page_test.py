"""Live updates, tested in a real browser against the deployed database (Supabase Realtime):

1. a new message for this demo session appears in the open chat without a reload; at the bottom, the chat follows it
2. scrolled up: it doesn't move what you're reading; a "↓ 1 new" pill appears and takes you to it
3. row rules on the channel: another demo session's message and an owner message (only with SUPABASE_SERVICE_KEY,
   as in Admin; deleted right after) never reach this demo session
4. no socket (WebSocket blocked): the page says so and still catches up on tab focus
5. Check now in the demo plays queued -> logging in -> reading -> "Demo: found N new..." (a bubble) or a thin
   "Checked HH:MM · nothing new" line

    python setup/live_page_test.py            # the published site
    python setup/live_page_test.py --local    # a local build
Runs on GitHub as Actions > Admin > live-page.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "setup"))

TOKEN_JS = """() => { for (const k of Object.keys(localStorage)) if (/^sb-.*-auth-token$/.test(k))
                return JSON.parse(localStorage.getItem(k)).access_token; return null; }"""
NO_SOCKET = """window.WebSocket = class { constructor() { this.readyState = 3;
  setTimeout(() => { this.onerror && this.onerror(new Event('error')); this.onclose && this.onclose({ code: 1006, reason: 'blocked' }); }, 30); }
  send() {} close() {} addEventListener() {} removeEventListener() {} };"""


def open_demo(browser, url, init_script=None):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    if init_script:
        page.add_init_script(init_script)
    page.goto(url + ("&" if "?" in url else "?") + "anon-demo=1")    # the hidden demo session for checks
    page.click("#view-demo")
    page.wait_for_selector("[data-onboarding], #ask-input", timeout=30000)
    if page.locator(".chips .chip:has-text('Use the demo profile')").count():
        page.click(".chips .chip:has-text('Use the demo profile')")
    page.wait_for_selector("#ask-input", timeout=30000)
    return page


def main(argv: list[str]) -> int:
    import requests
    from playwright.sync_api import sync_playwright
    from ask_ping_page_test import live_url, serve
    from ping.supabase_admin import demo_session
    if "--local" in argv:
        import subprocess
        subprocess.run(["bash", str(ROOT / "dashboard" / "build.sh")], check=True, cwd=ROOT)
        url = serve(ROOT / "_site")
    else:
        url = live_url()
    print(f"dashboard: {url}")
    fails = 0

    def check(ok: bool, what: str) -> None:
        nonlocal fails
        fails += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {what}")

    with sync_playwright() as p:
        exe = os.environ.get("PING_CHROMIUM")          # a browser of another Playwright version, if needed
        browser = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        page = open_demo(browser, url)
        cfg = page.evaluate("window.PING_CONFIG")
        base, key = cfg["supabaseUrl"], cfg["supabaseKey"]
        token = page.evaluate(TOKEN_JS)
        mine = {"apikey": key, "Authorization": f"Bearer {token}", "Prefer": "return=minimal"}
        page.wait_for_selector("body[data-live=on]", timeout=30000)
        check(True, "the demo session's Realtime channel is open")

        def post(hdr, text, sample=True):
            r = requests.post(f"{base}/rest/v1/chat_messages", headers=hdr, timeout=30,
                              json=[{"role": "ping", "text": text, **({"is_sample": True} if sample else {})}])
            assert r.status_code < 300, r.text

        def bubble(text, timeout=8000):
            try:
                page.wait_for_function("t => [...document.querySelectorAll('.msg .text')].some(n => n.innerText === t)",
                                       arg=text, timeout=timeout)
                return True
            except Exception:
                return False

        thread_bottom = "() => { const t = document.querySelector('#thread'); return t.scrollHeight - t.scrollTop - t.clientHeight; }"
        # 1. at the bottom: it appears and the chat follows
        page.evaluate("() => { const t = document.querySelector('#thread'); t.scrollTop = t.scrollHeight; }")
        page.wait_for_timeout(400)
        t1 = f"Live test {uuid.uuid4().hex[:6]}: appears without a reload"
        t0 = time.monotonic()
        post(mine, t1)
        got = bubble(t1)
        check(got, f"a new message appears without a reload ({time.monotonic() - t0:.1f} s)")
        page.wait_for_timeout(500)
        check(page.evaluate(thread_bottom) < 80, "at the bottom, the chat followed it")

        # 2. scrolled up: nothing moves; the pill says 1 new and takes you there
        page.evaluate("() => { document.querySelector('#thread').scrollTop = 300; }")
        page.wait_for_timeout(400)
        anchor = page.evaluate("""() => { const t = document.querySelector('#thread'), top = t.getBoundingClientRect().top;
            const n = [...t.querySelectorAll('[data-key]')].find(n => n.getBoundingClientRect().bottom > top);
            return { key: n.dataset.key, y: n.getBoundingClientRect().top, scroll: t.scrollTop }; }""")
        t2 = f"Live test {uuid.uuid4().hex[:6]}: arrives while you read further up"
        post(mine, t2)
        bubble(t2)
        page.wait_for_timeout(500)
        after = page.evaluate("""k => { const n = document.querySelector(`[data-key="${CSS.escape(k)}"]`);
            return { y: n.getBoundingClientRect().top, scroll: document.querySelector('#thread').scrollTop }; }""", anchor["key"])
        check(abs(after["y"] - anchor["y"]) < 2, f"what you were reading didn't move ({anchor['y']:.0f} -> {after['y']:.0f} px)")
        pill = page.locator("#jump")
        check(pill.is_visible() and pill.inner_text() == "↓ 1 new", f"the pill says '{pill.inner_text() if pill.is_visible() else 'hidden'}'")
        pill.click()
        page.wait_for_timeout(900)
        seen = page.evaluate("""t => { const n = [...document.querySelectorAll('.msg .text')].find(n => n.innerText === t);
            const r = n.getBoundingClientRect(), th = document.querySelector('#thread').getBoundingClientRect();
            return r.top >= th.top - 2 && r.bottom <= th.bottom + 2; }""", t2)
        if not seen:
            print("   ", page.evaluate("""t => { const n = [...document.querySelectorAll('.msg .text')].find(n => n.innerText === t).closest('.msg');
                const th = document.querySelector('#thread'); return JSON.stringify({ msg: n.getBoundingClientRect(), thread: th.getBoundingClientRect(),
                scrollTop: th.scrollTop, max: th.scrollHeight - th.clientHeight }); }""", t2))
        check(seen, "the pill took you to the new message")

        # 3. row rules on the channel
        other, _ = demo_session(base, key)
        t3 = f"Live test {uuid.uuid4().hex[:6]}: another demo session's message"
        post({**other, "Prefer": "return=minimal"}, t3)
        check(not bubble(t3, timeout=6000), "another demo session's message never arrives")
        svc = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if svc:
            sh = {"apikey": svc, "Authorization": f"Bearer {svc}", "Prefer": "return=representation"}
            t4 = f"[realtime probe] isolation check {uuid.uuid4().hex[:6]}, deleted right away"
            r = requests.post(f"{base}/rest/v1/chat_messages", headers=sh, timeout=30, json=[{"role": "ping", "text": t4}])
            rid = r.json()[0]["id"] if r.status_code < 300 else None
            try:
                check(r.status_code < 300 and not bubble(t4, timeout=6000), "an owner message never reaches a demo session")
            finally:
                if rid:
                    requests.delete(f"{base}/rest/v1/chat_messages", headers=sh, timeout=30, params={"id": f"eq.{rid}"})
        else:
            print("skip owner message check (needs SUPABASE_SERVICE_KEY, as in Admin)")

        # 5. Check now in the demo
        page.click("#check-now-top")
        page.wait_for_selector(".msg.run .steps", timeout=5000)
        check(page.locator("#check-now-top").is_disabled(), "Check now is off while the check runs")
        # the demo's first Check now finds what its snapshot's last check brought; a later one finds nothing new
        # (a check that finds nothing is a thin line, "Checked 18:05 · nothing new (demo sample data)", not a bubble)
        done_line = "() => [...document.querySelectorAll('.msg.run .text, .note-line.sysline')].map(n => n.innerText)"
        try:
            page.wait_for_function(f"() => ({done_line})().some(t => /^(Demo: found \\d+ new from the snapshot's last check|Checked \\d\\d:\\d\\d · nothing new \\(demo sample data\\))$/.test(t))",
                                   timeout=15000)
            check(True, f"the demo's Check now ends with its own line ({page.evaluate(done_line)[-1]!r})")
        except Exception:
            check(False, "the demo's Check now ends 'Demo: found N new ...' or a 'Checked HH:MM · nothing new' line")
        try:
            page.wait_for_function("() => /found \\d+ new|checked just now|checked 1 min ago/.test(document.querySelector('#subtitle').innerText)", timeout=5000)
            check(True, "the header's status line follows the check")
        except Exception:
            check(False, f"the header's status line follows the check ({page.inner_text('#subtitle')!r})")
        check(page.locator("#check-now-top").inner_text() == "Check now" and not page.locator("#check-now-top").is_disabled(),
              "Check now is back on after it")
        page.close()

        # 4. no socket: the page catches up on focus
        page = open_demo(browser, url, NO_SOCKET)
        try:
            page.wait_for_selector("body[data-live=off]", timeout=20000)
            check(True, "with no socket the page knows it's not live")
        except Exception:
            check(False, "with no socket the page knows it's not live")
        token2 = page.evaluate(TOKEN_JS)
        t5 = f"Live test {uuid.uuid4().hex[:6]}: caught up on focus"
        post({"apikey": key, "Authorization": f"Bearer {token2}", "Prefer": "return=minimal"}, t5)
        page.wait_for_timeout(1500)
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        check(bubble(t5), "without the socket, a focus catches up on the new message")
        browser.close()
    print(f"\n{fails} problem(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
