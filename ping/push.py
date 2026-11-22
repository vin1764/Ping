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


def pick(new_items: list[dict], now: datetime) -> tuple[dict, int] | None:
    """The one message this run pushes (the most urgent new one that's for you) and how many others were for you."""
    mine = [it for it in new_items if is_for_you(it)]
    if not mine:
        return None
    future = lambda it: str(it.get("due_at") or it.get("event_at") or "9999")  # noqa: E731
    mine.sort(key=lambda it: (0 if it.get("category") == "test" else 1, future(it)))
    return mine[0], len(mine) - 1


def payload(it: dict, others: int, now: datetime) -> dict:
    body = first_line(it) + (f" (+{others} more for you)" if others else "")
    return {"mode": "notify", "id": it["id"], "title": label(it, now), "body": body,
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
        company = it.get("company") or "Your"
        body = f"{company} test at {at.astimezone(IST).strftime('%H:%M')}" + (f" · {where}" if where else "")
        out.append({"id": f"reminder:{it['id']}", "kind": "reminder", "title": f"Test · {_when(it['event_at'], now)}",
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
        what = "Form" if action == "fill_form" else "Test" if action == "take_test" else "Deadline"
        company = it.get("company") or "From your mail"
        body = f"{company}: " + ("fill the form" if action == "fill_form" else "complete the online test" if action == "take_test"
                                 else first_line(it, 120)) + f" by {at.astimezone(IST).strftime('%H:%M')}"
        row = {"id": f"reminder:{it['id']}", "kind": "reminder", "title": f"{what} · due {_when(it['due_at'], now)}",
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
