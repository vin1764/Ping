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


def _blank(text: str, roll: str) -> str:
    return re.sub(re.escape(roll), "<ROLL>", text or "", flags=re.I) if roll else (text or "")


def _links(html: str, roll: str) -> list[str]:
    """Every link and click handler on a page (where a file or page would open), roll number blanked."""
    out = []
    for m in re.finditer(r"""(?:href|onclick|src)\s*=\s*(["'])(.*?)\1""", html or "", re.I | re.S):
        v = re.sub(r"\s+", " ", m.group(2)).strip()
        if v and v not in ("#", "javascript:void(0)", "javascript:void(0);") and not v.startswith("data:"):
            out.append(_blank(v, roll)[:200])
    return list(dict.fromkeys(out))[:20]


def probe_jd(erp, roles, stored: dict, roll: str) -> None:
    """Where the job description of each "JD missing" role lives (and JP MorganChase's): the companies list's own
    document links for the role, the role popup, the "more details" popup and any link in the JD text. Prints
    company/role information only; downloads nothing, submits nothing (every request goes through the gate)."""
    from .parsers import _grid_rows, parse_role_popup
    from .relevance import no_jd
    js = getattr(erp, "placement_html", "") or ""
    print("\n===== companies page scripts: where its per-role links lead =====")
    for name in ("TPJNFDescription", "TPComDescription", "TPPPTDescription", "TPJNFView", "jnfMoreDet", "view1", "view2", "view3"):
        m = re.search(rf"function\s+{name}\s*\([^)]*\)\s*\{{.*?\n\s*\}}", js, re.S)
        print(f"--- {name}:", re.sub(r"\s+", " ", _blank(m.group(0), roll))[:700] if m else "(not found)")
    from .parsers import _call_args
    cells_by_id = {}
    for cells in _grid_rows(erp.companies_xml()):
        if len(cells) >= 13:
            jnf = _call_args(cells[3], "TPJNFView") or _call_args(cells[4], "TPJNFView")
            if len(jnf) >= 3:
                cells_by_id[f"{jnf[2]}:{jnf[1]}:{jnf[0]}"] = cells
    pick = [r for r in roles if no_jd((stored.get(r["id"]) or {}).get("job_description") or "")
            or "morgan" in r["company"].lower()]
    print(f"\n===== JD diagnosis: {len(pick)} roles (no usable JD in the database, plus JP MorganChase) =====")
    tally = {}
    for r in pick:
        jd = ((stored.get(r["id"]) or {}).get("job_description") or "").strip()
        cells = cells_by_id.get(r["id"]) or [""] * 13
        from .parsers import _text, _title
        cellmark = {k: _blank(cells[i], roll)[:300] for k, i in (("company doc", 1), ("PPT", 2), ("JNF doc", 7))}
        # an anchor is always there; a document only when the link has a label
        docs = {k: v for (k, i), v in zip((("company doc", 1), ("PPT", 2), ("JNF doc", 7)), cellmark.values())
                if _text(cells[i]) or _title(cells[i])}
        try:
            pop_html = erp.role_popup(r["yop"], r["com_id"], r["jnf_id"])
            pop = parse_role_popup(pop_html)
        except Exception as e:
            pop_html, pop = "", {"error": type(e).__name__}
        try:
            more_html = erp.role_more_details(r["yop"], r["com_id"], r["jnf_id"])
        except Exception:
            more_html = ""
        pop_jd = (pop.get("job_description") or "").strip()
        urls = re.findall(r"https?://\S+", jd + " " + pop_jd + " " + re.sub(r"<[^>]+>", " ", more_html))
        where = ("link" if urls else "attachment" if docs or re.search(r"\.(pdf|docx?)\b|AdmFile|download", " ".join(_links(pop_html, roll)), re.I)
                 else "detail" if len(pop_jd) > len(jd) + 40 else "mail" if re.search(r"mail", jd, re.I)
                 else "later" if re.search(r"will be shared|later|at the time", jd, re.I) else "none")
        tally[where] = tally.get(where, 0) + 1
        print(f"\n--- {r['company']} / {r['designation']}  [{where}]")
        print(f"    JD in the database ({len(jd)} chars): {jd[:160]!r}")
        print(f"    JD in the role popup ({len(pop_jd)} chars): {pop_jd[:160]!r}")
        print(f"    companies-list document links with a label: {docs or 'none'}")
        print(f"    companies-list cells (as served): {cellmark}")
        print(f"    role popup links: {_links(pop_html, roll)}")
        print(f"    'more details' links: {_links(more_html, roll)}")
        print(f"    URLs in the JD / popup / more details: {list(dict.fromkeys(u.rstrip(').,;') for u in urls))[:5]}")
    print(f"\nJD diagnosis, where the JD is: {tally}")


def probe(secrets, store=None) -> int:
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
        stored = {r["id"]: r for r in store.select("roles", {"is_sample": "is.false"})} if store else {}
        probe_jd(erp, roles, stored, secrets.erp_user_id)
        for r in roles[:0]:
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
