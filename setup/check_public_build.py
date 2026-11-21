"""The last gate before the dashboard is pushed to the PUBLIC repo: fail if the built files contain anything
that must stay private.

    python setup/check_public_build.py _site

Checks every file in the folder (and that only the expected files are there) for: a Supabase secret key
(sb_secret_), a service_role key, a Google API key (AIza), "+91", any 10-digit number outside the made-up
90000 xxxxx range (dates aren't numbers), your ERP roll number (ERP_USER_ID) and email (MAIL_ADDRESS), and the
words in ping/demo_from_real.BANNED_WORDS. The Supabase URL and publishable key in config.js are public by
design (the browser needs them; Row Level Security protects the data).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXPECTED = {"index.html", "app.js", "onboarding.js", "names.js", "live.js", "today.js", "answer_rules.js", "help.js", "setup.html", "style.css", "config.js", "demo-data.json", "README.md", ".nojekyll",
            "manifest.webmanifest", "sw.js"}
# the installable app's icons: the one sub-folder allowed, these files only (PNGs are images: no text checks)
ICONS = {"icon-192.png", "icon-512.png", "maskable-512.png", "apple-touch-icon.png", "badge-96.png", "favicon-32.png",
         "ping.svg", "ping-maskable.svg", "badge.svg", "ios-install.svg"}
LITERALS = ("sb_secret_", "service_role", "AIza", "+91")
TEN = re.compile(r"(?<![\d\-./])\d(?:[ \-.]?\d){9}(?![ \-.]?\d)")
DATE = re.compile(r"\d{1,2}[\-./]\d{1,2}[\-./]\d{4}|\d{4}[\-./]\d{1,2}[\-./]\d{1,2}")
FAKE = re.compile(r"^9\s?0000")


def problems_in(folder: Path, roll: str = "", email: str = "") -> list[str]:
    from ping.demo_from_real import BANNED_WORDS
    out = []
    files = {p.name for p in folder.iterdir() if p.is_file()}
    extra = files - EXPECTED
    missing = EXPECTED - files
    if extra:
        out.append(f"unexpected files: {sorted(extra)}")
    if missing:
        out.append(f"missing files: {sorted(missing)}")
    dirs = {p.name for p in folder.iterdir() if p.is_dir() and p.name != ".git"}
    if dirs - {"icons"}:
        out.append(f"unexpected sub-folders: {sorted(dirs - {'icons'})}")
    icons = folder / "icons"
    if icons.is_dir():
        have = {p.name for p in icons.iterdir()}
        if have - ICONS:
            out.append(f"unexpected files in icons/: {sorted(have - ICONS)}")
        if any(p.is_dir() for p in icons.iterdir()):
            out.append("unexpected sub-folders in icons/")
    texts = [p for p in folder.iterdir() if p.is_file()] + ([p for p in icons.iterdir() if p.suffix == ".svg"] if icons.is_dir() else [])
    for path in sorted(texts):
        text = path.read_text(encoding="utf-8", errors="replace")
        low = text.lower()
        for lit in LITERALS:
            if lit in text:
                out.append(f"{path.name}: contains '{lit}' ({text.count(lit)}x)")
        for m in TEN.finditer(text):
            ctx = text[max(0, m.start() - 6):m.end() + 6]
            if not DATE.search(ctx) and not FAKE.match(m.group(0)):
                out.append(f"{path.name}: a 10-digit number (...{m.group(0)[-4:]})")
                break
        if roll and roll.lower() in low:
            out.append(f"{path.name}: contains your roll number")
        if email and email.lower() in low:
            out.append(f"{path.name}: contains your email address")
        for word in BANNED_WORDS:
            if word in low:
                out.append(f"{path.name}: contains a banned word")
    return out


def main(argv: list[str]) -> int:
    folder = Path(argv[0] if argv else "_site")
    roll, email = os.environ.get("ERP_USER_ID", "").strip(), os.environ.get("MAIL_ADDRESS", "").strip()
    if not roll or not email:
        print("note: ERP_USER_ID / MAIL_ADDRESS not set here, so your roll number and email aren't checked")
    found = problems_in(folder, roll, email)
    for p in found:
        print(f"BLOCKED: {p}")
    print(f"checked {len(list(folder.iterdir()))} files in {folder}: " + ("clean" if not found else f"{len(found)} problems"))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
