"""A new student's first hour, timed, on the local replica (tests/fake_supabase.py: real Postgres with Supabase's
roles and row rules, its Auth and Data API; tests/fake_erp.py: the ERP).

  fresh project -> setup script -> first open and sign-in -> onboarding in the chat -> first check -> first digest

The replica has no Edge Functions, Storage, Realtime or push service, so the steps that need them (a preference said
in the chat, a CV upload, the install prompt and push opt-in) are checked elsewhere: tests/js/onboarding.test.js
(every onboarding branch), setup/install_check.js and setup/pwa_check.js (install, push), the live demo checks.
Needs root and Postgres 16 (like tests/test_setup_fresh_project.py).

    python setup/replica_walkthrough.py   -> prints each step with its time; screenshots to docs/screenshots/final/
"""

from __future__ import annotations

import functools
import http.server
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
OUT = ROOT / "docs" / "screenshots" / "final"


def main() -> int:
    import fake_supabase as fs
    from playwright.sync_api import sync_playwright
    from test_setup_fresh_project import STUDENT
    steps: list[tuple[str, float, str]] = []
    t_all = time.perf_counter()

    def step(name, t0, note=""):
        steps.append((name, time.perf_counter() - t0, note))
        print(f"{name:42} {time.perf_counter() - t0:6.1f} s  {note}", flush=True)

    tmp = Path(tempfile.mkdtemp())
    fake = fs.FakeSupabase().start()
    try:
        env = {**os.environ, **STUDENT, "SUPABASE_URL": fake.url, "PING_SUPABASE_API": fake.url,
               "PING_SUPABASE_REF": fs.REF, "PING_SETUP_TEST": "1", "DASHBOARD_EMAIL": "Student@Example.com",
               "PING_SETUP_ENV_FILE": str(tmp / ".env")}
        t0 = time.perf_counter()
        out = subprocess.run([sys.executable, str(ROOT / "setup" / "new_student_setup.py"), "--skip-erp-test", "--no-gh"],
                             env=env, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
        step("1. setup script on an empty project", t0, "OK" if out.returncode == 0 else out.stdout[-300:])
        if out.returncode:
            return 1
        # the dashboard, built for this project; the replica is reached through the page's own address
        site = tmp / "site"
        b = subprocess.run(["bash", str(ROOT / "dashboard" / "build.sh")], cwd=ROOT, capture_output=True, text=True,
                           env={**os.environ, "SUPABASE_URL": "http://127.0.0.1:1/sb", "SUPABASE_PUBLISHABLE_KEY": fs.PUBLISHABLE})
        if b.returncode:
            print(b.stdout[-500:], b.stderr[-500:])
            return 1
        subprocess.run(["cp", "-r", str(ROOT / "_site"), str(site)], check=True)
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):           # the socket's retries (no Realtime on the replica) aren't news
                pass
        handler = functools.partial(Quiet, directory=str(site))
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}/"
        (site / "config.js").write_text((site / "config.js").read_text().replace("http://127.0.0.1:1/sb", base + "sb"))

        with sync_playwright() as p:
            br = p.chromium.launch(executable_path=os.environ.get("PING_CHROMIUM") or None)
            page = br.new_page(viewport={"width": 390, "height": 844})
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))

            def proxy(route):
                req = route.request
                url = fake.url + req.url.split("/sb", 1)[1]
                try:
                    r = route.fetch(url=url)
                    route.fulfill(response=r)
                except Exception:
                    route.abort()
            page.route(base + "sb/**", proxy)
            page.on("response", lambda r: "/sb/" in r.url and r.status >= 400 and print("  replica", r.status, r.url.split("/sb")[1][:90]))
            t0 = time.perf_counter()
            page.goto(base)
            page.wait_for_selector("form.login", timeout=30000)
            page.fill("#login-email", "student@example.com")
            page.fill("#login-pw", STUDENT["DASHBOARD_PASSWORD"])
            page.click("form.login button.btn")
            try:
                page.wait_for_selector("[data-onboarding], #ask-input", timeout=30000)
            except Exception:
                page.screenshot(path=str(OUT / "replica-stuck-390.png"))
                print("stuck after sign-in:", page.inner_text("body")[:600], errs[:3])
                raise
            onb = page.locator("[data-onboarding]").count() > 0
            step("2. first open and sign-in", t0, "onboarding starts in the chat" if onb else "no onboarding shown")
            page.screenshot(path=str(OUT / "replica-onboarding-390.png"))
            # 3. onboarding: the first offered chip at each step, Skip where a step needs a service the replica lacks
            t0 = time.perf_counter()
            answered = []
            for _ in range(12):
                if not page.locator("[data-onboarding]").count():
                    break
                stepname = page.get_attribute("[data-onboarding]", "data-onboarding")
                chips = page.locator(".composer .chips .chip")
                labels = chips.all_inner_texts()
                if not labels:
                    break
                want = next((l for l in labels if l.lower().startswith("skip")), labels[0]) \
                    if stepname in ("targets", "cv", "first_check") else labels[0]
                chips.filter(has_text=want).first.click()
                answered.append(f"{stepname}: {want}")
                page.wait_for_timeout(800)
                if os.environ.get("WALK_DEBUG"):
                    print("   after", stepname, want, "->", page.get_attribute("[data-onboarding]", "data-onboarding") if page.locator("[data-onboarding]").count() else None,
                          "|", page.locator(".msg.ping .text").last.inner_text()[:120].replace("\n", " "), "| chips:", page.locator(".composer .chips .chip").all_inner_texts()[:6])
            step("3. onboarding in the chat", t0, "; ".join(answered)[:200])
            # 4. the first check (the hourly run, here against the fake ERP) and the first digest on the page
            from fake_erp import FakeErp
            import ping.erp as erp_mod
            from ping.config import IST, Secrets, SecurityAnswer
            from ping.gate import Gate
            from ping.run import Runner
            from ping.store import SupabaseStore
            erp_mod.MIN_OTP_TO_LOGIN = 0
            t0 = time.perf_counter()
            erp = FakeErp(datetime(2026, 11, 21, 9, 0, tzinfo=IST))
            secrets = Secrets("22XY10042", "pw", [SecurityAnswer("What is the name of your first pet?", "Bruno")],
                              "student@example.com", "x", fake.url, fs.SECRET, {})
            rec = Runner(secrets, SupabaseStore(fake.url, fs.SECRET), store_ok=True, gate=Gate(erp), mailbox=erp.mail,
                         now=datetime(2026, 11, 21, 9, 0, tzinfo=IST), pause=0).run()
            step("4. first check (fake ERP)", t0, rec["status"])
            t0 = time.perf_counter()
            page.reload()
            page.wait_for_selector("#ask-input", timeout=30000)
            page.wait_for_selector(".msg.item", timeout=30000)
            n = page.locator(".msg.item").count()
            step("5. first digest on the page", t0, f"{n} messages from Ping")
            page.screenshot(path=str(OUT / "replica-first-feed-390.png"))
            t0 = time.perf_counter()
            page.fill("#ask-input", "what's due tomorrow")
            page.press("#ask-input", "Enter")
            page.wait_for_timeout(400)
            last = page.locator(".msg.ping:not(.typing)").last
            step("6. a question, answered in the page", t0,
                 f"{last.get_attribute('data-answered-by')} in {last.get_attribute('data-ms')} ms")
            t0 = time.perf_counter()
            page.evaluate("location.hash = '#profile'")
            page.wait_for_selector("#pc-install", timeout=15000)
            page.screenshot(path=str(OUT / "replica-profile-390.png"), full_page=True)
            step("7. Profile: every card there", t0,
                 ", ".join(page.locator(".pcard h2").all_inner_texts()))
            # 8. signed in, every page at three widths, light and dark: no sideways scroll, nothing under 12 px
            issues = []
            t0 = time.perf_counter()
            for w, h, tag in ((390, 844, "390"), (768, 1024, "768"), (1280, 800, "1280")):
                for scheme in ("light", "dark"):
                    page.set_viewport_size({"width": w, "height": h})
                    page.emulate_media(color_scheme=scheme)
                    for pg in ("chat", "today", "feed", "companies", "profile"):
                        if pg == "today" and w >= 1100:
                            continue
                        page.evaluate(f"location.hash = '#{pg}'")
                        page.wait_for_timeout(450)
                        r = page.evaluate("""() => ({ over: document.documentElement.scrollWidth - innerWidth,
                          tiny: [...document.querySelectorAll('body *')].filter((el) => el.childElementCount === 0 && el.textContent.trim()
                            && el.getBoundingClientRect().width > 0 && parseFloat(getComputedStyle(el).fontSize) < 12).length })""")
                        if r["over"] > 1 or r["tiny"]:
                            issues.append(f"{pg} {tag} {scheme}: {r}")
                        page.screenshot(path=str(OUT / f"signed-in-{pg}-{tag}-{scheme}.png"))
            step("8. signed-in pages, 3 widths x light/dark", t0, "; ".join(issues) or "no sideways scroll, no text under 12 px")
            print(f"\npage errors: {errs[:3] or 'none'}")
            br.close()
        print(f"\nfresh project to first feed: {time.perf_counter() - t_all:.0f} s (machine time; a person adds the "
              f"time to create the Supabase project and paste the GitHub secrets, see docs/SETUP.md)")
        return 0
    finally:
        fake.stop()


if __name__ == "__main__":
    sys.exit(main())
