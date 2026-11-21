"""Job descriptions: where a role's JD lives and its text.

The companies list's "job description" field is often a placeholder ("Find Attached", "PFA the JD", "-") or a link
(Google Drive / Docs, a careers page). This module turns what the ERP gives into {jd_text, jd_source, jd_url}:

  jd_source = "inline"           the ERP's own field has the JD
              "detail"           the role popup / "more details" has more than the companies list
              "attachment"       a document on the ERP for the role (read like notice attachments, OCR included)
              "link"             a public link, fetched (Google Docs as text, Drive files, web pages)
              "link-unreadable"  a link that is private, dead or too big: kept with its URL
              "none"             nothing found

External links: GET only, no cookies, no forms, public hosts only (never a private or local address), 20 s and 12 MB
at most, at most 3 redirects, each re-checked. Nothing is ever submitted anywhere.
"""

from __future__ import annotations

import hashlib
import io
import ipaddress
import re
import socket
import zipfile
from urllib.parse import urlsplit

URL = re.compile(r"https?://[^\s<>\"')]+")
MAX_BYTES = 12 * 1024 * 1024     # a JD PDF with images (a brochure) can be ~8 MB
TIMEOUT = 20
USABLE = 200            # characters: below this a JD isn't something you can summarise


def clean(text: str) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text or "")
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def usable(text: str) -> bool:
    from .relevance import no_jd
    t = clean(URL.sub(" ", text or ""))
    return not no_jd(t) and len(t) >= USABLE


def links_in(text: str) -> list[str]:
    return [u.rstrip(".,;)") for u in URL.findall(text or "")]


def jd_key(role: dict) -> str:
    """Changes when the role's own JD information changes (then the JD is fetched again)."""
    raw = "|".join(str(role.get(k) or "") for k in ("job_description", "has_company_doc", "has_form_doc", "apply_end"))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


# ------------------------------------------------------------------ files -> text

def docx_text(data: bytes) -> str:
    """Word (.docx) without a library: the paragraphs of word/document.xml."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    paras = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
    out = ["".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S)) for p in paras]
    import html as _h
    return clean("\n".join(_h.unescape(p) for p in out if p.strip()))


def html_text(data: bytes) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(data, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer", "noscript", "svg", "form"]):
        t.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return clean(main.get_text("\n"))


def file_text(data: bytes, content_type: str = "") -> tuple[str, str]:
    """(text, kind) for a PDF (OCR when scanned), Word, Excel, HTML or plain-text file."""
    from .pdfs import _ocr_available, _ocr_pdf, _read_pdf, _read_xlsx, sniff
    kind = sniff(data, content_type)
    if kind == "pdf":
        doc = _read_pdf(data)
        text = "\n".join(p["text"] for p in doc["pages"])
        if len(text.strip()) < 30 * max(1, len(doc["pages"])) and _ocr_available():
            text = "\n".join(_ocr_pdf(data))
        return clean(text), "pdf"
    if kind == "docx":
        return docx_text(data), "docx"
    if kind == "xlsx":
        return clean("\n".join(p["text"] for p in _read_xlsx(data)["pages"])), "xlsx"
    if kind == "html" or "html" in content_type:
        return html_text(data), "html"
    if content_type.startswith("text/"):
        return clean(data.decode("utf-8", "ignore")), "text"
    return "", kind


# ------------------------------------------------------------------ public links

class Unreadable(Exception):
    pass


def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, 443)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def direct_url(url: str) -> str:
    """Google Docs as plain text, Drive files as a download; other links as they are."""
    m = re.search(r"docs\.google\.com/document/d/([\w-]+)", url)
    if m:
        return f"https://docs.google.com/document/d/{m.group(1)}/export?format=txt"
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:.*&)?id=)([\w-]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return url


def fetch_public(url: str, session=None) -> tuple[bytes, str]:
    """GET a public link: no cookies, no forms, public hosts only, 3 redirects, 20 s, 5 MB."""
    import requests
    s = session or requests.Session()
    target = direct_url(url)
    for _ in range(4):
        parts = urlsplit(target)
        if parts.scheme not in ("http", "https") or not parts.hostname or not _public_host(parts.hostname):
            raise Unreadable("not a public web address")
        r = s.get(target, timeout=TIMEOUT, allow_redirects=False, stream=True,
                  headers={"User-Agent": "Mozilla/5.0 (Ping JD reader; read-only)"})
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            target = requests.compat.urljoin(target, r.headers["location"])
            # Google asks to sign in for a private file: that's "unreadable", not a page to read
            if re.search(r"accounts\.google\.com|ServiceLogin", target):
                raise Unreadable("private (sign-in needed)")
            continue
        if r.status_code != 200:
            raise Unreadable(f"HTTP {r.status_code}")
        data = b""
        for chunk in r.iter_content(64 * 1024):
            data += chunk
            if len(data) > MAX_BYTES:
                raise Unreadable("larger than 12 MB")
        return data, r.headers.get("content-type", "")
    raise Unreadable("too many redirects")


def from_link(url: str, session=None) -> dict:
    """{jd_text, jd_source, jd_url} for a link; 'link-unreadable' (with the URL) when it can't be read."""
    try:
        data, ctype = fetch_public(url, session)
        text, kind = file_text(data, ctype)
        # Drive's own "can't preview / sign in" pages are HTML too: only real text counts
        if usable(text) and not re.search(r"(sign in|request access|you need access)", text[:400], re.I):
            return {"jd_text": text[:20000], "jd_source": "link", "jd_url": url}
        why = "no readable text" if kind else "unknown file"
    except Unreadable as e:
        why = str(e)
    except Exception as e:                  # a timeout, a reset connection, a broken file
        why = type(e).__name__
    return {"jd_text": None, "jd_source": "link-unreadable", "jd_url": url, "jd_note": why}


# ------------------------------------------------------------------ where the JD is

PAY = re.compile(r"ctc|salary|gross|take ?home|bonus|stipend|esop|perk|bond amount|compensation|variable|allowance", re.I)
DETAIL = re.compile(r"skill|responsib|job|role|work|additional information|selection|qualification|location|eligib", re.I)
ERP_FILE = "https://erp.iitkgp.ac.in/TrainingPlacementSSO/AdmFilePDF.htm?type={kind}&year={yop}{jnf}&com_id={com}"


def detail_text(role: dict) -> str:
    """The JD-like fields of the role's "more details" (skills, responsibilities, additional information...)."""
    fields = (role.get("more_details") or {}).get("fields") or {}
    lines = [f"{k}: {str(v).strip()}" for k, v in fields.items()
             if DETAIL.search(k) and not PAY.search(k) and len(str(v or "").strip()) > 3
             and str(v).strip().lower() not in ("na", "n/a", "nil", "none", "no", "yes")]
    return clean("\n".join(lines))


def erp_file_url(role: dict, kind: str) -> str:
    return ERP_FILE.format(kind=kind, yop=role.get("yop", ""), com=role.get("com_id", ""),
                           jnf=f"&jnf_id={role.get('jnf_id', '')}" if kind == "JNF" else "")


def resolve(role: dict, get_file, get_link=None) -> dict:
    """{jd_text, jd_source, jd_url[, jd_note]} for a role, in this order: the ERP's own field when it is a real JD;
    the role's JD file on the ERP; a public link in the field; the company's file; the role's "more details";
    a link that couldn't be read (kept with its URL); nothing. get_file(kind) -> (bytes, content type)."""
    get_link = get_link or from_link
    inline = clean(role.get("job_description") or "")
    detail = detail_text(role)
    if usable(inline):
        # the ERP's own text, as it is: the role keeps its "For you" cache key (more details go into the summary)
        return {"jd_text": inline[:20000], "jd_source": "inline", "jd_url": None}
    tried = []
    for kind, present in (("JNF", role.get("has_form_doc")), ):
        if present:
            text = _file(get_file, kind, tried)
            if usable(text):
                return {"jd_text": text[:20000], "jd_source": "attachment", "jd_url": erp_file_url(role, kind)}
    unreadable = None
    for url in links_in(inline):
        if re.search(r"youtube\.com|youtu\.be", url):
            continue                      # a video isn't a JD
        got = get_link(url)
        if got["jd_source"] == "link":
            return got
        unreadable = unreadable or got
    if role.get("has_company_doc"):
        text = _file(get_file, "COM", tried)
        if usable(text):
            return {"jd_text": text[:20000], "jd_source": "attachment", "jd_url": erp_file_url(role, "COM")}
    both = clean(("" if not inline or _placeholder(inline) else inline) + ("\n\n" + detail if detail else ""))
    if usable(both):
        return {"jd_text": both[:20000], "jd_source": "detail", "jd_url": None}
    if unreadable:
        return unreadable
    note = "; ".join(tried) or (inline[:80] if inline else "no JD on the ERP")
    return {"jd_text": None, "jd_source": "none", "jd_url": None, "jd_note": note}


def _placeholder(text: str) -> bool:
    from .relevance import no_jd
    return no_jd(URL.sub(" ", text).strip())


def _file(get_file, kind: str, tried: list) -> str:
    try:
        data, ctype = get_file(kind)
        text, fmt = file_text(data, ctype)
        if not usable(text):
            tried.append(f"{kind} file: no readable text ({fmt})")
        return text
    except Exception as e:
        tried.append(f"{kind} file: {type(e).__name__}")
        return ""


# ------------------------------------------------------------------ the short summary

SUMMARY_PROMPT = """Summarise this job description for a student deciding whether to apply. Use ONLY facts written in
the text. When the text doesn't say something, use null (or [] for a list). Never guess, never add general advice.
Reply with JSON only:
{{"role_team": "the role and the team, one line", "do": ["what you'd do", "...", "..."],
 "must_have": ["must-have skill or qualification", "..."], "location": "work location(s)",
 "eligibility": "who may apply (degree, branch, CGPA, batch) as written", "unusual": ["bond, shifts, rotation, relocation,
 travel, service agreement, contract length: only if written"]}}
At most 3 items in "do", 5 in "must_have", 3 in "unusual"; each item at most 12 words.

Job description:
<<<
{jd}
>>>"""
SUMMARY_KEYS = ("role_team", "do", "must_have", "location", "eligibility", "unusual")


def text_key(text: str) -> str:
    return hashlib.sha1(clean(text).encode()).hexdigest()[:16]


def summarise(text: str, cfg: dict, timeout: int = 45) -> dict | None:
    """The structured summary from Gemini, or None when no model answers (the rules summary is used then)."""
    import json as _json
    import requests
    from .ai import _msg
    if cfg.get("provider") != "openai_compatible" or not cfg.get("key"):
        return None
    prompt = SUMMARY_PROMPT.format(jd=clean(text)[:12000])
    for model in [cfg.get("model") or ""] + list(cfg.get("fallback_models", [])):
        try:
            r = requests.post(cfg["base_url"].rstrip("/") + "/chat/completions", timeout=timeout,
                              headers={"Authorization": f"Bearer {cfg['key']}"},
                              json={"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]})
            if r.status_code >= 400:
                _ = _msg(r)
                continue
            raw = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", raw, re.S)
            data = _json.loads(m.group(0)) if m else None
            if isinstance(data, dict):
                out = {k: data.get(k) for k in SUMMARY_KEYS}
                for k in ("do", "must_have", "unusual"):
                    out[k] = [str(x).strip() for x in (out[k] or []) if str(x).strip()][: {"do": 3, "must_have": 5, "unusual": 3}[k]]
                out["model"] = model
                return out
        except Exception:
            continue
    return None


SECTION = re.compile(r"^\s*(?:key\s+)?(responsibilit\w*|role|what you('ll| will) do|job description|requirements?|"
                     r"qualifications?|skills?(?: required)?|must[- ]haves?|required skill set|location|eligibility)\s*[:\-]?\s*$", re.I)


def rules_summary(text: str, designation: str = "") -> dict:
    """Without a model: the same fields, taken from labelled sections and lines (never written fresh)."""
    lines = [l.strip(" •·-*\t") for l in clean(text).splitlines() if l.strip(" •·-*\t")]
    sections, cur = {}, "intro"
    for l in lines:
        m = SECTION.match(l)
        if m:
            cur = m.group(1).lower()
            continue
        sections.setdefault(cur, []).append(l)
    def pick(*names):
        for n in names:
            for k, v in sections.items():
                if k.startswith(n):
                    return v
        return []
    do = pick("responsib", "what you", "role", "job description") or [s for s in sections.get("intro", []) if len(s.split()) > 4]
    must = pick("must", "required skill", "skill", "requirement", "qualification")
    loc = re.search(r"\blocation\s*[:\-]\s*([^\n.;]{2,60})", text, re.I)
    elig = re.search(r"\b(eligib\w*|cgpa|cg)\s*[:\-]?\s*([^\n]{2,80})", text, re.I)
    unusual = [l for l in lines if re.search(r"\bbond\b|\bshift|rotation|relocat|travel|service agreement|night", l, re.I)]
    short = lambda xs, n: [" ".join(x.split()[:14]) for x in xs[:n]]  # noqa: E731
    return {"role_team": designation or None, "do": short(do, 3), "must_have": short(must, 5),
            "location": loc.group(1).strip() if loc else None,
            "eligibility": " ".join(elig.group(0).split()[:14]) if elig else None,
            "unusual": short(unusual, 3), "model": "rules"}
