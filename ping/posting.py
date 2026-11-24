"""The posting guard: what one run may post in the chat (and push). Every run rebuilds the feed from the data; a
message is "posted" the first run it is visible. Before that, it passes these, in order:

  paused      PING_POSTING isn't "on": nothing new is posted or pushed; it's held and looked at again once posting
              is back (the run still reads and saves everything)
  silent      a re-scan, a backfill or a rule-version re-read: the data is updated, nothing is posted or pushed
  past        its deadline / time had already passed when Ping found it: never posted
  posted      the same company, task, deadline and form link was posted before, whatever the message's id: never again
  cap         at most one digest a run; more than 5 new messages in one run become one grouped message

A message held back is recorded (state "silenced_ids"), so the next run, which rebuilds it, keeps it back too. The
very first run (nothing saved yet) builds the thread you start with, history included: there is nothing to repeat.
Tests: tests/test_posting.py.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

CAP = 5


def paused() -> bool:
    """Posting is paused until PING_POSTING=on (the workflow sets it once the guard's tests pass)."""
    return os.environ.get("PING_POSTING", "paused").strip().lower() != "on"


def _dt(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")) if v else None
    except ValueError:
        return None


def _norm(s) -> str:
    s = re.sub(r"\(.*?\)", " ", str(s or "").lower())
    s = re.sub(r"\b(private|pvt|limited|ltd|llp|inc|india)\b\.?", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def task_of(it: dict) -> str:
    d = it.get("details") or {}
    a = (d.get("todo") or {}).get("action")
    if a:
        return a
    return d.get("kind") or it.get("category") or ""


def link_of(it: dict) -> str:
    d = it.get("details") or {}
    u = (d.get("todo") or {}).get("link") or (d.get("form") or {}).get("link") or (d.get("mail") or {}).get("link") or ""
    return re.sub(r"[?#].*$", "", str(u)).rstrip("/").lower()


def post_key(it: dict) -> str:
    """(company, task, deadline, form link): two messages with the same key are the same message to you."""
    when = it.get("due_at") or it.get("event_at") or ""
    when = (_dt(when).strftime("%Y-%m-%dT%H:%M") if _dt(when) else "") if when else ""
    return "|".join([_norm(it.get("company")), task_of(it), when, link_of(it)])


def is_past(it: dict, now: datetime) -> bool:
    t = _dt(it.get("due_at") or it.get("event_at"))
    return bool(t and t <= now)


def _hide(it: dict, why: str) -> None:
    it["level"] = "hidden"
    it.setdefault("details", {})["hidden_because"] = why


def guard(items: list[dict], previous: dict, store, now: datetime, paused: bool = False, silent: list[str] | None = None,
          log=print) -> list[dict]:
    """The items with this run's guard applied (held-back ones hidden, a grouped message added when needed)."""
    # the very first run builds the thread you start with (its history included): nothing to guard against yet
    if not previous:
        store.set_state("posted_keys", sorted({post_key(it) for it in items if it.get("level") != "hidden"})[-5000:])
        return items
    posted = set(store.get_state("posted_keys") or [])
    silenced = set(store.get_state("silenced_ids") or [])
    held = set(store.get_state("held_ids") or [])
    if not posted:                      # first run with the guard: everything already visible counts as posted
        posted = {post_key(p) for p in previous.values() if p.get("level") != "hidden" and not p.get("dismissed")}
    for it in items:                    # held back before: still held back
        if it["id"] in silenced:
            _hide(it, (previous.get(it["id"]) or {}).get("details", {}).get("hidden_because") or "not posted")
    new = [it for it in items if (it["id"] not in previous or (it["id"] in held and not paused))
           and it.get("level") != "hidden" and not it.get("dismissed") and it.get("category") not in ("apply", "reminder")]
    keep, report = [], {"paused": 0, "silent": 0, "past": 0, "posted": 0, "grouped": 0, "digest": 0}
    for it in new:
        key = post_key(it)
        if paused:
            _hide(it, "posting paused")
            held.add(it["id"])
            report["paused"] += 1
            continue
        held.discard(it["id"])
        if silent:
            _hide(it, f"found by a {silent[0]}: saved, not posted")
            silenced.add(it["id"])
            report["silent"] += 1
        elif is_past(it, now):
            _hide(it, "its time had already passed when Ping found it")
            silenced.add(it["id"])
            report["past"] += 1
        elif key in posted:
            _hide(it, "already posted (same company, task, deadline and link)")
            silenced.add(it["id"])
            report["posted"] += 1
        else:
            keep.append(it)
    # at most one digest a run
    digests = [it for it in keep if it.get("category") == "digest"]
    for it in digests[1:]:
        _hide(it, "one digest a run")
        silenced.add(it["id"])
        keep.remove(it)
        report["digest"] += 1
    # more than CAP new messages: one grouped message instead
    if len(keep) > CAP:
        for it in keep:
            _hide(it, "grouped into one message")
            silenced.add(it["id"])
        report["grouped"] = len(keep)
        names = [f"{it.get('company') or 'Placement office'}: {it.get('category') or 'update'}" for it in keep]
        items.append({"id": f"batch:{now.strftime('%Y%m%dT%H%M')}", "level": "show", "category": "update", "company": None,
                      "title": f"{len(keep)} new updates in this check: {', '.join(names[:3])}" + (f" +{len(keep) - 3} more" if len(keep) > 3 else ""),
                      "due_at": None, "event_at": None, "notice_id": None, "role_ids": [], "pdf_status": None, "needs_review": False,
                      "details": {"list": [{"head": None, "rows": [{"text": it.get("title") or "", "id": it["id"]} for it in keep]}],
                                  "grouped": [it["id"] for it in keep]}})
        keep = []
    for it in keep:
        posted.add(post_key(it))
    # grouped messages made by earlier runs stay
    ids = {it["id"] for it in items}
    items.extend(p for k, p in previous.items() if k.startswith("batch:") and k not in ids)
    store.set_state("posted_keys", sorted(posted)[-5000:])
    store.set_state("silenced_ids", sorted(silenced)[-20000:])
    store.set_state("held_ids", sorted(held))
    log(f"posting guard: {len(new)} new, {len(keep)} posted; held back: " + ", ".join(f"{k} {v}" for k, v in report.items() if v)
        + (" (paused)" if paused else "") + (f" (silent: {', '.join(silent)})" if silent else ""))
    return items
