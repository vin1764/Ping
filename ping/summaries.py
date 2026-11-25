"""The second line of an update / notice / mail card: one short sentence of what changed and what you must do
("APM Growth applicants: fill this form by Fri 27 Nov 23:59."), written once by the hourly run and kept with the card
(details.summary), never on page load. The full notice stays behind ⋯ / a tap.

  label(item)        the card's type: Form, Deadline change, Shortlist, Test, Interview, Assignment, Documents,
                     CV submission, Offer, Talk, Result, Info (never the vague "Update")
  summarize(...)     the model writes the line (Groq first, then Gemini flash-lite), paced for the free limits; it is
                     kept only if every date, time, number, link and name in it is in the notice (or the card's own
                     deadline, which the rules read from it); otherwise, or when no model answers, the rules write it
                     from the card (its task and deadline) or the notice's first sentence, cleaned up
  for_run(...)       which cards get a line this run: new ones and ones whose text changed, yours first
Tests: tests/test_summaries.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime

import requests

from .config import IST

MAX_CHARS = 100                 # two lines of a card at 390 px, never cut
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("PING_GROQ_MODEL") or "openai/gpt-oss-120b"
LITE = "gemini-3.1-flash-lite"
PACE_S = 2.2                    # Groq's free tier: 30 requests a minute
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

PROMPT = """You write the one line a student sees for a placement notice in their chat.
Say what changed and what the student must do, in plain words: one sentence, at most 15 words, under 95 characters.
If the notice is for a group, start with who ("APM Growth applicants: ..."). Don't start with the company's name: it is
shown already. Use only facts in the notice. If you give the deadline, write it exactly as: {due}.
No quotes, no emoji, no "Dear students", no [URGENT].

Company: {company}
Type: {label}
Notice:
<<<
{text}
>>>

Reply with the line only."""


# ---------------------------------------------------------------- the card's type
def label(it: dict) -> str:
    d = it.get("details") or {}
    todo = d.get("todo") or {}
    a, task = todo.get("action"), todo.get("task")
    title = str(it.get("title") or "")
    cat, kind = it.get("category"), d.get("kind")
    if a == "fill_form" or d.get("form") or re.search(r"\bfill (in )?the form\b", title, re.I):
        return "Form"
    if a == "submit":
        return {"assignment": "Assignment", "documents": "Documents", "cv": "CV submission"}.get(task) or \
            ("CV submission" if re.search(r"\bcv\b|resume", title, re.I) else "Assignment" if re.search(r"assignment|case|task", title, re.I) else "Documents")
    if cat == "result":
        return "Result"
    if cat == "shortlist" or kind == "shortlist":
        return "Shortlist"
    if kind == "interview" or re.search(r"\binterview", title, re.I) and cat in ("test", "todo"):
        return "Interview"
    if cat == "test" or kind in ("test", "test_rooms") or a == "take_test":
        return "Test"
    if cat == "deadline" or re.search(r"deadline (extended|moved|changed)|extended to|moved to|postponed|preponed", title, re.I):
        return "Deadline change"
    if cat == "offer" or a == "accept_offer":
        return "Offer"
    if cat == "ppt" or re.search(r"pre-placement talk|\bppt\b", title, re.I):
        return "Talk"
    return "Info"


# ---------------------------------------------------------------- the source text
def source_text(it: dict, notices: dict | None = None, emails: dict | None = None) -> str:
    """The notice's own text (or a mail's subject and summary, or the card's title): what the line may say."""
    d = it.get("details") or {}
    nkey = d.get("notice_key") or (f"{d.get('year')}:{it.get('notice_id')}" if it.get("notice_id") else None)
    n = (notices or {}).get(nkey) or (notices or {}).get(str(it.get("notice_id"))) if (notices and (nkey or it.get("notice_id"))) else None
    if n and (n.get("text") or n.get("preview")):
        return f"{n.get('subject') or ''}\n{n.get('text') or n.get('preview')}".strip()
    m = d.get("mail") or {}
    mid = str(it.get("id", "")).removeprefix("mail:")
    e = (emails or {}).get(mid) or {}
    parts = [e.get("subject"), e.get("snippet"), m.get("subject"), m.get("summary"), it.get("title")]
    return "\n".join(dict.fromkeys(p for p in parts if p)).strip()


def source_key(it: dict, text: str) -> str:
    """What the line depends on: the text, the deadline / time and the type. A change writes it again."""
    raw = json.dumps([text, it.get("due_at"), it.get("event_at"), label(it)], default=str)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------- dates as the cards write them
def fmt(iso) -> str:
    """'Fri 27 Nov 23:59' (IST), the cards' own way."""
    if not iso:
        return ""
    t = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(IST)
    return t.strftime(f"%a {t.day} %b %H:%M")


def _times(s: str) -> set[str]:
    out = set()
    for h, m, ap in re.findall(r"\b(\d{1,2})[:.](\d{2})\s*([ap]\.?\s?m\.?)?", s, re.I):
        h = int(h)
        if ap:
            ap = ap.lower().replace(".", "").replace(" ", "")
            h = (h % 12) + (12 if ap == "pm" else 0)
        if 0 <= h < 24:
            out.add(f"{h:02d}:{m}")
    for h, ap in re.findall(r"\b(\d{1,2})\s*([ap])\.?\s?m\b", s, re.I):
        h = (int(h) % 12) + (12 if ap.lower() == "p" else 0)
        out.add(f"{h:02d}:00")
    if re.search(r"\bmidnight\b", s, re.I):
        out.update({"23:59", "00:00"})
    if re.search(r"\bnoon\b", s, re.I):
        out.add("12:00")
    return out


def _dates(s: str) -> set[tuple[int, int]]:
    out = set()
    mon = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
    for d_, m in re.findall(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{mon}", s, re.I):
        out.add((int(d_), MONTHS[m[:3].lower()]))
    for m, d_ in re.findall(rf"\b{mon}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", s, re.I):
        out.add((int(d_), MONTHS[m[:3].lower()]))
    for d_, m in re.findall(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-]\d{2,4})?\b", s):
        if 1 <= int(m) <= 12:
            out.add((int(d_), int(m)))
    return out


# words a line may use without the notice having them (plain words, not facts)
PLAIN = set("""a an the and or of for to by on at in is are be your you all this that these those it its with from
before after until till today tonight tomorrow now new please must should can will may need check list lists link
fill form forms submit submission assignment documents document register registration apply application applicants
students student eligible candidates shortlisted shortlist test tests online offline interview interviews round
rounds result results offer offers deadline extended moved changed postponed preponed venue room slot time date
details notice update info join attend report bring carry complete take open read see following given above below
selected rejected only also both each every any no not yes cv resume ppt talk pre-placement placement internship
role roles company companies group process drive campus mail email portal erp cdc""".split())


def check(line: str, text: str, it: dict) -> str | None:
    """None if every date, time, number, link and name in the line is in the notice (or the card's own deadline /
    time, which the rules read from it); else why not."""
    if not line:
        return "empty"
    if len(line) > MAX_CHARS:
        return f"too long ({len(line)} characters)"
    if "…" in line or "..." in line:
        return "cut short"
    allowed = f"{text}\n{fmt(it.get('due_at'))}\n{fmt(it.get('event_at'))}\n{it.get('company') or ''}\n{it.get('title') or ''}"
    low = allowed.lower()
    for u in re.findall(r"https?://\S+", line):
        if u.rstrip(".,)") not in allowed:
            return f"link not in the notice: {u[:60]}"
    bad = _times(line) - _times(allowed)
    if bad:
        return f"time not in the notice: {sorted(bad)[0]}"
    dates = _dates(line) - _dates(allowed)
    if dates:
        return f"date not in the notice: {sorted(dates)[0]}"
    wd_ok = {fmt(x)[:3].lower() for x in (it.get("due_at"), it.get("event_at")) if x}
    for w in re.findall(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\b", line):
        if w[:3].lower() not in wd_ok and not re.search(rf"\b{w}", allowed, re.I):
            return f"weekday not in the notice: {w}"
    stripped = re.sub(r"\b\d{1,2}[:.]\d{2}\b|\b\d{1,2}(st|nd|rd|th)?\b(?=\s*(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))", " ", line, flags=re.I)
    for n in re.findall(r"\d+(?:[.,]\d+)*", stripped):
        if n not in allowed:
            return f"number not in the notice: {n}"
    # names: every capitalised word (a company, a role, a place) is in the notice
    words = re.findall(r"\b[A-Z][A-Za-z0-9&+-]*\b", line)
    for w in words:
        lw = w.lower()
        if lw in PLAIN or lw[:3] in MONTHS or lw[:3] in WEEKDAYS:
            continue
        if not re.search(rf"(?<![a-z0-9]){re.escape(lw)}(?![a-z0-9])", low):
            return f"name not in the notice: {w}"
    return None


# ---------------------------------------------------------------- the rules' line
DROP = re.compile(r"\[\s*urgent\s*\]|\burgent\b\s*[:|-]?|\bcdc\b\s*[:|-]?|\|+|dear (all|students?)[,:]?|greetings[^.]*[.!]", re.I)


def _clean(s: str, company: str | None) -> str:
    s = DROP.sub(" ", s or "")
    s = re.sub(r"\s+", " ", s).strip(" -:,.")
    if company:
        for name in {company, re.sub(r"\s*\(.*?\)", "", company), company.split()[0]}:
            if len(name) >= 3:
                s = re.sub(rf"^\s*{re.escape(name)}\b[\s:,-]*", "", s, flags=re.I)
    s = re.sub(r"^(update|notice|info|information)\b\s*[:-]?\s*", "", s, flags=re.I).strip()
    return s[:1].upper() + s[1:] if s else s


def _sentence(s: str) -> str:
    """The first whole sentence that fits; never a cut one."""
    for part in re.split(r"(?<=[.!?])\s+", s):
        part = part.strip()
        if 12 <= len(part) <= MAX_CHARS:
            return part if part[-1] in ".!?" else part + "."
    return ""


def rules_line(it: dict, text: str) -> str:
    d = it.get("details") or {}
    todo = d.get("todo") or {}
    due, ev = fmt(it.get("due_at")), fmt(it.get("event_at"))
    lab = label(it)
    a, task = todo.get("action"), todo.get("task")
    if a == "fill_form" and due:
        return f"Fill the form by {due}."
    if a == "submit" and due:
        return {"assignment": f"Submit the assignment by {due}.", "documents": f"Submit the documents by {due}.",
                "cv": f"Submit your CV by {due}."}.get(task, f"Submit it by {due}.")
    if a == "take_test" and due:
        return f"Take the test by {due}."
    if a == "accept_offer" and due:
        return f"Accept the offer by {due}."
    if lab == "Deadline change" and due:
        return f"Deadline moved to {due}."
    if lab in ("Test", "Interview") and ev:
        venue = d.get("venue")
        line = f"{lab} on {ev}" + (f", {venue}" if venue and len(venue) < 30 else "") + "."
        return line if len(line) <= MAX_CHARS else f"{lab} on {ev}."
    if lab == "Shortlist":
        st = (d.get("pdf") or {}).get("status") or it.get("pdf_status")
        return "You're on the shortlist." if st == "yes" else "The shortlist is out: check it for your name."
    first = _sentence(_clean(text.split("\n", 1)[-1] if "\n" in text else text, it.get("company")))
    if first:
        return first
    subj = _sentence(_clean(text.split("\n", 1)[0], it.get("company")))
    if subj and len(subj.split()) >= 3:
        return subj
    title = _sentence(_clean(it.get("title") or "", it.get("company")))
    if title:
        return title
    return "New notice: tap to read it." if lab == "Info" else f"New {lab.lower()} notice: tap to read it."


# ---------------------------------------------------------------- the models
class Writer:
    """The model calls of one run: Groq first, then Gemini flash-lite; paced; at most `budget` calls."""

    def __init__(self, groq_key: str = "", gemini_key: str = "", budget: int = 20, seconds: float = 120, sleep=time.sleep):
        self.groq, self.gemini, self.budget, self.deadline = groq_key, gemini_key, budget, time.monotonic() + seconds
        self.sleep, self.last = sleep, 0.0
        self.stats = {"model": 0, "rejected": 0, "failed": 0, "rules": 0, "skipped_budget": 0, "by": {}, "why": {}}

    def room(self) -> bool:
        return (self.groq or self.gemini) and self.budget > 0 and time.monotonic() < self.deadline

    def call(self, prompt: str) -> tuple[str, str] | None:
        self.budget -= 1
        if self.groq:
            wait = PACE_S - (time.monotonic() - self.last)
            if wait > 0:
                self.sleep(wait)
            self.last = time.monotonic()
            try:
                r = requests.post(GROQ_URL, timeout=12, headers={"Authorization": f"Bearer {self.groq}"},
                                  json={"model": GROQ_MODEL, "temperature": 0.2, "max_tokens": 300, "reasoning_effort": "low",
                                        "include_reasoning": False, "messages": [{"role": "user", "content": prompt}]})
                if r.status_code == 429 and r.headers.get("retry-after"):
                    self.sleep(min(20.0, float(r.headers["retry-after"])))
                    r = requests.post(GROQ_URL, timeout=12, headers={"Authorization": f"Bearer {self.groq}"},
                                      json={"model": GROQ_MODEL, "temperature": 0.2, "max_tokens": 300, "reasoning_effort": "low",
                                            "include_reasoning": False, "messages": [{"role": "user", "content": prompt}]})
                if r.ok:
                    t = ((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                    if t.strip():
                        return t.strip(), "groq"
            except Exception:
                pass
        if self.gemini:
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{LITE}:generateContent", timeout=12,
                                  headers={"x-goog-api-key": self.gemini},
                                  json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200}})
                if r.ok:
                    parts = ((r.json().get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
                    t = "".join(p.get("text", "") for p in parts).strip()
                    if t:
                        return t, "gemini-lite"
            except Exception:
                pass
        return None


def tidy(line: str, company: str | None) -> str:
    line = line.strip().strip('"“”').splitlines()[0].strip() if line.strip() else ""
    line = _clean(line, company) if line else ""
    if line and line[-1] not in ".!?":
        line += "."
    return line


def summarize(it: dict, text: str, writer: Writer | None) -> dict:
    """{summary, summary_by, label, summary_key, summary_why?}: the model's line if it passes the check, else the rules'."""
    lab = label(it)
    out = {"label": lab, "summary_key": source_key(it, text)}
    if writer and writer.room():
        res = writer.call(PROMPT.format(due=fmt(it.get("due_at") or it.get("event_at")) or "(no deadline)",
                                        company=it.get("company") or "", label=lab, text=text[:2500]))
        if res:
            line, by = tidy(res[0], it.get("company")), res[1]
            why = check(line, text, it)
            if not why:
                writer.stats["model"] += 1
                writer.stats["by"][by] = writer.stats["by"].get(by, 0) + 1
                return {**out, "summary": line, "summary_by": by}
            writer.stats["rejected"] += 1
            key = re.sub(r":.*", "", why)
            writer.stats["why"][key] = writer.stats["why"].get(key, 0) + 1
            out["summary_why"] = why
            out["summary_model"] = line
        else:
            writer.stats["failed"] += 1
    elif writer:
        writer.stats["skipped_budget"] += 1
        out["summary_pending"] = True                     # the next run tries the model again
    if writer:
        writer.stats["rules"] += 1
    return {**out, "summary": rules_line(it, text), "summary_by": "rules"}


# ---------------------------------------------------------------- which cards, in which order
TEXT_CARDS = {"update", "info", "deadline", "shortlist", "test", "result", "offer", "ppt", "todo", "form", "interview", "announcement", "notice"}


def wants(it: dict) -> bool:
    """Cards that carry a notice's or a mail's text (to-dos too: their type and line come from here)."""
    return it.get("category") in TEXT_CARDS and not str(it.get("id", "")).startswith(("batch:", "digest:", "listing:", "collapse:"))


def order(items: list[dict]) -> list[dict]:
    """Yours first (always, then shown), then the newest."""
    rank = {"always": 0, "show": 1}
    return sorted(items, key=lambda i: (rank.get(i.get("level"), 2), -(datetime.fromisoformat(str(i.get("first_seen") or "1970-01-01T00:00:00+00:00").replace("Z", "+00:00")).timestamp())))


def apply(items: list[dict], previous: dict, notices: dict, emails: dict, writer: Writer | None, only=None, log=print) -> dict:
    """Writes the line for the cards that need one (new, changed, or waiting for the model) and keeps the rest's.
    `only`: a test for which cards may get a new line (the run: the ones in the chat; the backfill: open / recent)."""
    todo = []
    for it in items:
        if not wants(it):
            continue
        d = it.setdefault("details", {})
        before = (previous.get(it["id"]) or {}).get("details") or {}
        text = source_text(it, notices, emails)
        key = source_key(it, text)
        if before.get("summary") and before.get("summary_key") == key and not before.get("summary_pending"):
            for k in ("summary", "summary_by", "label", "summary_key", "summary_why", "summary_model"):
                if before.get(k) is not None:
                    d[k] = before[k]
            continue
        if only is not None and not only(it):
            if before.get("summary"):                    # kept until it's asked for again
                for k in ("summary", "summary_by", "label", "summary_key"):
                    if before.get(k) is not None:
                        d[k] = before[k]
            continue
        todo.append((it, text))
    by_id = {id(p[0]): p for p in todo}
    for it in order([p[0] for p in todo]):
        _, text = by_id[id(it)]
        res = summarize(it, text, writer)
        d = it["details"]
        for k in ("summary_why", "summary_model", "summary_pending"):
            d.pop(k, None)
        d.update(res)
    stats = writer.stats if writer else {}
    if todo:
        log(f"card lines: {len(todo)} written ({json.dumps(stats)})")
    return {"written": len(todo), **stats}
