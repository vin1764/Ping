"""Reading a form's page, to tell forms apart and to see when one has closed. Read-only, like the rest of Ping:
a plain GET of the public page, no cookies, no sign-in, nothing typed, prefilled or submitted.

What is read (and kept in form_pages, by the form's key):
  - where a short link (forms.gle, bit.ly, tinyurl, lnkd.in, …) really points: followed hop by hop, at most 5 hops,
    only to http(s) addresses on public host names
  - the title, the description's first lines and the number of questions (Google Forms: from the page's own data;
    other form sites: the page's title and description when they have them)
  - "no longer accepting responses": the form is closed
  - "sign-in required": the page sends you to a sign-in page (an institute or Google / Microsoft account). Ping
    stores that and stops there; it never tries to sign in. The Forms tab then shows the link and the notice text.

Limits: one page at most 600 KB, 8 s per request, 15 pages and 45 s per run; a page is read again after 6 h, or at
once when the form is posted again. Anything unexpected (a timeout, an odd page) is stored as an error and the row
keeps what the notice said.
"""

from __future__ import annotations

import html
import ipaddress
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit

from .forms import SHORT_HOSTS, is_form_link, key_of

MAX_BYTES = 600_000
TIMEOUT = 8
MAX_HOPS = 5
PER_RUN = 15
RUN_BUDGET_S = 45
FRESH = timedelta(hours=6)
UA = "Mozilla/5.0 (compatible; form-reader; read-only)"

SIGNIN_HOSTS = ("accounts.google.com", "login.microsoftonline.com", "login.live.com", "login.microsoft.com",
                "accounts.zoho.com", "accounts.zoho.in")
CLOSED_RX = re.compile(r"no longer accepting responses|is not accepting responses|this form (?:is|has been) closed|"
                       r"form (?:is )?closed|responses? (?:are|is) closed|isn['’]t accepting responses", re.I)
SIGNIN_RX = re.compile(r"you need permission|sign in to continue|you must sign in|only users in .{1,60} can|"
                       r"requires? (?:you to )?sign[- ]?in|login required", re.I)
# Google Forms item types that aren't questions: 6 title/description, 8 section, 11 image, 12 video
NOT_QUESTIONS = {6, 8, 11, 12}


def _public_host(host: str) -> bool:
    host = (host or "").lower().strip(".")
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".lan")) or "." not in host:
        return False
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_global
    except ValueError:
        return True


def _allowed(url: str) -> bool:
    u = urlsplit(url)
    return u.scheme in ("http", "https") and _public_host(u.hostname or "")


def _meta(page: str, prop: str) -> str | None:
    m = re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]*content=["\']([^"\']*)["\']', page, re.I) \
        or re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']{re.escape(prop)}["\']', page, re.I)
    return html.unescape(m.group(1)).strip() if m else None


def _first_lines(text: str | None, n: int = 2, cap: int = 240) -> str | None:
    if not text:
        return None
    lines = [l.strip() for l in re.split(r"[\r\n]+", text) if l.strip()]
    out = " ".join(lines[:n])
    return (out[: cap - 1].rstrip() + "…") if len(out) > cap else (out or None)


def parse(page: str, final_url: str) -> dict:
    """What a form page says. Pure: tests feed it saved pages."""
    host = (urlsplit(final_url).hostname or "").lower()
    out = {"final_url": final_url, "title": None, "description": None, "question_count": None,
           "closed": False, "signin_required": False}
    if host in SIGNIN_HOSTS or re.search(r"/(ServiceLogin|signin|oauth2|login)\b", urlsplit(final_url).path, re.I) and host.startswith(("accounts.", "login.")):
        out["signin_required"] = True
        return out
    text = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", page, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text)
    title = _meta(page, "og:title")
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
        title = html.unescape(m.group(1)).strip() if m else None
    out["title"] = re.sub(r"\s*[-|–]\s*(Google Forms|Microsoft Forms|Zoho Forms|Typeform|Jotform)\s*$", "", title or "").strip() or None
    out["description"] = _first_lines(_meta(page, "og:description") or _meta(page, "description"))
    # Google Forms: FB_PUBLIC_LOAD_DATA_ = [null, [description, [items…], …], …, title, …]
    m = re.search(r"FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.*?\])\s*;\s*</script>", page, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            body = data[1]
            if isinstance(body, list):
                if body[0] and isinstance(body[0], str):
                    out["description"] = _first_lines(body[0])
                its = body[1] if len(body) > 1 and isinstance(body[1], list) else []
                out["question_count"] = sum(1 for it in its if isinstance(it, list) and len(it) > 3 and it[3] not in NOT_QUESTIONS)
                if len(body) > 8 and isinstance(body[8], str) and body[8].strip():
                    out["title"] = body[8].strip()
            if len(data) > 3 and isinstance(data[3], str) and data[3].strip() and not out["title"]:
                out["title"] = data[3].strip()
        except (ValueError, IndexError, TypeError):
            pass
    if "/closedform" in urlsplit(final_url).path or CLOSED_RX.search(text[:20000]):
        out["closed"] = True
    if SIGNIN_RX.search(text[:20000]) and not out["question_count"]:
        out["signin_required"] = True
    return out


def _is_form(url: str) -> bool:
    k = key_of(url) or ""
    return bool(k) and not k.startswith(("short:", "url:"))


def _through_signin(url: str) -> str:
    """A short link that lands on a sign-in page: the form it was going to (the sign-in page's continue=)."""
    u = urlsplit(url)
    if (u.hostname or "").lower() in SIGNIN_HOSTS:
        from urllib.parse import parse_qs
        for name in ("continue", "followup", "redirect_uri", "ru"):
            for v in parse_qs(u.query).get(name) or []:
                if _is_form(v):
                    return v
    return url


class Reader:
    """Follows short links and reads form pages for one run, within the run's limits. get(url) -> (final_url,
    body) is injectable for tests; the default is a plain GET with no cookies."""

    def __init__(self, cache: dict[str, dict] | None = None, get=None, now: datetime | None = None,
                 per_run: int = PER_RUN, budget_s: float = RUN_BUDGET_S):
        self.cache = dict(cache or {})
        self.now = now or datetime.now(timezone.utc)
        self._get = get or self._http_get
        self.left = per_run
        self.deadline = time.monotonic() + budget_s
        self.saved: list[dict] = []          # rows to store in form_pages
        self.stats = {"followed": 0, "read": 0, "cached": 0, "closed": 0, "signin": 0, "errors": 0}

    # ------------------------------------------------------------------ network (GET only, no cookies)
    @staticmethod
    def _http_get(url: str, stop=None) -> tuple[str, str]:
        """(final address, page). stop(url): stop following there (a short link has reached its form)."""
        import requests
        for _ in range(MAX_HOPS + 1):
            if not _allowed(url):
                raise ValueError("not a public web address")
            if stop and stop(url):
                return url, ""
            r = requests.get(url, allow_redirects=False, timeout=TIMEOUT, stream=True,
                             headers={"User-Agent": UA, "Accept": "text/html"})
            try:
                if r.is_redirect or r.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, r.headers.get("Location", ""))
                    continue
                body = b""
                for chunk in r.iter_content(32_768):
                    body += chunk
                    if len(body) >= MAX_BYTES:
                        break
                return url, body[:MAX_BYTES].decode(r.encoding or "utf-8", "replace")
            finally:
                r.close()
        raise ValueError("too many redirects")

    def _can(self) -> bool:
        return self.left > 0 and time.monotonic() < self.deadline

    def _fresh(self, row: dict | None, posted_at: str | None = None) -> bool:
        if not row or not row.get("fetched_at"):
            return False
        try:
            at = datetime.fromisoformat(str(row["fetched_at"]).replace("Z", "+00:00"))
        except ValueError:
            return False
        if posted_at:
            try:
                if datetime.fromisoformat(str(posted_at).replace("Z", "+00:00")) > at:
                    return False           # posted again since: read it again (an extension may reopen it)
            except ValueError:
                pass
        return self.now - at < FRESH

    def _store(self, key: str, info: dict, error: str | None = None) -> dict:
        row = {"key": key, "final_url": info.get("final_url"), "fetched_at": self.now.isoformat(),
               "title": info.get("title"), "description": info.get("description"),
               "question_count": info.get("question_count"), "closed": bool(info.get("closed")),
               "signin_required": bool(info.get("signin_required")), "error": error}
        self.cache[key] = row
        self.saved.append(row)
        return row

    # ------------------------------------------------------------------ short links (forms.build's fetch)
    def follow(self, url: str) -> str:
        """Where a short link points (cached by its own key)."""
        k = key_of(url)
        cached = self.cache.get(k)
        if cached and cached.get("final_url"):
            self.stats["cached"] += 1
            return cached["final_url"]
        if not self._can():
            return url
        self.left -= 1
        try:
            final, _ = self._get(url, stop=_is_form)
            final = _through_signin(final)
            self.stats["followed"] += 1
            self._store(k, {"final_url": final})
            return final
        except Exception as e:
            self.stats["errors"] += 1
            self._store(k, {"final_url": None}, error=f"{type(e).__name__}: {str(e)[:120]}")
            return url

    # ------------------------------------------------------------------ form pages
    def read(self, key: str, url: str, posted_at: str | None = None) -> dict | None:
        if not url or not is_form_link(url) and not key.startswith(("gform:", "msform:", "zoho:", "typeform:", "jotform:")):
            return self.cache.get(key)
        if self._fresh(self.cache.get(key), posted_at):
            self.stats["cached"] += 1
            return self.cache[key]
        if not self._can():
            return self.cache.get(key)
        self.left -= 1
        try:
            final, body = self._get(url)
            info = parse(body, final)
            self.stats["read"] += 1
            self.stats["closed"] += int(info["closed"])
            self.stats["signin"] += int(info["signin_required"])
            return self._store(key, info)
        except Exception as e:
            self.stats["errors"] += 1
            return self._store(key, {"final_url": url}, error=f"{type(e).__name__}: {str(e)[:120]}")

    def read_rows(self, rows: list[dict]) -> dict[str, dict]:
        """Read the page of each form that has a link (soonest deadline first), within the run's limits."""
        for r in sorted(rows, key=lambda r: (r.get("closed"), r.get("due_at") or "9999")):
            url = r.get("final_url") or r.get("link")
            if url and not r["key"].startswith(("notice:", "item:", "short:")):
                last = max((s.get("at") or "" for s in r.get("sources") or []), default=None)
                self.read(r["key"], url, last or None)
        return {k: v for k, v in self.cache.items()}
