#!/usr/bin/env python3
"""
Ping - one-time ERP capture (run this by hand, once, on your own laptop).

WHAT IT DOES
  Opens a normal Chrome-style window on the ERP login page. YOU log in and
  click around by hand. While you browse, the script quietly saves copies of
  the pages and the data the ERP sends back, so Ping can be built from the
  real pages instead of guesses.

WHAT IT NEVER DOES
  - It never clicks, types or submits anything on the ERP. Only you do.
  - It never saves what you type while logging in (password, security answer,
    OTP). During login it records only the NAMES of the form fields.
  - It never saves cookies, and it blanks out session tokens in addresses.

HOW TO RUN (on Mac/Linux type `python3` instead of `python`)
    python -m pip install --user playwright
    python setup/capture_erp.py

It uses the Google Chrome already installed on your computer, and Microsoft
Edge if Chrome can't be started. To pick one yourself:
    python setup/capture_erp.py --browser edge
Only if you have neither: `python -m playwright install chromium`, then
`--browser chromium` (that one is blocked on some managed work laptops).

Everything is saved under ./captures/ (git is told to ignore that folder).
"""

import argparse
import asyncio
import shutil
import json
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit, urlunsplit

try:
    from playwright.async_api import async_playwright
except ImportError:
    sys.exit("Playwright is not installed. Run:  python -m pip install --user playwright")

# name -> (what we call it, how Playwright starts it)
BROWSERS = {
    "chrome": ("Google Chrome", {"channel": "chrome"}),
    "edge": ("Microsoft Edge", {"channel": "msedge"}),
    "chromium": ("Playwright's own Chromium", {}),
}
DEFAULT_ORDER = ["chrome", "edge"]  # chromium only when asked for: managed laptops may block it

START_URL = os.environ.get("PING_CAPTURE_START_URL", "https://erp.iitkgp.ac.in/IIT_ERP3/")
ERP_HOST = urlsplit(START_URL).hostname or ""

# Any URL parameter or form field whose name matches this is treated as secret.
SENSITIVE_KEY = re.compile(r"token|session|sso|auth|otp|pass|pwd|answer|ans\b|secret|key|cookie",
                           re.IGNORECASE)
TOKEN_IN_TEXT = re.compile(
    r"((?:[A-Za-z_]*(?:token|session|sso)[A-Za-z_]*)\s*=\s*)([^&\"'\s<>;]+)", re.IGNORECASE)
JSESSION_IN_PATH = re.compile(r";jsessionid=[^?#&\"'\s<>]+", re.IGNORECASE)
JS_TOKEN_ASSIGN = re.compile(  # myform.elements['ssoToken'].value = '...'
    r"""((?:token|session|sso)[A-Za-z_]*['"]?\]?(?:\.value)?\s*[:=]\s*['"])([^'"]+)""", re.IGNORECASE)
HIDDEN_INPUT_VALUE = re.compile(
    r"(<input\b[^>]*\b(?:name|id)\s*=\s*[\"']?[^\"'>]*(?:token|session|sso|otp)[^\"'>]*[\"']?[^>]*"
    r"\bvalue\s*=\s*[\"'])([^\"']*)", re.IGNORECASE)

SKIP_TYPES = {"stylesheet", "image", "font", "media", "websocket", "manifest", "texttrack", "ping"}
TEXT_HINTS = ("html", "json", "xml", "javascript", "text", "x-www-form-urlencoded")


def scrub_text(s: str) -> str:
    s = JSESSION_IN_PATH.sub(";jsessionid=REDACTED", s)
    s = TOKEN_IN_TEXT.sub(lambda m: m.group(1) + "REDACTED", s)
    s = HIDDEN_INPUT_VALUE.sub(lambda m: m.group(1) + "REDACTED", s)
    s = JS_TOKEN_ASSIGN.sub(lambda m: m.group(1) + "REDACTED", s)
    return s


def scrub_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return scrub_text(url)
    query = "&".join(
        f"{k}={'REDACTED' if SENSITIVE_KEY.search(k) else v}"
        for k, v in parse_qsl(parts.query, keep_blank_values=True))
    path = JSESSION_IN_PATH.sub(";jsessionid=REDACTED", parts.path)
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


def describe_post(post: str | None, names_only: bool):
    """Return the form fields sent, with secret values hidden."""
    if not post:
        return None
    if "=" in post and not post.lstrip().startswith(("{", "[", "<")):
        fields = parse_qsl(post, keep_blank_values=True)
        if names_only:
            return {k: "<typed by you - not saved>" for k, _ in fields}
        return {k: ("REDACTED" if SENSITIVE_KEY.search(k) else v) for k, v in fields}
    return "<not saved>" if names_only else scrub_text(post)[:20000]


def safe_name(url: str, limit: int = 60) -> str:
    path = urlsplit(url).path.rstrip("/").split("/")[-1] or "index"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", path)[:limit] or "page"


def guess_ext(content_type: str, url: str) -> str:
    ct = content_type.lower()
    for hint, ext in (("pdf", ".pdf"), ("json", ".json"), ("html", ".html"), ("xml", ".xml"),
                      ("javascript", ".js"), ("csv", ".csv"), ("spreadsheet", ".xlsx"),
                      ("excel", ".xls"), ("msword", ".doc"), ("wordprocessing", ".docx"),
                      ("text/plain", ".txt")):
        if hint in ct:
            return ext
    tail = urlsplit(url).path.lower()
    m = re.search(r"\.(pdf|xlsx?|docx?|csv|json|xml|html?|jsp)$", tail)
    return ("." + m.group(1).replace("jsp", "html")) if m else ".bin"


class Recorder:
    def __init__(self, out: Path):
        self.out = out
        for sub in ("network", "pages", "screenshots", "downloads"):
            (out / sub).mkdir(parents=True, exist_ok=True)
        self.phase = "login"
        self.seq = 0
        self.log: list[dict] = []
        self.tasks: set[asyncio.Task] = set()
        self.snapshots = 0

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def spawn(self, coro):
        task = asyncio.ensure_future(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def drain(self):
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)

    # ---- network -------------------------------------------------------
    def on_response(self, resp):
        self.spawn(self.save_response(resp, self.phase))

    async def save_response(self, resp, phase: str):
        req = resp.request
        rtype = req.resource_type
        if rtype in SKIP_TYPES or resp.url.startswith("data:"):
            return
        host = urlsplit(resp.url).hostname or ""
        if rtype == "script" and host != ERP_HOST:
            return  # third-party libraries, not useful
        seq = self.next_seq()
        headers = await resp.all_headers()
        ctype = headers.get("content-type", "")
        entry = {
            "seq": seq, "phase": phase, "time": datetime.now().isoformat(timespec="seconds"),
            "method": req.method, "url": scrub_url(resp.url), "type": rtype,
            "status": resp.status, "content_type": ctype,
            "content_disposition": headers.get("content-disposition"),
            "location": scrub_url(headers["location"]) if "location" in headers else None,
            "frame": scrub_url(req.frame.url) if req.frame else None,
            "sent_fields": describe_post(req.post_data, names_only=(phase == "login")),
            "file": None,
        }
        # While you are logging in we keep only plain page loads, never the
        # replies to the security-question / OTP / login calls.
        keep_body = not (phase == "login" and not (req.method == "GET" and rtype in ("document", "script")))
        if keep_body and not (300 <= resp.status < 400):
            try:
                body = await resp.body()
            except Exception as e:  # downloads and some redirects have no body here
                entry["note"] = f"body not available ({type(e).__name__})"
                body = None
            if body and "pdf" in ctype.lower() and not body.startswith(b"%PDF"):
                # Chrome's built-in PDF viewer hands us its own wrapper page instead of the
                # file. Fetch the same address again with the same logged-in session.
                try:
                    again = await resp.frame.page.context.request.get(resp.url)
                    if (await again.body()).startswith(b"%PDF"):
                        body = await again.body()
                        entry["note"] = "PDF re-fetched (browser viewer intercepted it)"
                except Exception as e:
                    entry["note"] = f"PDF re-fetch failed ({type(e).__name__})"
            if body:
                ext = guess_ext(ctype, resp.url)
                path = self.out / "network" / f"{seq:04d}_{safe_name(resp.url)}{ext}"
                if any(h in ctype.lower() for h in TEXT_HINTS) or ext in (".html", ".json", ".xml", ".js", ".txt", ".csv"):
                    path.write_text(scrub_text(body.decode("utf-8", errors="replace")), encoding="utf-8")
                else:
                    path.write_bytes(body)
                entry["file"] = str(path.relative_to(self.out))
        self.log.append(entry)

    def on_download(self, download):
        self.spawn(self.save_download(download))

    async def save_download(self, download):
        seq = self.next_seq()
        name = re.sub(r"[^A-Za-z0-9._ -]+", "_", download.suggested_filename or "file")
        path = self.out / "downloads" / f"{seq:04d}_{name}"
        try:
            await download.save_as(str(path))
            note = None
        except Exception as e:
            note = f"download failed ({type(e).__name__})"
        self.log.append({"seq": seq, "phase": self.phase, "type": "download",
                         "url": scrub_url(download.url), "file": str(path.relative_to(self.out)),
                         "note": note})
        print(f"   saved file: {name}")

    def attach(self, page):
        page.on("download", self.on_download)

    # ---- snapshots of what is on screen --------------------------------
    async def snapshot(self, context, label: str):
        self.snapshots += 1
        n = self.snapshots
        count = 0
        for p_i, page in enumerate(context.pages):
            if page.is_closed():
                continue
            try:
                await page.screenshot(path=str(self.out / "screenshots" / f"{n:02d}_{label}_tab{p_i}.png"),
                                      full_page=True, timeout=15000)
            except Exception:
                pass
            for f_i, frame in enumerate(page.frames):
                try:
                    html = await frame.content()
                except Exception:
                    continue
                name = f"{n:02d}_{label}_tab{p_i}_frame{f_i}_{safe_name(frame.url, 40)}.html"
                header = f"<!-- captured from: {scrub_url(frame.url)} -->\n"
                (self.out / "pages" / name).write_text(header + scrub_text(html), encoding="utf-8")
                count += 1
        return count


def redact_files(out: Path, words: list[tuple[str, str]]):
    if not words:
        return 0
    changed = 0
    for path in out.rglob("*"):
        if path.suffix.lower() not in (".html", ".json", ".xml", ".js", ".txt", ".csv"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        new = text
        for word, label in words:
            new = re.sub(re.escape(word), label, new, flags=re.IGNORECASE)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
    return changed


async def ask(prompt: str) -> str:
    # Reading the keyboard in a side thread keeps the recorder running meanwhile.
    loop = asyncio.get_running_loop()
    try:
        return (await loop.run_in_executor(None, input, prompt)).strip()
    except EOFError:
        return "done"


CHECKLIST = """
 Now browse the PLACEMENT pages only. Open and look - do NOT click Apply,
 Submit, Upload or Save anywhere. After each page below has fully loaded,
 come back to this window and press Enter to take a snapshot.

   1. The companies list (one row per role). Scroll to the bottom.
   2. The details / job description of 2-3 companies - ideally one you are
      eligible for and one you are not.
   3. Any page that shows what you have applied to and its status.
   4. The CDC notice board. Scroll through it.
   5. Open 4-5 notices: a shortlist, a test schedule, a deadline extension,
      a "fill this form" one. Open their PDF attachments too (they may
      download instead of opening - that is fine, they are saved).
   6. (Optional) A page showing your CGPA / department / degree, if the
      placement section has one.

 New tabs are fine - everything is recorded.
"""


def short_error(e: Exception) -> str:
    text = str(e).strip()
    return text.splitlines()[0][:200] if text else type(e).__name__


async def open_browser(pw, order: list[str], rec: "Recorder"):
    """Start the first browser in `order` that actually opens a page."""
    headless = os.environ.get("PING_CAPTURE_HEADLESS") == "1"  # only for testing the script
    failures = []
    for key in order:
        label, opts = BROWSERS[key]
        opts = dict(opts, headless=headless)
        if key == "chromium" and os.environ.get("PING_CAPTURE_CHROMIUM"):
            opts["executable_path"] = os.environ["PING_CAPTURE_CHROMIUM"]
        print(f" Starting {label}...")
        browser = None
        try:
            browser = await pw.chromium.launch(**opts)
            context = await browser.new_context(accept_downloads=True,
                                                viewport={"width": 1366, "height": 850})
            context.on("response", rec.on_response)
            context.on("page", rec.attach)  # attaches the download saver to every tab
            page = await context.new_page()
            await page.goto("about:blank")
            print(f" Using {label}.")
            return browser, context, page
        except Exception as e:
            failures.append(f"   {label}: {short_error(e)}")
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
    print("\nCould not start a browser:\n" + "\n".join(failures))
    print("\nIf Chrome or Edge is installed but still fails, your organisation may block")
    print("automated control of it. Try the other one with --browser chrome / --browser edge.")
    return None


async def main():
    parser = argparse.ArgumentParser(description="Ping - one-time ERP capture")
    parser.add_argument("--browser", choices=list(BROWSERS),
                        help="which browser to use (default: Chrome, then Edge)")
    args = parser.parse_args()
    order = [args.browser] if args.browser else DEFAULT_ORDER

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path.cwd() / "captures" / f"erp-{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    rec = Recorder(out)

    print("\nPing - ERP capture\n" + "-" * 40)
    async with async_playwright() as pw:
        opened = await open_browser(pw, order, rec)
        if not opened:
            shutil.rmtree(out, ignore_errors=True)
            sys.exit(1)
        browser, context, page = opened

        print("\nWords to hide in the saved copies (they become placeholders).")
        roll = await ask(" Your roll number / ERP user id (Enter to skip): ")
        extra = await ask(" Your name, email, phone - separated by commas (Enter to skip): ")
        words = [(roll, "<<MY_ROLL_NO>>")] if roll else []
        words += [(w.strip(), "<<MY_INFO>>") for w in extra.split(",") if len(w.strip()) >= 3]

        await page.goto(START_URL, wait_until="domcontentloaded")

        print("\nSTEP 1 - Log in yourself in the browser window that just opened")
        print(" (user id, password, security answer, Get OTP, type the OTP, Log In).")
        print(" Nothing you type there is saved.")
        await ask(" As soon as you see the ERP home page (before clicking anything else),\n press Enter here... ")
        await rec.drain()
        rec.phase = "browse"
        await rec.snapshot(context, "home")

        print("\nSTEP 2" + CHECKLIST)
        while True:
            cmd = await ask(f" [{rec.snapshots} snapshots so far] Enter = snapshot, type done = finish: ")
            if cmd.lower() in ("done", "d", "q", "quit", "exit"):
                break
            await asyncio.sleep(1.5)  # let late data arrive
            n = await rec.snapshot(context, "page")
            print(f"   snapshot {rec.snapshots} saved ({n} frame(s)).")

        await asyncio.sleep(2)
        await rec.drain()
        await rec.snapshot(context, "final")
        await browser.close()

    rec.log.sort(key=lambda e: e["seq"])
    (out / "network_log.json").write_text(json.dumps(rec.log, indent=1), encoding="utf-8")
    changed = redact_files(out, words)

    zip_path = out.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(out.parent))

    files = len(list((out / "downloads").iterdir())) + len(list((out / "network").glob("*.pdf")))
    print("\nDone.")
    print(f" Requests recorded : {len(rec.log)}")
    print(f" Snapshots         : {rec.snapshots}")
    print(f" PDFs / downloads  : {files}")
    print(f" Files with your words hidden: {changed}")
    print(f"\n Folder: {out}\n Zip   : {zip_path}")
    print("\n Screenshots and PDFs are NOT redacted (they contain your name and other")
    print(" students' names). Do not put this zip on GitHub - send it to Claude directly.")
    print(" Your ERP session times out by itself after 10 minutes.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped. Anything captured so far is in ./captures/")
