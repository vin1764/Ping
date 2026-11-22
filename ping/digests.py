"""Fewer, fuller messages: deadline digests, new-role listings and same-run collapses.

The feed is rebuilt from stored data every run, so every message here has a stable id and, once sent, keeps the
content it was sent with (copied from the previous run). That is what makes "one message, then nothing on the
other hourly runs" hold.

Deadline batches: everything of one kind (application / form / test) that closes at the same date and time.
  - digest    posted once, when the batch is within DIGEST_WINDOW (it replaces the per-role 24h reminder cards).
              Not posted if the new-roles message of the same run already listed every role in it.
  - reminder  posted once, `reminder_hours` (profile, default 2) before it closes, listing only what is still
              unapplied (forms: not marked done). Skipped if the digest itself came out inside that window.
  - update    posted once per change after the batch was announced: roles moved in by an extension, or added
              without being announced elsewhere. Never a second full digest.
New roles: the roles a run sees for the first time become ONE message for that run ("5 new roles listed"),
  each with its close time. One role stays a message of its own.
Shortlists / test lists that arrive in the same run: one message when there are several ("3 shortlists out").

Every list message ends with its source: the ERP check time and the notices the dates came from.
"""

from __future__ import annotations

import hashlib
import re
from typing import Callable
from datetime import datetime, timedelta

from .config import IST
from .dates import fmt_when

DIGEST_WINDOW = timedelta(hours=24)
REMINDER_HOURS = 2
OWN = ("digest", "listing", "collapse")          # categories made here
EXPIRED = ("deadline gone", "already happened", "older than 3 days")
COLLAPSIBLE = {"shortlist": ("shortlist", "shortlists out"), "test": ("test list", "test lists out")}


def _dt(v) -> datetime | None:
    if not v:
        return None
    return v if isinstance(v, datetime) else datetime.fromisoformat(v)


def _key(at: datetime) -> str:
    return at.astimezone(IST).strftime("%Y%m%dT%H%M")   # no 10-digit runs (the demo privacy check)


def when(at: datetime, now: datetime) -> str:
    """'tonight, Sat 21 Nov 20:00' / 'today, ...' / 'tomorrow, ...' / 'Mon 23 Nov 12:00'."""
    a, n = at.astimezone(IST), now.astimezone(IST)
    base = fmt_when(at, now)
    if a.date() == n.date():
        return f"{'tonight' if a.hour >= 17 else 'today'}, {base}"
    if a.date() == (n + timedelta(days=1)).date():
        return f"tomorrow, {base}"
    return base


def _clock(at: datetime) -> str:
    return at.astimezone(IST).strftime("%H:%M")


def _short(h8: list[str]) -> str:
    return hashlib.sha1(",".join(sorted(h8)).encode()).hexdigest()[:8]


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _source(check_at: datetime, sources: list[str]) -> str:
    notices = sorted({s.split(" ", 1)[1] for s in sources if s and s.startswith("notice ")}, key=lambda x: (len(x), x))
    bits = [f"ERP check {_clock(check_at)}"]
    if any(s == "companies list" for s in sources) or not notices:
        bits.append("companies list")
    if notices:
        bits.append(("notice " if len(notices) == 1 else "notices ") + ", ".join(notices))
    return " · ".join(bits)


def role_row(m: dict) -> dict:
    """One line of a list. Part B adds 'for you' / 'others' and the reason; until then every role is plain."""
    note = m.get("note") or ""
    if m.get("cv"):
        note = f"{note} · Apply with: {m['cv']}" if note else f"Apply with: {m['cv']}"
    return {"text": f"{m['company']} — {m['label']}", "note": note, "tag": m.get("tag") or "role", "id": m["id"],
            **({"cv": m["cv"]} if m.get("cv") else {})}


def split_rows(members: list[dict], list_others: bool = True) -> list[dict]:
    """Rows of a list: for-you first, then the others, then the ones you've applied to / done."""
    first = [m for m in members if m.get("tag") == "for_you"]
    plain = [m for m in members if m.get("tag") in (None, "role")]
    others = [m for m in members if m.get("tag") == "other"]
    groups = []
    if first:
        groups.append({"head": "For you", "rows": [role_row(m) for m in first]})
    if plain:
        groups.append({"head": "", "rows": [role_row(m) for m in plain]})
    if others:
        if list_others:
            groups.append({"head": f"Others ({len(others)})", "collapsed": True,
                           "rows": [role_row({**m, "note": ""}) for m in others]})
        else:
            groups.append({"head": f"{_plural(len(others), 'other role')} not shown (Profile: list other roles)",
                           "rows": []})
    return groups


_URL_PAREN = re.compile(r"\s*\((?:[^()]*?(?:https?://|www\.|\.com\b|\.in\b|\.io\b|\.ai\b))[^()]*\)", re.I)
_SUFFIX = re.compile(r"[\s,]+(?:private\s+limited|pvt\.?\s*ltd\.?|limited|ltd\.?|inc\.?|llp|corporation|corp\.?)\s*$", re.I)


def _co_name(company: str) -> str:
    """A company as it reads in a title: no bracketed website, no 'Private Limited'."""
    s = _URL_PAREN.sub("", company or "")
    for _ in range(2):
        s = _SUFFIX.sub("", s)
    return re.sub(r"\s{2,}", " ", s).strip() or (company or "").strip()


def _named(title: Callable[[str], str], companies: list[str], limit: int = 160) -> str:
    """Never a count without names: the title with its companies (the first 5, then '+N more'), shortened to fit."""
    cos = sorted({_co_name(c) for c in companies if c}, key=str.lower)
    for n in range(min(5, len(cos)), 0, -1):
        names = ", ".join(cos[:n]) + (f" +{len(cos) - n} more" if len(cos) > n else "")
        t = title(names)
        if len(t) <= limit:
            return t
    return title(f"{len(cos)} companies")[:limit]


def _for_you(members: list[dict]) -> str:
    """' — 8 for you' when the roles are marked (Profile: What I'm looking for), else nothing."""
    if not any(m.get("tag") in ("for_you", "other") for m in members):
        return ""
    return f" — {sum(m.get('tag') == 'for_you' for m in members)} for you"


def _left_title(pending: list[dict], applied: int, due_text: str, list_others: bool, prefix: str = "") -> str:
    """What's left to do, first: '1 for you to apply by tonight, Sat 21 Nov 20:00 (Groww); 11 others not applied.
    You've done 11.' The applied ones are said once, at the end (never in a reminder)."""
    tagged = any(m.get("tag") in ("for_you", "other") for m in pending)
    fy = [m for m in pending if m.get("tag") == "for_you"] if tagged else pending
    ot = [m for m in pending if m.get("tag") != "for_you"] if tagged else []
    if fy:
        head = f"{len(fy)}{' for you' if tagged else ''} to apply by {due_text}"
        names, extra = fy, (f"; {len(ot)} other{'s' if len(ot) != 1 else ''} not applied" if ot and list_others else "")
    else:
        head = (f"{_plural(len(ot), 'other role')} to apply by {due_text}" if list_others
                else f"None for you to apply by {due_text}")
        names, extra = (ot if list_others else []), ""
    done = f". You've done {applied}." if applied and not prefix else ""
    cos = list(dict.fromkeys(m["company"] for m in names))
    if not cos:
        return f"{prefix}{head}{extra}{done}"
    return _named(lambda n: f"{prefix}{head} ({n}){extra}{done}", cos)


ERP_MISSING = ("role details not read yet",)     # the ERP hasn't given this role's criteria (yet)


def _unverified_line(members: list[dict]) -> str:
    """CG cut-off and departments are checked wherever the ERP gives them and the profile has them. The note counts
    only roles whose criteria the ERP doesn't give; a gap in your own profile is one line, not a count."""
    unk = [m for m in members if any(f in ERP_MISSING for f in m.get("flags") or [])]
    out = []
    if len(unk) == 1:
        out.append(f"Eligibility not verified for {unk[0]['company']} {unk[0]['label']} (the ERP gives no criteria yet).")
    elif unk:
        out.append(f"Eligibility not verified for {len(unk)} of these (the ERP gives no criteria yet).")
    # a gap in your own profile (CGPA, degree, department) is said once by the page, with a dot on Profile, not
    # under every digest
    return " ".join(out)


def build(items: list[dict], members_by_role: dict[str, dict], previous: dict[str, dict], profile: dict,
          now: datetime) -> list[dict]:
    """Returns the feed with the new messages added and the per-role cards they replace hidden.

    members_by_role: role id -> {id, company, label, due (datetime), source, applied, eligible, first_seen,
                                 tag/note (relevance, optional)} for every role that counts (eligible or unknown,
                                 not marked not-interested).
    previous: last run's items by id (their content and first_seen are kept).
    """
    reminder_h = float(profile.get("reminder_hours") or REMINDER_HOURS)
    list_others = profile.get("list_other_roles", True) is not False
    # messages written before the keys got their "T" (202611212000 -> 20261121T2000) count as the same messages;
    # their old rows are hidden below so nothing shows twice
    renamed = {}
    fixed_prev = {}
    for pid, pit in previous.items():
        nid = _new_key(pid)
        if nid != pid and pit.get("category") in OWN:
            renamed[pid] = pit
            d = dict(pit.get("details") or {})
            if d.get("batch"):
                d["batch"] = _new_key(d["batch"])
            pit = {**pit, "id": nid, "details": d}
        fixed_prev[_new_key(pid) if pid in renamed else pid] = pit
    previous = fixed_prev
    out = [it for it in items]
    made: dict[str, dict] = {}
    by_id = {it["id"]: it for it in out}

    def emit(it: dict) -> None:
        """Keep what was sent: an id seen before keeps its title, list and first_seen."""
        old = previous.get(it["id"])
        if old:
            keep = {k: old.get(k) for k in ("title", "first_seen") if old.get(k)}
            det = dict(old.get("details") or {})
            if str(det.get("hidden_because", "")).startswith(EXPIRED):
                det.pop("hidden_because")          # re-checked below
            level = "hidden" if det.get("hidden_because") else det.get("sent_level") or old.get("level") or it["level"]
            it = {**it, **keep, "level": level, "details": det}
        it["details"].setdefault("sent_level", it["level"] if it["level"] != "hidden" else "show")
        made[it["id"]] = it

    def hide(it: dict, why: str) -> None:
        it["level"] = "hidden"
        it["details"] = {**(it.get("details") or {}), "hidden_because": why}

    # ------------------------------------------------------------------ new roles, per run
    runs: dict[str, list[dict]] = {}
    for m in members_by_role.values():
        seen = _dt(m.get("first_seen")) or now
        due = m.get("due")
        # only roles that were open and unapplied when Ping first saw them are news
        if due is None or due <= seen or m.get("applied") or seen < now - timedelta(days=3):
            continue
        runs.setdefault(seen.astimezone(IST).strftime("%Y%m%dT%H%M"), []).append({**m, "seen": seen})
    listed_in: dict[str, str] = {}       # role id -> listing message id
    listing_at: dict[str, datetime] = {}
    for rk, ms in sorted(runs.items()):
        seen = min(m["seen"] for m in ms)
        lid = f"listing:{rk}"
        for m in ms:
            listed_in[m["id"]] = lid
        listing_at[lid] = seen
        ms.sort(key=lambda m: (m["due"], m["company"], m["label"]))
        groups = []
        for due in sorted({m["due"] for m in ms}):
            batch = [m for m in ms if m["due"] == due]
            for g in split_rows(batch, list_others):
                groups.append({**g, "head": f"Close {fmt_when(due, seen)}" + (f" · {g['head']}" if g["head"] else "")})
        companies = {m["company"] for m in ms}
        if len(ms) == 1:
            m = ms[0]
            title = f"New: {m['company']} {m['label']}. Apply by {fmt_when(m['due'], seen)}."
        else:
            soonest = ms[0]["due"]
            title = _named(lambda names: f"{_plural(len(ms), 'new role')} listed at {_plural(len(companies), 'company', 'companies')} "
                                         f"({names}); the first closes {fmt_when(soonest, seen)}.", [m["company"] for m in ms])
        note = _unverified_line(ms)
        emit({"id": lid, "level": "show", "category": "listing", "company": ms[0]["company"] if len(companies) == 1 else None,
              "role_ids": [m["id"] for m in ms], "notice_id": None, "due_at": None, "event_at": None, "pdf_status": None,
              "needs_review": False, "title": title[:160], "first_seen": seen.isoformat(), "sort_at": seen.isoformat(),
              "details": {"kind": "listing", "list": groups, "note": note, "members": sorted(m["id"] for m in ms),
                          "source": _source(seen, [m.get("source") or "" for m in ms])}})

    # ------------------------------------------------------------------ application batches
    batches: dict[str, list[dict]] = {}
    for m in members_by_role.values():
        if m.get("due"):
            batches.setdefault(_key(m["due"]), []).append(m)
    known = _known_members(previous, "application")
    moved_into: dict[str, dict[str, str]] = {}           # new batch key -> {role id: old batch key}
    for bk, ms in batches.items():
        for m in ms:
            for ok, ids in known.items():
                if ok != bk and m["id"] in ids:
                    moved_into.setdefault(bk, {})[m["id"]] = ok
    for bk, ms in sorted(batches.items()):
        due = ms[0]["due"]
        did = f"digest:application:{bk}"
        ms.sort(key=lambda m: (m["company"], m["label"]))
        pending = [m for m in ms if not m.get("applied")]
        ids = sorted(m["id"] for m in ms)
        anchor = previous.get(did)
        if due <= now and not anchor:
            continue
        in_window = now >= due - DIGEST_WINDOW
        moved = moved_into.get(bk, {})
        if not anchor and not in_window and not moved:
            continue
        if not anchor and not pending:
            continue
        sources = [m.get("source") or "" for m in ms]
        # when this batch's first message is due: the run in which it came within the window. Normally that's
        # this run; after a gap (first run with digests, missed runs) it's the earlier check, so the history
        # reads as it would have.
        firsts = [_dt(m.get("first_seen")) for m in ms if _dt(m.get("first_seen"))]
        entered = max(due - DIGEST_WINDOW, min(firsts)) if firsts else now
        sent = now if moved or now - entered < timedelta(hours=2) else entered
        if not anchor:
            # the first message for this batch
            applied = len(ms) - len(pending)
            if len(ms) == 1:
                m = ms[0]
                title = f"{m['company']} {m['label']} closes {when(due, sent)}. You haven't applied."
            else:
                title = _left_title(pending, applied, when(due, sent), list_others)
            det = {"kind": "application", "batch": bk, "role": "digest", "members": ids,
                   "list": split_rows(pending, list_others) + ([{"head": f"Applied ({applied})", "collapsed": True,
                           "rows": [role_row({**m, "note": "", "tag": "done"}) for m in ms if m.get("applied")]}]
                           if applied else []),
                   "note": _unverified_line(pending), "source": _source(sent, sources), "sent_at": sent.isoformat()}
            it = {"id": did, "level": "show", "category": "digest", "company": None, "role_ids": ids, "notice_id": None,
                  "due_at": due.isoformat(), "event_at": None, "pdf_status": None, "needs_review": False,
                  "title": title[:160], "first_seen": sent.isoformat(), "sort_at": due.isoformat(), "details": det}
            all_listed_now = all(listing_at.get(listed_in.get(m["id"], "")) and
                                 abs((listing_at[listed_in[m["id"]]] - sent).total_seconds()) < 3600 for m in pending)
            from_moves = moved and all(m["id"] in moved for m in ms)
            if from_moves:
                old = sorted(set(moved.values()))[0]
                hide(it, f"announced as an update of the {old} batch")
                upd = _update_item(f"digest:application:{old}:moved:{bk}", old, bk, due, ms, moved, now,
                                   list_others, sources)
                emit(upd)
            elif all_listed_now:
                hide(it, "announced in the new roles message")
            emit(it)
        else:
            emit({**anchor, "details": dict(anchor.get("details") or {})})
            last = known.get(bk) or set(anchor.get("details", {}).get("members") or [])
            added = [m for m in ms if m["id"] not in last]
            if added and due > now:
                # roles that a new-roles message of this run already announced need no update of their own
                quiet = [m for m in added if m["id"] in listed_in and
                         abs((listing_at[listed_in[m["id"]]] - now).total_seconds()) < 3600]
                uid = f"digest:application:{bk}:upd:{_short(ids)}"
                upd = _update_item(uid, None, bk, due, added, moved, now, list_others, sources, members=ids)
                if len(quiet) == len(added):
                    hide(upd, "announced in the new roles message")
                emit(upd)
        # one reminder, N hours before
        rid = f"digest:application:{bk}:reminder"
        sent = _dt((made.get(did) or {}).get("first_seen")) or now
        if previous.get(rid):
            emit(dict(previous[rid]))
        elif pending and due - timedelta(hours=reminder_h) <= now < due and sent < due - timedelta(hours=reminder_h):
            title = _left_title(pending, 0, when(due, now), list_others, prefix="Reminder: ")
            emit({"id": rid, "level": "show", "category": "digest", "company": None,
                  "role_ids": [m["id"] for m in pending], "notice_id": None, "due_at": due.isoformat(),
                  "event_at": None, "pdf_status": None, "needs_review": False, "title": title[:160],
                  "first_seen": now.isoformat(), "sort_at": due.isoformat(),
                  "details": {"kind": "application", "batch": bk, "role": "reminder",
                              "members": sorted(m["id"] for m in pending), "list": split_rows(pending, list_others),
                              "note": _unverified_line(pending), "source": _source(now, sources),
                              "sent_at": now.isoformat()}})

    # the per-role cards are replaced by the messages above
    for it in out:
        if it.get("category") in ("apply", "reminder") and it["level"] != "hidden":
            rid = (it.get("role_ids") or [None])[0]
            hide(it, "in the deadline digest" if rid in members_by_role else "in a list message")

    # ------------------------------------------------------------------ forms and tests at the same time
    def _form_reminder(rid: str, its: list[dict], at: datetime, base: dict | None) -> None:
        """Reminder: the forms of one deadline still not done (filled = your tick), `reminder_h` before it closes.
        Posted once; not when the digest itself came out inside that window."""
        pending = [it for it in its if not (previous.get(it["id"]) or {}).get("done")]
        sent = _dt((base or {}).get("first_seen")) or (now if base else at - timedelta(days=1))
        if previous.get(rid):
            emit(dict(previous[rid]))
        elif pending and at - timedelta(hours=reminder_h) <= now < at and sent < at - timedelta(hours=reminder_h):
            ticked = len(its) - len(pending)          # filled (your tick) or marked done: no reminder for them
            rows = [{"text": it["title"], "note": "", "tag": "role", "id": it["id"]} for it in pending]
            emit({"id": rid, "level": "always" if any(it["level"] == "always" for it in its) else "show",
                  "category": "digest", "company": None, "role_ids": [], "notice_id": None,
                  "due_at": at.isoformat(), "event_at": None, "pdf_status": None, "needs_review": False,
                  "title": _named(lambda names: f"Reminder: {_plural(len(pending), 'form')} due {when(at, now)}: {names}"
                                  + (f" ({ticked} filled)" if ticked else ""), [p.get("company") or "" for p in pending])[:160],
                  "first_seen": now.isoformat(), "sort_at": at.isoformat(),
                  "details": {**((base or {}).get("details") or {"kind": "form", "batch": rid.split(":")[2],
                                                                   "members": sorted(it["id"] for it in its),
                                                                   "source": _source(now, [f"notice {it['notice_id']}" for it in its if it.get("notice_id")]),
                                                                   "sent_at": now.isoformat()}),
                              "role": "reminder", "list": [{"head": "", "rows": rows}]}})

    for kind, pick, label in (("form", lambda it: it["category"] == "todo" and
                               ((it.get("details") or {}).get("todo") or {}).get("action") == "fill_form",
                               ("form", "forms due")),
                              ("test", lambda it: it["category"] == "test" and it.get("event_at"),
                               ("test", "tests at"))):
        groups: dict[str, list[dict]] = {}
        for it in out:
            if it["level"] == "hidden" or not pick(it):
                continue
            at = _dt(it.get("due_at") if kind == "form" else it.get("event_at"))
            if at and at > now:
                groups.setdefault(_key(at), []).append(it)
        for bk, all_its in groups.items():
            did = f"digest:{kind}:{bk}"
            # a form already in the chat whose deadline a repost moved here: it keeps its place (its own message,
            # or the digest it was in, with one "deadline extended" line) and isn't announced again. It still
            # counts for the reminder below.
            moved_here = [it for it in all_its if kind == "form" and (it.get("details") or {}).get("extended")
                          and it["id"] in previous and it["id"] not in ((previous.get(did) or {}).get("details") or {}).get("members", [])]
            for it in moved_here:
                was = ((previous.get(it["id"]) or {}).get("details") or {}).get("hidden_because") or ""
                if was.startswith("in the form digest"):
                    hide(it, was)
            its = [it for it in all_its if it not in moved_here]
            if len(its) < 2 and not previous.get(did):
                if kind == "form" and moved_here and len(all_its) >= 2:
                    _form_reminder(f"{did}:reminder", all_its, at=_dt(all_its[0].get("due_at")), base=None)
                continue
            at = _dt(its[0].get("due_at") if kind == "form" else its[0].get("event_at"))
            rows = [{"text": it["title"], "note": "", "tag": "role", "id": it["id"]} for it in its]
            title = _named(lambda names: f"{len(its)} {label[1]} {when(at, now)}: {names}", [it.get("company") or "" for it in its])
            level = "always" if any(it["level"] == "always" for it in its) else "show"
            for it in its:
                hide(it, f"in the {kind} digest")
            ids = sorted(it["id"] for it in its)
            emit({"id": did, "level": level,
                  "category": "digest", "company": None, "role_ids": [], "notice_id": None,
                  "due_at": at.isoformat() if kind == "form" else None,
                  "event_at": at.isoformat() if kind == "test" else None, "pdf_status": None, "needs_review": False,
                  "title": title[:160], "first_seen": now.isoformat(), "sort_at": at.isoformat(),
                  "details": {"kind": kind, "batch": bk, "role": "digest", "members": ids,
                              "list": [{"head": "", "rows": rows}],
                              "source": _source(now, [f"notice {it['notice_id']}" for it in its if it.get("notice_id")]),
                              "sent_at": now.isoformat()}})
            if kind == "form":
                _form_reminder(f"{did}:reminder", all_its, at=at, base=made[did])

    # ------------------------------------------------------------------ one notice extends several deadlines
    ext: dict[str, list[dict]] = {}
    for it in out:
        if it["category"] != "deadline" or it["level"] == "hidden" or not it.get("due_at"):
            continue
        posted = _dt((it.get("details") or {}).get("notice_time")) or _dt((previous.get(it["id"]) or {}).get("first_seen")) or now
        ext.setdefault(f"{_key(_dt(it['due_at']))}:{posted.astimezone(IST).strftime('%Y%m%dT%H')}", []).append(it)
    for k, its in ext.items():
        cid = f"collapse:deadline:{k}"
        if len(its) < 2 and not previous.get(cid):
            continue
        due = _dt(its[0]["due_at"])
        posted = min(_dt((it.get("details") or {}).get("notice_time")) or now for it in its)
        mine = all((it.get("details") or {}).get("applied") or "you've applied" in it["title"] or it["level"] == "always"
                   for it in its)
        level = "always" if any(it["level"] == "always" for it in its) else "show"
        seen = min((_dt((previous.get(it["id"]) or {}).get("first_seen")) or now for it in its))
        for it in its:
            hide(it, "in the deadline extensions message")
        rows = [{"text": it["title"].replace(" (you've applied).", "").replace("Update - ", ""), "note": "",
                 "tag": "role", "id": it["id"]} for it in sorted(its, key=lambda x: x.get("company") or "")]
        emit({"id": cid, "level": level,
              "category": "collapse", "company": None, "role_ids": sorted({r for it in its for r in it.get("role_ids") or []}),
              "notice_id": None, "due_at": due.isoformat(), "event_at": None, "pdf_status": None, "needs_review": False,
              "title": _named(lambda names: f"{len(its)} deadlines{' for roles you applied to' if mine else ''} moved to "
                                            f"{fmt_when(due, posted)}: {names}", [it.get("company") or "" for it in its]),
              "first_seen": posted.isoformat(), "sort_at": due.isoformat(),
              "details": {"kind": "deadline", "role": "collapse", "members": sorted(it["id"] for it in its),
                          "notice_time": posted.isoformat(), "list": [{"head": "", "rows": rows}],
                          "source": _source(seen, [f"notice {it['notice_id']}" for it in its if it.get("notice_id")])}})

    # ------------------------------------------------------------------ several lists out in the same run
    for cat, (one, many) in COLLAPSIBLE.items():
        arrived: dict[str, list[dict]] = {}
        for it in out:
            if it["category"] != cat or it["level"] == "hidden" or not it.get("notice_id"):
                continue
            seen = _dt((previous.get(it["id"]) or {}).get("first_seen")) or now
            posted = _dt((it.get("details") or {}).get("notice_time"))
            if posted and posted < seen - timedelta(hours=3):
                continue   # a backlog read on a first run keeps its own place in the history
            arrived.setdefault(seen.astimezone(IST).strftime("%Y%m%dT%H%M"), []).append(it)
        for rk, its in arrived.items():
            cid = f"collapse:{cat}:{rk}"
            if len(its) < 2 and not previous.get(cid):
                continue
            its.sort(key=lambda it: (it.get("pdf_status") != "yes", it.get("company") or ""))
            level = "always" if any(it["level"] == "always" for it in its) else "show"
            for it in its:
                hide(it, f"in the {many} message")
            seen = _dt((previous.get(its[0]["id"]) or {}).get("first_seen")) or now
            emit({"id": cid, "level": level,
                  "category": "collapse", "company": None, "role_ids": [], "notice_id": None, "due_at": None,
                  "event_at": None, "pdf_status": None, "needs_review": False,
                  "title": f"{len(its)} {many}: " + "; ".join(it.get("company") or "?" for it in its)[:120],
                  "first_seen": seen.isoformat(), "sort_at": seen.isoformat(),
                  "details": {"kind": cat, "role": "collapse", "members": sorted(it["id"] for it in its),
                              "list": [{"head": "", "rows": [{"text": it["title"], "note": "", "tag": "role",
                                                              "id": it["id"]} for it in its]}],
                              "source": _source(seen, [f"notice {it['notice_id']}" for it in its])}})

    # messages from earlier runs that this run didn't make again stay as they were (they expire below)
    for pid, p in previous.items():
        if p.get("category") in OWN and pid not in made:
            made[pid] = dict(p)
    # a form digest whose form a repost extended stays up until the new deadline (its row says "deadline extended")
    for did, dg in made.items():
        d = dg.get("details") or {}
        if dg.get("category") != "digest" or d.get("kind") != "form" or d.get("role") == "reminder":
            continue
        dues = [_dt(by_id[m]["due_at"]) for m in d.get("members") or [] if m in by_id and by_id[m].get("due_at")
                and (by_id[m].get("details") or {}).get("extended")]
        if dues and _dt(dg.get("due_at")) and max(dues) > _dt(dg["due_at"]):
            made[did] = {**dg, "due_at": max(dues).isoformat()}
    # the rows under the old keys: hidden (their messages live on under the new keys)
    for pid, p in renamed.items():
        by_id[pid] = {**p, "level": "hidden", "details": {**(p.get("details") or {}), "hidden_because": "renamed"}}
    for it in made.values():
        _expire(it, now)
        by_id[it["id"]] = it
    return list(by_id.values())


def _new_key(s: str) -> str:
    """202611212000 -> 20261121T2000 and 2026112100 -> 20261121T00 inside an id or a batch key."""
    return re.sub(r"(?<![0-9T])(\d{8})(\d{2}|\d{4})(?![0-9])", r"\1T\2", s)


def _known_members(previous: dict[str, dict], kind: str) -> dict[str, set[str]]:
    """The role ids each batch was last announced with (its digest, or its latest update)."""
    latest: dict[str, tuple[str, set[str]]] = {}
    for p in previous.values():
        d = p.get("details") or {}
        if p.get("category") != "digest" or d.get("kind") != kind or not d.get("batch") or d.get("role") == "reminder":
            continue
        if d.get("role") == "moved":
            continue
        at = p.get("first_seen") or ""
        if d["batch"] not in latest or at >= latest[d["batch"]][0]:
            latest[d["batch"]] = (at, set(d.get("members") or []))
    return {k: v[1] for k, v in latest.items()}


def _update_item(uid, old_key, bk, due, ms, moved, now, list_others, sources, members=None) -> dict:
    old_at = datetime.strptime(old_key, "%Y%m%dT%H%M").replace(tzinfo=IST) if old_key else None
    if old_key:
        title = _named(lambda names: f"Update: {_plural(len(ms), 'application')} ({names}) that closed {fmt_when(old_at, now)} now "
                       f"close{'s' if len(ms) == 1 else ''} {when(due, now)}", [m["company"] for m in ms])
    else:
        mv = [m for m in ms if m["id"] in moved]
        title = _named(lambda names: f"Update: {_plural(len(ms), 'more application')} ({names}) now close{'s' if len(ms) == 1 else ''} "
                                     f"{when(due, now)}", [m["company"] for m in ms])
        if mv:
            title += f" ({len(mv)} moved from an earlier deadline)"
    return {"id": uid, "level": "show", "category": "digest", "company": None, "role_ids": [m["id"] for m in ms],
            "notice_id": None, "due_at": due.isoformat(), "event_at": None, "pdf_status": None, "needs_review": False,
            "title": title[:160], "first_seen": now.isoformat(), "sort_at": due.isoformat(),
            "details": {"kind": "application", "batch": bk, "role": "moved" if old_key else "update",
                        "members": members or sorted(m["id"] for m in ms),
                        "list": split_rows([m for m in ms if not m.get("applied")], list_others),
                        "note": _unverified_line(ms), "source": _source(now, sources), "sent_at": now.isoformat()}}


def _expire(it: dict, now: datetime) -> None:
    """Past digests stay in the history, marked as past; a hidden anchor stays hidden."""
    d = it.get("details") or {}
    if it["level"] == "hidden" and not str(d.get("hidden_because", "")).startswith(EXPIRED):
        return
    due, ev, sort = _dt(it.get("due_at")), _dt(it.get("event_at")), _dt(it.get("sort_at"))
    why = None
    if due and due <= now:
        why = "deadline gone"
    elif ev and ev < now - timedelta(hours=12):
        why = "already happened"
    elif not due and not ev and sort and sort < now - timedelta(days=3):
        why = "older than 3 days"
    if why:
        it["level"] = "hidden"
        it["details"] = {**d, "hidden_because": why}
    elif it["level"] == "hidden":
        it["level"] = d.get("sent_level") or "show"
        it["details"] = {k: v for k, v in d.items() if k != "hidden_because"}
