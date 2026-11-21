"""Build the demo from your real data, anonymised.

Kept as they are: company names, roles, pay, deadlines, notice wording, and
your applied / not-applied list (so applied -> shortlisted -> test room
still holds together).
Replaced: your roll number and name (fake ones), your CGPA (fake; your
number is removed from every sentence).
Removed: every other student's name, roll number and phone number (notice
contacts, offer lists), and everything from your mailbox.

`verify()` scans the finished data for your real roll number, email and
name, and for any roll-number or phone-number pattern left over. If it
finds anything, nothing is written.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from .config import IST

FAKE_ROLL = "22XY10042"
FAKE_NAME = "Demo Student"
FAKE_CGPA = 8.0
PREFIX = "sample:"
REAL = {"is_sample": "not.is.true"}

# Uppercase on purpose ("11thNovember" must not match); no word boundaries, because the ERP glues
# text together ("[name] [name] - 22XY00000The students...").
ROLL_RE = re.compile(r"\d{2}[A-Z]{2}[A-Z0-9]{5}")  # also back-to-back lists: "23CH3001023CH30020"
URL_RE = re.compile(r"(https?://\S+)")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
CONTACT_RE = re.compile(r"[A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){0,2}\s*\(\s*\[phone removed\]\s*\)")
_NAME = r"[A-Z][A-Za-z.]*(?:\s+[A-Z][A-Za-z.]*){0,3}"
NAME_ROLL_RE = re.compile(_NAME + r"\s*[-–:(,]?\s*\[roll removed\]\)?")          # "Name - ROLL", "Name ROLL"
ROLL_NAME_RE = re.compile(r"\[roll removed\]\s*[-–:,)]?\s*\d{0,3}\s*" + _NAME)     # "ROLL Name", "ROLL 20Name"
LEFTOVER_RE = re.compile(r"[A-Z][a-z]+\s+[A-Z][a-z]+\s*\[(?:roll|student) removed\]|\[(?:roll|student) removed\]\s*[A-Z][a-z]+\s+[A-Z][a-z]+")
YOUR_CG_RE = re.compile(r"\byour (?:CGPA )?\d{1,2}(?:\.\d+)?\b", re.I)
NAMEISH = re.compile(r"^[A-Za-z.]+(?:\s+[A-Za-z.]+)+$")


class Scrubber:
    def __init__(self, real_roll: str, real_name: str | None, mail: str | None):
        self.roll = (real_roll or "").strip()
        self.name = (real_name or "").strip()
        self.mail = (mail or "").strip()

    def text(self, s: str) -> str:
        """Scrub everything except links (a form link's random code can look like a roll number)."""
        if not s:
            return s
        parts = URL_RE.split(s)
        return "".join(p if i % 2 else self._plain(p) for i, p in enumerate(parts))

    def _plain(self, s: str) -> str:
        me = "\u0000ME\u0000"
        s = s.replace(FAKE_ROLL, me)  # the demo's own fake roll number stays
        if self.roll:
            s = re.sub(re.escape(self.roll), me, s, flags=re.I)
        if self.mail:
            s = re.sub(re.escape(self.mail), "[email removed]", s, flags=re.I)
        if len(self.name) > 3:
            s = re.sub(re.escape(self.name), FAKE_NAME, s, flags=re.I)
        s = PHONE_RE.sub("[phone removed]", s)
        s = CONTACT_RE.sub("[contact removed]", s)
        s = ROLL_RE.sub("[roll removed]", s)
        for _ in range(3):  # lists of students: names on either side of each roll
            s = NAME_ROLL_RE.sub("[roll removed]", s)
            s = ROLL_NAME_RE.sub("[roll removed]", s)
        s = re.sub(r"(?:\[roll removed\][\s,;]*)+", "[student removed] ", s)
        s = YOUR_CG_RE.sub("your CGPA", s)
        return s.replace(me, FAKE_ROLL)

    def walk(self, obj):
        if isinstance(obj, str):
            return self.text(obj)
        if isinstance(obj, list):
            return [self.walk(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.walk(v) for k, v in obj.items()}
        return obj


def _fake_row(header: list | None, row: list | None) -> list | None:
    """Your own row from a PDF: roll is already fake; the name cell becomes the fake name."""
    if not row:
        return row
    out = []
    for i, cell in enumerate(row):
        h = (header[i] if header and i < len(header) else "") or ""
        c = str(cell or "")
        if re.search(r"name|student", h, re.I) or (c and NAMEISH.match(c) and not re.search(
                r"room|lab|hall|slot|nalanda|vikramshila|complex|block|floor", c, re.I) and c != FAKE_ROLL):
            out.append(FAKE_NAME.upper() if c else c)
        else:
            out.append(cell)
    return out


def _fresh_items(roles, notices, checks, real_profile, stored_items, real_roll):
    """Rebuild the feed with today's rules (same code as the hourly run), keeping when each
    message was first posted so the chat reads in the right order."""
    from datetime import timedelta
    from .items import build_items
    from .matching import CompanyIndex
    from .notices import analyze
    now = datetime.now(IST)
    profile = {"roll": real_roll, "notice_types": ["PLACEMENT"], **{k: v for k, v in real_profile.items() if v is not None}}
    from .pdfs import refresh_details
    for c in checks:
        refresh_details(c, real_roll)
    index = CompanyIndex(roles)
    for n in notices:
        if (n.get("analysis") or {}).get("method") != "ai" and (n.get("text") or n.get("preview")):
            n["analysis"] = analyze(n, n.get("text") or n.get("preview"), index, real_roll, profile.get("name") or "")
    items = build_items(roles, [n for n in notices if n.get("analysis")], {c["notice_id"]: c for c in checks},
                        profile, now)
    starts = {r["id"]: r.get("apply_start") for r in roles}
    for it in items:
        old = stored_items.get(it["id"]) or {}
        first = old.get("first_seen")
        if not first:
            d = it.get("details") or {}
            if it["category"] == "reminder" and it.get("due_at"):
                first = (datetime.fromisoformat(it["due_at"]) - timedelta(hours=24)).isoformat()
            else:
                first = d.get("notice_time") or (starts.get((it.get("role_ids") or [None])[0])) or now.isoformat()
        if datetime.fromisoformat(first) > now:
            first = now.isoformat()
        it["first_seen"] = first
    return [i for i in items if i.get("category") != "email"]


def _prefix(v):
    return v if v is None or str(v).startswith(PREFIX) else f"{PREFIX}{v}"


def build_from_store(store, real_roll: str, mail: str) -> dict:
    prof_rows = store.select("profile", {"id": "eq.1"})
    real_profile = prof_rows[0] if prof_rows else {}
    real_name = real_profile.get("name")
    roles = store.select("roles", REAL)
    notices = store.select("notices", REAL)
    checks = store.select("pdf_checks", REAL)
    stored_items = {i["id"]: i for i in store.select("items", REAL)}
    items = _fresh_items(roles, notices, checks, real_profile, stored_items, real_roll)
    runs = sorted(store.select("runs", REAL), key=lambda r: r.get("started_at") or "", reverse=True)[:1]

    for r in roles:
        r["id"] = _prefix(r["id"])
        r["is_sample"] = True
    for n in notices:
        n["id"] = _prefix(n["id"])
        n["is_sample"] = True
        if isinstance(n.get("analysis"), dict):
            n["analysis"]["contacts"] = []
    for c in checks:
        c["notice_id"] = _prefix(c["notice_id"])
        c["my_row"] = _fake_row(c.get("header"), c.get("my_row"))
        c["is_sample"] = True
    for it in items:
        it["id"] = _prefix(it["id"])
        it["role_ids"] = [_prefix(x) for x in (it.get("role_ids") or [])]
        d = it.get("details") or {}
        for k in ("notice_key", "update_of", "updated_by"):
            if d.get(k):
                d[k] = _prefix(d[k])
        d.pop("mail_links", None)
        d["contacts"] = []
        if isinstance(d.get("pdf"), dict):
            d["pdf"]["my_row"] = _fake_row(d["pdf"].get("header"), d["pdf"].get("my_row"))
        it["details"] = d
        it["is_sample"] = True
        it["dismissed"] = False
        it["done"] = False
    run = []
    if runs:
        r = runs[0]
        counts = {k: v for k, v in (r.get("counts") or {}).items() if k not in ("dedupe_examples",)}
        run = [{**r, "id": "sample-run", "problems": [], "counts": counts, "is_sample": True}]
    profile = {
        "id": 2, "roll": FAKE_ROLL, "name": FAKE_NAME, "department": real_profile.get("department"),
        "degree": real_profile.get("degree"), "cgpa": FAKE_CGPA, "active_backlogs": False,
        "cv_names": ["Software CV", "Data CV", "Product CV"],
        "interested_companies": real_profile.get("interested_companies") or [],
        "not_interested_companies": real_profile.get("not_interested_companies") or [],
        "notice_types": real_profile.get("notice_types") or ["PLACEMENT"], "is_sample": True,
    }
    data = {"profile": profile, "roles": roles, "notices": notices, "pdf_checks": checks, "items": items,
            "emails": [], "contacts": [], "runs": run}
    data = Scrubber(real_roll, real_name, mail).walk(data)
    data["generated_at"] = datetime.now(IST).isoformat()
    data["about"] = ("Anonymised snapshot of a real Ping run: real companies, roles, pay, deadlines and notice "
                     "wording; fake roll number, name and CGPA; other students' details and all mail removed.")
    return data


def verify(data: dict, real_roll: str, mail: str, real_name: str | None) -> list[str]:
    text = json.dumps(data, default=str, ensure_ascii=False)
    problems = []
    if real_roll and real_roll.lower() in text.lower():
        problems.append("your real roll number is still in the demo")
    if mail and mail.lower() in text.lower():
        problems.append("your email address is still in the demo")
    if real_name and len(real_name) > 3 and real_name.lower() in text.lower():
        problems.append("your real name is still in the demo")
    plain = URL_RE.sub(" ", text)  # links keep their random codes; your own details are checked above, links included
    rolls = {m.group(0).upper() for m in ROLL_RE.finditer(plain)} - {FAKE_ROLL}
    if rolls:
        problems.append(f"{len(rolls)} other roll-number-like strings left")
    phones = PHONE_RE.findall(plain)
    if phones:
        problems.append(f"{len(phones)} phone-number-like strings left")
    names = LEFTOVER_RE.findall(plain)
    if names:
        problems.append(f"{len(names)} names still next to a removed roll number")
    return problems


def load_to_db(store, data: dict) -> dict:
    """Replace the demo rows the reviewer login sees (is_sample = true). Real rows are never touched."""
    counts = {}
    for table in ("items", "pdf_checks", "notices", "roles", "runs", "contacts", "emails"):
        store.delete(table, {"is_sample": "is.true"})
    store.upsert("profile", [data["profile"]])
    for table, key in (("roles", "id"), ("notices", "id"), ("pdf_checks", "notice_id"), ("items", "id"),
                       ("runs", "id")):
        rows = data[table]
        if rows:
            store.upsert(table, rows, key=key)
        counts[table] = len(rows)
    return counts
