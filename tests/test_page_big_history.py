"""The page with a long history (25 Nov: 1,211 messages, and the newest never reached the chat because one read stopped
at the database API's 1,000 rows). On the local replica (tests/fake_supabase.py: real Postgres with Supabase's row
rules and an API that, like Supabase's, returns at most 1,000 rows a request) with 2,500 messages and 1,200 chat
messages: the newest message, a to-do found minutes ago, a form posted 20 days ago that's still open, and a to-do
first seen long ago but posted again just now all appear where they should; the chat opens in under 2 s; the page
never reads the whole history to open.
Needs Postgres 16, psycopg and Playwright's Chromium (skipped without them, like the other replica tests)."""

from __future__ import annotations

import functools
import http.server
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

fs = pytest.importorskip("fake_supabase")
if fs.psycopg is None or not Path(fs.PG_BIN).exists():
    pytest.skip("needs Postgres 16 and psycopg (the local replica)", allow_module_level=True)
sync_api = pytest.importorskip("playwright.sync_api")

from test_setup_fresh_project import STUDENT  # noqa: E402

N_ITEMS, N_CHAT = 2500, 1200
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def iso(d):
    return d.isoformat()


def seed(store):
    """2,500 messages over 40 days (oldest first), 1,200 chat messages, a run, and the four that matter."""
    items = []
    n = N_ITEMS - 4
    for i in range(n):
        at = NOW - timedelta(days=40) + timedelta(minutes=23 * i)
        seen = at
        if i >= n - 300:
            # like a first check: 300 notices of the last two weeks found at once (one first-seen time, their own
            # notice times spread over the weeks before; the chat draws them at their notice's time)
            seen = NOW - timedelta(days=2)
            at = NOW - timedelta(days=16) + timedelta(hours=(i - (n - 300)))
        items.append({"id": f"notice:2026-2027:{10000 + i}:0", "level": "show", "category": "update", "company": f"Company {i % 90}",
                      "title": f"Company {i % 90} update number {i}", "first_seen": iso(seen), "sort_at": iso(at),
                      "details": {"notice_time": iso(at)}, "dismissed": False, "is_sample": False})
    items += [
        # the newest message
        {"id": "notice:2026-2027:99001:0", "level": "show", "category": "update", "company": "Newestco",
         "title": "NEWEST-MESSAGE Newestco update", "first_seen": iso(NOW - timedelta(minutes=1)), "sort_at": iso(NOW - timedelta(minutes=1)),
         "details": {"notice_time": iso(NOW - timedelta(minutes=2))}, "dismissed": False, "is_sample": False},
        # a to-do found minutes ago, due in 2 days
        {"id": "mail:new-todo", "level": "always", "category": "todo", "company": "Todoco Newfound",
         "title": "Todoco: submit the assignment NEW-TODO", "first_seen": iso(NOW - timedelta(minutes=5)), "sort_at": iso(NOW - timedelta(minutes=5)),
         "due_at": iso(NOW + timedelta(days=2)), "dismissed": False, "is_sample": False,
         "details": {"via": "email", "todo": {"action": "submit", "task": "assignment", "link": "https://example.com/brief"}}},
        # a form posted 20 days ago, still open (deep in the history: far past the newest 200)
        {"id": "notice:2026-2027:88001:0:todo0", "level": "always", "category": "todo", "company": "Oldformco Stillopen",
         "title": "Oldformco: fill the form OLD-OPEN-FORM", "first_seen": iso(NOW - timedelta(days=20)), "sort_at": iso(NOW - timedelta(days=20)),
         "due_at": iso(NOW + timedelta(days=3)), "dismissed": False, "is_sample": False,
         "details": {"notice_time": iso(NOW - timedelta(days=20)), "posted_at": iso(NOW - timedelta(days=20)),
                     "form": {"key": "forms.gle/oldform", "link": "https://forms.gle/oldform"},
                     "todo": {"action": "fill_form", "link": "https://forms.gle/oldform"}}},
        # first seen long ago, posted again just now: at the bottom of the chat
        {"id": "notice:2026-2027:77001:0:todo1", "level": "always", "category": "todo", "company": "Repostco Againnow",
         "title": "Repostco: submit the assignment REPOSTED-TODO", "first_seen": iso(NOW - timedelta(days=12)), "sort_at": iso(NOW - timedelta(days=12)),
         "due_at": iso(NOW + timedelta(days=4)), "dismissed": False, "is_sample": False,
         "details": {"notice_time": iso(NOW - timedelta(days=12)), "reposted_at": iso(NOW - timedelta(seconds=30)),
                     "todo": {"action": "submit", "task": "assignment", "link": "https://example.com/repost"}}},
    ]
    store.upsert("items", items)
    store.upsert("forms", [{"key": "forms.gle/oldform", "company": "Oldformco Stillopen", "companies": ["Oldformco Stillopen"], "title": "Oldformco form OLD-OPEN-FORM",
                            "link": "https://forms.gle/oldform", "due_at": iso(NOW + timedelta(days=3)), "item_ids": ["notice:2026-2027:88001:0:todo0"],
                            "sources": [], "deadline_history": [], "is_sample": False}], key="key")
    chat = []
    for i in range(N_CHAT):
        at = NOW - timedelta(days=60) + timedelta(minutes=35 * i)       # a month or two back (the window's messages fill the chat)
        chat.append({"role": "me" if i % 2 == 0 else "ping", "text": f"chat line {i}", "created_at": iso(at), "is_sample": False})
    chat.append({"role": "me", "text": "NEWEST-CHAT what's due?", "created_at": iso(NOW - timedelta(minutes=3)), "is_sample": False})
    for k in range(0, len(chat), 500):
        store._req("POST", "chat_messages", json=chat[k:k + 500], headers={"Prefer": "return=minimal"})
    store.upsert("runs", [{"id": 1, "started_at": iso(NOW - timedelta(minutes=8)), "finished_at": iso(NOW - timedelta(minutes=6)),
                           "trigger": "schedule", "status": "ok", "stage": "done"}])


@pytest.fixture(scope="module")
def replica():
    tmp = Path(tempfile.mkdtemp())
    fake = fs.FakeSupabase().start()
    httpd = None
    try:
        env = {**os.environ, **STUDENT, "SUPABASE_URL": fake.url, "PING_SUPABASE_API": fake.url, "PING_SUPABASE_REF": fs.REF,
               "PING_SETUP_TEST": "1", "DASHBOARD_EMAIL": "Student@Example.com", "PING_SETUP_ENV_FILE": str(tmp / ".env")}
        out = subprocess.run([sys.executable, str(ROOT / "setup" / "new_student_setup.py"), "--skip-erp-test", "--no-gh"],
                             env=env, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
        assert out.returncode == 0, out.stdout[-800:]
        from ping.store import SupabaseStore
        store = SupabaseStore(fake.url, fs.SECRET)
        seed(store)
        try:
            store._req("PATCH", "profile", params={"id": "eq.1"}, json={"onboarding_step": "done"}, headers={"Prefer": "return=minimal"})
        except Exception:
            pass
        b = subprocess.run(["bash", str(ROOT / "dashboard" / "build.sh")], cwd=ROOT, capture_output=True, text=True,
                           env={**os.environ, "SUPABASE_URL": "http://127.0.0.1:1/sb", "SUPABASE_PUBLISHABLE_KEY": fs.PUBLISHABLE})
        assert b.returncode == 0, b.stderr[-500:]
        site = tmp / "site"
        shutil.copytree(ROOT / "_site", site)

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(site)))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}/"
        (site / "config.js").write_text((site / "config.js").read_text().replace("http://127.0.0.1:1/sb", base + "sb"))
        yield fake, base
    finally:
        if httpd:
            httpd.shutdown()
        fake.stop()
        shutil.rmtree(tmp, ignore_errors=True)


def test_a_long_history_opens_fast_and_shows_what_matters(replica):
    fake, base = replica
    rows_read = []                                # (path, rows) of every read the page made
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("PING_CHROMIUM") or ("/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None)
        br = p.chromium.launch(executable_path=exe)
        ctx = br.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))

        def proxy(route):
            url = fake.url + route.request.url.split("/sb", 1)[1]
            r = route.fetch(url=url)
            if "/rest/v1/" in url and route.request.method == "GET":
                try:
                    rows_read.append((url.split("/rest/v1/", 1)[1][:160], len(r.json()) if isinstance(r.json(), list) else 1))
                except Exception:
                    pass
            route.fulfill(response=r)
        page.route(base + "sb/**", proxy)
        # sign in once (the session is kept in this browser, as on a phone)
        page.goto(base)
        page.wait_for_selector("form.login", timeout=30000)
        page.fill("#login-email", "student@example.com")
        page.fill("#login-pw", STUDENT["DASHBOARD_PASSWORD"])
        page.click("form.login button.btn")
        page.wait_for_selector("#thread", timeout=30000)
        assert not errs, errs[:3]

        # the chat opens: from the address to the newest message on screen
        # a fresh open (a new page load, as when you open the app), not a change of tab
        page.goto("about:blank")
        rows_read.clear()
        t0 = time.perf_counter()
        page.goto(base + "#chat")
        page.wait_for_selector("#thread >> text=NEWEST-MESSAGE", timeout=15000)
        opened = time.perf_counter() - t0
        print(f"\nchat opened in {opened:.2f} s with {N_ITEMS} messages and {N_CHAT + 1} chat messages; "
              f"rows read: {sum(n for _, n in rows_read)} in {len(rows_read)} requests")
        assert opened < 2.0, f"the chat took {opened:.2f} s to open"
        thread = page.inner_text("#thread")
        # a full screen of history: the window's messages are drawn even when their notices are older than the window
        drawn = page.locator("#thread [data-key]").count()
        assert drawn >= 50, f"only {drawn} messages drawn"
        # the first check's notices (found at once two days ago, each drawn at its notice's time) are in the chat; the
        # newest of them is 3.5 days old, so it is among the last messages drawn, before today's
        assert f"update number {N_ITEMS - 5}" in thread, "the first check's notices are missing from the chat"
        # the newest message, the newest chat line, the to-do found minutes ago and the repost are in the chat
        # (a to-do's card shows its company and task: the companies are the markers)
        for want in ("NEWEST-MESSAGE", "NEWEST-CHAT", "Todoco Newfound", "Repostco Againnow"):
            assert want in thread, f"{want} not in the chat"
        # the old open form is in To do, not drawn 20 days back in the chat
        assert "Oldformco Stillopen" not in thread
        # the reposted one is at the bottom (after the newest message), not 12 days up
        assert thread.index("Repostco Againnow") > thread.index("NEWEST-MESSAGE")
        # never the whole history to open: no read of the items table without a filter or a limit
        items_reads = [(path, n) for path, n in rows_read if path.startswith("items?")]
        assert sum(n for _, n in items_reads) < 600, items_reads
        assert not [p_ for p_, _ in items_reads if "limit=" not in p_ and "dismissed=eq.false" not in p_ and "first_seen=lt" not in p_], items_reads

        # To do: the new to-do and the form posted 20 days ago that's still open
        page.goto(base + "#forms")
        page.wait_for_selector("text=Todoco Newfound", timeout=10000)
        todo = page.inner_text("#app")
        print("To do:", " | ".join(l for l in todo.splitlines() if "co " in l)[:300])
        assert "Todoco Newfound" in todo and "Oldformco Stillopen" in todo and "Repostco Againnow" in todo
        # Today (the next 48 hours): the to-do due in 2 days is past it; the form in 3 days too; so the page says what's
        # within 48 h only, and every item it shows is open
        page.goto(base + "#today")
        page.wait_for_timeout(500)

        # scrolling up reads older messages (and keeps the newest where they were)
        page.goto(base + "#chat")
        page.wait_for_selector("#thread >> text=NEWEST-MESSAGE", timeout=10000)
        before = page.locator("#thread [data-key]").count()
        for _ in range(8):
            page.evaluate("document.querySelector('#thread').scrollTop = 0")
            page.wait_for_timeout(400)
        after = page.locator("#thread [data-key]").count()
        assert after > before, (before, after)
        assert not errs, errs[:3]
        br.close()


def test_a_message_arriving_while_you_read_further_up_moves_nothing(replica):
    """Live updates with the window: reading further up, a new message arrives (here by a focus catch-up; the replica
    has no Realtime): what you read stays put, the pill says '↓ 1 new' and takes you there."""
    fake, base = replica
    from ping.store import SupabaseStore
    store = SupabaseStore(fake.url, fs.SECRET)
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("PING_CHROMIUM") or ("/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None)
        br = p.chromium.launch(executable_path=exe)
        page = br.new_context(viewport={"width": 390, "height": 844}, service_workers="block").new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.route(base + "sb/**", lambda route: route.fulfill(response=route.fetch(url=fake.url + route.request.url.split("/sb", 1)[1])))
        page.goto(base)
        page.wait_for_selector("form.login", timeout=30000)
        page.fill("#login-email", "student@example.com")
        page.fill("#login-pw", STUDENT["DASHBOARD_PASSWORD"])
        page.click("form.login button.btn")
        page.wait_for_selector("#thread >> text=NEWEST-MESSAGE", timeout=30000)
        page.evaluate("() => { const t = document.querySelector('#thread'); t.scrollTop = t.scrollHeight; }")
        page.wait_for_timeout(300)
        page.evaluate("() => { document.querySelector('#thread').scrollTop = 300; }")
        page.wait_for_timeout(400)
        anchor = page.evaluate("""() => { const t = document.querySelector('#thread'), top = t.getBoundingClientRect().top;
            const n = [...t.querySelectorAll('[data-key]')].find(n => n.getBoundingClientRect().bottom > top);
            return { key: n.dataset.key, y: n.getBoundingClientRect().top }; }""")
        text = "LIVE-WHILE-READING arrives further down"
        store._req("POST", "chat_messages", json=[{"role": "ping", "text": text, "is_sample": False}], headers={"Prefer": "return=minimal"})
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        page.wait_for_function("t => [...document.querySelectorAll('.msg .text')].some(n => n.innerText === t)", arg=text, timeout=10000)
        page.wait_for_timeout(500)
        y = page.evaluate("k => document.querySelector(`[data-key=\"${CSS.escape(k)}\"]`).getBoundingClientRect().top", anchor["key"])
        assert abs(y - anchor["y"]) < 2, f"what you were reading moved ({anchor['y']:.0f} -> {y:.0f} px)"
        pill = page.locator("#jump")
        assert pill.is_visible() and pill.inner_text() == "↓ 1 new", pill.inner_text() if pill.is_visible() else "hidden"
        assert not errs, errs[:3]
        br.close()
