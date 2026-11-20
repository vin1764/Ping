"""Read one notice: what kind it is, which companies/roles, to-dos, dates,
links, venue, contacts. Rules first; an optional AI model can be plugged in
for deadlines and company lists when the rules come back empty (see ai.py)."""

from __future__ import annotations

import re
from datetime import datetime

from . import ai
from .dates import Moment, find_moments
from .matching import CompanyIndex, is_generic, roles_named_in, tokens

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+?(?=(?:Deadline|Interested|Note|Venue|POC|CDC)\b|[\s<>\"')\]]|$)")
FORM_RE = re.compile(r"forms\.gle|docs\.google\.com/forms|forms\.office|form", re.I)
PHONE_POC = re.compile(r"([A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){0,2})\s*\(\s*((?:\+?91[\s-]?)?\d[\d\s-]{8,13}\d)\s*\)")
VENUE_RE = re.compile(r"(?:Venue|Reporting Venue|Location)\s*[:\-]\s*([^\n]{2,80}?)(?=\s*(?:Date|Reporting|Time|POC|Students|Note|$|\n))", re.I)
ENTRY_RE = re.compile(
    r"(?:^|\n|(?<=[.)\s]))(?P<num>\d{1,2})\s*\.\s*"
    r"(?:\[(?P<tag>[^\]]{1,30})\]\s*)?"
    r"(?P<name>[A-Za-z0-9&.,'/\- ]{2,80}?)\s*"
    r"\((?:Profiles?|Roles?)\s*:\s*(?P<profiles>[^)]*)\)"
    r"(?:\s*\((?P<when>[^)]*\d[^)]*)\))?", re.I)
TIME_RANGE = re.compile(r"(\d{1,2}(?::\d{2})?\s*[AP]M)\s*(?:-|–|to)?\s*(\d{1,2}(?::\d{2})?\s*[AP]M)?(?:\s*,\s*(.*))?", re.I)
ROLE_PHRASES = [
    re.compile(r"for the roles? of\s*\(([^)]+)\)", re.I),
    re.compile(r"for the roles? of\s+([^,.\n(]+?)(?:\s+has|\s+have|\s+is|\s+are|,|\.|\n|$)", re.I),
    re.compile(r"\(Profiles?\s*:\s*([^)]*)\)", re.I),
]

KINDS = ("apply_open", "deadline_extended", "form", "test", "test_rooms", "shortlist", "result",
         "ppt", "ppo", "schedule", "info")


def classify(subject: str, text: str) -> str:
    s = (subject or "").lower()
    t = text or ""
    if s.startswith("cv submission"):
        return "apply_open"
    if s.startswith("date extension"):
        return "deadline_extended"
    if s.startswith("additional requirement"):
        return "form"
    rooms_now = re.search(r"room allocation|seating", t, re.I) and not re.search(
        r"room allocation[^.\n]{0,40}will be (?:released|shared)", t, re.I)
    if s.startswith("shortlist"):
        return "test_rooms" if rooms_now else "shortlist"
    if s.startswith("result"):
        return "result"
    if s.startswith("ppo"):
        return "ppo"
    if s.startswith("ppt"):
        return "ppt"
    if s.startswith("schedule") or s.startswith("re-schedule"):
        if re.search(r"\[TEST\]|\btest\b|assessment", t, re.I):
            return "test"
        if re.search(r"\[PPT|placement talk|pre-placement|\bppt\b", t, re.I):
            return "ppt"
        return "schedule"
    # Urgent / General / anything new: read the text
    if rooms_now:
        return "test_rooms"
    if re.search(r"shortlist", t, re.I):
        return "shortlist"
    if re.search(r"\b(result|selected|offer(?:ed)? to)\b", t, re.I):
        return "result"
    if re.search(r"extended|extension", t, re.I) and re.search(r"cv|submission|apply|deadline", t, re.I):
        return "deadline_extended"
    if re.search(r"open(?:ed)? for cv submission|cv submission .* opened", t, re.I):
        return "apply_open"
    if re.search(r"\b(test|assessment|exam|interview)\b", t, re.I) and re.search(r"scheduled|link|onwards|slot", t, re.I):
        return "test"
    if re.search(r"\bform\b", t, re.I) and re.search(r"fill|link|deadline", t, re.I):
        return "form"
    if re.search(r"placement talk|\bppt\b|workshop|seminar", t, re.I):
        return "ppt"
    return "info"


def split_profiles(raw: str) -> list[str]:
    parts = re.split(r",|\band\b|/(?=\s*[A-Z])", raw or "")
    return [p.strip(" .-") for p in parts if p.strip(" .-")]


def parse_entries(text: str, ref: datetime, day: datetime | None) -> list[dict]:
    """Numbered lists: '1. ATHER ENERGY (Profile: All)', '2. [TEST] GROWW (Profile: X) (3:00 PM  4:00 PM)'."""
    out = []
    for m in ENTRY_RE.finditer(text or ""):
        name = re.sub(r"\s+", " ", m.group("name")).strip(" .,-")
        if not name or len(tokens(name)) == 0:
            continue
        entry = {"name": name, "tag": (m.group("tag") or "").strip() or None,
                 "profiles": split_profiles(m.group("profiles")), "when_text": m.group("when")}
        if m.group("when"):
            tr = TIME_RANGE.search(m.group("when"))
            base = day
            if tr and tr.group(3):
                ds = find_moments(tr.group(3), ref)
                if ds:
                    base = ds[0].at
            if tr and base is not None:
                ms = find_moments(f"{base.strftime('%d %B %Y')} {tr.group(1)}", ref)
                if ms and ms[0].has_time:
                    entry["start"] = ms[0].at.isoformat()
                if tr.group(2):
                    me = find_moments(f"{base.strftime('%d %B %Y')} {tr.group(2)}", ref)
                    if me and me[0].has_time:
                        entry["end"] = me[0].at.isoformat()
        out.append(entry)
    return out


def role_phrases(text: str) -> list[str]:
    found = []
    for pat in ROLE_PHRASES:
        for m in pat.finditer(text or ""):
            found += split_profiles(m.group(1))
    return list(dict.fromkeys(found))


def analyze(notice: dict, text: str, index: CompanyIndex, roll: str = "", name: str = "",
            ai_cfg: dict | None = None) -> dict:
    ref = datetime.fromisoformat(notice["notice_time"]) if notice.get("notice_time") else datetime.now()
    kind = classify(notice.get("subject", ""), text)
    moments = find_moments(text, ref)
    day_dates = [m for m in moments]
    day = day_dates[0].at if day_dates else None
    entries = parse_entries(text, ref, day)
    links = list(dict.fromkeys(u.rstrip(".,;") for u in URL_RE.findall(text or "")))
    forms = [l for l in links if FORM_RE.search(l)]
    contacts = [{"name": n.strip(), "phone": re.sub(r"[\s-]", "", p)} for n, p in PHONE_POC.findall(text or "")
                if not re.match(r"(?i)poc|pocs|contact", n.strip())]
    venue_m = VENUE_RE.search(text or "")
    mentions_me = bool(roll) and re.search(rf"\b{re.escape(roll)}\b", text or "", re.I) is not None
    if not mentions_me and name and len(name) > 4:
        mentions_me = re.search(re.escape(name), text or "", re.I) is not None
    email_hint = bool(re.search(r"(shared|sent|mailed|communicated)\b.{0,60}\b(e-?mail|mail ids?|email ids?)|"
                                r"check your (?:e-?mail|mail)", text or "", re.I))

    # ---- which companies
    col = (notice.get("company") or "").strip()
    targets = []
    unsure = []
    if col and col.lower() != "multiple companies" and not is_generic(col):
        m = index.match(col, text)
        if m.company:
            targets.append({"name": col, "company": m.company, "profiles": role_phrases(text), "score": m.score})
        elif m.unsure:
            unsure.append({"name": col, "candidates": m.candidates})
        else:
            targets.append({"name": col, "company": None, "profiles": role_phrases(text), "score": 0.0})
    else:
        for e in entries:
            m = index.match(e["name"], text)
            t = {"name": e["name"], "company": m.company, "profiles": e["profiles"], "score": m.score,
                 "tag": e.get("tag"), "start": e.get("start"), "end": e.get("end")}
            if m.company or not m.unsure:
                targets.append(t)
            else:
                unsure.append({"name": e["name"], "candidates": m.candidates})
        if not entries:
            for c in index.scan_text(text):
                targets.append({"name": c, "company": c, "profiles": role_phrases(text), "score": 0.9})

    deadlines = [m for m in moments if m.kind == "deadline"]
    events = [m for m in moments if m.kind in ("event", "date") and m.has_time]
    method = "rules"
    misses = []
    if kind in ("apply_open", "deadline_extended", "form") and not deadlines:
        misses.append("no deadline found")
    if (col.lower() == "multiple companies" or is_generic(col)) and not targets and not unsure \
            and kind not in ("info", "schedule"):
        misses.append("no companies found in a multi-company notice")
    if misses and ai_cfg and ai_cfg.get("provider"):
        better = ai.refine_notice(text, ref, [c for c in index.by_company], ai_cfg)
        if better:
            method = "ai"
            for d in better.get("deadlines", []):
                deadlines.append(Moment(datetime.fromisoformat(d["at"]), "deadline", d.get("text", ""), True))
            for c in better.get("companies", []):
                m = index.match(c.get("name", ""), text)
                targets.append({"name": c.get("name"), "company": m.company, "profiles": c.get("profiles", []),
                                "score": m.score})

    todos = []
    first_deadline = min(deadlines, key=lambda m: m.at) if deadlines else None
    if kind in ("apply_open", "deadline_extended") or re.search(r"apply on the portal", text or "", re.I):
        todos.append({"action": "apply", "due": first_deadline.at.isoformat() if first_deadline else None,
                      "due_text": first_deadline.text if first_deadline else None})
    for f in forms:
        todos.append({"action": "fill_form", "link": f,
                      "due": first_deadline.at.isoformat() if first_deadline else None,
                      "due_text": first_deadline.text if first_deadline else None})
    if kind == "ppo" and re.search(r"acceptance|accept", text or "", re.I) and mentions_me:
        todos.append({"action": "accept_offer", "due": first_deadline.at.isoformat() if first_deadline else None})
    if kind not in ("apply_open", "deadline_extended", "form") and first_deadline:
        todos.append({"action": "submit", "due": first_deadline.at.isoformat(), "due_text": first_deadline.text})

    return {
        "kind": kind,
        "targets": targets,
        "unsure": unsure,
        "entries": entries,
        "deadlines": [m.as_dict() for m in deadlines],
        "events": [m.as_dict() for m in events],
        "todos": todos,
        "links": links,
        "forms": forms,
        "contacts": contacts,
        "venue": venue_m.group(1).strip() if venue_m else None,
        "mentions_me": mentions_me,
        "email_hint": email_hint,
        "method": method,
        "rule_misses": misses,
    }


def roles_for_target(target: dict, index: CompanyIndex, kind: str, text: str) -> tuple[list[dict], str]:
    """Pick roles: named in text > (test/shortlist) written-test roles I applied to > roles I applied to > all."""
    roles = index.by_company.get(target.get("company") or "", [])
    if not roles:
        return [], "no roles"
    profiles = target.get("profiles") or []
    if profiles and not any(p.lower() == "all" for p in profiles):
        named = [r for r in roles if any(_same_role(p, r["designation"]) for p in profiles)]
        if named:
            return named, "role named in notice"
    named = roles_named_in(text, roles)
    if named:
        return named, "role named in notice"
    applied = [r for r in roles if r.get("applied")]
    if kind in ("test", "test_rooms", "shortlist") and applied:
        written = [r for r in applied if r.get("has_written_test")]
        if written:
            return written, "roles with a written test that you applied to"
    if applied:
        return applied, "roles you applied to"
    return roles, "all roles of this company"


def _same_role(profile: str, designation: str) -> bool:
    a, b = set(tokens(profile, True)), set(tokens(designation, True))
    if not a or not b:
        return False
    return a <= b or b <= a or len(a & b) / len(a | b) >= 0.6
