"""Talks to the ERP the same way the browser does, but only through the gate.

Login order (from the real login page's code):
  1. open the login page          -> it carries a hidden sessionToken
  2. send the roll number         -> ERP replies with the security question
  3. pick the stored answer that matches that question
  4. press Get OTP                -> ERP checks password + answer, mails an OTP
  5. read the OTP from the mailbox (only mails that arrived after step 4)
  6. press Log In                 -> redirects to the ERP home page
"""

from __future__ import annotations

import difflib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from .config import IST, OTP_WAIT_SECONDS, REQUEST_PAUSE_SECONDS, Secrets, norm_text
from .gate import Gate

LOGIN_ENTRY = "/IIT_ERP3/"
REQUESTED_URL = "https://erp.iitkgp.ac.in/IIT_ERP3/"
TP_LINK = "https://erp.iitkgp.ac.in/TrainingPlacementSSO/TPStudent.jsp"
MIN_OTP_TO_LOGIN = 15  # seconds between pressing Get OTP and pressing Log In


class LoginError(Exception):
    def __init__(self, message: str, kind: str = "login"):
        super().__init__(message)
        self.kind = kind


@dataclass
class LoginStats:
    seconds_total: float = 0.0
    seconds_waiting_otp: float = 0.0
    otp_requests: int = 0
    question_matched: str = ""
    notes: list[str] = field(default_factory=list)


def match_question(shown: str, stored: list) -> object | None:
    """Loose match: ignore capitals, spaces and punctuation; allow small typos."""
    target = norm_text(shown)
    if not target:
        return None
    for s in stored:
        if norm_text(s.question) == target:
            return s
    best, best_score = None, 0.0
    for s in stored:
        score = difflib.SequenceMatcher(None, norm_text(s.question), target).ratio()
        if score > best_score:
            best, best_score = s, score
    # Only tiny typos pass (a letter or two). 'favourite food' vs 'favourite colour'
    # scores 0.875 and must NOT match: a wrong answer makes the ERP refuse the OTP.
    return best if best_score >= 0.95 else None


def _clean_question(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", text).strip()


def _login_failure_hint(reply, user_id: str = "") -> str:
    """What the ERP showed after Log In, without echoing anything we typed."""
    from urllib.parse import urlsplit
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", reply.text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"[^.]{0,80}\b(invalid|incorrect|wrong|expired|mismatch|not match|blocked|locked|"
                  r"try again|already|error|fail\w*)\b[^.]{0,80}", text, re.I)
    where = urlsplit(reply.url).path
    if m:
        return f"HTTP {reply.status} at {where}; ERP says: \"{m.group(0).strip()[:200]}\""
    shown = text.strip()[:300]
    if user_id:
        shown = re.sub(re.escape(user_id), "<ROLL>", shown, flags=re.I)
    return f"HTTP {reply.status} at {where}; no home page. Page starts: \"{shown}\""


class ErpClient:
    def __init__(self, gate: Gate, secrets: Secrets, mailbox, log=print,
                 otp_wait: float = OTP_WAIT_SECONDS, pause: float = REQUEST_PAUSE_SECONDS):
        self.gate = gate
        self.secrets = secrets
        self.mailbox = mailbox
        self.log = log
        self.otp_wait = otp_wait
        self.pause = pause
        self.logged_in = False
        self.tp_open = False

    # ------------------------------------------------------------------ login
    def login(self) -> LoginStats:
        """Log in; if Log In itself fails after a valid OTP, start over once, a minute later."""
        try:
            return self._login_once()
        except LoginError as e:
            if e.kind != "login_failed":
                raise
            self.log(f"login attempt 1 failed ({e}); trying once more in 60s")
            time.sleep(60)
            self.gate.transport = type(self.gate.transport)() if hasattr(self.gate.transport, "session") \
                else self.gate.transport  # fresh cookies on the real network
            stats = self._login_once()
            stats.notes.insert(0, f"first attempt failed: {e}")
            return stats

    def _login_once(self) -> LoginStats:
        stats = LoginStats()
        t0 = time.monotonic()
        page = self.gate.get(LOGIN_ENTRY)
        m = re.search(r'name="sessionToken"\s+id="sessionToken"\s+value="([^"]*)"', page.text) or \
            re.search(r'id="sessionToken"[^>]*value="([^"]*)"', page.text)
        if not m:
            raise LoginError("login page did not contain a sessionToken (has the page changed?)", "page_changed")
        session_token = m.group(1)

        q = self.gate.post("/SSOAdministration/getSecurityQues.htm", {"user_id": self.secrets.erp_user_id})
        question = _clean_question(q.text)
        if not question or "FALSE" in q.text:
            raise LoginError("ERP did not return a security question (wrong user id?)", "bad_user")
        chosen = match_question(question, self.secrets.security_answers)
        if chosen is None:
            raise LoginError(f"The ERP asked a security question that matches none of your 3 stored ones: "
                             f"\"{question}\". Update ERP_SECQ_1/2/3.", "unknown_question")
        stats.question_matched = chosen.question

        form = {
            "user_id": self.secrets.erp_user_id,
            "password": self.secrets.erp_password,
            "answer": chosen.answer,
            "typeee": "SI",
            "sessionToken": session_token,
            "requestedUrl": REQUESTED_URL,
            "email_otp": "",
        }
        code = None
        used: set[str] = set()
        for attempt in (1, 2):  # press Get OTP, and once more if nothing arrives
            clicked = datetime.now(IST)
            r = self.gate.post("/SSOAdministration/getEmilOTP.htm", form)
            stats.otp_requests += 1
            try:
                msg = json.dumps(json.loads(r.text))
            except ValueError:
                msg = r.text[:300]
            if "unable to send otp" in msg.lower():
                raise LoginError("ERP refused to send an OTP (password or security answer wrong?)", "otp_refused")
            w0 = time.monotonic()
            code, uid = self.mailbox.wait_for_otp(clicked, timeout=self.otp_wait, ignore_uids=used)
            stats.seconds_waiting_otp += time.monotonic() - w0
            if code:
                delay = getattr(self.mailbox, "last_otp_delay", None)
                if delay is not None:
                    self.log(f"OTP mail arrived {delay:+.0f}s after Get OTP")
                break
            stats.notes.append(f"no OTP mail within {int(self.otp_wait)}s (attempt {attempt})")
        if not code:
            raise LoginError("No OTP email arrived after pressing Get OTP twice", "no_otp")

        # The ERP can mail the OTP within ~3s, possibly before it has saved the code; a person
        # never types it that fast. Log In no sooner than MIN_OTP_TO_LOGIN after Get OTP.
        wait = MIN_OTP_TO_LOGIN - (datetime.now(IST) - clicked).total_seconds()
        if wait > 0:
            time.sleep(wait)
        form["email_otp"] = code
        done = self.gate.post("/SSOAdministration/auth.htm", form)
        if "/IIT_ERP3/home.htm" not in done.url and "logout.htm" not in done.text:
            raise LoginError(f"Login failed: {_login_failure_hint(done, self.secrets.erp_user_id)}", "login_failed")
        self.logged_in = True
        stats.seconds_total = time.monotonic() - t0
        return stats

    def logout(self) -> None:
        if self.logged_in:
            try:
                self.gate.get("/IIT_ERP3/logout.htm")
            finally:
                self.logged_in = False

    # ------------------------------------------------------- placement section
    def open_placement(self) -> None:
        r = self.gate.post("/IIT_ERP3/showmenu.htm", {
            "module_id": "26", "menu_id": "11", "link": TP_LINK, "delegated_by": "",
            "module_name": "CDC", "parent_display_name": "Student",
            "display_name": "Application of Placement/Internship"})
        m = re.search(r"elements\['ssoToken'\]\.value\s*=\s*'([^']+)'", r.text)
        if not m:
            raise LoginError("could not open the CDC section (menu page changed?)", "page_changed")
        page = self.gate.post("/TrainingPlacementSSO/TPStudent.jsp",
                              {"ssoToken": m.group(1), "module_id": "26", "menu_id": "11"})
        self.placement_html = page.text      # the companies page's own scripts say where its links lead
        self.tp_open = True

    def _grid(self, qid: str) -> str:
        r = self.gate.get("/TrainingPlacementSSO/ERPMonitoring.htm", {
            "action": "fetchData", "jqqueryid": qid, "_search": "false",
            "nd": str(int(time.time() * 1000)), "rows": "20", "page": "1", "sidx": "", "sord": "asc"})
        if "<rows" not in r.text:
            raise LoginError(f"grid {qid} did not return data (session expired?)", "page_changed")
        return r.text

    def companies_xml(self) -> str:
        return self._grid("37")

    def notices_xml(self) -> str:
        self.gate.get("/TrainingPlacementSSO/Notice.jsp")
        return self._grid("54")

    def role_popup(self, yop: str, com_id: str, jnf_id: str) -> str:
        time.sleep(self.pause)
        return self.gate.get("/TrainingPlacementSSO/TPJNFView.jsp", {
            "jnf_id": jnf_id, "com_id": com_id, "yop": yop, "user_type": "SU",
            "rollno": self.secrets.erp_user_id}).text

    def role_more_details(self, yop: str, com_id: str, jnf_id: str) -> str:
        time.sleep(self.pause)
        return self.gate.get("/TrainingPlacementSSO/JnfMoreDet.jsp", {
            "mode": "jnfMoreDet", "rollno": self.secrets.erp_user_id, "year": yop,
            "com_id": com_id, "jnf_id": jnf_id}).text

    def notice_text(self, year: str, notice_id: str) -> str:
        time.sleep(self.pause)
        return self.gate.get("/TrainingPlacementSSO/ShowContent.jsp", {"year": year, "id": notice_id}).text

    def notice_attachment(self, year: str, notice_id: str) -> tuple[bytes, str]:
        time.sleep(self.pause)
        r = self.gate.get("/TrainingPlacementSSO/AdmFilePDF.htm", {"type": "NOTICE", "year": year, "id": notice_id})
        return r.content, r.headers.get("content-type", "")
