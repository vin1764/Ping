"""The read-only gate. EVERY request to the ERP goes through `Gate.request`.

On this ERP, applying for a job is a plain page visit
(TPJNFViewAction.jsp?mode=ApplyCV1...), so "only send GET requests" is not a
safety rule. Instead there is a short list of exact addresses Ping may
contact, each with the exact parameters it may send. Anything else is refused
before it leaves the machine, including redirects the ERP tries to send us to.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

import requests

from .config import ERP_BASE


class BlockedRequest(Exception):
    """Raised when something tries to reach an address Ping is not allowed to."""


# Words that must never appear in an ERP path Ping visits. This is a second
# lock behind the allow list: even if someone adds a rule by mistake, these fail.
DENY_WORDS = (
    "action", "apply", "upload", "tpfile", "accept", "cancel", "deactiv", "delete",
    "save", "submit", "register", "vote", "resume", "cvgenerate", "feedback", "noc",
    "publish", "block", "confirm", "update", "insert", "edit", "remove", "withdraw",
    "reject", "signup", "forgot", "changepass", "switchacc", "survey",
)


@dataclass(frozen=True)
class Rule:
    method: str
    path: str
    query: tuple = ()        # allowed query keys
    query_fixed: tuple = ()  # (key, (allowed values...)) pairs that MUST be present
    form: tuple = ()         # allowed form keys (POST)
    form_fixed: tuple = ()   # (key, (allowed values...)) pairs that MUST be present
    purpose: str = ""


LOGIN_FORM = ("user_id", "password", "answer", "typeee", "sessionToken", "requestedUrl", "email_otp")
CDC_MENU = (("module_id", ("26",)), ("menu_id", ("11",)))

RULES: tuple[Rule, ...] = (
    # --- logging in ---------------------------------------------------------
    Rule("GET", "/IIT_ERP3/", query=("ssoToken",), purpose="ERP entry / post-login redirect"),
    Rule("GET", "/SSOAdministration/login.htm", query=("sessionToken", "requestedUrl"), purpose="login page"),
    Rule("POST", "/SSOAdministration/getSecurityQues.htm", form=("user_id",), purpose="ask which security question"),
    Rule("POST", "/SSOAdministration/getEmilOTP.htm", form=LOGIN_FORM, form_fixed=(("typeee", ("SI",)),),
         purpose="press Get OTP"),
    Rule("POST", "/SSOAdministration/auth.htm", form=LOGIN_FORM, form_fixed=(("typeee", ("SI",)),),
         purpose="press Log In"),
    Rule("GET", "/SSOAdministration/success.htm", query=("reqType",), purpose="login redirect"),
    Rule("GET", "/IIT_ERP3/home.htm", purpose="ERP home"),
    Rule("GET", "/IIT_ERP3/logout.htm", purpose="log out"),
    # --- opening the placement section --------------------------------------
    Rule("POST", "/IIT_ERP3/showmenu.htm",
         form=("module_id", "menu_id", "link", "delegated_by", "module_name", "parent_display_name", "display_name"),
         form_fixed=CDC_MENU + (("link", ("https://erp.iitkgp.ac.in/TrainingPlacementSSO/TPStudent.jsp",)),),
         purpose="open CDC > Application of Placement/Internship"),
    Rule("POST", "/TrainingPlacementSSO/TPStudent.jsp", form=("ssoToken", "module_id", "menu_id"),
         form_fixed=CDC_MENU, purpose="companies page"),
    # --- reading ------------------------------------------------------------
    Rule("GET", "/TrainingPlacementSSO/ERPMonitoring.htm",
         query=("action", "jqqueryid", "_search", "nd", "rows", "page", "sidx", "sord"),
         query_fixed=(("action", ("fetchData",)), ("jqqueryid", ("37", "54"))),
         purpose="companies list (37) / notice board (54) data"),
    Rule("GET", "/TrainingPlacementSSO/TPJNFView.jsp", query=("jnf_id", "com_id", "yop", "user_type", "rollno"),
         query_fixed=(("user_type", ("SU",)),), purpose="role details popup"),
    Rule("GET", "/TrainingPlacementSSO/JnfMoreDet.jsp", query=("mode", "rollno", "year", "com_id", "jnf_id"),
         query_fixed=(("mode", ("jnfMoreDet",)),), purpose="role 'more details' popup"),
    Rule("GET", "/TrainingPlacementSSO/Notice.jsp", purpose="notice board page"),
    Rule("GET", "/TrainingPlacementSSO/ShowContent.jsp", query=("year", "id"), purpose="full notice text"),
    Rule("GET", "/TrainingPlacementSSO/AdmFilePDF.htm", query=("type", "year", "id"),
         query_fixed=(("type", ("NOTICE",)),), purpose="notice attachment"),
    # the job description file of a role ("Download" in the companies list: TPJNFDescription) and the company's
    # own file (TPComDescription); never a CV or anything with a roll number
    Rule("GET", "/TrainingPlacementSSO/AdmFilePDF.htm", query=("type", "year", "jnf_id", "com_id"),
         query_fixed=(("type", ("JNF", "COM")),), purpose="a role's or company's job description file"),
)


def _norm_path(path: str) -> str:
    path = re.sub(r";jsessionid=[^/?#]*", "", path, flags=re.I)
    return path or "/"


def check(method: str, url: str, data: dict | None = None, base: str = ERP_BASE) -> Rule:
    """Return the matching Rule, or raise BlockedRequest. Pure function, easy to test."""
    method = method.upper()
    parts = urlsplit(url)
    allowed = urlsplit(base)
    if parts.scheme != allowed.scheme or parts.netloc.split(":")[0] != allowed.netloc.split(":")[0]:
        raise BlockedRequest(f"host not allowed: {parts.scheme}://{parts.netloc}")
    if parts.port not in (None, allowed.port, 443 if parts.scheme == "https" else 80):
        raise BlockedRequest(f"port not allowed: {parts.port}")
    path = _norm_path(parts.path)
    low = path.lower()
    for word in DENY_WORDS:
        if word in low:
            raise BlockedRequest(f"blocked word '{word}' in {path}")
    query = parse_qsl(parts.query, keep_blank_values=True)
    form = list((data or {}).items())
    refused = None
    for rule in RULES:          # one address can have several rules (each a fixed shape): any one may allow it
        if rule.method != method or rule.path != path:
            continue
        try:
            _check_fields("query", query, rule.query, rule.query_fixed, path)
            if method == "POST":
                _check_fields("form", form, rule.form, rule.form_fixed, path)
            elif form:
                raise BlockedRequest(f"GET with a body to {path}")
        except BlockedRequest as e:
            refused = e
            continue
        return rule
    raise refused or BlockedRequest(f"not on the allow list: {method} {path}")


def _check_fields(kind: str, pairs: list, allowed: tuple, fixed: tuple, path: str) -> None:
    keys = [k for k, _ in pairs]
    extra = sorted(set(keys) - set(allowed))
    if extra:
        raise BlockedRequest(f"{kind} field(s) {extra} not allowed for {path}")
    values = dict(pairs)
    for key, ok_values in fixed:
        if values.get(key) not in ok_values:
            raise BlockedRequest(f"{kind} field {key}={values.get(key)!r} not allowed for {path}")
    for k, v in pairs:
        if k.lower() == "mode" and v not in ("jnfMoreDet",):
            raise BlockedRequest(f"mode={v!r} not allowed")


@dataclass
class Reply:
    status: int
    url: str
    headers: dict
    content: bytes

    @property
    def text(self) -> str:
        ctype = self.headers.get("content-type", "").lower()
        enc = "utf-8"
        m = re.search(r"charset=([\w-]+)", ctype)
        if m:
            enc = m.group(1)
        try:
            return self.content.decode(enc, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")


class RequestsTransport:
    """Real network. Redirects are NOT followed here; the gate follows them."""

    def __init__(self, timeout: float = 40):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 Ping-personal-reader")
        self.timeout = timeout

    def send(self, method: str, url: str, data: dict | None, headers: dict | None) -> Reply:
        # Reads are retried on brief network errors (seen on the real ERP: 3 of 64 PDFs).
        # Login steps (POST) are never repeated automatically.
        tries = 3 if method == "GET" else 1
        for attempt in range(tries):
            try:
                r = self.session.request(method, url, data=data, headers=headers or {},
                                         timeout=self.timeout, allow_redirects=False)
                break
            except (requests.ConnectionError, requests.Timeout):
                if attempt == tries - 1:
                    raise
                time.sleep(2 * (attempt + 1))
        return Reply(r.status_code, r.url, {k.lower(): v for k, v in r.headers.items()}, r.content)


class Gate:
    def __init__(self, transport=None, base: str = ERP_BASE):
        self.transport = transport or RequestsTransport()
        self.base = base
        self.count = 0
        self.log: list[str] = []  # "METHOD /path" only, never parameters

    def url(self, path: str, query: dict | None = None) -> str:
        u = self.base + path
        if query:
            u += "?" + urlencode(query)
        return u

    def request(self, method: str, url: str, data: dict | None = None,
                headers: dict | None = None, max_redirects: int = 8) -> Reply:
        method = method.upper()
        for _ in range(max_redirects + 1):
            check(method, url, data, self.base)
            self.count += 1
            self.log.append(f"{method} {_norm_path(urlsplit(url).path)}")
            reply = self.transport.send(method, url, data, headers)
            if reply.status in (301, 302, 303, 307, 308) and reply.headers.get("location"):
                url = urljoin(url, reply.headers["location"])
                url = re.sub(r"^(https?://[^/:]+):443(/|$)", r"\1\2", url)
                if reply.status in (301, 302, 303):
                    method, data = "GET", None
                continue
            reply.url = url
            return reply
        raise BlockedRequest("too many redirects")

    def get(self, path: str, query: dict | None = None, **kw) -> Reply:
        return self.request("GET", self.url(path, query), **kw)

    def post(self, path: str, data: dict, **kw) -> Reply:
        return self.request("POST", self.url(path), data=data, **kw)
