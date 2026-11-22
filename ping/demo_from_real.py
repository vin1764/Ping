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

import hashlib
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
# text together ("TEST NAME - 22XY10051The students...").
ROLL_RE = re.compile(r"\d{2}[A-Z]{2}[A-Z0-9]{5}")  # also back-to-back lists: "22XY1005122XY10052"
URL_RE = re.compile(r"(https?://\S+)")
# Any 10-digit Indian mobile, digits grouped any way ("90000 12345", "900 001 2345", "9000-012-345"), with or
# without +91 / 91 / 0 in front, in brackets or not.
PHONE_RE = re.compile(r"(?<!\d)(?:\(?\+\s?91\)?[\s\-.]*|\b91[\s\-.]+|\b0[\s\-.]?)?[6-9](?:[\s\-.]?\d){9}(?![\s\-.]?\d)")
# Any other number with exactly 10 digits (landlines, toll-free), except dates like "21-11-2026 00:07"
TEN_DIGITS_RE = re.compile(r"(?<![\d\-./])\d(?:[\s\-.]?\d){9}(?![\s\-.]?\d)")
DATEISH = re.compile(r"\d{1,2}[\-./]\d{1,2}[\-./]\d{4}|\d{4}[\-./]\d{1,2}[\-./]\d{1,2}")
PLUS91_RE = re.compile(r"\(?\+\s?91\)?[\s\-.]*")
# Who to contact: keep the role word ("POC", "Placement coordinator"), drop every name after it, up to the
# end of the line, "CDC, IIT Kharagpur", or the end of the sentence.
CONTACT_LINE_RE = re.compile(
    r"(?i)(\b(?:POCs?|points? of contact|(?:student |placement |company |campus |cdc )?coordinators?|"
    r"contact (?:persons?|details|us)|for (?:any )?(?:queries|doubts)[^:\n]{0,30}|contacts?)\s*[:\-–]\s*)"
    r"([^\n]{1,200}?)(?=CDC\b|\\n|\n|(?<=[\w\])])\.(?:\s|$)|$)")
CONTACT_RE = re.compile(r"[A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){0,2}\s*\(\s*\[phone removed\]\s*\)")
# Meeting IDs and passcodes, also when the ERP glues them to the text around them ("...111Passcode: Ab12...")
MEETING_RE = re.compile(r"(?i)(meeting|webinar|conference|)\s*(id|number|no\.?)\s*[:\-]\s*\d{3}[\d ]{5,}\d")
PASSCODE_RE = re.compile(r"(?i)(?<![a-z])(pass ?code|meeting password|password|pwd)\s*[:\-]\s*\S+")
MEETING_URL = re.compile(r"(?i)teams\.(?:microsoft|live)\.com|zoom\.us|meet\.google\.com|webex\.com|gotomeet")
# meeting links written without https:// ("meet.google.com/abc-defg-hij"), glued to the next word or not
BARE_MEETING_RE = re.compile(r"(?i)(?:[\w-]+\.)?(?:teams\.(?:microsoft|live)\.com|zoom\.us|meet\.google\.com|webex\.com)"
                             r"/[\w\-/?=&.%]*?[\w-]{3}-[\w]{4}-[\w]{3}|(?:[\w-]+\.)?(?:teams\.(?:microsoft|live)\.com|"
                             r"zoom\.us|meet\.google\.com|webex\.com)/[\w\-/?=&.%]*")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
DEMO_EMAIL = "careers@example.com"
_NAME = r"[A-Z][A-Za-z.]*(?:\s+[A-Z][A-Za-z.]*){0,3}"
NAME_ROLL_RE = re.compile(_NAME + r"\s*[-–:(,]?\s*\[roll removed\]\)?")          # "Name - ROLL", "Name ROLL"
ROLL_NAME_RE = re.compile(r"\[roll removed\]\s*[-–:,)]?\s*\d{0,3}\s*" + _NAME)     # "ROLL Name", "ROLL 20Name"
LEFTOVER_RE = re.compile(r"[A-Z][a-z]+\s+[A-Z][a-z]+\s*\[(?:roll|student) removed\]|\[(?:roll|student) removed\]\s*[A-Z][a-z]+\s+[A-Z][a-z]+")
YOUR_CG_RE = re.compile(r"\byour (?:CGPA )?\d{1,2}(?:\.\d+)?\b", re.I)
NAMEISH = re.compile(r"^[A-Za-z.]+(?:\s+[A-Za-z.]+)+$")
# Names of real people seen in the real data; the build fails if any of them survives anywhere. Kept as
# SHA-256 of the lowercased name (one word, or two words joined by one space) so the names themselves
# aren't in the code. To add one: hashlib.sha256("first last".encode()).hexdigest().
DENY_HASHES = frozenset({
    "3af40b5168a5a66e941f92f93459cc81f055cd6d0b7e281b475f60c96f0bd89d",
    "2d8c49c359726b5d770713eab20cb5ae733a828d8870d314c301ce2cd0b32c2c",
    "3728a121efabad8dd43c044d9832ca3b8d79fe3d14055613dfdcce96c9405710",
    "6ac7f00933165014d1db908e1181ffa75bc7298e8143aa61062b0a08ac6366c0",
    "aa03bd0734ef137df356430385dedcd10ee6791b38925e88d1d9c3173e3a1a46",
    "da9660c38bcd7f409ec94a6c749af6c4cb1af22699071fc2d32a2d99acaeaf66",
})
WORD_RE = re.compile(r"[A-Za-z]+")


def _sha(w: str) -> str:
    return hashlib.sha256(w.lower().encode()).hexdigest()


def deny_hits(text: str, hashes=DENY_HASHES) -> list[tuple[int, int]]:
    """Spans of denylisted names in text: single words and two-word names."""
    words = list(WORD_RE.finditer(text))
    out = []
    for i, m in enumerate(words):
        if _sha(m.group(0)) in hashes:
            out.append((m.start(), m.end()))
        if i + 1 < len(words):
            n = words[i + 1]
            if text[m.end():n.start()] == " " and _sha(f"{m.group(0)} {n.group(0)}") in hashes:
                out.append((m.start(), n.end()))
    return out


# Words the owner asked to keep out of everything Ping publishes, stored hex-encoded so they don't appear in
# the code either. Replaced with a word of the same meaning, keeping the case of the first letter.
BANNED_WORDS = {bytes.fromhex("696e7374696e6374").decode(): ("intuition", "intuit")}


def _replace_banned(s: str) -> str:
    for word, (noun, stem) in BANNED_WORDS.items():
        def sub(m, noun=noun, stem=stem):
            tail = m.group(1)
            out = stem + tail if tail.startswith(("iv", "ual")) else noun + tail
            out = out.replace("intuitual", "intuitive")
            return out[0].upper() + out[1:] if m.group(0)[0].isupper() else out
        s = re.sub(rf"(?i)\b{word}(\w*)", sub, s)
    return s


def _banned_left(text: str) -> int:
    return sum(len(re.findall(rf"(?i){w}", text)) for w in BANNED_WORDS)


def _ten_digit_numbers(text: str) -> list[str]:
    return [m.group(0) for m in TEN_DIGITS_RE.finditer(text) if not DATEISH.search(m.group(0))
            and not DATEISH.search(text[max(0, m.start() - 6):m.end() + 6])]


class Scrubber:
    def __init__(self, real_roll: str, real_name: str | None, mail: str | None):
        self.roll = (real_roll or "").strip()
        self.name = (real_name or "").strip()
        self.mail = (mail or "").strip()

    def text(self, s: str) -> str:
        """Scrub everything; links are kept as they are (a form link's random code can look like a roll
        number), except meeting links, which are removed."""
        if not s:
            return s
        parts = URL_RE.split(s)
        return _replace_banned("".join(("[meeting link removed]" if MEETING_URL.search(p) else p) if i % 2
                                       else self._plain(p) for i, p in enumerate(parts)))

    def _plain(self, s: str) -> str:
        me = "\u0000ME\u0000"
        s = s.replace(FAKE_ROLL, me)  # the demo's own fake roll number stays
        if self.roll:
            s = re.sub(re.escape(self.roll), me, s, flags=re.I)
        if self.mail:
            s = re.sub(re.escape(self.mail), "[email removed]", s, flags=re.I)
        s = EMAIL_RE.sub(lambda m: m.group(0) if m.group(0).lower().endswith("example.com") else DEMO_EMAIL, s)
        if len(self.name) > 3:
            s = re.sub(re.escape(self.name), FAKE_NAME, s, flags=re.I)
        s = BARE_MEETING_RE.sub("[meeting link removed]", s)
        s = MEETING_RE.sub(lambda m: f"{(m.group(1) + ' ') if m.group(1) else ''}{m.group(2)}: [removed]", s)
        s = PASSCODE_RE.sub(lambda m: f"{m.group(1)}: [removed]", s)
        s = PHONE_RE.sub("[phone removed]", s)
        s = TEN_DIGITS_RE.sub(lambda m: m.group(0) if DATEISH.search(s[max(0, m.start() - 6):m.end() + 6])
                              else "[number removed]", s)
        s = PLUS91_RE.sub("", s)
        s = CONTACT_RE.sub("[contact removed]", s)
        s = CONTACT_LINE_RE.sub(lambda m: m.group(1) + "[contact removed]", s)
        s = ROLL_RE.sub("[roll removed]", s)
        for _ in range(3):  # lists of students: names on either side of each roll
            s = NAME_ROLL_RE.sub("[roll removed]", s)
            s = ROLL_NAME_RE.sub("[roll removed]", s)
        s = re.sub(r"(?:\[roll removed\][\s,;]*)+", "[student removed] ", s)
        s = YOUR_CG_RE.sub("your CGPA", s)
        for a, b in sorted(deny_hits(s), reverse=True):  # last line of defence for names we know are real
            s = s[:a] + "[name removed]" + s[b:]
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


def sample_mails(roles: list[dict], now: datetime) -> list[dict]:
    """Four made-up placement mails for the demo (the real mailbox never goes into it), so View demo shows how mail
    looks: a form with a deadline, a test link to complete by a time, an interview slot, a placement-office note.
    Companies are ones on the snapshot's list; senders and links are example.com; nothing comes from a real mail."""
    from datetime import timedelta
    from .mail_source import RULES_VERSION
    open_roles = sorted({r["company"] for r in roles if not r.get("applied") and r.get("apply_end")
                         and str(r["apply_end"]) > now.isoformat()})
    applied = sorted({r["company"] for r in roles if r.get("applied")})
    pool = open_roles + [c for c in applied if c not in open_roles] + sorted({r["company"] for r in roles})
    picks, firsts = [], set()
    for c in dict.fromkeys(pool):                  # three different companies ("Accenture Japan" and "Accenture
        first = (c.split() or [""])[0].lower()     # Solutions" would read as one)
        if first not in firsts:
            picks.append(c)
            firsts.add(first)
        if len(picks) == 3:
            break
    while len(picks) < 3:
        picks.append(f"Sample Company {len(picks) + 1}")
    at = lambda h: (now - timedelta(hours=h)).isoformat()  # noqa: E731
    day = lambda d, hh, mm=0: (now + timedelta(days=d)).replace(hour=hh, minute=mm, second=0, microsecond=0).isoformat()  # noqa: E731
    rows = [
        {"id": "demo-mail-1", "received_at": at(5), "sender": "Campus Hiring <campus@example.com>", "company": picks[0],
         "subject": f"{picks[0]}: fill the candidate details form", "kind": "form",
         "snippet": "Please fill the candidate details form before the assessment.",
         "links": ["https://example.com/forms/ping-demo-details"], "main_link": "https://example.com/forms/ping-demo-details",
         "due_at": day(5, 17), "event_at": None, "when_text": "Deadline: 5:00 PM", "pdf": None,
         "kept_because": "company", "rules_version": RULES_VERSION},
        {"id": "demo-mail-2", "received_at": at(4), "sender": "Assessments <invites@assess.example.com>", "company": picks[1],
         "subject": f"Invitation: {picks[1]} online assessment", "kind": "test",
         "snippet": "You have been invited to the online assessment. Complete it before the deadline.",
         "links": ["https://assess.example.com/test/ping-demo"], "main_link": "https://assess.example.com/test/ping-demo",
         "due_at": day(6, 23, 59), "event_at": None, "when_text": "Complete it by 11:59 PM", "pdf": None,
         "kept_because": "company:assessment", "rules_version": RULES_VERSION},
        {"id": "demo-mail-3", "received_at": at(3), "sender": "Talent Team <talent@example.com>", "company": picks[2],
         "subject": f"Interview schedule - {picks[2]}", "kind": "interview",
         "snippet": "Your interview slot is confirmed. The joining link is below.",
         "links": ["https://example.com/interview/ping-demo"], "main_link": "https://example.com/interview/ping-demo",
         "due_at": None, "event_at": day(3, 11), "when_text": "11:00 AM", "pdf": None,
         "kept_because": "company:interview", "rules_version": RULES_VERSION},
        {"id": "demo-mail-4", "received_at": at(2), "sender": "Placement Office <placement-office@example.com>", "company": None,
         "subject": "Placement season: dress code and reporting guidelines", "kind": "announcement",
         "snippet": "Please read the reporting guidelines for test days.", "links": [], "main_link": None,
         "due_at": None, "event_at": None, "when_text": None, "pdf": None,
         "kept_because": "placement_office", "rules_version": RULES_VERSION},
    ]
    return [{**r, "is_sample": True} for r in rows]


def add_sample_mails(data: dict) -> dict:
    """The four sample mails added to an existing snapshot (demo-data.json), at its own time, without rebuilding it
    from real data: the same feed code makes their messages. Idempotent: earlier sample mails are replaced."""
    from .eligibility import evaluate
    from .items import _mail_item, open_for_me_at
    from .matching import CompanyIndex
    now = datetime.fromisoformat(data["generated_at"])
    roles = data["roles"]
    profile = data["profile"]
    mails = sample_mails(roles, now)
    index = CompanyIndex(roles)
    elig = {r["id"]: evaluate(r, profile) for r in roles}
    items = [it for it in data["items"] if (it.get("details") or {}).get("via") != "email"]
    for m in mails:
        it = _mail_item(m, roles, elig, profile, now, index, open_for_me_at(roles, elig, profile, now))
        it.update({"id": _prefix(it["id"]), "is_sample": True, "dismissed": False, "done": False,
                   "first_seen": m["received_at"], "role_ids": [_prefix(x) for x in it.get("role_ids") or []]})
        items.append(it)
    data["items"] = items
    data["emails"] = [{**m, "id": _prefix(m["id"])} for m in mails]
    data["about"] = ("Anonymised snapshot of a real Ping run: real companies, roles, pay, deadlines and notice "
                     "wording; fake roll number, name and CGPA; other students' details and all real mail removed (the 4 "
                     "mails shown are made-up samples).")
    return data


def _fresh_items(roles, notices, checks, real_profile, stored_items, real_roll, emails=None):
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
                        profile, now, emails or [])
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
    # the real mailbox never goes into the demo: four made-up sample mails do, through the same feed code
    emails = sample_mails(roles, datetime.now(IST))
    items = _fresh_items(roles, notices, checks, real_profile, stored_items, real_roll, emails)
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
        if d.get("via") != "email":            # the sample mails' links are example.com; real mail links never come
            d.pop("mail_links", None)
            d.pop("mail", None)
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
            "emails": [{**e, "id": _prefix(e["id"])} for e in emails], "contacts": [], "runs": run}
    data = Scrubber(real_roll, real_name, mail).walk(data)
    data["generated_at"] = datetime.now(IST).isoformat()
    data["profile"]["updated_at"] = data["generated_at"]  # a demo session reads the snapshot time from here
    data["about"] = ("Anonymised snapshot of a real Ping run: real companies, roles, pay, deadlines and notice "
                     "wording; fake roll number, name and CGPA; other students' details and all real mail removed (the 4 "
                     "mails shown are made-up samples).")
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
    names = LEFTOVER_RE.findall(plain)
    if names:
        problems.append(f"{len(names)} names still next to a removed roll number")
    problems += final_check(data)
    return problems


def final_check(data) -> list[str]:
    """The last gate before anything is written: anywhere in the output (links included), no 10-digit number,
    no "+91", and none of the real names we know of. Any hit fails the build."""
    text = data if isinstance(data, str) else json.dumps(data, default=str, ensure_ascii=False)
    problems = []
    tens = _ten_digit_numbers(text)
    if tens:
        problems.append(f"{len(tens)} ten-digit numbers left (e.g. ...{tens[0][-4:]})")
    if "+91" in text:
        problems.append(f"{text.count('+91')} '+91' left")
    hits = deny_hits(text)
    if hits:
        problems.append(f"{len(hits)} real names from the denylist left")
    emails = {e for e in EMAIL_RE.findall(text) if not e.lower().endswith("example.com")}
    if emails:
        problems.append(f"{len(emails)} email addresses left")
    if _banned_left(text):
        problems.append(f"{_banned_left(text)} words from the banned list left")
    if MEETING_URL.search(text):
        problems.append("a meeting link is left")
    if re.search(r"(?i)pass ?code\s*[:\-]\s*(?!\[removed\])\S", text):
        problems.append("a meeting passcode is left")
    if re.search(r"(?i)\bid\s*[:\-]\s*\d{3}[\d ]{5,}\d", text):
        problems.append("a meeting ID is left")
    return problems


def load_to_db(store, data: dict) -> dict:
    """Replace the demo rows a one-click demo session sees (is_sample = true). Real rows are never touched."""
    counts = {}
    for table in ("items", "pdf_checks", "notices", "roles", "runs", "contacts", "emails"):
        store.delete(table, {"is_sample": "is.true"})
    # the demo's "now": a demo session reads the snapshot time from the profile's updated_at
    store.upsert("profile", [{**data["profile"], "updated_at": data["profile"].get("updated_at") or data["generated_at"]}])
    for table, key in (("roles", "id"), ("notices", "id"), ("pdf_checks", "notice_id"), ("items", "id"),
                       ("runs", "id"), ("emails", "id")):
        rows = data.get(table) or []
        if rows:
            store.upsert(table, rows, key=key)
        counts[table] = len(rows)
    return counts


if __name__ == "__main__":
    # python -m ping.demo_from_real add-mails   (adds the 4 sample mails to dashboard/demo-data.json, checked)
    import sys
    from pathlib import Path
    if sys.argv[1:] == ["add-mails"]:
        path = Path(__file__).resolve().parents[1] / "dashboard" / "demo-data.json"
        data = add_sample_mails(json.loads(path.read_text(encoding="utf-8")))
        problems = final_check(data)
        if problems:
            sys.exit("NOT written: " + "; ".join(problems))
        path.write_text(json.dumps(data, default=str, ensure_ascii=False), encoding="utf-8")
        print(f"added {len(data['emails'])} sample mails; check passed")
