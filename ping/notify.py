"""When Ping needs you (wrong security question, database not set up, login
keeps failing) it emails you, from your institute mailbox to itself, using the
same app password. At most once per problem per day."""

from __future__ import annotations

import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from .config import IST


def send_self(address: str, app_password: str, subject: str, body: str, host: str = "smtp.gmail.com") -> bool:
    msg = EmailMessage()
    msg["From"] = address
    msg["To"] = address
    msg["Subject"] = f"[Ping] {subject}"
    msg.set_content(body + "\n\n- Ping (sent from your own mailbox to yourself)")
    try:
        with smtplib.SMTP_SSL(host, 465, timeout=30) as s:
            s.login(address, app_password)
            s.send_message(msg)
        return True
    except Exception:
        return False


def should_alert(store, key: str, store_ok: bool) -> bool:
    now = datetime.now(timezone.utc)
    if store_ok:
        last = store.get_state(f"alert:{key}")
        if last and now - datetime.fromisoformat(last) < timedelta(hours=20):
            return False
        store.set_state(f"alert:{key}", now.isoformat())
        return True
    # No database to remember what was sent: only alert on a manual run or the 9am run.
    manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    return manual or datetime.now(IST).hour == 9
