"""Build the feed: one item per thing you should know or do, each with a
one-line title under 160 characters and a level:

  always  anything about a role you applied to (shortlist, test, extension, result),
          or any list/notice that names you
  show    eligible, not applied, deadline ahead, not marked not-interested
          ("apply by X"), plus 24h reminders and "is this about X?" questions
  hidden  kept but not shown: not eligible, deadline gone, not interested,
          or not about you
The whole feed is rebuilt every run from stored data, so profile changes
(CGPA, not-interested list...) take effect on the next run.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from .config import IST
from .dates import fmt_when
from .eligibility import evaluate
from .matching import CompanyIndex, compact
from .notices import roles_for_target

APPLY_KINDS = ("apply_open", "deadline_extended", "form")
LIST_KINDS = ("test", "test_rooms", "shortlist", "result")


def clip(s: str, n: int = 160) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rstrip(" ,.;:") + "…"


def _dt(v) -> datetime | None:
    if not v:
        return None
    return v if isinstance(v, datetime) else datetime.fromisoformat(v)


def _roles_label(roles: list[dict]) -> str:
    names = list(dict.fromkeys(r["designation"] for r in roles))
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    joined = ", ".join(names)
    return joined if len(joined) <= 50 else f"{len(names)} roles"


def _in(company: str, names: list[str]) -> bool:
    c = compact(company)
    return any(compact(n) and (compact(n) == c or compact(n) in c or c in compact(n)) for n in names or [])


def effective_deadlines(roles: list[dict], notices: list[dict], index: CompanyIndex) -> dict[str, dict]:
    """A notice that gives a later deadline than the companies list wins."""
    out = {}
    for r in roles:
        out[r["id"]] = {"at": r.get("apply_end"), "source": "companies list", "text": r.get("apply_end_text")}
    for n in sorted(notices, key=lambda n: n.get("notice_time") or ""):
        a = n.get("analysis") or {}
        if a.get("kind") not in APPLY_KINDS:
            continue
        apply_due = next((t for t in a.get("todos", []) if t["action"] == "apply" and t.get("due")), None)
        if not apply_due:
            continue
        for t in a.get("targets", []):
            if not t.get("company"):
                continue
            picked, _ = roles_for_target(t, index, a["kind"], n.get("text") or "")
            for r in picked:
                cur = _dt(out[r["id"]]["at"])
                new = _dt(apply_due["due"])
                if cur is None or new > cur:
                    out[r["id"]] = {"at": apply_due["due"], "source": f"notice {n['notice_id']}",
                                    "text": apply_due.get("due_text")}
    return out


def build_items(roles: list[dict], notices: list[dict], pdf_checks: dict, profile: dict, now: datetime,
                emails: list[dict] | None = None, corrections: dict | None = None,
                stats: dict | None = None, previous: dict[str, dict] | None = None) -> list[dict]:
    corrections = corrections or {}
    emails = emails or []
    index = CompanyIndex(roles)
    not_int = profile.get("not_interested_companies") or []
    interested = profile.get("interested_companies") or []
    types = [t.upper() for t in (profile.get("notice_types") or ["PLACEMENT"])]
    deadlines = effective_deadlines(roles, notices, index)
    elig = {r["id"]: evaluate(r, profile) for r in roles}
    items: list[dict] = []

    def open_for_me(r):
        due = _dt(deadlines[r["id"]]["at"])
        return (not r.get("applied") and elig[r["id"]]["eligible"] is not False
                and due is not None and due > now and not _in(r["company"], not_int))

    # ---------------------------------------------------------- role items
    for r in roles:
        e = elig[r["id"]]
        dl = deadlines[r["id"]]
        due = _dt(dl["at"])
        if r.get("applied"):
            continue
        base = {"company": r["company"], "role_ids": [r["id"]], "notice_id": None, "due_at": dl["at"],
                "event_at": None, "pdf_status": None, "needs_review": False}
        details = {"reasons": e["reasons"], "flags": e["flags"], "deadline_source": dl["source"],
                   "deadline_text": dl["text"], "ctc": r.get("ctc"), "currency": r.get("currency"),
                   "interested": _in(r["company"], interested)}
        why_hidden = None
        if _in(r["company"], not_int):
            why_hidden = "marked not interested"
        elif e["eligible"] is False:
            why_hidden = "not eligible: " + "; ".join(e["reasons"])
        elif due is None or due <= now:
            why_hidden = "deadline gone"
        level = "hidden" if why_hidden else "show"
        crit = ", ".join(e["reasons"]) or "check criteria"
        if e["eligible"] is None:
            crit = "check: " + ", ".join(e["flags"])
        title = f"{r['company']} opened, eligible for {r['designation']} ({crit}). Apply by {fmt_when(due, now)}."
        if e["eligible"] is None:
            title = f"{r['company']} {r['designation']} is open ({crit}). Apply by {fmt_when(due, now)}."
        if why_hidden:
            details["hidden_because"] = why_hidden
            title = f"{r['company']} {r['designation']}: {why_hidden.rstrip('.')}."
        items.append({**base, "id": f"role:{r['id']}:apply", "level": level, "category": "apply",
                      "title": clip(title), "details": details, "sort_at": dl["at"]})
        if level == "show" and due and now >= due - timedelta(hours=24):
            items[-1]["level"] = "hidden"  # the reminder takes its place, so the role isn't listed twice
            items[-1]["details"] = {**details, "hidden_because": "replaced by the 24h reminder"}
            items.append({**base, "id": f"role:{r['id']}:reminder24", "level": "show", "category": "reminder",
                          "title": clip(f"Reminder: {r['company']} {r['designation']} closes {fmt_when(due, now)}. "
                                        f"You haven't applied."),
                          "details": details, "sort_at": dl["at"]})

    # -------------------------------------------------------- notice items
    for n in notices:
        if (n.get("type") or "PLACEMENT").upper() not in types:
            continue
        a = n.get("analysis") or {}
        kind = a.get("kind", "info")
        text = n.get("text") or n.get("preview") or ""
        check = pdf_checks.get(n["id"])
        pdf_status = check["status"] if check else None
        fix = corrections.get(n["id"]) or {}
        if fix.get("ignore"):
            continue
        targets = list(a.get("targets", []))
        unsure = list(a.get("unsure", []))
        if fix.get("company"):
            targets = [{"name": fix["company"], "company": index.canonical(fix["company"]),
                        "profiles": fix.get("profiles", []), "score": 1.0}]
            unsure = []
        when_event = next((e["at"] for e in a.get("events", [])), None)
        nbase = {"notice_id": n["notice_id"], "pdf_status": pdf_status, "needs_review": False}
        ndetails = {"subject": n.get("subject"), "kind": kind, "venue": a.get("venue"),
                    "contacts": a.get("contacts"), "links": a.get("links"), "forms": a.get("forms"),
                    "deadlines": a.get("deadlines"), "method": a.get("method"),
                    "notice_time": n.get("notice_time"), "notice_year": n.get("year"), "notice_key": n["id"]}
        if check:
            ndetails["pdf"] = {k: check.get(k) for k in ("status", "matched_by", "details", "error", "header", "my_row")}

        produced = False
        for ti, t in enumerate(targets):
            picked, why = roles_for_target(t, index, kind, text) if t.get("company") else ([], "not in your companies list")
            applied = [r for r in picked if r.get("applied")]
            open_roles = [r for r in picked if open_for_me(r)]
            company = t.get("company") or t.get("name") or n.get("company")
            label = _roles_label(applied or picked) or ", ".join(t.get("profiles") or [])
            label_s = f" ({label})" if label else ""
            event_at = t.get("start") or when_event
            pdf_yes = pdf_status == "yes"
            about_me = pdf_yes or a.get("mentions_me")
            mail_links = _mail_links(emails, company, n.get("notice_time")) if a.get("email_hint") else []
            det = {**ndetails, "role_match": why, "mail_links": mail_links, "applied": bool(applied),
                   "profiles": [p for p in (t.get("profiles") or []) if p.strip().lower() != "all"]}
            base = {**nbase, "company": company, "role_ids": [r["id"] for r in (applied or picked)],
                    "event_at": event_at, "due_at": None, "details": det}
            nid = f"notice:{n['id']}:{ti}"

            if about_me:
                level = "always"
            elif applied:
                level = "always"
            elif open_roles and kind in APPLY_KINDS + ("ppt",):
                level = "show"
            else:
                level = "hidden"
            if not t.get("company") and not about_me:
                continue  # a company that isn't in your companies list at all: not about you

            # a day schedule tags each entry: "[PPT] OLA (6 PM)" is a talk even in a list of tests
            tag = (t.get("tag") or "").upper()
            tkind = "ppt" if tag.startswith("PPT") else "test" if tag.startswith("TEST") and kind in LIST_KINDS + ("ppt",) else kind
            kind_for_target = tkind

            # -- lists: shortlist / room allocation / test schedule / result
            if kind_for_target in LIST_KINDS:
                what = {"shortlist": "shortlist", "result": "result", "test_rooms": "test room list",
                        "test": "test"}[kind]
                room = _room(check)
                ev = f" {fmt_when(_dt(event_at), now)}" if event_at else ""
                venue = f", {a['venue']}" if a.get("venue") else ""
                mail = " Link in your mail." if mail_links else (" Check your mail for the link." if a.get("email_hint") else "")
                if pdf_yes:
                    title = f"You're on the {company} {what}{label_s}.{' Test' + ev if ev else ''}{venue}{room}.{mail}"
                elif pdf_status == "no":
                    title = f"{company} {what} is out{label_s}. You're not on it."
                    if not applied:
                        level = "hidden"
                elif pdf_status == "unknown":
                    title = f"{company} {what} is out{label_s} but the file couldn't be read. Check it yourself."
                elif n.get("has_attachment") and check is None:
                    title = f"{company} {what} is out{label_s}. File not checked yet."
                else:
                    title = f"{company} {what}{label_s}{ev}{venue}.{mail}"
                items.append({**base, "id": nid, "level": level, "category": kind if kind != "test_rooms" else "test",
                              "title": clip(title), "sort_at": event_at or n.get("notice_time")})
                produced = True
            elif kind_for_target == "ppt":
                ev = fmt_when(_dt(event_at), now) if event_at else "time in notice"
                venue = f", {a['venue']}" if a.get("venue") else ""
                items.append({**base, "id": nid, "level": level, "category": "ppt",
                              "title": clip(f"{company} pre-placement talk{label_s}: {ev}{venue}."),
                              "sort_at": event_at or n.get("notice_time")})
                produced = True
            elif kind in ("ppo", "info", "schedule"):
                first = re.split(r"(?<=[.!?])\s|\n", text.strip())[0] if text.strip() else n.get("subject", "")
                title = f"{company}: you're named in this notice ({n.get('subject')})." if a.get("mentions_me") \
                    else f"{company} update ({n.get('subject')}): {first}"
                items.append({**base, "id": nid, "level": level if (about_me or applied) else "hidden",
                              "category": "offer" if kind == "ppo" else "info", "title": clip(title),
                              "sort_at": n.get("notice_time")})
                produced = True
            elif kind == "deadline_extended" and applied:
                due = next((d["due"] for d in a.get("todos", []) if d["action"] == "apply" and d.get("due")), None)
                items.append({**base, "id": nid, "level": "always", "category": "deadline", "due_at": due,
                              "title": clip(f"{company}{label_s} deadline extended to {fmt_when(_dt(due), now)} "
                                            f"(you've applied)."), "sort_at": due})
                produced = True

            # -- to-dos: forms / submissions (one notice can mean several)
            for k, todo in enumerate(a.get("todos", [])):
                if todo["action"] == "apply":
                    continue  # the role item already says "apply by", with this notice's deadline if later
                due = todo.get("due")
                if todo["action"] == "fill_form":
                    title = (f"{company}{label_s}: fill the form by {fmt_when(_dt(due), now)}." if due
                             else f"{company}{label_s}: fill the form (no deadline given, see the notice).")
                    if not applied and not open_roles:
                        lvl = "hidden"
                    else:
                        lvl = level if level != "hidden" else "show"
                elif todo["action"] == "accept_offer":
                    title = f"{company} offered you a PPO. Accept by {fmt_when(_dt(due), now)}."
                    lvl = "always"
                else:
                    title = (f"{company}{label_s}: submit by {fmt_when(_dt(due), now)}." if due
                             else f"{company}{label_s}: submit (no deadline given, see the notice).")
                    lvl = "always" if (applied or about_me) else "hidden"
                if due and _dt(due) <= now and lvl != "always":
                    lvl = "hidden"
                items.append({**base, "id": f"{nid}:todo{k}", "level": lvl, "category": "todo", "due_at": due,
                              "title": clip(title), "details": {**det, "todo": todo}, "sort_at": due})
                produced = True

        # -- couldn't match: ask instead of guessing
        for ui, u in enumerate(unsure):
            cands = [c for c, _ in u.get("candidates", [])][:3]
            relevant = any(r.get("applied") or open_for_me(r)
                           for c in cands for r in index.by_company.get(c, []))
            items.append({**nbase, "id": f"notice:{n['id']}:unsure{ui}", "level": "show" if relevant else "hidden",
                          "category": "review", "company": None, "role_ids": [], "due_at": None, "event_at": None,
                          "needs_review": True,
                          "title": clip(f"A {n.get('subject', '').lower()} notice says \"{u['name']}\". "
                                        f"Which company is that: {' or '.join(cands)}? Tap to choose."),
                          "details": {**ndetails, "candidates": cands, "name_in_notice": u["name"]},
                          "sort_at": n.get("notice_time")})
            produced = True

        if not produced and a.get("mentions_me"):
            items.append({**nbase, "id": f"notice:{n['id']}:me", "level": "always", "category": "info",
                          "company": n.get("company"), "role_ids": [], "due_at": None, "event_at": None,
                          "title": clip(f"You're named in a {n.get('subject')} notice ({n.get('company')})."),
                          "details": ndetails, "sort_at": n.get("notice_time")})

    # --------------------------------------------------------- email items
    applied_companies = {r["company"] for r in roles if r.get("applied")}
    for m in emails:
        c = m.get("company")
        if c and c in applied_companies:
            items.append({"id": f"mail:{m['id']}", "level": "always", "category": "email", "company": c,
                          "role_ids": [], "notice_id": None, "due_at": None, "event_at": None,
                          "pdf_status": None, "needs_review": False,
                          "title": clip(f"{c} emailed you: {m.get('subject', '')}"),
                          "details": {"from": m.get("sender"), "links": m.get("links", [])[:10],
                                      "received_at": m.get("received_at")},
                          "sort_at": m.get("received_at")})
    for it in items:
        it.setdefault("details", {})
        it["title"] = clip(it["title"])
    # Is it really new? Collapse repeats (re-posted notices, extensions repeating the original,
    # emails repeating a notice) and turn real changes into one "Update" message. This runs over
    # everything that was ever sent, before old messages are marked as past, so a repeat of last
    # week's notice is still recognised.
    from .dedupe import dedupe
    items, dstats = dedupe(items, now)
    for it in items:
        _expire(it, now)
    # fewer, fuller messages: deadline digests, one "new roles" message per run, same-run list collapses
    from . import digests
    members = {}
    for r in roles:
        e = elig[r["id"]]
        if e["eligible"] is False or _in(r["company"], not_int):
            continue
        dl = deadlines[r["id"]]
        members[r["id"]] = {"id": r["id"], "company": r["company"], "label": r["designation"], "due": _dt(dl["at"]),
                            "source": dl["source"], "applied": bool(r.get("applied")), "eligible": e["eligible"],
                            "first_seen": r.get("first_seen")}
    items = digests.build(items, members, previous or {}, profile, now)
    if stats is not None:
        stats.update(dstats)
    return items


def _expire(it: dict, now: datetime) -> None:
    """Past things drop out of the feed (kept as hidden): deadlines that have gone,
    tests/talks that finished 12h+ ago, and list news older than 3 days."""
    if it["level"] == "hidden" or it["category"] in ("apply", "reminder", "review"):
        return
    due, event = _dt(it.get("due_at")), _dt(it.get("event_at"))
    sort = _dt(it.get("sort_at"))
    why = None
    if due and due < now:
        why = "deadline gone"
    elif event and event < now - timedelta(hours=12):
        why = "already happened"
    elif not due and not event and sort and sort < now - timedelta(days=3):
        why = "older than 3 days"
    if why:
        it["level"] = "hidden"
        it["details"] = {**it.get("details", {}), "hidden_because": why}


def _room(check: dict | None) -> str:
    if not check or check.get("status") != "yes":
        return ""
    d = check.get("details") or {}
    bits = []
    if d.get("slot") or d.get("slot_from_heading"):
        bits.append(str(d.get("slot") or d.get("slot_from_heading")))
    if d.get("time") or d.get("time_from_heading"):
        bits.append(str(d.get("time") or d.get("time_from_heading")))
    if d.get("room") or d.get("room_or_venue_from_heading"):
        bits.append(f"room {d.get('room') or d.get('room_or_venue_from_heading')}")
    return (", " + ", ".join(bits)) if bits else ""


def _mail_links(emails: list[dict], company: str, after: str | None) -> list[str]:
    links = []
    c = compact(company or "")
    for m in emails:
        if after and (m.get("received_at") or "") < after:
            continue
        if c and (c in compact(m.get("subject", "")) or c in compact(m.get("sender", ""))
                  or c in compact(m.get("company") or "")):
            links += m.get("links", [])[:5]
    return list(dict.fromkeys(links))[:5]
