"""One company, now: the ERP's notices for it and their attachments, read again (read-only, through the gate).

  python -m ping.run --mode diagnose --company FirstClub     (PING_MODE=diagnose, PING_COMPANY=…)
      prints what the ERP has for the company and what Ping stored and found, changes nothing
  python -m ping.run --mode recheck --company FirstClub      (the chat's "check FirstClub again")
      reads the company's notices and files again with today's code, saves the results, rebuilds the feed and
      writes the answer to the rechecks table (the page waits for it)

Privacy: as everywhere in Ping, only your own row and the table heading are kept from a file; the diagnosis prints
structure (pages, counts, how roll numbers are written) and where your roll was or wasn't found, never anyone else's.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .matching import compact
from .parsers import parse_notice_page, parse_notices
from .pdfs import check_attachment, inspect

REAL = {"is_sample": "is.false"}


def company_matches(n: dict, company: str) -> bool:
    want = compact(company)
    if not want:
        return False
    return want in compact(n.get("company") or "") or want in compact(n.get("subject") or "")


def links_in(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"https?://[^\s<>\"')\]]+", text or "")))[:10]


def diagnose(runner, company: str, log=print) -> int:
    """Report only; nothing is written."""
    profile = runner.profile()
    roll, name = profile["roll"], profile.get("name") or ""
    erp_id = (runner.secrets.roll or "").upper()
    raw = (runner.store.select("profile") or [{}])[0] if runner.store_ok else {}
    log(f"roll searched for: shape {re.sub(r'[0-9]', 'D', re.sub(r'[A-Z]', 'L', roll))}, "
        f"same as your ERP login id: {roll == erp_id}; profile.roll set: {bool(raw.get('roll'))}, "
        f"profile.roll == ERP id: {str(raw.get('roll') or '').upper() == erp_id}; profile updated_at: {raw.get('updated_at')}")
    stored = {n["id"]: n for n in runner.store.select("notices", REAL) if company_matches(n, company)}
    checks = {c["notice_id"]: c for c in runner.store.select("pdf_checks", REAL) if c["notice_id"] in stored}
    items = [it for it in runner.store.select("items") if compact(company) in compact(it.get("company") or "")]
    log(f"==== {company}: what Ping stored ====")
    for nid, n in sorted(stored.items(), key=lambda kv: kv[1].get("notice_time") or ""):
        c = checks.get(nid) or {}
        log(f"notice {nid} | {n.get('notice_time')} | {n.get('type')} | {n.get('subject')!r} | attachment={n.get('has_attachment')}"
            f" | kind={(n.get('analysis') or {}).get('kind')} | first_seen={n.get('first_seen')}")
        if c:
            log(f"    stored check: {c.get('status')} by={c.get('matched_by')} {c.get('format')} {c.get('pages')}p "
                f"{c.get('text_chars')} chars scanned={c.get('scanned')} ocr={c.get('ocr')} roll-like={c.get('roll_like_count')} "
                f"error={c.get('error')} checked_at={c.get('checked_at')}")
    for it in sorted(items, key=lambda x: x.get("first_seen") or ""):
        log(f"    item {it['id']} | {it.get('level')} | {it.get('pdf_status')} | {it.get('title')!r} | first_seen={it.get('first_seen')}")

    log(f"\n==== {company}: what the ERP has now ====")
    runner.login_stats = runner.erp.login()
    try:
        runner.erp.open_placement()
        board = parse_notices(runner.erp.notices_xml())
        mine = sorted([n for n in board if company_matches(n, company)], key=lambda n: n.get("notice_time") or "")
        log(f"notice board: {len(board)} notices, {len(mine)} for {company}")
        for n in mine:
            log(f"notice {n['id']} | {n['notice_time']} ({n.get('notice_time_text')}) | {n['type']} | {n['subject']!r} | "
                f"company={n['company']!r} | attachment={n['has_attachment']} | stored={'yes' if n['id'] in stored else 'NO'}")
            try:
                page = parse_notice_page(runner.erp.notice_text(n["year"], str(n["notice_id"])))
                text = page["text"] or ""
                old = (stored.get(n["id"]) or {}).get("text") or ""
                log(f"    text: {len(text)} chars; same as stored: {text.strip() == old.strip() if old else 'not stored'}; "
                    f"links: {[re.sub(r'^https?://([^/]+).*$', r'\1', l) for l in links_in(text)]}; "
                    f"roll in text: {bool(roll and re.search(re.escape(roll), text, re.I))}")
            except Exception as e:
                log(f"    text not read: {type(e).__name__}")
            if not n["has_attachment"]:
                continue
            try:
                data, ctype = runner.erp.notice_attachment(n["year"], str(n["notice_id"]))
            except Exception as e:
                log(f"    attachment not downloaded: {type(e).__name__}")
                continue
            info = inspect(data, roll, name, ctype)
            if erp_id and erp_id != roll:
                alt = inspect(data, erp_id, "", ctype, ocr=False)
                log(f"      with your ERP login id instead: {alt['found']}, nearest {alt['nearest_roll_distance']}")
            res = check_attachment(data, roll, name, ctype)
            log(f"    file: {info['format']} {info['bytes']} bytes, content-type {ctype!r}, error={info['error']}")
            for p in info["pages"]:
                log(f"      page {p['page']}: {p}")
            log(f"      roll shapes in the file: {info['roll_shapes']} (yours: {info['my_roll_shape']}); "
                f"roll-like total {info.get('roll_like_total')}; nearest same-length roll is {info['nearest_roll_distance']} edit(s) from yours; "
                f"rolls ending in your last five digits: {info.get('same_last5')}")
            log(f"      your roll: {info['found']}")
            log(f"      today's checker says: {res['status']} by={res['matched_by']} scanned={res['scanned']} "
                f"ocr={res['ocr']} roll-like={res['roll_like_count']} error={res['error']} section={bool(res.get('section'))}")
    finally:
        try:
            runner.erp.logout()
        except Exception:
            pass
    return 0
