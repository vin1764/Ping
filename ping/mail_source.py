"""The institute mailbox as a source: placement mail only, read-only, privacy-first (docs/SECURITY.md, "Mailbox").

Two steps, so a mail that isn't about placements is never read beyond its headers:

1. scope(head): From, Subject, Date and List-Unsubscribe / Precedence only. A mail is kept when
   - it comes from the placement office (a CDC / placement / career-development / training-and-placement address,
     or an address in PING_PLACEMENT_SENDERS), or
   - it names a company in the ERP companies list (subject, sender name or sender domain; the same company matching
     as notices, incl. "PineLabs" for "Pine Labs" and one typo in a long name), or
   - it comes from an online-test platform, or its subject carries a placement signal: test link, assessment,
     shortlist, interview, pre-placement talk / PPT, offer letter / PPO, placement, recruitment, campus drive;
     "form", "deadline", "offer", "registration" or "last date" count only next to a word like internship, job,
     role, hiring, campus, CV or candidate.
   Never kept: OTP / verification-code mails (used for the ERP login only, never stored or shown), account and
   shopping mails (security alert, password, receipt, order...), job-board alerts (LinkedIn, Naukri...), and bulk
   mail (List-Unsubscribe) unless it is from the placement office, a listed company or a test platform.
2. read(): for kept mails only, the whole message: company, kind, deadline / date-time, links, and PDF / Excel
   attachments through the notice attachment checker (only your row and the table heading are kept).

Nothing here changes "applied": that comes from the ERP alone.
"""

from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .dates import find_moments
from .mailbox import Attachment, Head, Mail, extract_otp
from .matching import CompanyIndex, compact, tokens
from .pdfs import check_attachment

RULES_VERSION = 2   # 2: a JD / role description (attachment or the mail itself) is kept whole
KINDS = ("form", "test", "interview", "shortlist", "ppt", "offer", "announcement")

OTP_RE = re.compile(r"\botp\b|one[\s-]*time[\s-]*pass(?:word|code)?|verification code|login code|"
                    r"security code|sign[\s-]*in code", re.I)
PLACEMENT_SENDER = re.compile(
    r"\b(cdc|placements?|placementcell|career\s*development|careerdevelopment|tnp|t\s*(?:&|and)\s*p|"
    r"training\s*(?:&|and)\s*placement|recruitment\s*cell)\b", re.I)
TEST_PLATFORMS = ("hackerrank", "hackerearth", "mettl", "codility", "codesignal", "imocha", "shl", "aon",
                  "talview", "hirepro", "amcat", "cocubes", "glider", "testgorilla", "karat", "mercer",
                  "superset", "joinsuperset", "hirevue", "interviewbit", "myanatomy", "eklavvya")
JOB_BOARDS = ("linkedin", "naukri", "indeed", "glassdoor", "internshala", "instahyre", "foundit", "monster",
              "apna", "cutshort", "wellfound", "angel", "timesjobs", "shine", "iimjobs", "hirist")
MAIL_HOSTS = ("gmail", "googlemail", "outlook", "hotmail", "yahoo", "live", "icloud", "proton", "protonmail",
              "rediffmail", "zoho", "mail", "email", "ac", "edu", "co", "com", "in", "org", "net", "io")
NOT_PLACEMENT = re.compile(
    r"security alert|sign[\s-]*in attempt|new sign[\s-]*in|password|verify your (?:e-?mail|account)|receipt|invoice|"
    r"\border\b.{0,40}\b(?:confirmed|shipped|placed|delivered|dispatched)|refund|"
    r"payment (?:received|successful|due|failed)|"
    r"subscription|newsletter|unsubscribe|% off|\bsale\b|cashback|coupon|webinar recording", re.I)
STRONG = re.compile(
    r"test link|assessment|online test|coding (?:test|round|challenge)|aptitude test|written test|"
    r"shortlist|interview|pre[\s-]*placement talk|offer letter|job offer|pre[\s-]*placement offer|"
    r"placement|recruitment|campus (?:drive|hiring|recruitment)|hiring process|selection process", re.I)
STRONG_CASE = re.compile(r"\bPPT\b|\bPPO\b")
WEAK = re.compile(r"\bforms?\b|deadline|\boffer\b|registration|last date|\bdue\b", re.I)
CONTEXT = re.compile(r"intern(?:ship)?|\bjob\b|\broles?\b|hiring|campus|\bcv\b|resume|candidate|"
                     r"selection|recruit|\bdrive\b|\bctc\b|stipend|profile", re.I)

FORM_LINK = re.compile(r"forms\.gle|/forms/|docs\.google\.com/forms|forms\.office\.com|forms\.microsoft|typeform\.com|"
                       r"jotform|zoho\.\w+/forms|airtable\.com/shr", re.I)
TEST_LINK = re.compile(r"|".join(TEST_PLATFORMS) + r"|/test|/assess|assessment|/exam|quiz", re.I)
MEET_LINK = re.compile(r"meet\.google\.com|zoom\.us|teams\.microsoft|webex", re.I)
JUNK_LINK = re.compile(r"unsubscribe|list-manage|/track|/open\?|pixel|\.(?:png|gif|jpe?g)(?:\?|$)|"
                       r"googleusercontent|mailto:|/preferences|manage[-_]?subscription", re.I)


@dataclass
class Verdict:
    keep: bool
    because: str                       # placement_office | company | test_platform | signal | otp | not_placement | ...
    company: str | None = None
    signal: str | None = None


@dataclass
class Stats:
    headers_seen: int = 0
    kept: int = 0
    bodies_read: int = 0
    attachments_read: int = 0
    otp_skipped: int = 0
    dropped: dict = field(default_factory=dict)
    kept_because: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"headers_seen": self.headers_seen, "kept": self.kept, "bodies_read": self.bodies_read,
                "attachments_read": self.attachments_read, "otp_skipped": self.otp_skipped,
                "dropped": dict(self.dropped), "kept_because": dict(self.kept_because)}


# --------------------------------------------------------------------------- step 1: headers only

def _address(sender: str) -> tuple[str, str, str]:
    """('Pine Labs Hiring', 'jobs', 'pinelabs.example') from 'Pine Labs Hiring <jobs@pinelabs.example>'."""
    m = re.search(r"<([^>]+)>", sender or "")
    addr = (m.group(1) if m else sender or "").strip().lower()
    name = re.sub(r"<[^>]*>", "", sender or "").strip().strip('"').strip()
    local, _, domain = addr.partition("@")
    return name, local, domain


def _domain_words(domain: str) -> list[str]:
    return [w for w in re.split(r"[.\-]", domain or "") if w and w not in MAIL_HOSTS and len(w) >= 3]


def _one_typo(a: str, b: str) -> bool:
    if min(len(a), len(b)) < 6 or abs(len(a) - len(b)) > 1:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.9


COMMON = {"test", "tests", "online", "interview", "form", "forms", "india", "indian", "data", "global", "digital",
          "systems", "solutions", "technologies", "technology", "services", "capital", "financial", "finance",
          "bank", "labs", "group", "consulting", "software", "tech", "analytics", "energy", "motors", "health",
          "invitation", "offer", "placement", "campus", "hiring", "new", "first", "united", "general", "national",
          "international", "american", "media", "power", "infra", "network", "networks", "partners", "ventures",
          "research", "products", "industries", "international", "management", "assessment", "schedule", "talk"}


def find_companies(text: str, index: CompanyIndex, domains: list[str] | None = None) -> list[str]:
    """Companies of the ERP list named in a subject / sender, as notices are matched: the whole core name as words
    ("Pine Labs"), written together ("PineLabs", "pinelabs.com"), its distinctive first word alone ("Accenture" for
    "Accenture Solutions Private Limited"; not a common word like "Global"), and one typo in a word of 6+ letters
    ("Acenture")."""
    found = list(index.scan_text(text))
    words = tokens(text, keep_stop=True) + list(domains or [])
    grams = {"".join(words[i:i + n]) for n in (1, 2, 3) for i in range(len(words) - n + 1)}
    for c in index.by_company:
        if c in found:
            continue
        core = tokens(c)
        cc, first = compact(c), (core[0] if core else "")
        if len(cc) < 4:
            continue
        if cc in grams or any(_one_typo(g, cc) for g in grams if len(g) >= 6):
            found.append(c)
        elif len(first) >= 5 and first not in COMMON and (first in grams or any(
                _one_typo(g, first) for g in grams if len(g) >= 6)):
            found.append(c)
    return found


def scope(head: Head, index: CompanyIndex, extra_senders: tuple[str, ...] = ()) -> Verdict:
    """Keep this mail or not, from its headers alone (module docstring)."""
    subject = head.subject or ""
    name, local, domain = _address(head.sender)
    addr = f"{local}@{domain}"
    if OTP_RE.search(subject):
        return Verdict(False, "otp")
    dwords = _domain_words(domain)
    sender_text = f"{name} {local}"
    office = bool(PLACEMENT_SENDER.search(sender_text) or PLACEMENT_SENDER.search(" ".join(dwords))) or \
        any(s and (s.lower() == addr or addr.endswith("@" + s.lower().lstrip("@")) or s.lower() == domain)
            for s in extra_senders)
    if any(w in JOB_BOARDS for w in dwords) and not office:
        return Verdict(False, "job_board")
    if NOT_PLACEMENT.search(subject) and not office:
        return Verdict(False, "not_placement")
    if office:
        return Verdict(True, "placement_office")
    sig = signal(subject)
    companies = find_companies(f"{subject} {name}", index, dwords)
    # a listed company's newsletter or promotion (bulk mail) is kept only when its subject is about hiring
    if companies and (not head.bulk or sig or CONTEXT.search(subject) or re.search(r"applica", subject, re.I)):
        return Verdict(True, "company", companies[0] if len(companies) == 1 else None, sig)
    if any(w in TEST_PLATFORMS for w in dwords):
        return Verdict(True, "test_platform", signal=sig)
    if head.bulk:
        return Verdict(False, "bulk")
    if sig:
        return Verdict(True, "signal", signal=sig)
    return Verdict(False, "no_placement_signal")


def signal(subject: str) -> str | None:
    """The placement signal in a subject, if any. "PPT" / "PPO" count in capitals only, and like "form",
    "deadline", "offer", "registration", "last date" and "due" only next to a hiring word."""
    m = STRONG.search(subject or "")
    if m:
        return m.group(0).lower()
    w = WEAK.search(subject or "") or STRONG_CASE.search(subject or "")
    if w and CONTEXT.search(subject or ""):
        return w.group(0).lower()
    return None


# --------------------------------------------------------------------------- step 2: kept mails only

def classify(subject: str, text: str, links: list[str], on_a_list: bool) -> str:
    """form / test / interview / shortlist / ppt / offer / announcement: the subject first, then the links, then a
    few clear sentences of the body ("your interview is scheduled", "you have been shortlisted")."""
    s, t = subject or "", f"{subject}\n{text}"
    forms = any(FORM_LINK.search(u) for u in links)
    tests = any(TEST_LINK.search(u) and not FORM_LINK.search(u) for u in links)
    if re.search(r"offer letter|job offer|\bPPO\b|pre[\s-]*placement offer|offer of (?:employment|internship)|"
                 r"pleased to offer|offer (?:roll[\s-]*out|release)", t, re.I):
        return "offer"
    if re.search(r"shortlist|selected for (?:the )?(?:next|further|final)|list of (?:the )?(?:selected|shortlisted)",
                 s, re.I) or on_a_list:
        return "shortlist"
    if re.search(r"\bform\b|register|registration", s, re.I) and forms:
        return "form"
    if re.search(r"interview", s, re.I) and not re.search(r"test|assessment", s, re.I):
        return "interview"
    if re.search(r"pre[\s-]*placement talk", t, re.I) or re.search(r"\bPPT\b", s):
        return "ppt"
    if tests or (re.search(r"\btest\b|assessment|coding (?:round|challenge)|\bexam\b|\bquiz\b", s, re.I) and not forms):
        return "test"
    if forms or re.search(r"\bfill (?:out |in |up )?(?:the|this|a)\b.{0,20}form", t, re.I):
        return "form"
    if re.search(r"your interview|interview (?:is |has been )?scheduled|interview slot", t, re.I):
        return "interview"
    if re.search(r"you (?:have been|are|were) shortlisted", t, re.I):
        return "shortlist"
    return "announcement"


def clean_links(links: list[str]) -> list[str]:
    """Links worth showing: no unsubscribe, tracking pixels or images; forms and tests first."""
    keep = [u for u in dict.fromkeys(links or []) if not JUNK_LINK.search(u)]
    rank = lambda u: 0 if FORM_LINK.search(u) else 1 if TEST_LINK.search(u) else 2 if MEET_LINK.search(u) else 3  # noqa: E731
    return sorted(keep, key=rank)[:10]


def main_link(kind: str, links: list[str]) -> str | None:
    for pat in ((FORM_LINK,) if kind == "form" else (TEST_LINK, MEET_LINK) if kind in ("test", "interview")
                else (MEET_LINK,) if kind == "ppt" else ()):
        for u in links:
            if pat.search(u) and not (pat is TEST_LINK and FORM_LINK.search(u)):
                return u
    return links[0] if kind in ("form", "test") and links else None


def moments(text: str, received: datetime, kind: str) -> tuple[str | None, str | None, str | None]:
    """(due_at, event_at, wording): the first deadline and the first event after the mail arrived, a mention with a
    time before one without. A deadline given as a date only counts to the end of that day (23:59); an event without
    a time has no event time (the wording keeps the date)."""
    ms = [m for m in find_moments(text, received) if m.at >= received - timedelta(hours=1)]
    pick = lambda kinds: (next((m for m in ms if m.kind in kinds and m.has_time), None)  # noqa: E731
                          or next((m for m in ms if m.kind in kinds), None))
    due = pick(("deadline",))
    ev = pick(("event",)) if kind in ("test", "interview", "ppt", "shortlist") else None
    if kind in ("test", "interview", "ppt") and (ev is None or not ev.has_time):
        ev = next((m for m in ms if m.kind == "date" and m.has_time), ev)
    if kind == "form" and due is None:
        due = next((m for m in ms if m.has_time), None)
    due_at = None
    if due is not None:
        due_at = due.at if due.has_time else due.at.replace(hour=23, minute=59)
    ev_at = ev.at if ev is not None and ev.has_time else None
    words = "; ".join(dict.fromkeys(m.text for m in (due, ev) if m))[:200] or None
    return (due_at.isoformat() if due_at else None, ev_at.isoformat() if ev_at else None, words)


def mail_id(received: datetime, sender: str, subject: str) -> str:
    return hashlib.sha1(f"{received.isoformat()}|{sender}|{subject}".encode()).hexdigest()[:20]


def read(mail: Mail, attachments: list[Attachment], verdict: Verdict, index: CompanyIndex, roll: str,
         name: str = "") -> dict | None:
    """The stored row for one kept mail, or None when the body shows it is an OTP mail after all."""
    if extract_otp(mail.subject, mail.text) or OTP_RE.search(mail.subject):
        return None
    company = verdict.company
    if company is None:
        _, _, domain = _address(mail.sender)
        hits = find_companies(f"{mail.subject} {_address(mail.sender)[0]}", index, _domain_words(domain)) \
            or index.scan_text(mail.text[:4000])
        company = hits[0] if len(hits) == 1 else None
    checks = []
    for a in attachments[:3]:
        res = check_attachment(a.data, roll, name, a.content_type)
        checks.append({"file": (a.filename or "attachment")[:80], **{k: res.get(k) for k in (
            "status", "matched_by", "format", "pages", "roll_like_count", "header", "my_row", "details", "error")},
            # a job description (no students in it): the whole text, for the company's roles (ping/notice_jd.py)
            **({"context": res.get("context")} if res.get("status") == "jd" else {})})
    mine = next((c for c in checks if c["status"] == "yes"), None)
    jd_doc = next((c for c in checks if c["status"] == "jd"), None)
    if not jd_doc and not mine:
        from .pdfs import ROLL_LIKE, classify as doc_kind, jd_document
        if doc_kind(mail.text or "", len(set(ROLL_LIKE.findall((mail.text or "").upper())))) == "jd":
            jd_doc = {"file": "(mail text)", "status": "jd", "context": jd_document(mail.text)}
    a_list = any((c.get("roll_like_count") or 0) >= 5 for c in checks)
    pdf = mine or next((c for c in checks if c["status"] == "no" and (c.get("roll_like_count") or 0) >= 5), None) \
        or jd_doc or (checks[0] if checks else None)
    links = clean_links(mail.links)
    kind = classify(mail.subject, mail.text, links, on_a_list=bool(mine) or a_list)
    due, event, words = moments(f"{mail.subject}\n{mail.text}", mail.received, kind)
    sender = re.sub(r"\s+", " ", mail.sender)[:200]
    return {"id": mail_id(mail.received, mail.sender, mail.subject), "received_at": mail.received.isoformat(),
            "sender": sender, "subject": re.sub(r"\s+", " ", mail.subject)[:300],
            "snippet": " ".join(mail.text.split())[:300], "company": company, "links": links, "kind": kind,
            "main_link": main_link(kind, links), "due_at": due, "event_at": event, "when_text": words,
            "pdf": pdf, "kept_because": verdict.because + (f":{verdict.signal}" if verdict.signal else ""),
            "rules_version": RULES_VERSION}


def scan(mailbox, since: datetime, index: CompanyIndex, roll: str, name: str = "",
         extra_senders: tuple[str, ...] = (), limit: int = 400) -> tuple[list[dict], Stats]:
    """Placement mails since `since`: headers of everything, bodies of kept mails only."""
    st = Stats()
    rows = []
    for head in mailbox.heads_after(since, limit=limit):
        st.headers_seen += 1
        v = scope(head, index, extra_senders)
        if not v.keep:
            st.dropped[v.because] = st.dropped.get(v.because, 0) + 1
            if v.because == "otp":
                st.otp_skipped += 1
            continue
        full = mailbox.fetch_full(head.uid)
        st.bodies_read += 1
        if not full:
            continue
        mail, atts = full
        st.attachments_read += len(atts)
        row = read(mail, atts, v, index, roll, name)
        if row is None:
            st.otp_skipped += 1
            st.dropped["otp"] = st.dropped.get("otp", 0) + 1
            continue
        st.kept += 1
        st.kept_because[v.because] = st.kept_because.get(v.because, 0) + 1
        rows.append(row)
    return rows, st


# --------------------------------------------------------------------------- the ERP twin of a mail

TWIN_KINDS = {"form": ("form", "apply_open", "deadline_extended"), "test": ("test", "test_rooms", "schedule"),
              "interview": ("test", "test_rooms", "schedule", "shortlist", "result"),
              "shortlist": ("shortlist", "test_rooms", "result"), "ppt": ("ppt", "schedule"),
              "offer": ("result", "ppo", "info"), "announcement": None}
TWIN_WINDOW = timedelta(days=3)


def _t(v) -> datetime | None:
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")) if v else None
    except ValueError:
        return None


def _words(s: str) -> set[str]:
    return {w for w in tokens(s or "", keep_stop=False) if len(w) >= 3}


def erp_twin(mail: dict, notices: list[dict]) -> dict | None:
    """The ERP notice that says what this mail says: same company, a matching kind, within 3 days; for a mail
    without a company (a general placement-office mail), most of its words in the notice. None: mail-only."""
    at = _t(mail.get("received_at"))
    if at is None:
        return None
    c = compact(mail.get("company") or "")
    best, best_gap = None, None
    mwords = _words(f"{mail.get('subject')} {mail.get('snippet')}")
    for n in notices:
        nt = _t(n.get("notice_time"))
        if nt is None or abs(nt - at) > TWIN_WINDOW:
            continue
        a = n.get("analysis") or {}
        if c:
            names = {compact(n.get("company") or "")} | {compact(t.get("company") or t.get("name") or "")
                                                       for t in a.get("targets") or []}
            if c not in names:
                continue
            kinds = TWIN_KINDS.get(mail.get("kind") or "announcement")
            if kinds is not None and a.get("kind") not in kinds:
                continue
        else:
            nwords = _words(f"{n.get('subject')} {(n.get('text') or n.get('preview') or '')[:1500]}")
            if not mwords or len(mwords & nwords) / len(mwords) < 0.6:
                continue
        gap = abs(nt - at)
        if best_gap is None or gap < best_gap:
            best, best_gap = n, gap
    return best
