"""Read-only access to the institute mailbox (Google-hosted, IMAP + app password).

The mailbox is opened with EXAMINE (read-only) and messages are fetched with
BODY.PEEK, so Ping never marks anything as read, moves or deletes anything.
It searches "All Mail" so it still finds OTP mails after you add a filter
that skips the inbox.
"""

from __future__ import annotations

import email
import email.policy
import imaplib
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .config import IST

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")


@dataclass
class Mail:
    uid: str
    received: datetime
    sender: str
    subject: str
    text: str
    links: list[str] = field(default_factory=list)


def extract_otp(subject: str, body: str) -> str | None:
    text = f"{subject}\n{body}"
    if not re.search(r"\botp\b|one[\s-]*time[\s-]*pass", text, re.I):
        return None
    m = re.search(r"(?:otp|one[\s-]*time[\s-]*password)[^0-9]{0,60}?(\d{4,8})\b", text, re.I | re.S)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{6})\b", text)
    return m.group(1) if m else None


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", html)
    html = re.sub(r"(?i)<a\s[^>]*href=[\"']([^\"']+)[\"'][^>]*>", r" \1 ", html)
    text = re.sub(r"<[^>]+>", " ", html)
    import html as _h
    return re.sub(r"[ \t]+", " ", _h.unescape(text))


def parse_message(uid: str, raw: bytes, internal: datetime | None) -> Mail:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    subject = str(msg.get("subject", "") or "")
    sender = str(msg.get("from", "") or "")
    parts = []
    for part in msg.walk():
        ctype = part.get_content_type()
        if part.get_content_disposition() == "attachment":
            continue
        if ctype in ("text/plain", "text/html"):
            try:
                content = part.get_content()
            except Exception:
                continue
            parts.append(_html_to_text(content) if ctype == "text/html" else content)
    text = "\n".join(parts)
    if internal is None:
        try:
            internal = parsedate_to_datetime(str(msg.get("date")))
        except Exception:
            internal = datetime.now(timezone.utc)
    links = list(dict.fromkeys(u.rstrip(".,;") for u in URL_RE.findall(text)))
    return Mail(uid, internal.astimezone(IST), sender, subject, text, links)


class Mailbox:
    def __init__(self, address: str, app_password: str, host: str = "imap.gmail.com"):
        self.address = address
        self.app_password = app_password
        self.host = host
        self.imap: imaplib.IMAP4_SSL | None = None
        self.folder = "INBOX"
        self.gmail = False
        self.last_otp_sender = ""
        self.last_otp_subject = ""

    # -- connection ----------------------------------------------------------
    def connect(self) -> None:
        if self.imap is not None:
            return
        self.imap = imaplib.IMAP4_SSL(self.host, 993, timeout=40)
        self.imap.login(self.address, self.app_password)
        self.gmail = b"X-GM-EXT-1" in b" ".join(
            c if isinstance(c, bytes) else c.encode() for c in self.imap.capabilities)
        self.folder = self._all_mail_folder() or "INBOX"
        typ, _ = self.imap.select(_quote(self.folder), readonly=True)  # EXAMINE: read-only
        if typ != "OK":
            self.folder = "INBOX"
            self.imap.select("INBOX", readonly=True)

    def _all_mail_folder(self) -> str | None:
        typ, data = self.imap.list()
        if typ != "OK":
            return None
        for line in data or []:
            s = line.decode(errors="replace") if isinstance(line, bytes) else str(line)
            if "\\All" in s:
                m = re.search(r'"([^"]+)"\s*$', s) or re.search(r"(\S+)\s*$", s)
                if m:
                    return m.group(1)
        return None

    def close(self) -> None:
        if self.imap is not None:
            try:
                self.imap.logout()
            except Exception:
                pass
        self.imap = None

    # -- searching -----------------------------------------------------------
    def _search_uids(self, after: datetime, words: str = "") -> list[str]:
        self.connect()
        self.imap.noop()  # refresh the read-only view so new mail shows up
        if self.gmail:
            q = f"after:{int(after.timestamp())}" + (f" {words}" if words else "")
            typ, data = self.imap.uid("SEARCH", "X-GM-RAW", _quote(q))
        else:
            since = (after - timedelta(days=1)).strftime("%d-%b-%Y")
            typ, data = self.imap.uid("SEARCH", "SINCE", since)
        if typ != "OK" or not data or not data[0]:
            return []
        return data[0].decode().split()

    def fetch(self, uids: list[str], limit: int = 200) -> list[Mail]:
        out = []
        for uid in uids[-limit:]:
            typ, data = self.imap.uid("FETCH", uid, "(INTERNALDATE BODY.PEEK[])")
            if typ != "OK" or not data or not isinstance(data[0], tuple):
                continue
            meta, raw = data[0][0], data[0][1]
            internal = None
            m = re.search(rb'INTERNALDATE "([^"]+)"', meta or b"")
            if m:
                internal = imaplib.Internaldate2tuple(b'INTERNALDATE "' + m.group(1) + b'"')
                internal = datetime.fromtimestamp(time.mktime(internal), timezone.utc) if internal else None
            out.append(parse_message(uid, raw, internal))
        return out

    def mails_after(self, after: datetime, words: str = "") -> list[Mail]:
        mails = self.fetch(self._search_uids(after, words))
        return [m for m in mails if m.received >= after - timedelta(seconds=5)]

    def wait_for_otp(self, clicked_at: datetime, timeout: float, poll: float = 5.0,
                     ignore_uids: set[str] | None = None) -> tuple[str | None, str | None]:
        """Poll until an OTP mail that arrived after `clicked_at` shows up."""
        deadline = time.monotonic() + timeout
        ignore = ignore_uids or set()
        # 30s of slack for clock differences between GitHub and Google
        since = clicked_at - timedelta(seconds=30)
        while True:
            try:
                for mail in sorted(self.mails_after(since, "OTP"), key=lambda m: m.received, reverse=True):
                    if mail.uid in ignore:
                        continue
                    code = extract_otp(mail.subject, mail.text)
                    if code:
                        self.last_otp_sender, self.last_otp_subject = mail.sender, mail.subject
                        return code, mail.uid
            except imaplib.IMAP4.abort:
                self.close()
            if time.monotonic() >= deadline:
                return None, None
            time.sleep(poll)


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
