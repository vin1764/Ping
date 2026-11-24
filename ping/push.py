"""Notifications from the hourly run (docs/PUSH.md).

- At most one push per run: the most urgent new message that is for you (a digest with roles for you, a test or
  list that names you, a form you must fill, an update about a role you applied to). Nothing for "nothing new"
  runs or for messages about other roles only. Title = the message's label as the chat shows it ("Reminder · closes
  tonight 20:00"), body = its first line, tap = the thread at that message.
- Test-day reminders: every test a list says you're on gets a row in push_queue at the reminder lead time; pg_cron
  sends it through the send-push function at that time, whether or not a run happens.
- Optional: the same for-you messages by email (profile.email_digests, off by default).
The sending itself (VAPID, encryption) is the send-push function's; this module never holds the private key.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.parse import quote

import requests

from .config import IST

FOR_YOU_N = re.compile(r"(?:—\s*)?\b(\d+)\s+for you\b")


def _when(iso: str | None, now: datetime) -> str:
    if not iso:
        return ""
    t = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(IST)
    n = now.astimezone(IST)
    hm = t.strftime("%H:%M")
    if t.date() == n.date():
        return f"tonight {hm}" if t.hour >= 17 else f"today {hm}"
    if t.date() == (n + timedelta(days=1)).date():
        return f"tomorrow {hm}"
    return f"{t.strftime('%a')} {t.day} {t.strftime('%b')} {hm}"


def is_for_you(it: dict) -> bool:
    """A new chat message worth a push: about you, not only about other roles."""
    if it.get("level") == "hidden" or it.get("dismissed") or it.get("category") in ("apply", "reminder", "review"):
        return False
    d = it.get("details") or {}
    cat, kind = it.get("category"), d.get("kind")
    if cat in ("test", "shortlist", "result") or kind in ("test", "test_rooms", "shortlist", "result", "interview"):
        st = (d.get("pdf") or {}).get("status") or it.get("pdf_status")
        return st == "yes" or (st != "no" and it.get("level") == "always")
    if cat in ("digest", "listing") or kind in ("application", "deadline", "listing"):
        groups = d.get("list") or []
        if any(str(g.get("head", "")).split(" · ")[-1].startswith("For you") and g.get("rows") for g in groups):
            return True
        m = FOR_YOU_N.search(it.get("title") or "")
        return bool(m and int(m.group(1)) > 0) or (cat == "collapse" and it.get("level") == "always")
    if cat in ("todo", "form"):
        return it.get("level") in ("always", "show")
    return it.get("level") == "always"


def label(it: dict, now: datetime) -> str:
    """The message's label, as the chat's label line says it."""
    d = it.get("details") or {}
    cat, kind = it.get("category"), d.get("kind")
    due = it.get("due_at") or it.get("event_at")
    if cat in ("test",) or kind in ("test", "test_rooms", "interview"):
        return f"Test · {_when(it.get('event_at'), now)}".rstrip(" ·")
    if cat == "shortlist" or kind == "shortlist":
        return "Shortlist"
    if cat == "result" or kind == "result":
        return "Result"
    if cat == "listing" or kind == "listing":
        m = FOR_YOU_N.search(it.get("title") or "")
        return f"New · {m.group(1)} for you" if m else "New roles"
    if cat in ("todo", "form"):
        return f"Form · due {_when(due, now)}".rstrip(" ·due")
    if kind in ("application", "deadline") or cat == "digest":
        return f"Reminder · closes {_when(due, now)}".rstrip(" ·closes")
    return "Update"


def first_line(it: dict, limit: int = 160) -> str:
    t = re.sub(r"\s+", " ", str(it.get("title") or "")).strip()
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


# ---------------------------------------------------------------------------- what a notification says (23 Nov)
# Title: WHO and WHAT TO DO ("ZS Associates · Apply by tomorrow 20:00"); body: only what's needed to act (the role,
# "Apply with <CV>", the countdown), one or two short lines. Never the other roles ("Others") in a push.
_URLPAREN = re.compile(r"\s*\((?:[^()]*?(?:www\.|https?://|\.com|\.in|\.io|\.ai)[^()]*)\)", re.I)
_LEGAL = re.compile(r"[\s,]+(?:private\s+limited|pvt\.?\s*ltd\.?|limited|ltd\.?|llp|inc\.?)\s*$", re.I)
_ACRONYMS = set("ICICI HDFC IDFC HSBC HPCL BPCL IOCL ONGC NTPC BHEL GAIL SAIL KPMG NVIDIA EXL BNY UBS DBS ITC TVS JSW EY ZS SLB LTM AIG".split())


def display_name(name: str) -> str:
    """A company as a notification names it: no website in brackets, no 'Private Limited', a shouted name in title case
    with its acronyms kept ('ICICI LOMBARD' -> 'ICICI Lombard', 'BLUESTONE' -> 'Bluestone', 'ZS ASSOCIATES' ->
    'ZS Associates')."""
    s = _URLPAREN.sub("", name or "")
    for _ in range(2):
        s = _LEGAL.sub("", s)
    s = re.sub(r"\s{2,}", " ", s).strip() or (name or "").strip()
    if s != s.upper() or not re.search(r"[A-Z]{4,}", s):
        return s
    return " ".join(w if (len(w) <= 3 or re.search(r"\d", w) or re.sub(r"[^A-Z]", "", w) in _ACRONYMS) else w[0] + w[1:].lower()
                    for w in s.split(" "))


def _at(v) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(IST)
    except ValueError:
        return None


def by_when(at: datetime, now: datetime) -> str:
    """'20:00' today, 'tomorrow 20:00', 'Wed 14:00' within the week, 'Wed 26 Nov 14:00' after that."""
    a, n = at.astimezone(IST), now.astimezone(IST)
    hm = a.strftime("%H:%M")
    if a.date() == n.date():
        return hm
    if a.date() == (n + timedelta(days=1)).date():
        return f"tomorrow {hm}"
    if (a.date() - n.date()).days < 7:
        return f"{a.strftime('%a')} {hm}"
    return f"{a.strftime('%a')} {a.day} {a.strftime('%b')} {hm}"


def countdown(at: datetime, now: datetime) -> str:
    mins = int((at - now).total_seconds() // 60)
    if mins <= 0:
        return "now"
    if mins < 60:
        return f"in {mins} min"
    if mins < 24 * 60:
        h, m = divmod(mins, 60)
        return f"in {h} h {m} min" if m else f"in {h} h"
    return f"in {round(mins / 1440)} day{'s' if round(mins / 1440) != 1 else ''}"


def _role_of(roles: dict, rid) -> dict:
    return roles.get(rid) or roles.get(str(rid).replace("sample:", "")) or {}


def acts(items: list[dict], roles: dict[str, dict], now: datetime) -> list[dict]:
    """Every thing a for-you message asks you to do, one per role / form / test: {type, company, role, cv, at, item}.
    Types: apply, new, extended, form, test, shortlist. Roles you've applied to, forms you've ticked, lists that
    don't name you and other roles are left out."""
    out = []
    for it in items:
        d = it.get("details") or {}
        # a message folded into a digest is stored hidden but still to do (as on Today)
        if (it.get("level") == "hidden" and "digest" not in str(d.get("hidden_because") or "")) or it.get("dismissed") or it.get("done"):
            continue
        cat, kind = it.get("category"), d.get("kind")
        if cat in ("digest", "listing") and kind not in ("application", "listing"):
            continue                                  # a forms digest: its forms are their own to-dos below
        if kind in ("application", "listing"):
            # the For you rows only (when the roles are marked); every pending row when nothing is marked
            groups = d.get("list") or []
            marked = any(str(g.get("head", "")).split(" · ")[-1].startswith(("For you", "Others")) for g in groups)
            rows = [r for g in groups for r in (g.get("rows") or [])
                    if (str(g.get("head", "")).split(" · ")[-1].startswith("For you") if marked else not str(g.get("head", "")).startswith("Applied"))]
            typ = "new" if kind == "listing" else "extended" if d.get("role") in ("moved", "update") and "moved" in (it.get("title") or "").lower() else "apply"
            for r in rows:
                role = _role_of(roles, r.get("id"))
                if not role or role.get("applied") or r.get("tag") == "done":
                    continue                          # only rows that are roles you haven't applied to
                text = str(r.get("text") or "")
                co = role.get("company") or text.split(" — ")[0]
                label = role.get("designation") or (text.split(" — ", 1)[1] if " — " in text else "")
                cv = r.get("cv") or (role.get("relevance") or {}).get("best_cv")
                at = _at(role.get("effective_deadline") or role.get("apply_end")) or _at(it.get("due_at"))
                if at and at > now:
                    out.append({"type": typ, "company": display_name(co), "role": label, "cv": cv, "at": at, "item": it})
        elif ":update:" in str(it.get("id")) and cat in ("apply", "reminder"):
            role = _role_of(roles, (it.get("role_ids") or [None])[0])
            at = _at(it.get("due_at"))
            if at and at > now and not role.get("applied"):
                out.append({"type": "extended", "company": display_name(it.get("company") or role.get("company") or ""),
                            "role": role.get("designation") or "", "cv": (role.get("relevance") or {}).get("best_cv"), "at": at, "item": it})
        elif cat == "todo" and (d.get("todo") or {}).get("action") == "fill_form":
            at = _at(it.get("due_at"))
            if (d.get("form") or {}).get("filled") or not at or at <= now:
                continue
            # extended: only when the extension is new (in the last 3 h), never for a form's old history
            last = (d.get("extended") or [{}])[-1] if d.get("extended") else {}
            moved_at = _at(last.get("at") or last.get("seen_at"))
            typ = "extended" if moved_at and now - moved_at < timedelta(hours=3) else "form"
            out.append({"type": typ, "form": True, "company": display_name(it.get("company") or ""), "role": "", "cv": None,
                        "at": at, "item": it})
        elif cat in ("test",) or kind in ("test", "test_rooms", "interview"):
            st = (d.get("pdf") or {}).get("status") or it.get("pdf_status")
            at = _at(it.get("event_at"))
            if st == "no" or (st != "yes" and it.get("level") != "always") or not at or at <= now:
                continue
            row = (d.get("pdf") or {}).get("details") or {}
            room = row.get("room") or row.get("room_or_venue_from_heading")
            out.append({"type": "test", "company": display_name(it.get("company") or ""), "role": _roles_text(it, roles),
                        "room": room, "venue": d.get("venue"), "at": at, "item": it})
        elif cat == "shortlist" or kind == "shortlist":
            st = (d.get("pdf") or {}).get("status") or it.get("pdf_status")
            if st == "yes":
                out.append({"type": "shortlist", "company": display_name(it.get("company") or ""), "role": _roles_text(it, roles),
                            "at": None, "item": it})
    return out


def _roles_text(it: dict, roles: dict) -> str:
    names = [_role_of(roles, r).get("designation") for r in it.get("role_ids") or []]
    names = [n for n in dict.fromkeys(names) if n]
    if names:
        return ", ".join(names[:2])
    m = re.search(r"\(([^)]+)\)", it.get("title") or "")
    return m.group(1) if m else ""


ORDER = {"test": 0, "shortlist": 1, "form": 2, "extended": 2, "apply": 2, "new": 3}


def _url(a: dict) -> str:
    it = a["item"]
    if a["type"] in ("test", "shortlist"):
        return f"./#m-{quote(str(it['id']), safe='')}"
    ms = int(a["at"].timestamp() * 1000)
    return f"./#sheet/{'form' if a.get('form') else 'apply'}/{ms}"


def _line(a: dict, now: datetime, with_company: bool = True) -> str:
    who = f"{a['company']} — {a['role']}" if with_company and a.get("role") else a["company"] if with_company else a.get("role") or ""
    bits = [who] if who else []
    if a.get("cv"):
        bits.append(f"Apply with {a['cv']}")
    return " · ".join(bits)


def compose(items: list[dict], roles: dict[str, dict], now: datetime) -> dict | None:
    """The one notification for these new messages (the most urgent thing to do), or None. Several things due at the
    same time in this run become one: '2 to apply by tomorrow 20:00', one per line (first 3, then 'and N more')."""
    return render(acts(items, roles, now), now)


def render(all_acts: list[dict], now: datetime) -> dict | None:
    """The notification for these things to do: the most urgent, with the others due at the same time grouped."""
    if not all_acts:
        return None
    far = datetime.max.replace(tzinfo=IST)
    all_acts.sort(key=lambda a: (ORDER[a["type"]], a["at"] or far))
    first = all_acts[0]
    same = [a for a in all_acts if a["type"] == first["type"] and a["at"] == first["at"] and a["type"] not in ("test", "shortlist")] \
        if first["type"] in ("apply", "form", "new", "extended") else [first]
    # one company several times (two roles) still reads as one per line
    if len(same) > 1:
        n, when = len(same), by_when(first["at"], now)
        verb = {"apply": "to apply by", "new": "new roles for you, apply by", "form": "forms to fill by", "extended": "deadlines extended to"}[first["type"]]
        title = f"{n} {verb} {when}"
        lines = [_line(a, now) for a in same[:3]]
        if n > 3:
            lines.append(f"and {n - 3} more")
        body = "\n".join(lines + [countdown(first["at"], now)])
    else:
        a = first
        if a["type"] == "apply":
            title, body = f"{a['company']} · Apply by {by_when(a['at'], now)}", " · ".join(x for x in (a["role"], f"Apply with {a['cv']}" if a.get("cv") else "", countdown(a["at"], now)) if x)
        elif a["type"] == "new":
            title = f"{a['company']} · New role for you: {a['role']}" if a["role"] else f"{a['company']} · New role for you"
            body = " · ".join(x for x in (f"Apply with {a['cv']}" if a.get("cv") else "", f"apply by {by_when(a['at'], now)}", countdown(a["at"], now)) if x)
        elif a["type"] == "extended":
            title = f"{a['company']} · Deadline extended to {by_when(a['at'], now)}"
            body = " · ".join(x for x in (a["role"] or ("Fill the form" if a.get("form") else ""), f"Apply with {a['cv']}" if a.get("cv") else "", countdown(a["at"], now)) if x)
        elif a["type"] == "form":
            title, body = f"{a['company']} · Fill form by {by_when(a['at'], now)}", countdown(a["at"], now)
        elif a["type"] == "test":
            where = f"Room {a['room']}" if a.get("room") else a.get("venue") or ""
            title = " · ".join(x for x in (a["company"], f"Test at {by_when(a['at'], now)}", where) if x)
            body = " · ".join(x for x in (a["role"], countdown(a["at"], now)) if x)
        else:
            title, body = f"{a['company']} · You're on the shortlist", a["role"] or "Open the list in the chat"
    return {"mode": "notify", "id": first["item"]["id"], "title": title, "body": body, "url": _url(first),
            "tag": str(first["item"]["id"])[:120]}


def pick(new_items: list[dict], now: datetime) -> tuple[dict, int] | None:
    """The one message this run pushes (the most urgent new one that's for you) and how many others were for you."""
    mine = [it for it in new_items if is_for_you(it)]
    if not mine:
        return None
    future = lambda it: str(it.get("due_at") or it.get("event_at") or "9999")  # noqa: E731
    mine.sort(key=lambda it: (0 if it.get("category") == "test" else 1, future(it)))
    return mine[0], len(mine) - 1


def payload(it: dict, others: int, now: datetime) -> dict:
    """Kept for the email digest's subject; notifications come from compose()."""
    return {"mode": "notify", "id": it["id"], "title": label(it, now), "body": first_line(it),
            "url": f"./#m-{quote(str(it['id']), safe='')}", "tag": str(it["id"])[:120]}


def send(base_url: str, service_key: str, body: dict, timeout: int = 30) -> dict:
    r = requests.post(f"{base_url.rstrip('/')}/functions/v1/send-push", json=body, timeout=timeout,
                      headers={"Authorization": f"Bearer {service_key}", "apikey": service_key})
    try:
        out = r.json()
    except ValueError:
        out = {"error": r.text[:200]}
    return {"status": r.status_code, **out}


def reminders(items: list[dict], profile: dict, now: datetime) -> list[dict]:
    """push_queue rows for tests a list says you're on: "Groww test at 15:00 · room 304", sent at the lead time."""
    lead = timedelta(hours=float(profile.get("reminder_hours") or 2))
    out = []
    for it in items:
        d = it.get("details") or {}
        if not (it.get("category") == "test" or d.get("kind") in ("test", "test_rooms", "interview")) or not it.get("event_at"):
            continue
        st = (d.get("pdf") or {}).get("status") or it.get("pdf_status")
        if st == "no" or (st != "yes" and it.get("level") != "always"):
            continue
        at = datetime.fromisoformat(str(it["event_at"]).replace("Z", "+00:00"))
        if at <= now:
            continue
        row = (d.get("pdf") or {}).get("details") or {}
        where = " · ".join(x for x in (f"room {row['room']}" if row.get("room") else "", f"slot {row['slot']}" if row.get("slot") else "",
                                        d.get("venue") if not row.get("room") and d.get("venue") else "") if x)
        company = display_name(it.get("company") or "") or "Your test"
        where = where.replace("room ", "Room ", 1)
        title = " · ".join(x for x in (company, f"Test at {by_when(at, now)}", where) if x)
        m = re.search(r"\(([^)]+)\)", it.get("title") or "")
        body = m.group(1) if m else "Your test"
        out.append({"id": f"reminder:{it['id']}", "kind": "reminder", "title": title,
                    "body": body, "url": f"./#m-{quote(str(it['id']), safe='')}", "tag": f"reminder:{it['id']}"[:120],
                    "event_at": at.isoformat(), "send_at": max(at - lead, now).isoformat()})
    return out


def mail_reminders(items: list[dict], profile: dict, now: datetime) -> list[dict]:
    """push_queue rows for deadlines only your mail has (a form, a test link to complete by a time): sent at the
    reminder lead time before the deadline, like the ERP's own deadline reminders."""
    lead = timedelta(hours=float(profile.get("reminder_hours") or 2))
    out = []
    for it in items:
        d = it.get("details") or {}
        if d.get("via") != "email" or it.get("level") == "hidden" or it.get("dismissed") or it.get("done") or not it.get("due_at"):
            continue
        if (d.get("form") or {}).get("filled"):         # you've ticked this form: no reminder
            continue
        at = datetime.fromisoformat(str(it["due_at"]).replace("Z", "+00:00"))
        if at <= now:
            continue
        action = (d.get("todo") or {}).get("action")
        company = display_name(it.get("company") or "") or "From your mail"
        do = "Fill form" if action == "fill_form" else "Complete the test" if action == "take_test" else "Due"
        body = "From your mail" if action in ("fill_form", "take_test") else first_line(it, 120)
        row = {"id": f"reminder:{it['id']}", "kind": "reminder", "title": f"{company} · {do} by {by_when(at, now)}",
               "body": body, "url": f"./#m-{quote(str(it['id']), safe='')}", "tag": f"reminder:{it['id']}"[:120],
               "event_at": at.isoformat(), "send_at": max(at - lead, now).isoformat()}
        if (d.get("form") or {}).get("key"):           # send-push checks your tick again when it's time to send
            row["form_key"] = d["form"]["key"]
        out.append(row)
    return out


def email_text(new_items: list[dict], now: datetime, dashboard: str) -> tuple[str, str] | None:
    """Subject and body of the optional for-you email (profile.email_digests)."""
    mine = [it for it in new_items if is_for_you(it)]
    if not mine:
        return None
    first = mine[0]
    lines = [f"{label(it, now)}: {first_line(it, 300)}" for it in mine[:10]]
    if len(mine) > 10:
        lines.append(f"+{len(mine) - 10} more")
    return (f"Ping · {label(first, now)}" + (f" (+{len(mine) - 1} more)" if len(mine) > 1 else ""),
            "\n".join(lines) + f"\n\nOpen the chat: {dashboard}\n\n(You get these because \"Also email me\" is on in Profile.)")


def vapid_keys() -> tuple[str, str]:
    """A new VAPID key pair (P-256), base64url: (public key, uncompressed point; private key, 32 bytes)."""
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    b64u = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()  # noqa: E731
    pub = k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return b64u(pub), b64u(k.private_numbers().private_value.to_bytes(32, "big"))


if __name__ == "__main__":
    # python -m ping.push keys   (prints a key pair; Actions > Admin > push-setup does the whole setup instead)
    import sys
    if sys.argv[1:] == ["keys"]:
        pub, priv = vapid_keys()
        print(f"VAPID_PUBLIC_KEY={pub}\nVAPID_PRIVATE_KEY={priv}")
