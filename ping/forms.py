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
    """One posting per form to-do (a notice's, or a mail's): its company, every form link it gives, its sources, its
    deadline. A notice that asks several companies' applicants to fill forms is several to-dos of ONE notice: they
    end up in one row (build)."""
    out = []
    for it in items:
        d = it.get("details") or {}
        todo = d.get("todo") or {}
        if it.get("category") != "todo" or todo.get("action") != "fill_form":
            continue
        own = todo.get("link") if str(todo.get("link") or "").startswith(("http://", "https://")) else None
        links = list(dict.fromkeys(l for l in [own, *(x for x in [*(d.get("forms") or []), (d.get("mail") or {}).get("link")]
                                                     if x and is_form_link(x))] if l))
        sources = []
        if it.get("notice_id"):
            sources.append({"type": "notice", "id": str(it["notice_id"]), "at": d.get("notice_time") or it.get("first_seen")})
        if d.get("mail"):
            sources.append({"type": "mail", "id": str(d["mail"].get("id") or ""), "at": d["mail"].get("received_at")})
        text = " ".join(x for x in (d.get("subject") or "", it.get("title") or "", todo.get("due_text") or "") if x)
        out.append({"item_id": it["id"], "company": it.get("company") or "", "links": links, "link": links[0] if links else None,
                    "due": todo.get("due") or it.get("due_at"), "text": text,
                    "purpose": purpose_of(d.get("subject") or "", it.get("title") or "", todo.get("due_text") or ""),
                    "sources": sources, "role_ids": it.get("role_ids") or [], "at": (sources[0]["at"] if sources else it.get("first_seen")),
                    "level": it.get("level"), "is_sample": bool(it.get("is_sample"))})
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).strip()


def _company_key(s: str) -> str:
    s = re.sub(r"\([^)]*(?:www\.|https?:)[^)]*\)", " ", (s or "").lower())       # "Auro Group(www.AuroIM.com)"
    s = _norm(s)
    s = re.sub(r"\b(private|pvt|limited|ltd|llp|inc|india|technologies|technology|solutions|services|group)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def similarity(a: dict, b: dict) -> float:
    """How alike two forms are (company, purpose, title, questions), 0..1. Kept for reports; Ping no longer merges
    or asks on it."""
    ca, cb = _company_key(a.get("company")), _company_key(b.get("company"))
    if not ca or not cb or not (ca == cb or ca.startswith(cb) or cb.startswith(ca)):
        return 0.0
    score = 0.4 + (0.2 if a.get("purpose") == b.get("purpose") else 0.0)
    ta, tb = _norm(a.get("title") or a.get("text")), _norm(b.get("title") or b.get("text"))
    score += 0.3 * (SequenceMatcher(None, ta, tb).ratio() if ta and tb else 0.0)
    return round(min(score, 1.0), 2)


KNOWN = ("gform", "msform", "zoho", "typeform", "jotform")


def _dtv(v):
    return _dt(v) or datetime.max.replace(tzinfo=timezone.utc)


def build(items: list[dict], previous: dict[str, dict] | None = None, merges: list[dict] | None = None,
          pages: dict[str, dict] | None = None, fetch=None, now: datetime | None = None) -> list[dict]:
    """Forms rows from this run's items: one row per form posting, merged silently when it's the same thing:
      - the same notice (a notice for 11 companies is ONE row with the 11 companies), or the same mail
      - any form link in common (after short links are followed: forms.gle / bit.ly / … and usp / prefill ignored)
      - the same companies (as a set, names normalised) + the same purpose, posted again with the same or a later
        deadline (an extension)
    A merged row keeps the earliest first-seen, the latest deadline with its history and every source. Ping never
    asks "is this the same form?": a genuinely different posting stays its own row. previous: the stored rows by key
    (first_seen, history); pages: what was read from each form page, by key; merges: ignored (no prompts any more)."""
    previous, pages = previous or {}, pages or {}
    now = now or datetime.now(timezone.utc)
    posts = sorted(postings(items), key=lambda x: (str(x.get("at") or ""), x["item_id"]))
    finals = {}
    for p in posts:
        keys = []
        for link in p["links"]:
            final, key = resolve(link, fetch)
            if key:
                keys.append(key)
                finals.setdefault(key, final)
        p["keys"] = list(dict.fromkeys(keys))
    parent = list(range(len(posts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)       # the earliest posting stays the root
    first_by: dict[tuple, int] = {}
    for i, p in enumerate(posts):
        for k in [("src", s["type"], s["id"]) for s in p["sources"]] + [("link", k) for k in p["keys"]]:
            if k in first_by:
                union(first_by[k], i)
            else:
                first_by[k] = i
    # groups so far; then the same companies + purpose, the same or a later deadline, merge (repeat until stable)
    def groups():
        g: dict[int, list[int]] = {}
        for i in range(len(posts)):
            g.setdefault(find(i), []).append(i)
        return g
    changed = True
    while changed:
        changed = False
        gs = groups()
        sig = {}
        for root, members in sorted(gs.items()):
            comps = frozenset(_company_key(posts[i]["company"]) for i in members if _company_key(posts[i]["company"]))
            purposes = {posts[i]["purpose"] for i in members}
            purpose = next(iter(purposes - {"form"}), "form") if len(purposes - {"form"}) <= 1 else None
            if not comps or purpose is None:
                continue
            due = max((_dtv(posts[i]["due"]) for i in members), default=None)
            key = (comps, purpose)
            if key in sig:
                other_root, other_first = sig[key]
                if due >= other_first:            # the same deadline as one it had, or a later one (an extension)
                    union(other_root, root)
                    changed = True
                    break
            else:
                sig[key] = (root, min((_dtv(posts[i]["due"]) for i in members), default=None))
    rows, used = [], set()
    for root, members in sorted(groups().items()):
        ps = [posts[i] for i in members]
        notice_ids = sorted({int(s["id"]) if str(s["id"]).isdigit() else s["id"] for p in ps for s in p["sources"] if s["type"] == "notice"},
                            key=lambda v: (str(type(v)), v))
        keys = list(dict.fromkeys(k for p in ps for k in p["keys"]))
        # the row it was before (a stored row with any of these postings or links): its key stays, so your tick,
        # its first-seen and its deadline history stay with it
        ids = {p["item_id"] for p in ps}
        before = sorted((pr for pr in previous.values() if ids & set(pr.get("item_ids") or [])
                         or set(keys) & ({pr.get("key")} | set(pr.get("merged_keys") or []))),
                        key=lambda pr: (str(pr.get("first_seen") or ""), str(pr.get("key"))))
        before = [pr for pr in before if pr.get("key") not in used]
        if before:
            key = before[0]["key"]
        elif notice_ids:
            key = f"notice:{notice_ids[0]}"
        elif keys:
            key = keys[0]
        else:
            key = f"item:{ps[0]['item_id']}"
        page = next((pages[k] for k in keys if k in pages), None)
        g = {"key": key, "posts": ps, "link": ps[0]["link"], "final_url": finals.get(keys[0]) if keys else None,
             "links": [finals.get(k) or k for k in keys]}
        prev = dict(before[0]) if before else None
        if prev and len(before) > 1:              # several old rows collapse into this one: all their history and sources
            prev["deadline_history"] = list({(h.get("from"), h.get("to")): h for b in before for h in (b.get("deadline_history") or [])}.values())
            prev["sources"] = [x for b in before for x in (b.get("sources") or [])]
        if key in used:                           # never two rows with one key
            key = g["key"] = f"item:{ps[0]['item_id']}"
        used.add(key)
        r = _row(g, prev, page, now)
        r["form_keys"] = keys
        rows.append(r)
    return sorted(rows, key=lambda r: (r["due_at"] or "9999", r["company"]))


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
    seen_c, companies = set(), []
    for p in posts:
        ck = _company_key(p["company"])
        if p["company"] and ck not in seen_c:
            seen_c.add(ck)
            companies.append(p["company"])
    purposes = [p["purpose"] for p in posts if p["purpose"] != "form"]
    first = posts[0] if posts else {}
    return {"key": g["key"], "company": companies[0] if len(companies) == 1 else ("several companies" if companies else ""),
            "companies": companies, "purpose": purposes[-1] if purposes else "form",
            "title": page.get("title") or None, "description": page.get("description") or None,
            "question_count": page.get("question_count"), "closed": bool(page.get("closed")),
            "signin_required": bool(page.get("signin_required")),
            "due_at": due, "deadline_history": history, "link": g.get("link"), "final_url": g.get("final_url"),
            "links": g.get("links") or [],
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
        "looks_like": [], "merged_keys": row.get("form_keys") or []}       # no merge prompts: the same form is merged


def carry_ticks(status_rows: list[dict], previous: dict[str, dict], rows: list[dict]) -> list[dict]:
    """Ticks on rows that were merged into another row: the same tick on the row that now holds their postings."""
    keys = {r["key"] for r in rows}
    moved = []
    for st in status_rows:
        if st.get("form_key") in keys or not st.get("filled") or st.get("is_demo"):
            continue
        old = previous.get(st["form_key"]) or {}
        to = next((r for r in rows if set(old.get("item_ids") or []) & set(r["item_ids"])
                   or st["form_key"] in (r.get("form_keys") or [])), None)
        if to and not any(m["owner_id"] == st.get("owner_id") and m["form_key"] == to["key"] for m in moved):
            moved.append({"owner_id": st.get("owner_id"), "form_key": to["key"], "filled": True,
                          "filled_at": st.get("filled_at"), "is_demo": False})
    return moved


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
        h = r["deadline_history"]
        d["form"] = {"key": r["key"], "filled": r["key"] in filled, "sources": len(r["sources"]),
                     "extended": bool(h), "moved": ({"from": h[0]["from"], "to": h[-1]["to"]} if h else None),
                     "closed": r["closed"], "signin_required": r.get("signin_required", False)}
