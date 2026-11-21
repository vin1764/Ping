"""Is it really new? Collapses repeats before anything is shown.

The same news often arrives two or three times: a notice re-posted with a
small edit, a deadline extension that repeats the original, an email that
says what a notice already said. Rules:

- Same company + same kind of thing + same deadline (or same date and venue),
  posted within WINDOW_DAYS of each other -> the same item. The first one
  stays; later copies are hidden ("duplicate of ...") and noted on it.
- Same company + kind within the window but a real change (deadline moved,
  time/venue changed, you're now on the list) -> ONE new "Update" message
  that says what changed. The earlier message stays in the thread, marked
  as updated.
- An email about a company that a notice already covered (within the window)
  -> merged into that notice's message; its links are kept there.
- Unsure (e.g. one of the two doesn't say which role) -> treated as the
  same, with a note saying why.
"""

from __future__ import annotations

import difflib
import re
from datetime import datetime, timedelta

from .dates import fmt_when
from .matching import compact

WINDOW_DAYS = 4
KIND = {"test": "list:test", "shortlist": "list:shortlist", "result": "list:result", "deadline": "deadline",
        "ppt": "ppt", "info": "info", "offer": "offer", "email": "email", "review": "review"}


def _dt(v):
    return datetime.fromisoformat(v) if isinstance(v, str) and v else v if isinstance(v, datetime) else None


def _when(it) -> datetime | None:
    d = it.get("details") or {}
    return _dt(d.get("notice_time")) or _dt(d.get("received_at")) or _dt(it.get("first_seen")) or _dt(it.get("sort_at"))


def _kind(it) -> str | None:
    if it["category"] == "todo":
        return "todo:" + ((it.get("details") or {}).get("todo") or {}).get("action", "")
    return KIND.get(it["category"])


def _text(it) -> str:
    return re.sub(r"\s+", " ", it.get("title") or "").lower()


def _same_day(a, b) -> bool:
    a, b = _dt(a), _dt(b)
    return bool(a and b and a.date() == b.date())


def _profiles(it) -> set[str]:
    return {compact(p) for p in ((it.get("details") or {}).get("profiles") or []) if compact(p)}


def _roles_compatible(a, b) -> tuple[bool, str | None]:
    pa, pb = _profiles(a), _profiles(b)
    if pa and pb and not (pa & pb) and not any(x in y or y in x for x in pa for y in pb):
        return False, None  # the notices name different profiles: two different things
    ra, rb = set(a.get("role_ids") or []), set(b.get("role_ids") or [])
    if not ra or not rb:
        return True, "one of them doesn't say which role"
    if ra & rb:
        return True, None
    return False, None


def _changes(old: dict, new: dict, now: datetime) -> list[str]:
    out = []
    od, nd = old.get("details") or {}, new.get("details") or {}
    if new.get("due_at") and old.get("due_at") and _dt(new["due_at"]) != _dt(old["due_at"]):
        out.append(f"deadline moved from {fmt_when(_dt(old['due_at']), now)} to {fmt_when(_dt(new['due_at']), now)}")
    if new.get("event_at") and old.get("event_at") and _dt(new["event_at"]) != _dt(old["event_at"]):
        out.append(f"time moved from {fmt_when(_dt(old['event_at']), now)} to {fmt_when(_dt(new['event_at']), now)}")
    if nd.get("venue") and od.get("venue") and compact(nd["venue"]) != compact(od["venue"]):
        out.append(f"venue changed to {nd['venue']}")
    if new.get("pdf_status") == "yes" and old.get("pdf_status") != "yes":
        out.append("you're now on the list")
    elif new.get("pdf_status") == "no" and old.get("pdf_status") == "yes":
        out.append("you're no longer on the list")
    return out


def _same_values(old: dict, new: dict) -> bool:
    od, nd = old.get("details") or {}, new.get("details") or {}
    due_ok = not new.get("due_at") or not old.get("due_at") or _dt(new["due_at"]) == _dt(old["due_at"])
    ev_ok = not new.get("event_at") or not old.get("event_at") or _same_day(new["event_at"], old["event_at"]) \
        and _dt(new["event_at"]) == _dt(old["event_at"])
    venue_ok = not nd.get("venue") or not od.get("venue") or compact(nd["venue"]) == compact(od["venue"])
    pdf_ok = not new.get("pdf_status") or new.get("pdf_status") == old.get("pdf_status") or \
        not old.get("pdf_status")
    return due_ok and ev_ok and venue_ok and pdf_ok


def dedupe(items: list[dict], now: datetime) -> tuple[list[dict], dict]:
    stats = {"duplicates_merged": 0, "updates": 0, "emails_merged": 0, "unsure_merges": 0, "examples": []}
    live = [it for it in items if it["level"] != "hidden" and (it["id"].startswith("notice:") or it["category"] == "email")]
    live.sort(key=lambda it: (_when(it) or now, it["id"]))
    current: dict[tuple, list[dict]] = {}     # (company, kind) -> latest version of each thing
    added = []
    window = timedelta(days=WINDOW_DAYS)

    for it in live:
        company = compact(it.get("company") or "")
        kind = _kind(it)
        t = _when(it) or now
        if not company or not kind or kind == "review":
            continue
        if kind == "email":
            target = None
            for (c, k), versions in current.items():
                if c == company and k != "email":
                    for v in versions:
                        if abs(t - (_when(v) or t)) <= window:
                            target = v
            if target is not None:
                d = target.setdefault("details", {})
                d["mail_links"] = list(dict.fromkeys((d.get("mail_links") or []) + (it["details"].get("links") or [])))[:5]
                d.setdefault("merged", []).append({"id": it["id"], "note": "email said what this notice said"})
                _hide(it, f"already said in {target['id']}")
                stats["emails_merged"] += 1
                _example(stats, it, target, "email repeats the notice")
                continue
        match, note = None, None
        for v in current.get((company, kind), []):
            if abs(t - (_when(v) or t)) > window:
                continue
            ok, why = _roles_compatible(v, it)
            if not ok:
                continue
            if kind in ("info", "offer") and difflib.SequenceMatcher(None, _text(v), _text(it)).ratio() < 0.5:
                continue
            match, note = v, why
            break
        if match is None:
            current.setdefault((company, kind), []).append(it)
            continue
        changes = _changes(match, it, now)
        earlier = next((v for v in (match.get("_versions") or []) if _same_values(v, it) and not _changes(v, it, now)), None)
        if changes and earlier is not None:
            changes, note = [], "matches an earlier version of the same thing"
        if not changes and _same_values(match, it) or earlier is not None and not changes:
            d = match.setdefault("details", {})
            d.setdefault("merged", []).append({"id": it["id"], "notice_id": it.get("notice_id"),
                                               "note": note or "same company, kind and dates"})
            for key in ("mail_links", "forms", "links"):
                if (it.get("details") or {}).get(key):
                    d[key] = list(dict.fromkeys((d.get(key) or []) + it["details"][key]))[:8]
            _hide(it, f"duplicate of {match['id']}")
            stats["duplicates_merged"] += 1
            if note:
                stats["unsure_merges"] += 1
            _example(stats, it, match, "duplicate" + (f" ({note})" if note else ""))
            continue
        if not changes:
            # same thing, values differ in a way we can't describe (e.g. an extra date): unsure -> same, with a note
            d = match.setdefault("details", {})
            d.setdefault("merged", []).append({"id": it["id"], "note": "looked like the same thing; small differences"})
            _hide(it, f"probably a duplicate of {match['id']}")
            stats["duplicates_merged"] += 1
            stats["unsure_merges"] += 1
            _example(stats, it, match, "probably the same")
            continue
        # a real change: one Update message, the earlier one stays (marked as updated)
        what = _what(match)
        upd = {**it, "id": f"{match['id']}:update:{it['id']}", "category": match["category"],
               "title": _clip(f"Update - {match.get('company')}{what}: " + "; ".join(changes) + "."),
               "details": {**(it.get("details") or {}), "update_of": match["id"], "changes": changes,
                           "previous_title": match["title"]}}
        _hide(it, f"sent as an update to {match['id']}")
        match["details"] = {**(match.get("details") or {}), "updated_by": upd["id"]}
        if match["level"] != "hidden":
            match["level"] = "hidden"
            match["details"]["hidden_because"] = "updated by a later message"
        upd["_versions"] = (match.get("_versions") or []) + [match]
        current[(company, kind)] = [upd if v is match else v for v in current[(company, kind)]]
        added.append(upd)
        stats["updates"] += 1
        _example(stats, it, match, "update: " + "; ".join(changes))
    for it in items + added:
        it.pop("_versions", None)
    return items + added, stats


def changes_since_last_run(previous: dict[str, dict], items: list[dict], now: datetime) -> list[dict]:
    """A role's deadline that moved between runs becomes one Update message."""
    out = []
    for it in items:
        if it["category"] not in ("apply", "reminder") or it["level"] == "hidden":
            continue
        old = previous.get(it["id"])
        if not old or not old.get("due_at") or not it.get("due_at") or _dt(old["due_at"]) == _dt(it["due_at"]):
            continue
        change = f"deadline moved from {fmt_when(_dt(old['due_at']), now)} to {fmt_when(_dt(it['due_at']), now)}"
        out.append({**it, "id": f"{it['id']}:update:{_dt(it['due_at']).strftime('%Y%m%d%H%M')}",
                    "title": _clip(f"Update - {it.get('company')}: {change}."), "first_seen": now.isoformat(),
                    "details": {**(it.get("details") or {}), "update_of": it["id"], "changes": [change]}})
    return out


def _what(it) -> str:
    cat = it["category"]
    return {"test": " test", "shortlist": " shortlist", "result": " result", "deadline": " deadline",
            "ppt": " pre-placement talk", "todo": " form"}.get(cat, "")


def _hide(it, why):
    it["level"] = "hidden"
    it["details"] = {**(it.get("details") or {}), "hidden_because": why}


def _clip(s: str, n: int = 160) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip(" ,.;:") + "…"


def _example(stats, it, into, why):
    if len(stats["examples"]) < 12:
        stats["examples"].append({"merged": it["title"], "into": into["title"], "why": why})
