"""Forms: every form that has come in (ERP notices, the PDFs attached to them, placement mail), one row per form, for
the Forms tab, the Today panel and reminders. Ping only reads: it never submits, prefills or signs in to a form, and
a tick ("filled") is the student's own record in form_status, never written anywhere else.

One form = one canonical key, whatever the notice or mail around it says:
  - a link is resolved to the form itself: short links (forms.gle, bit.ly, tinyurl, lnkd.in) followed to the final
    address; Google Forms by their id (/forms/d/e/<id>/..., /forms/d/<id>/...; viewform, formResponse, edit and
    usp=... all the same form); Microsoft Forms by the id parameter; Zoho by the form's perma id; Typeform by the
    /to/<id>; Jotform by the form number; anything else by host and path without the query
  - postings without a link, or with different keys, are matched on company + form title + purpose (+ the questions
    when the form page could be read): a high-confidence match is merged, a medium one is kept apart and offered as
    "Looks like the same form as …" (your choice is remembered in form_merges)
A repost never makes a new row: it moves the deadline (with the history), adds its notice or mail to the row's
sources, and keeps your tick.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urlsplit

SHORT_HOSTS = {"forms.gle", "bit.ly", "tinyurl.com", "lnkd.in", "goo.gl", "t.ly", "rb.gy", "cutt.ly", "shorturl.at"}
FORM_HOST_RE = re.compile(r"(docs\.google\.com/forms|forms\.gle|forms\.office\.com|forms\.microsoft\.com|"
                          r"zfrmz\.|forms\.zoho|zohopublic\.|typeform\.com|jotform\.(com|me)|form\.jotform)", re.I)

# what a form is for, from the notice's subject and text (first match wins)
PURPOSES = (
    ("test slot", r"\b(test|assessment|exam|interview)\s+(slot|time\s*slot|schedul|preference)|\bslot\s+(booking|selection|preference)"),
    ("PPT RSVP", r"\b(ppt|pre[- ]?placement\s+talk)\b"),
    ("CV submission", r"\bcv\s*(submission|upload)|\bresume\s+(submission|upload)|submit\s+(your\s+)?(cv|resume)"),
    ("additional requirement", r"additional\s+(requirement|details|information|info)|\bdetails?\s+form|candidate\s+details"),
    ("registration", r"\bregist(er|ration)|\binterest(ed)?\s+form|\bexpression\s+of\s+interest|\bopt[- ]?in\b"),
    ("feedback", r"\bfeedback\b|\bsurvey\b"),
    ("document upload", r"\bupload\b.*\b(document|marksheet|certificate|id)\b"),
)


def purpose_of(*texts: str) -> str:
    t = " ".join(x or "" for x in texts).lower()
    for name, rx in PURPOSES:
        if re.search(rx, t):
            return name
    return "form"


# ---------------------------------------------------------------------------- canonical keys
def is_form_link(url: str) -> bool:
    if not url:
        return False
    host = (urlsplit(url).hostname or "").lower()
    return bool(FORM_HOST_RE.search(url)) or host in SHORT_HOSTS


def key_of(url: str) -> str | None:
    """The form's own identity from its (final) address; None when it isn't a web link."""
    try:
        u = urlsplit(url.strip())
    except ValueError:
        return None
    if u.scheme not in ("http", "https") or not u.hostname:
        return None
    host, path = u.hostname.lower(), re.sub(r"/+$", "", u.path)
    q = parse_qs(u.query)
    if host == "docs.google.com" and "/forms/" in path:
        m = re.search(r"/forms/(?:u/\d+/)?d/(?:e/)?([A-Za-z0-9_-]{10,})", path)
        if m:
            return f"gform:{m.group(1)}"
    if host in ("forms.office.com", "forms.microsoft.com", "forms.office365.com") or host.endswith(".forms.office.com"):
        fid = (q.get("id") or q.get("ID") or [None])[0]
        if fid:
            return f"msform:{fid}"
        m = re.search(r"/r/([A-Za-z0-9]{6,})", path)
        if m:
            return f"msform:{m.group(1)}"
    if "zoho" in host or host.startswith("zfrmz."):
        m = re.search(r"/formperma/([A-Za-z0-9_-]{8,})", path)
        if m:
            return f"zoho:{m.group(1)}"
        if host.startswith("zfrmz."):
            return f"zoho-short:{path.strip('/')}"
    if host.endswith("typeform.com"):
        m = re.search(r"/to/([A-Za-z0-9]{4,})", path)
        if m:
            return f"typeform:{m.group(1)}"
    if "jotform" in host:
        m = re.search(r"/(\d{10,})", path)
        if m:
            return f"jotform:{m.group(1)}"
    if host in SHORT_HOSTS:
        return f"short:{host}{path}"          # not followed yet (resolve() does that): the short link itself
    return f"url:{host}{path.lower()}"


def resolve(url: str, fetch=None) -> tuple[str, str | None]:
    """(final address, key). Short links are followed to where they point (HEAD, then GET; no cookies, nothing
    submitted). fetch(url) -> final url is injectable for tests; without it, short links keep their own key."""
    host = (urlsplit(url).hostname or "").lower()
    final = url
    if host in SHORT_HOSTS and fetch:
        try:
            final = fetch(url) or url
        except Exception:
            final = url
    return final, key_of(final)


# ---------------------------------------------------------------------------- postings and grouping
def _dt(v) -> datetime | None:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def postings(items: list[dict]) -> list[dict]:
    """One posting per (item, form link): every to-do that asks you to fill a form, from a notice (and the mail that
    repeated it) or from mail alone. A notice that asks for a form without a link is a posting with no link."""
    out = []
    for it in items:
        d = it.get("details") or {}
        todo = d.get("todo") or {}
        if it.get("category") != "todo" or todo.get("action") != "fill_form":
            continue
        links = [x for x in [todo.get("link"), *(d.get("forms") or []), (d.get("mail") or {}).get("link")] if x]
        links = list(dict.fromkeys(l for l in links if is_form_link(l))) or [None]
        sources = []
        if it.get("notice_id"):
            sources.append({"type": "notice", "id": str(it["notice_id"]), "at": d.get("notice_time") or it.get("first_seen")})
        if d.get("mail"):
            sources.append({"type": "mail", "id": str(d["mail"].get("id") or ""), "at": d["mail"].get("received_at")})
        text = " ".join(x for x in (d.get("subject") or "", it.get("title") or "", todo.get("due_text") or "") if x)
        for link in links:
            out.append({"item_id": it["id"], "company": it.get("company") or "", "link": link, "due": todo.get("due") or it.get("due_at"),
                        "text": text, "purpose": purpose_of(d.get("subject") or "", it.get("title") or "", todo.get("due_text") or ""),
                        "sources": sources, "role_ids": it.get("role_ids") or [], "at": (sources[0]["at"] if sources else it.get("first_seen")),
                        "level": it.get("level"), "is_sample": bool(it.get("is_sample"))})
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).strip()


def _company_key(s: str) -> str:
    s = _norm(s)
    s = re.sub(r"\b(private|pvt|limited|ltd|llp|inc|india|technologies|technology|solutions|services|group)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def similarity(a: dict, b: dict) -> float:
    """How alike two forms are when their keys differ: company, purpose, title (the form page's, else the notice's
    words) and the question count when both pages were read. 0..1."""
    ca, cb = _company_key(a.get("company")), _company_key(b.get("company"))
    if not ca or not cb or not (ca == cb or ca.startswith(cb) or cb.startswith(ca)):
        return 0.0
    score = 0.4
    score += 0.2 if a.get("purpose") == b.get("purpose") else 0.0
    ta, tb = _norm(a.get("title") or a.get("text")), _norm(b.get("title") or b.get("text"))
    score += 0.3 * (SequenceMatcher(None, ta, tb).ratio() if ta and tb else 0.0)
    qa, qb = a.get("question_count"), b.get("question_count")
    if qa and qb:
        score += 0.1 if qa == qb else -0.15
    return round(min(score, 1.0), 2)


HIGH, MEDIUM = 0.85, 0.6


def build(items: list[dict], previous: dict[str, dict] | None = None, merges: list[dict] | None = None,
          pages: dict[str, dict] | None = None, fetch=None, now: datetime | None = None) -> list[dict]:
    """Forms rows (see sql/schema.sql, forms) from this run's items. previous: the stored rows by key (first_seen,
    deadline history and sources survive runs). merges: your Merge / Keep both answers. pages: what was read from
    each form's page, by key."""
    previous, pages = previous or {}, pages or {}
    now = now or datetime.now(timezone.utc)
    decided = {}
    for m in merges or []:
        decided[tuple(sorted((m["a"], m["b"])))] = m["choice"]
    groups: dict[str, dict] = {}
    alias: dict[str, str] = {}                     # a key merged into another
    keyless = []
    for p in sorted(postings(items), key=lambda x: str(x.get("at") or "")):
        final, key = resolve(p["link"], fetch) if p["link"] else (None, None)
        if not key:
            keyless.append(p)
            continue
        key = alias.get(key, key)
        g = groups.setdefault(key, {"key": key, "posts": [], "link": p["link"], "final_url": final})
        g["posts"].append(p)
    rows = {k: _row(g, previous.get(k), pages.get(k), now) for k, g in groups.items()}
    # keys that differ but are the same form (high confidence, or your "Merge")
    keys = sorted(rows, key=lambda k: rows[k]["first_seen"] or "")
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if a not in rows or b not in rows:
                continue
            choice = decided.get(tuple(sorted((a, b))))
            s = similarity(rows[a], rows[b])
            if choice == "merge" or (choice != "keep" and s >= HIGH and a.split(":")[0] == "url"):
                groups[a]["posts"] += groups[b]["posts"]
                rows[a] = _row(groups[a], previous.get(a), pages.get(a), now)
                rows[a]["merged_keys"] = sorted(set(rows[a].get("merged_keys", [])) | {b})
                del rows[b]
            elif choice != "keep" and s >= MEDIUM:
                rows[b].setdefault("looks_like", []).append({"key": a, "title": rows[a]["title"] or rows[a]["purpose"], "score": s})
    # postings without a link: the form they belong to, else a form of their own (keyed by notice / item)
    for p in keyless:
        best, best_s = None, 0.0
        for k, r in rows.items():
            s = similarity({**p, "title": p["text"]}, r)
            if s > best_s:
                best, best_s = k, s
        if best and best_s >= HIGH:
            groups[best]["posts"].append(p)
            rows[best] = _row(groups[best], previous.get(best), pages.get(best), now)
            continue
        key = f"notice:{p['sources'][0]['id']}" if p["sources"] and p["sources"][0]["type"] == "notice" else f"item:{p['item_id']}"
        g = groups.setdefault(key, {"key": key, "posts": [], "link": None, "final_url": None})
        g["posts"].append(p)
        rows[key] = _row(g, previous.get(key), None, now)
        if best and best_s >= MEDIUM and decided.get(tuple(sorted((key, best)))) != "keep":
            rows[key].setdefault("looks_like", []).append({"key": best, "title": rows[best]["title"] or rows[best]["purpose"], "score": best_s})
    return sorted(rows.values(), key=lambda r: (r["due_at"] or "9999", r["company"]))


def _row(g: dict, prev: dict | None, page: dict | None, now: datetime) -> dict:
    posts = sorted(g["posts"], key=lambda p: str(p.get("at") or ""))
    page = page or {}
    # the deadline: the latest posting's (a repost moves it); every change kept
    history = list((prev or {}).get("deadline_history") or [])
    due = None
    for p in posts:
        if p.get("due") and p["due"] != due:
            if due and not any(h.get("to") == p["due"] for h in history):
                history.append({"from": due, "to": p["due"], "at": p.get("at"),
                                "source": (p["sources"][0] if p["sources"] else {"type": "item", "id": p["item_id"]})})
            due = p["due"]
    sources, seen = [], set()
    for p in posts:
        for s in p["sources"]:
            k = (s["type"], s["id"])
            if k not in seen:
                seen.add(k)
                sources.append(s)
    for s in (prev or {}).get("sources") or []:
        if (s["type"], s["id"]) not in seen:
            seen.add((s["type"], s["id"]))
            sources.append(s)
    companies = list(dict.fromkeys(p["company"] for p in posts if p["company"]))
    purposes = [p["purpose"] for p in posts if p["purpose"] != "form"]
    first = posts[0] if posts else {}
    return {"key": g["key"], "company": companies[0] if len(companies) == 1 else ("several companies" if companies else ""),
            "companies": companies, "purpose": purposes[-1] if purposes else "form",
            "title": page.get("title") or None, "description": page.get("description") or None,
            "question_count": page.get("question_count"), "closed": bool(page.get("closed")),
            "signin_required": bool(page.get("signin_required")),
            "due_at": due, "deadline_history": history, "link": g.get("link"), "final_url": g.get("final_url"),
            "sources": sources, "first_seen": (prev or {}).get("first_seen") or first.get("at") or now.isoformat(),
            "last_seen": now.isoformat(), "item_ids": list(dict.fromkeys(p["item_id"] for p in posts)),
            "role_ids": list(dict.fromkeys(r for p in posts for r in p["role_ids"])), "text": first.get("text") or "",
            "is_sample": all(p.get("is_sample") for p in posts) if posts else False}


def stored(row: dict) -> dict:
    """A row as the forms table takes it (the working fields left out)."""
    keep = ("key", "company", "companies", "purpose", "title", "description", "question_count", "closed", "signin_required",
            "due_at", "deadline_history", "link", "final_url", "sources", "first_seen", "last_seen", "item_ids", "role_ids",
            "is_sample", "looks_like", "merged_keys")
    return {k: row.get(k) for k in keep if k in row or k in ("looks_like", "merged_keys")} | {
        "looks_like": row.get("looks_like") or [], "merged_keys": row.get("merged_keys") or []}


def filled_keys(status_rows: list[dict]) -> set[str]:
    """The forms you ticked (your own rows only; a demo session's ticks never count)."""
    return {r["form_key"] for r in status_rows if r.get("filled") and not r.get("is_demo")}


def mark_items(items: list[dict], rows: list[dict], filled: set[str]) -> None:
    """Each form item learns its form (details.form: key, filled, and 'extended' when a repost moved the deadline),
    so the chat, Today and reminders all follow the tick."""
    by_item = {}
    for r in rows:
        for iid in r["item_ids"]:
            by_item[iid] = r
    for it in items:
        r = by_item.get(it["id"])
        if not r:
            continue
        d = it.setdefault("details", {})
        d["form"] = {"key": r["key"], "filled": r["key"] in filled, "sources": len(r["sources"]),
                     "extended": bool(r["deadline_history"]), "closed": r["closed"]}
