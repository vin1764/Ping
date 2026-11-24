"""Job descriptions that come as a notice's attachment (ping/pdfs.py classifies the file: status "jd", the whole
text kept in pdf_checks.context, no phone numbers or emails) linked to that company's roles.

A role whose own JD is missing (nothing on the companies list, a link Ping can't open, or only the role popup's
details) takes the notice's: its own section when the PDF has one heading per role, else the whole PDF (every role
the PDF names, or every role of the company when it names none). Roles with a real JD of their own keep it. The role
says where it came from (jd_source "notice", jd_url the notice's file on the ERP, jd_note "the PDF on notice 1841
(24 Nov)"), so Ask Ping and the Companies tab can say so and link it.
"""

from __future__ import annotations

import re
from datetime import datetime

from .matching import tokens

NOTICE_FILE = "https://erp.iitkgp.ac.in/TrainingPlacementSSO/AdmFilePDF.htm?type=NOTICE&year={year}&id={id}"
# a role's own JD that isn't one: the notice's PDF fills these
WEAK = (None, "", "none", "link-unreadable", "detail", "notice", "mail")


def _day(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(str(iso)).strftime("%-d %b")
    except (TypeError, ValueError):
        return ""


def note_for(notice: dict) -> str:
    d = _day(notice.get("notice_time"))
    if notice.get("mail"):
        who = re.sub(r"\s*<[^>]*>", "", notice.get("sender") or "").strip() or "placement mail"
        return f"the {d} mail from {who}" + (" (PDF attached)" if notice.get("file") and notice["file"] != "(mail text)" else "")
    return f"the PDF on notice {notice.get('notice_id')}" + (f" ({d})" if d else "")


# ---------------------------------------------------------------- facts a document states (for the re-scan report)
CTC_RE = re.compile(r"\b(ctc|compensation|package|stipend|salary)\b[^\n]{0,40}?(\d[\d,.]*\s*(lpa|lakhs?|l\b|cr|inr|/-|per annum|k\b))", re.I)
ELIG_RE = re.compile(r"\b(cgpa|cpi|gpa)\b[^\n]{0,30}?\b([5-9](\.\d+)?)\b|eligible (branches|departments)|open to (all )?(branches|departments)", re.I)
DATE_RE = re.compile(r"\b(last date|deadline|apply by|before)\b[^\n]{0,30}?\b\d{1,2}(st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.I)


def doc_facts(text: str) -> set[str]:
    out = set()
    if CTC_RE.search(text or ""):
        out.add("ctc")
    if ELIG_RE.search(text or ""):
        out.add("eligibility")
    if DATE_RE.search(text or ""):
        out.add("date")
    return out


def coverage(roles: list[dict], store=None) -> dict:
    """How many roles have a real JD, and which facts the linked documents add to roles that lack them."""
    real = [r for r in roles if r.get("jd_source") not in (None, "", "none", "link-unreadable")]
    from_docs = [r for r in roles if r.get("jd_source") in ("notice", "mail")]
    facts = {"ctc": 0, "eligibility": 0, "date": 0}
    for r in from_docs:
        f = doc_facts(r.get("jd_text") or "")
        facts["ctc"] += "ctc" in f and not r.get("ctc")
        facts["eligibility"] += "eligibility" in f and not r.get("cgpa_cutoff")
        facts["date"] += "date" in f and not (r.get("effective_deadline") or r.get("apply_end"))
    by = {}
    for r in from_docs:
        by[r.get("company") or "?"] = by.get(r.get("company") or "?", 0) + 1
    return {"jd": len(real), "from_docs": len(from_docs), "doc_facts": facts, "gained_by_company": by}


def roles_of(notice: dict, index) -> list[dict]:
    """Every role of the companies the notice is about (its targets; else the notice's company)."""
    names = [t.get("company") for t in (notice.get("analysis") or {}).get("targets", []) if t.get("company")]
    if not names and notice.get("company"):
        names = [index.canonical(notice["company"])]
    out, seen = [], set()
    for n in names:
        for r in index.by_company.get(n or "", []):
            if r["id"] not in seen:
                seen.add(r["id"])
                out.append(r)
    return out


def _heading_at(text: str, designation: str) -> int:
    """Where a role's name starts a line (or a "Role:" / "Position:" line) in the JD text; -1 if it doesn't."""
    words = [w for w in re.split(r"\W+", re.sub(r"\([^)]*\)", " ", designation or "")) if w]
    if not words:
        return -1
    pat = r"[\W_]*".join(re.escape(w) for w in words)
    for m in re.finditer(rf"(?im)^[ \t•*\-\d.)]*(?:(?:role|position|designation|job title|profile)\s*[:\-–]\s*)?{pat}\b", text):
        return m.start()
    return -1


def split_by_role(text: str, roles: list[dict]) -> dict[str, tuple[str, bool]]:
    """{role id: (its JD text, True when it's that role's own section)}. Sections only when at least two roles each
    start a section of their own; the company's opening lines (before the first section) go with every section."""
    at = {r["id"]: _heading_at(text, r.get("designation") or "") for r in roles}
    found = sorted((p, rid) for rid, p in at.items() if p >= 0)
    starts = sorted({p for p, _ in found})
    if len(starts) >= 2:
        intro = text[:starts[0]].strip()
        intro = (intro[:1500] + "\n\n") if len(intro) > 80 else ""
        out = {}
        for p, rid in found:
            end = next((s for s in starts if s > p), len(text))
            out[rid] = (intro + text[p:end].strip(), True)
        for r in roles:
            if r["id"] not in out:
                out[r["id"]] = (text, False)       # a role the PDF doesn't head: the whole PDF
        return out
    named = [r for r in roles if at[r["id"]] >= 0 or _mentioned(text, r.get("designation") or "")]
    return {r["id"]: (text, False) for r in (named or roles)}


def _mentioned(text: str, designation: str) -> bool:
    t = set(tokens(text, True))
    d = [w for w in tokens(designation, True) if len(w) > 2]
    return bool(d) and all(w in t for w in d)


def mail_docs(mails: list[dict], index) -> tuple[dict, dict]:
    """JD documents from placement mail (the mail's attachment or its own text, status "jd") as notice-like rows, so
    the same linking applies: ({key: check}, {key: pseudo-notice})."""
    checks, notices = {}, {}
    for m in mails or []:
        doc = m.get("pdf") or {}
        if doc.get("status") != "jd" or not (doc.get("context") or "").strip() or not m.get("company"):
            continue
        key = f"mail:{m['id']}"
        checks[key] = doc
        notices[key] = {"id": key, "mail": True, "company": m["company"], "notice_time": m.get("received_at"),
                        "sender": m.get("sender"), "subject": m.get("subject"), "file": doc.get("file"),
                        "analysis": {"targets": [{"company": index.canonical(m["company"])}]}}
    return checks, notices


def apply(checks: dict, notices: dict, roles: list[dict], index, mails: list[dict] | None = None) -> tuple[list[dict], dict]:
    """The role rows to update from the JD files on notices and in placement mail (newest first), and counts:
    {jd_files, roles_linked, roles_gained (had no JD before), sections}."""
    mc, mn = mail_docs(mails or [], index)
    checks, notices = {**checks, **mc}, {**notices, **mn}
    jd_checks = [(nid, c) for nid, c in checks.items() if (c or {}).get("status") == "jd" and (c.get("context") or "").strip()]
    # the same PDF posted again (a reminder, an extension): one document, the first posting, "posted again as 1860"
    import hashlib
    key = lambda c: hashlib.sha1(re.sub(r"\s+", " ", c["context"]).strip().encode()).hexdigest()  # noqa: E731
    first: dict = {}
    for nid, c in sorted(jd_checks, key=lambda x: str((notices.get(x[0]) or {}).get("notice_time") or "")):
        first.setdefault(key(c), []).append(nid)
    reposts = {ids[0]: ids[1:] for ids in first.values()}
    jd_checks = [(nid, c) for nid, c in jd_checks if nid in reposts]
    jd_checks.sort(key=lambda x: str((notices.get(x[0]) or {}).get("notice_time") or ""), reverse=True)
    by_id = {r["id"]: r for r in roles}
    taken, ups, stats = set(), [], {"jd_files": len(jd_checks), "roles_linked": 0, "roles_gained": 0, "sections": 0,
                                    "companies": {}}
    for nid, c in jd_checks:
        n = notices.get(nid)
        if not n:
            continue
        rs = [r for r in roles_of(n, index) if r["id"] not in taken]
        if not rs:
            continue
        url = None if n.get("mail") else NOTICE_FILE.format(year=n.get("year", ""), id=n.get("notice_id", ""))
        for rid, (text, own) in split_by_role(c["context"], rs).items():
            r = by_id.get(rid) or {}
            if r.get("jd_source") not in WEAK:
                continue                                   # a real JD of its own: kept
            taken.add(rid)
            again = [str((notices.get(x) or {}).get("notice_id") or "") for x in reposts.get(nid, [])]
            note = note_for(n)
            if again and not n.get("mail"):
                note = note[:-1] + f"; posted again as {', '.join(a for a in again if a)})" if note.endswith(")") else note
            row = {"id": rid, "jd_text": text[:20000], "jd_source": "mail" if n.get("mail") else "notice", "jd_url": url,
                   "jd_note": note + ("" if own else (" (one PDF for several roles)" if len(rs) > 1 else ""))}
            stats["roles_linked"] += 1
            stats["sections"] += own
            if r.get("jd_source") not in ("notice", "mail"):
                stats["roles_gained"] += 1
                co = r.get("company") or n.get("company") or "?"
                stats["companies"][co] = stats["companies"].get(co, 0) + 1
            if any(r.get(k) != v for k, v in row.items()):
                ups.append(row)
                r.update(row)
    return ups, stats
