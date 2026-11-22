"""Staying signed in on a phone, in both engines: WebKit as an iPhone (Safari / the Home Screen app) and Chromium as
an Android phone (Chrome / the installed app). Runs the built dashboard against the local replica
(tests/fake_supabase.py: real Postgres, Supabase's roles, and Auth with expiring access tokens and single-use refresh
tokens that rotate, like Supabase Auth).

For each engine:
  1. sign in once (a real <form>, the fields a password manager fills)
  2. close the app (the browser context), reopen it with the same storage: no sign-in screen, a valid session; and the
     same after the update that moved the session to Ping's own key (a session saved under the old key is kept)
  3. reopen with the access token expired: refreshed silently, no sign-in screen, never a flash of it; and when the
     phone lost the localStorage write of that refresh (an installed app closed right after it), the IndexedDB copy
     carries the new token: still signed in, the replaced token never sent
  4. reopen with the token expired and the network not ready for the first try (a phone waking up): no sign-in screen;
     and with the server unreachable for a while: a "trying again" note, never the sign-in form, then back in by itself
  5. in the background past the token's life, then back to the foreground: refreshed, the session survives
  6. a demo session in another app copy signing out doesn't touch the owner's session
  7. the owner's password is in no storage (localStorage, sessionStorage, cookies)

    python setup/stay_signed_in.py            -> prints each check per engine; exit 1 on any failure
Needs root and Postgres 16 (like setup/replica_walkthrough.py). PING_WEBKIT / PING_CHROMIUM: a browser's executable
when it isn't in Playwright's default folder.
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
EMAIL, PASSWORD = "student@example.com", "a-long-test-password-1"


def serve(fake, tmp: Path) -> str:
    """The dashboard as built for a project, served on localhost (service workers need https or localhost); the
    replica answers under <site>/sb, so the page, its storage and the API share one origin, as on GitHub Pages."""
    import fake_supabase as fs
    site = tmp / "site"
    b = subprocess.run(["bash", str(ROOT / "dashboard" / "build.sh")], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "SUPABASE_URL": "http://127.0.0.1:1/sb", "SUPABASE_PUBLISHABLE_KEY": fs.PUBLISHABLE})
    if b.returncode:
        raise SystemExit(b.stdout[-500:] + b.stderr[-500:])
    subprocess.run(["cp", "-r", str(ROOT / "_site"), str(site)], check=True)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(site)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://localhost:{httpd.server_address[1]}/"
    (site / "config.js").write_text((site / "config.js").read_text().replace("http://127.0.0.1:1/sb", base + "sb"))
    return base


def main() -> int:
    import fake_supabase as fs
    from playwright.sync_api import sync_playwright
    from test_setup_fresh_project import STUDENT
    fails: list[str] = []
    tmp = Path(tempfile.mkdtemp())
    fake = fs.FakeSupabase().start()
    try:
        env = {**os.environ, **STUDENT, "SUPABASE_URL": fake.url, "PING_SUPABASE_API": fake.url,
               "PING_SUPABASE_REF": fs.REF, "PING_SETUP_TEST": "1", "DASHBOARD_EMAIL": EMAIL,
               "DASHBOARD_PASSWORD": PASSWORD, "PING_SETUP_ENV_FILE": str(tmp / ".env")}
        out = subprocess.run([sys.executable, str(ROOT / "setup" / "new_student_setup.py"), "--skip-erp-test", "--no-gh"],
                             env=env, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
        if out.returncode:
            print(out.stdout[-800:])
            return 1
        base = serve(fake, tmp)
        fake.jwt_exp = 3600

        def check(engine, ok, what, note=""):
            print(f"  {'ok  ' if ok else 'FAIL'} {what}{(': ' + note) if note else ''}", flush=True)
            if not ok:
                fails.append(f"{engine}: {what}")

        with sync_playwright() as p:
            engines = [("iPhone (WebKit)", "webkit", "iPhone 13"), ("Android (Chromium)", "chromium", "Pixel 7")]
            for name, kind, device in engines:
                print(f"\n{name}")
                if kind == "webkit":
                    br = p.webkit.launch(executable_path=os.environ.get("PING_WEBKIT") or None)
                else:
                    br = p.chromium.launch(executable_path=os.environ.get("PING_CHROMIUM") or None)
                dev = dict(p.devices[device])

                def open_app(state=None, before=None, path="?source=app#chat"):
                    ctx = br.new_context(**dev, storage_state=state, service_workers="block")
                    page = ctx.new_page()
                    page.errors = []
                    page.on("pageerror", lambda e: page.errors.append(str(e)))

                    def proxy(route):
                        req = route.request
                        url = fake.url + req.url.split("/sb", 1)[1]
                        if before and before(req):
                            return route.abort("internetdisconnected")
                        try:
                            r = route.fetch(url=url)
                            route.fulfill(response=r)
                        except Exception:
                            route.abort()
                    page.route(base + "sb/**", proxy)
                    # a log of what the page showed while it decided: was the sign-in form ever on screen?
                    page.add_init_script("""window.__sawLogin = false; new MutationObserver(() => {
                        if (document.querySelector('form.login')) window.__sawLogin = true; })
                        .observe(document, { childList: true, subtree: true });""")
                    page.goto(base + path)
                    return ctx, page

                def signed_in(page, timeout=20000):
                    page.wait_for_selector("form.login, #ask-input, [data-onboarding]", timeout=timeout)
                    return page.locator("form.login").count() == 0

                def stored(page):
                    return page.evaluate("""() => { for (const k of Object.keys(localStorage)) {
                        if (/auth/.test(k)) { try { const v = JSON.parse(localStorage.getItem(k));
                          if (v && v.refresh_token) return { key: k, ...v }; } catch (e) {} } } return null; }""")

                # 1. sign in once
                ctx, page = open_app()
                page.wait_for_selector("form.login", timeout=20000)
                form = page.evaluate("""() => { const f = document.querySelector('form.login');
                    const u = f.querySelector('input[autocomplete=username]'), w = f.querySelector('input[autocomplete=current-password]');
                    return { form: f.tagName, user: u && u.type, pw: w && w.type, submit: !!f.querySelector('button:not([type=button])'),
                             note: f.innerText.includes("You'll stay signed in") }; }""")
                check(name, form["form"] == "FORM" and form["user"] == "email" and form["pw"] == "password" and form["submit"],
                      "sign-in is a real form a password manager fills", json.dumps(form))
                check(name, form["note"], "\"You'll stay signed in\" under the button")
                check(name, page.locator("#view-demo").count() == 0, "no demo button on the sign-in screen")
                page.fill("#login-email", EMAIL)
                page.fill("#login-pw", PASSWORD)
                page.click("form.login button[type=submit]")
                try:
                    page.wait_for_selector("#ask-input, [data-onboarding]", timeout=20000)
                    ok = True
                except Exception:
                    ok = False
                check(name, ok, "signed in", "" if ok else page.inner_text("body")[:200])
                s = stored(page)
                check(name, bool(s), "the session is in localStorage", s and s["key"])
                in_idb = page.evaluate("""() => new Promise((res) => { const r = indexedDB.open('ping-session');
                    r.onsuccess = () => { try { const g = r.result.transaction('kv').objectStore('kv').get('ping-auth');
                      g.onsuccess = () => res(!!g.result); g.onerror = () => res(false); } catch (e) { res(false); } };
                    r.onerror = () => res(false); })""")
                check(name, in_idb, "and a second copy in IndexedDB")
                sess = page.evaluate("Object.keys(sessionStorage).filter((k) => /auth/.test(k)).length")
                check(name, sess == 0, "nothing of the session in sessionStorage")
                state = ctx.storage_state(indexed_db=True)
                blob = json.dumps(state) + page.evaluate("JSON.stringify(sessionStorage)")
                check(name, PASSWORD not in blob, "the password is in no storage or cookie")
                ctx.close()

                # 2. reopen: no sign-in screen
                ctx, page = open_app(state)
                check(name, signed_in(page) and not page.evaluate("window.__sawLogin"), "reopened: no sign-in screen, not even a flash")
                state = ctx.storage_state(indexed_db=True)
                ctx.close()

                # 2b. a session saved by the version before this one (supabase-js's default key) survives the update
                def rename(st, old_key, new_key):
                    """The state an earlier version left: the session under supabase-js's default key, localStorage only."""
                    st = json.loads(json.dumps(st))
                    for o in st.get("origins", []):
                        for kv in o.get("localStorage", []):
                            if kv["name"] == old_key:
                                kv["name"] = new_key
                        o["indexedDB"] = [d for d in o.get("indexedDB", []) if d.get("name") != "ping-session"]
                    return st
                ctx, page = open_app(rename(state, "ping-auth", "sb-localhost-auth-token"))
                ok = signed_in(page) and not page.evaluate("window.__sawLogin")
                keys = page.evaluate("Object.keys(localStorage).filter((k) => /auth/.test(k))")
                check(name, ok and keys == ["ping-auth"], "a session from before the update is kept (moved to Ping's own key)", json.dumps(keys))
                ctx.close()

                # 3. reopen with the access token expired (a day later): refreshed silently
                def session_records(st):
                    """Every stored copy of a session in a saved state: localStorage entries and IndexedDB records."""
                    for o in st.get("origins", []):
                        for kv in o.get("localStorage", []):
                            yield kv, "name"
                        for db in o.get("indexedDB", []):
                            for store in db.get("stores", []):
                                for rec in store.get("records", []):
                                    yield rec, "key"

                def expire(st):
                    """A day later: every copy of the session (localStorage and IndexedDB) has run out."""
                    st = json.loads(json.dumps(st))
                    for rec, key in session_records(st):
                        if "auth" not in str(rec.get(key)) or not isinstance(rec.get("value"), str):
                            continue
                        try:
                            v = json.loads(rec["value"])
                        except ValueError:
                            continue
                        if isinstance(v, dict) and v.get("refresh_token"):
                            v["expires_at"] = int(time.time()) - 86400
                            rec["value"] = json.dumps(v)
                    return st
                n = len([x for x in fake.auth_log if x[0] == "refresh" and x[2] == "ok"])
                ctx, page = open_app(expire(state))
                ok = signed_in(page) and not page.evaluate("window.__sawLogin")
                page.wait_for_timeout(500)
                refreshed = len([x for x in fake.auth_log if x[0] == "refresh" and x[2] == "ok"]) > n
                check(name, ok and refreshed, "token expired: refreshed silently, no sign-in screen")
                s2 = stored(page)
                check(name, bool(s2) and s2["expires_at"] > time.time() + 600, "a fresh token is stored")
                state = ctx.storage_state(indexed_db=True)
                ctx.close()

                # 3b. the phone lost the localStorage write of a refresh: localStorage still has the old, replaced token,
                #     IndexedDB the new one. Ping must use the new one (sending the old one would be refused).
                stale = expire(state)              # expired, so this open refreshes; keep its localStorage for later
                ctx, page = open_app(stale)
                signed_in(page)
                page.wait_for_timeout(500)
                after = ctx.storage_state(indexed_db=True)
                ctx.close()
                old_rt = next((json.loads(kv["value"]).get("refresh_token") for o in stale["origins"] for kv in o["localStorage"]
                               if kv["name"] == "ping-auth"), None)
                lost = json.loads(json.dumps(after))
                for o in lost["origins"]:
                    for kv in o["localStorage"]:
                        if kv["name"] == "ping-auth":
                            kv["value"] = next(k["value"] for oo in stale["origins"] for k in oo["localStorage"] if k["name"] == "ping-auth")
                fake.reuse_seconds = 0              # a replaced token is refused at once, as after the reuse window
                ctx, page = open_app(lost)
                ok = signed_in(page) and not page.evaluate("window.__sawLogin")
                sent_old = [x for x in fake.auth_log if x[0] == "refresh" and x[1] == old_rt and x[2] != "ok"]
                check(name, ok and not sent_old, "a refresh whose localStorage write was lost: the IndexedDB copy keeps it signed in")
                fake.reuse_seconds = 10
                state = ctx.storage_state(indexed_db=True)
                ctx.close()

                # 4. expired, and the first refresh can't reach the network (a phone waking up)
                tries = {"n": 0}

                def first_refresh_fails(req):
                    if "grant_type=refresh_token" in req.url:
                        tries["n"] += 1
                        return tries["n"] == 1
                    return False
                ctx, page = open_app(expire(state), before=first_refresh_fails)
                ok = signed_in(page, 30000) and not page.evaluate("window.__sawLogin")
                check(name, ok, "token expired and the network not ready at first: no sign-in screen",
                      f"{tries['n']} refresh tries")
                state = ctx.storage_state(indexed_db=True)

                ctx.close()

                # 4b. the server unreachable for a while: a "trying again" note, never the sign-in form; back in by itself
                net = {"down": True}
                ctx, page = open_app(expire(state), before=lambda req: net["down"] and "/auth/v1/" in req.url)
                page.wait_for_selector("#reconnecting, form.login, #ask-input", timeout=30000)
                shown = page.evaluate("document.querySelector('#reconnecting') ? 'reconnecting' : document.querySelector('form.login') ? 'login' : 'app'")
                check(name, shown == "reconnecting" and not page.evaluate("window.__sawLogin"),
                      "server unreachable: \"trying again\", no sign-in form", shown)
                net["down"] = False
                page.evaluate("window.dispatchEvent(new Event('online'))")
                check(name, signed_in(page, 30000) and page.locator("form.login").count() == 0, "back online: in, without signing in")
                state = ctx.storage_state(indexed_db=True)

                # 5. background past the token's life, back to the foreground: refreshed, still signed in
                n = len([x for x in fake.auth_log if x[0] == "refresh" and x[2] == "ok"])
                page.evaluate("""() => { const set = (v) => Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => v });
                    set('hidden'); Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
                    document.dispatchEvent(new Event('visibilitychange')); }""")
                # while it's away the token runs out (the clock jumps 2 h)
                page.evaluate("""() => { const real = Date.now.bind(Date), skew = 2 * 3600 * 1000;
                    Date.now = () => real() + skew; }""")
                page.evaluate("""() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
                    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
                    document.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('focus')); }""")
                page.wait_for_timeout(2500)
                refreshed = len([x for x in fake.auth_log if x[0] == "refresh" and x[2] == "ok"]) > n
                check(name, refreshed and page.locator("form.login").count() == 0, "back from the background: refreshed, still signed in")
                state = ctx.storage_state(indexed_db=True)
                ctx.close()

                # 6. a demo session signing out elsewhere doesn't touch the owner's session
                ctx, page = open_app(path="?anon-demo=1#chat")   # a fresh copy: the hidden demo session, then Exit demo
                page.wait_for_selector("#view-demo", timeout=20000)
                page.click("#view-demo")
                page.wait_for_selector("#ask-input, [data-onboarding]", timeout=20000)
                page.evaluate("location.hash = '#profile'")
                exit_btn = page.locator("button", has_text="Exit demo")
                exit_btn.first.wait_for(timeout=15000)
                exit_btn.first.click()
                page.wait_for_selector("form.login", timeout=20000)
                demo_left = stored(page)
                check(name, demo_left is None, "Exit demo signs the demo session out (nothing left behind)")
                ctx.close()
                ctx, page = open_app(state)
                check(name, signed_in(page) and not page.evaluate("window.__sawLogin"), "after a demo session signed out elsewhere, the owner is still signed in")
                logouts = [x for x in fake.auth_log if x[0] == "logout"]
                check(name, all(x[1] == "local" for x in logouts), "every sign-out signs out only that device", json.dumps(logouts[-2:]))
                errs = page.errors
                check(name, not errs, "no page errors", "; ".join(errs[:2]))
                ctx.close()
                br.close()
        print(f"\n{len(fails)} problem(s)" + ("".join(f"\n  - {f}" for f in fails)))
        return 1 if fails else 0
    finally:
        fake.stop()


if __name__ == "__main__":
    sys.exit(main())
