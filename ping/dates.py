"""Pull dates and times out of notice sentences, e.g.
  'has been opened till 4:00 PM, 21st November, 2026'
  'Deadline: 21st November 2026, 4:00 PM'
  'scheduled from 7:15 PM onwards on 19th November, 2026'
  'by 5:00 PM today', 'on 23 November 2026', 'Date: 14-06-2026 Reporting Time: 5:45 PM'
Every result keeps the original wording next to the IST datetime.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .config import IST

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_DAY = r"(?P<day>\d{1,2})(?:st|nd|rd|th)?"
_YEAR = r"(?P<year>20\d{2})(?!\d)"
_WEEKDAY = r"(?:(?:mon|tues|wednes|thurs|fri|satur|sun)day,?\s*)?"

DATE_PATTERNS = [
    re.compile(_WEEKDAY + _DAY + r"\s*(?:of\s+)?" + _MON + r"(?:\s*,?\s*" + _YEAR + r")?", re.I),
    re.compile(_WEEKDAY + _MON + r"\s+" + _DAY + r"(?:\s*\(\w+\))?(?:\s*,?\s*" + _YEAR + r")?", re.I),
    re.compile(r"(?<![\d/])(?P<day>\d{1,2})[./-](?P<mnum>\d{1,2})[./-](?P<year>20\d{2})(?!\d)"),
    re.compile(r"\b(?P<rel>today|tonight|tomorrow)\b", re.I),
]
# Case-sensitive on purpose: '4:00 PMInterested' (text glued by the ERP) must still match.
TIME_RE = re.compile(
    r"(?<![\d:])(?P<h>\d{1,2})(?:[:.](?P<m>\d{2}))?\s*(?P<ap>[aApP]\.?\s?[mM]\.?)(?![a-z])"
    r"|(?<![\d:])(?P<h24>[01]?\d|2[0-3]):(?P<m24>[0-5]\d)(?!\s*[aApP]\.?[mM])(?![\d])"
    r"|\b(?P<noon>[Nn]oon|[Mm]idnight)\b")

DEADLINE_WORDS = re.compile(
    r"\b(till|until|upto|up to|by|before|deadline|last date|closes?|closing|extended|due|latest|"
    r"submit|register|fill|complete|accept)", re.I)
EVENT_WORDS = re.compile(
    r"\b(scheduled|onwards|test|assessment|exam|interview|ppt|talk|session|workshop|held|"
    r"reporting|report|venue|slot|round|gd|group discussion|from)\b", re.I)


@dataclass
class Moment:
    at: datetime
    kind: str          # 'deadline' | 'event' | 'date'
    text: str          # original wording around it
    has_time: bool
    start: int = 0

    def as_dict(self) -> dict:
        return {"at": self.at.isoformat(), "kind": self.kind, "text": self.text,
                "has_time": self.has_time}


def _parse_time(m: re.Match) -> tuple[int, int]:
    if m.group("noon"):
        return (12, 0) if m.group("noon").lower() == "noon" else (23, 59)
    if m.group("h24"):
        return int(m.group("h24")), int(m.group("m24"))
    h, mi = int(m.group("h")), int(m.group("m") or 0)
    ap = m.group("ap").lower().replace(".", "").replace(" ", "")
    if h == 12:
        h = 0
    if ap.startswith("p"):
        h += 12
    return min(h, 23), min(mi, 59)


def _sentences(text: str) -> list[tuple[int, str]]:
    out, pos = [], 0
    # split at line breaks and at '. ' / '.X' where X is a capital letter (ERP glues sentences)
    for piece in re.split(r"(\n+|(?<=[a-z0-9)])\.(?=\s*[A-Z]))", text):
        if piece is None:
            continue
        if piece.strip() and not re.fullmatch(r"\n+|\.", piece):
            out.append((pos, piece))
        pos += len(piece)
    return out


def _resolve(m: re.Match, ref: datetime) -> datetime | None:
    gd = m.groupdict()
    if gd.get("rel"):
        rel = gd["rel"].lower()
        base = ref.date() + timedelta(days=1 if rel == "tomorrow" else 0)
        return datetime(base.year, base.month, base.day, tzinfo=IST)
    try:
        day = int(gd["day"])
        mon = int(gd["mnum"]) if gd.get("mnum") else MONTHS[gd["mon"][:3].lower()]
    except (KeyError, TypeError, ValueError):
        return None
    year = int(gd["year"]) if gd.get("year") else None
    if year is None:
        year = ref.year
        try:
            cand = datetime(year, mon, day, tzinfo=IST)
        except ValueError:
            return None
        if cand < ref - timedelta(days=60):   # 'Jan 5' written in December
            year += 1
    try:
        return datetime(year, mon, day, tzinfo=IST)
    except ValueError:
        return None


def find_moments(text: str, ref: datetime) -> list[Moment]:
    """All date(+time) mentions with a guess whether each is a deadline or an event."""
    moments: list[Moment] = []
    for s_start, sentence in _sentences(text or ""):
        dates = []
        taken: list[tuple[int, int]] = []
        for pat in DATE_PATTERNS:
            for m in pat.finditer(sentence):
                if any(a < m.end() and m.start() < b for a, b in taken):
                    continue
                d = _resolve(m, ref)
                if d:
                    dates.append((m, d))
                    taken.append((m.start(), m.end()))
        if not dates:
            continue
        # '27th July (today)': drop the relative word when a real date sits right next to it
        real = [m for m, _ in dates if not m.groupdict().get("rel")]
        dates = [(m, d) for m, d in dates if not m.groupdict().get("rel")
                 or not any(abs(m.start() - r.end()) < 15 or abs(r.start() - m.end()) < 15 for r in real)]
        times = [t for t in TIME_RE.finditer(sentence)
                 if not any(a <= t.start() < b for a, b in taken)]
        for m, d in sorted(dates, key=lambda x: x[0].start()):
            # nearest time in the same sentence (prefer one within 40 characters)
            best = None
            for t in times:
                dist = min(abs(t.start() - m.end()), abs(m.start() - t.end()))
                if best is None or dist < best[0]:
                    best = (dist, t)
            has_time = best is not None and best[0] <= 60
            at = d
            if has_time:
                h, mi = _parse_time(best[1])
                at = d.replace(hour=h, minute=mi)
            elif m.groupdict().get("rel") == "tonight":
                at = d.replace(hour=23, minute=59)
            lo = max(0, m.start() - 70)
            hi = min(len(sentence), m.end() + 40)
            if has_time:
                lo = min(lo, max(0, best[1].start() - 70))
                hi = max(hi, best[1].end() + 10)
            ctx = sentence[lo:hi]
            before = sentence[max(0, min(m.start(), best[1].start() if has_time else m.start()) - 70):m.end()]
            if DEADLINE_WORDS.search(before) or re.search(r"deadline", sentence, re.I):
                kind = "deadline"
            elif EVENT_WORDS.search(sentence):
                kind = "event"
            else:
                kind = "date"
            moments.append(Moment(at, kind, re.sub(r"\s+", " ", ctx).strip(), has_time, s_start + m.start()))
    unique, seen = [], set()
    for mo in moments:
        if (mo.at, mo.kind) not in seen:
            seen.add((mo.at, mo.kind))
            unique.append(mo)
    return unique


def first_deadline(text: str, ref: datetime) -> Moment | None:
    ms = [m for m in find_moments(text, ref) if m.kind == "deadline"]
    return min(ms, key=lambda m: m.start) if ms else None


def fmt_when(at: datetime | None, now: datetime) -> str:
    """'Sat 21 Nov 16:00'. Always with the date: a chat message is read days later, when 'Sat' is ambiguous."""
    if at is None:
        return "no date given"
    at = at.astimezone(IST)
    hm = at.strftime("%H:%M")
    return f"{at.strftime('%a %d %b')} {hm}"
