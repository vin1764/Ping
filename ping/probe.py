"""Diagnostics: log in, print the *layout* of pages Ping had to guess, log out.

Prints only company/job information from a role's "more details" popup, with
your roll number blanked. Never prints notices, PDFs or anything personal.
Run from GitHub: Actions > Ping > Run workflow > mode 'probe'.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .erp import ErpClient
from .gate import Gate
from .mailbox import Mailbox
from .parsers import parse_companies, parse_more_details


def _skeleton(html: str, roll: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    tags = {}
    for el in soup.find_all(True):
        tags[el.name] = tags.get(el.name, 0) + 1
    text = soup.get_text("\n")
    text = re.sub(re.escape(roll), "<ROLL>", text, flags=re.I)
    text = re.sub(r"\+?\d[\d\s-]{8,}\d", "<NUMBER>", text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return f"tags: {dict(sorted(tags.items(), key=lambda x: -x[1])[:15])}\n" + "\n".join(lines[:120])


def probe(secrets) -> int:
    from datetime import datetime
    from . import ai
    from .config import IST
    if secrets.ai.get("provider"):
        test = ("The CV submission of Northwind (made-up company) closes once the clock strikes five in the "
                "evening on the twenty-second of November, 2026.")
        res = ai.refine_notice(test, datetime(2026, 11, 20, tzinfo=IST), ["Northwind"], secrets.ai)
        print(f"AI fallback check ({secrets.ai.get('model')}): {res} | stats {ai.stats}")
    mb = Mailbox(secrets.mail_address, secrets.mail_app_password)
    erp = ErpClient(Gate(), secrets, mb, log=print)
    try:
        erp.login()
        print(f"OTP mail came from: {mb.last_otp_sender}")
        erp.open_placement()
        roles = parse_companies(erp.companies_xml())
        for r in roles[:2]:
            html = erp.role_more_details(r["yop"], r["com_id"], r["jnf_id"])
            print(f"\n===== more details: {r['company']} / {r['designation']} ({len(html)} bytes) =====")
            print(_skeleton(html, secrets.roll))
            print("parsed fields:", list(parse_more_details(html)["fields"])[:30])
            raw = re.sub(re.escape(secrets.erp_user_id), "<ROLL>", html, flags=re.I)
            body = raw[raw.lower().find("<body"):] if "<body" in raw.lower() else raw
            print("----- html (first 4000 chars of body) -----")
            print(re.sub(r"\s+", " ", re.sub(r"(?is)<script.*?</script>", "", body))[:4000])
        return 0
    finally:
        erp.logout()
        mb.close()
