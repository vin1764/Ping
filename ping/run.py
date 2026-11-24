"""One Ping run, start to finish.

  python -m ping.run                  real run (needs the secrets)
  python -m ping.run --mode check     only check secrets + database, no ERP login
  python -m ping.run --mode load-sample / remove-sample   demo data for the dashboard
"""

from __future__ import annotations

import argparse
import json
import hashlib
import os
import re
import sys
import time
import traceback
from collections import Counter
from datetime import datetime, timedelta, timezone

from . import ai, notify
from .config import FIRST_RUN_LOOKBACK_DAYS, IST, ConfigError, load_dotenv, load_secrets
from .erp import ErpClient, LoginError
from .gate import Gate
from .items import build_items, effective_deadlines
from .eligibility import evaluate
from .mailbox import Mailbox
from .matching import CompanyIndex, tokens
from .notices import analyze, roles_for_target
from .parsers import parse_companies, parse_more_details, parse_notice_page, parse_notices, parse_role_popup
from .pdfs import check_attachment, refresh_details
from .store import MemoryStore, SupabaseStore

PROFILE_DEFAULTS = {"roll": None, "name": None, "department": None, "degree": None, "cgpa": None,
                    "active_backlogs": False, "cv_names": [], "interested_companies": [],
                    "not_interested_companies": [], "notice_types": ["PLACEMENT"]}
LIST_KINDS = ("test", "test_rooms", "shortlist", "result")
MAIL_LOOKBACK_DAYS = 14
ROLE_LIST_COLUMNS = ("id", "yop", "com_id", "jnf_id", "company", "designation", "ctc", "ctc_text", "currency",
                     "has_company_doc", "has_ppt_doc", "has_form_doc", "applied", "apply_start", "apply_end",
                     "apply_end_text", "interview_date", "contract")


REAL = {"is_sample": "not.is.true"}  # demo rows (is_sample) are never mixed into your feed

# Two kinds of failed run, handled differently:
#  - credentials: the ERP refused who you are (wrong user id, password/answer refused, a security question
#    none of your answers match). Trying again hourly can't fix it and could lock the account, so Ping
#    alerts at once (email + chat message) and pauses scheduled runs until you start one by hand.
#  - everything else (ERP unreachable, blank login page, Log In not accepted, no OTP mail, network errors):
#    normal ERP behaviour. Never pause; try again at the next hourly run. After 3 in a row, one email and
#    one chat message for that streak, and a "back online" message when a run works again.
CREDENTIAL_KINDS = ("bad_user", "otp_refused", "unknown_question")
STREAK_ALERT_AT = 3
def _failure_note(status: str) -> str:
    """What the dashboard says when a run you started couldn't finish (no chat message was posted for it)."""
    kind = failure_kind(status)
    why = status.removeprefix("failed: ")
    if kind == "credentials":
        return f"The ERP refused the login ({why}). Fix the secret, then press Check now again."
    if why in ("login_failed", "no_otp", "page_changed") or re.search(r"Connection|Timeout|HTTP|SSL", why):
        return f"Couldn't get into the ERP this time ({why}); that happens. I'll try again at the next hourly check."
    return f"The check stopped before the end ({why}). I'll try again at the next hourly check."


# the dashboard, for links in emails (the public Pages site of this repo's owner)
DASHBOARD_URL = os.environ.get("PING_DASHBOARD_URL") or \
    f"https://{(os.environ.get('GITHUB_REPOSITORY') or 'owner/x').split('/')[0].lower()}.github.io/ping-dashboard/"
JD_FETCH_PER_RUN = 40        # ERP files and public links read per run for job descriptions
JD_SUMMARIES_PER_RUN = 40     # new JDs summarised by Gemini per run (the rest by rules, upgraded later)
JD_AI_UPGRADES_PER_RUN = 20   # rules summaries redone by Gemini per run, open roles first
JD_AI_SECONDS = 90            # time for Gemini JD summaries per run (keeps Check now to a couple of minutes)


UNREACHABLE_MSG = "Couldn't reach the ERP for the last 3 runs; I'll keep trying hourly."
BACK_ONLINE_MSG = "Back online: reached the ERP again after {n} failed runs."


def failure_kind(status: str) -> str | None:
    if status == "ok":
        return None
    return "credentials" if status.removeprefix("failed: ") in CREDENTIAL_KINDS else "unreachable"


def credentials_pause(store) -> dict | None:
    """Set when the ERP refused the credentials; scheduled runs skip until a run started by hand."""
    return store.get_state("paused_for_credentials") or None


def now_ist() -> datetime:
    return datetime.now(IST)


def log(msg: str) -> None:
    print(f"[{now_ist().strftime('%H:%M:%S')}] {msg}", flush=True)


class Runner:
    def __init__(self, secrets, store, store_ok: bool, gate: Gate | None = None, mailbox=None,
                 now: datetime | None = None, otp_wait: float | None = None, pause: float | None = None,
                 trigger: str = "manual", read_form_pages: bool = False, form_get=None):
        self.secrets = secrets
        # reading form pages (ping/form_pages.py: plain GETs, never a sign-in or a submit): on in the real run,
        # off in tests unless they hand in a fake page source
        self.read_form_pages = read_form_pages or form_get is not None
        self.form_get = form_get
        self.store = store
        self.store_ok = store_ok
        self.gate = gate or Gate()
        self.mailbox = mailbox or Mailbox(secrets.mail_address, secrets.mail_app_password)
        self.now = now or now_ist()
        self.trigger = trigger
        kw = {}
        if otp_wait is not None:
            kw["otp_wait"] = otp_wait
        if pause is not None:
            kw["pause"] = pause
        self.erp = ErpClient(self.gate, secrets, self.mailbox, log=log, **kw)
        self.counts: dict = {k: 0 for k in (
            "roles_seen", "roles_new", "notices_seen", "notices_new", "pdfs_considered", "pdfs_read",
            "pdf_yes", "pdf_no", "pdf_unknown", "pdfs_skipped_not_relevant", "notices_rules_unsure")}
        self.problems: list[str] = []
        self.login_stats = None
        self.jd_updates: list[dict] = []
        self.told: str | None = None        # the last message this run posted in the chat (failure policy)
        self.new_in_chat = 0                # new messages in the chat from this run (the dashboard says "N new")
        self.stage_off = False

    # ------------------------------------------------------------------ helpers
    def c(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    def profile(self) -> dict:
        # your own row only (id 1). The table also holds the demo's made-up profile (id 2, is_sample): reading
        # "the first row" once picked that one up, and lists were searched for the demo's roll (22 Nov, FirstClub)
        rows = [r for r in (self.store.select("profile", {"id": "eq.1"}) if self.store_ok else []) if not r.get("is_sample")]
        prof = dict(PROFILE_DEFAULTS)
        if rows:
            prof.update({k: v for k, v in rows[0].items() if v is not None})
        prof["roll"] = (prof.get("roll") or self.secrets.roll).upper()
        return prof

    # --------------------------------------------------------------------- run
    def _stage(self, stage: str, status: str = "running") -> None:
        """Progress for the dashboard (it listens to the runs table): one small update per step. Best effort: a run
        never fails because the progress couldn't be written."""
        self.stage = stage
        if not self.store_ok or getattr(self, "stage_off", False):
            return
        try:
            self.store.upsert("runs", [{"id": self.run_id, "started_at": self.started.isoformat(), "trigger": self.trigger,
                                        "mode": "run", "status": status, "stage": stage}])
        except Exception as e:
            self.stage_off = True       # e.g. the stage column isn't there yet (Admin > apply-sql adds it)
            log(f"progress not saved ({type(e).__name__}); the run goes on")

    def run(self) -> dict:
        started = datetime.now(timezone.utc)
        self.started = started
        # Check now creates the run's row ("queued") before GitHub starts the run, and passes its id along
        self.run_id = os.environ.get("PING_RUN_ROW", "").strip() or \
            started.strftime("%Y%m%dT%H%M%S") + "-" + hashlib.sha1(os.urandom(8)).hexdigest()[:6]
        self._stage("logging in")
        t0 = time.monotonic()
        status = "ok"
        profile = self.profile()
        roll = profile["roll"]
        stored_roles = {r["id"]: r for r in self.store.select("roles", REAL)}
        stored_notice_ids = {r["id"] for r in self.store.select("notices", REAL, columns="id")}
        first_run = not stored_notice_ids
        self.counts["first_run"] = first_run
        new_roles, fresh_notices, checks, list_roles = [], [], {}, []
        try:
            log("logging in")
            self.login_stats = self.erp.login()
            if getattr(self.mailbox, "last_otp_sender", ""):
                log(f"OTP mail came from: {self.mailbox.last_otp_sender} (use this for your mail filter)")
            log(f"logged in in {self.login_stats.seconds_total:.0f}s "
                f"(waiting for OTP {self.login_stats.seconds_waiting_otp:.0f}s, "
                f"Get OTP pressed {self.login_stats.otp_requests}x)")
            self.erp.open_placement()

            # ---- companies list
            self._stage("reading companies")
            list_roles = parse_companies(self.erp.companies_xml())
            self.c("roles_seen", len(list_roles))
            for r in list_roles:
                old = stored_roles.get(r["id"])
                if old and old.get("details_fetched"):
                    continue
                self.c("roles_new")
                details = self._role_details(r)
                new_roles.append({**r, **details})
            log(f"companies list: {len(list_roles)} roles, {self.counts.get('roles_new', 0)} new "
                f"(applied: {sum(1 for r in list_roles if r['applied'])})")

            # ---- notice board
            self._stage("reading notices")
            board = parse_notices(self.erp.notices_xml())
            self.c("notices_seen", len(board))
            if first_run or len(board) - len(stored_notice_ids) > 400:
                cutoff = self.now - timedelta(days=FIRST_RUN_LOOKBACK_DAYS)
                todo = [n for n in board if n["notice_time"] and datetime.fromisoformat(n["notice_time"]) >= cutoff
                        and n["id"] not in stored_notice_ids]
            else:
                todo = [n for n in board if n["id"] not in stored_notice_ids]
            for n in todo:
                try:
                    page = parse_notice_page(self.erp.notice_text(n["year"], str(n["notice_id"])))
                    n["text"] = page["text"] or n["preview"]
                except Exception as e:
                    self.c("notice_text_failed")
                    n["text"] = n["preview"]
                    self.problems.append(f"notice {n['notice_id']}: full text not read ({type(e).__name__})")
                fresh_notices.append(n)
            self.c("notices_new", len(fresh_notices))
            log(f"notice board: {len(board)} notices, {len(fresh_notices)} new"
                + (f" (first run: last {FIRST_RUN_LOOKBACK_DAYS} days only)" if first_run else ""))

            # ---- analyse new notices with the current roles
            all_roles = self._merge_roles(list_roles, stored_roles, new_roles)
            index = CompanyIndex(all_roles)
            for n in fresh_notices:
                n["analysis"] = analyze(n, n["text"], index, roll, profile.get("name") or "", self.secrets.ai)
                if n["analysis"]["rule_misses"]:
                    self.c("notices_rules_unsure")

            # ---- attachments (PDFs): yours first, other shortlists/schedules last
            self._stage("reading PDFs")
            checks = self._check_attachments(fresh_notices, index, all_roles, profile, roll)
            # ---- job descriptions that aren't in the companies list's own field (ERP file, public link, more details)
            self._jds(all_roles, stored_roles)
        except LoginError as e:
            status = f"failed: {e.kind}"
            self.problems.append(str(e))
            log(f"STOPPED: {e}")
        except Exception as e:
            status = f"failed: {type(e).__name__}"
            self.problems.append(f"{type(e).__name__}: {e}")
            log("STOPPED with an unexpected error:\n" + traceback.format_exc(limit=4))
        finally:
            try:
                self.erp.logout()
            except Exception:
                pass

        # ---- mailbox: placement mails since last run (read-only)
        emails = []
        if status == "ok":
            emails = self._scan_mail(list_roles or list(stored_roles.values()), profile)

        # ---- save + rebuild the feed
        self._stage("saving")
        self._save(list_roles, new_roles, fresh_notices, checks, emails, stored_roles)
        if self.jd_updates and self.store_ok:
            try:
                self.store.upsert("roles", self.jd_updates)
            except Exception as e:                       # e.g. before Admin > apply-sql added the columns
                self.problems.append(f"saving job descriptions failed: {type(e).__name__}")
        items = self._rebuild(profile)
        self._login_failure_tracking(status)

        finished = datetime.now(timezone.utc)
        ls = self.login_stats
        record = {
            "id": self.run_id,
            "started_at": started.isoformat(), "finished_at": finished.isoformat(),
            "trigger": self.trigger, "mode": "run", "status": status,
            "login_seconds": round(ls.seconds_total, 1) if ls else None,
            "otp_seconds": round(ls.seconds_waiting_otp, 1) if ls else None,
            "otp_requests": ls.otp_requests if ls else None,
            "gate_requests": self.gate.count,
            "counts": {**self.counts, "items": self._item_counts(items), "ai": dict(ai.stats),
                       "erp_addresses": dict(Counter(self.gate.log)),
                       "seconds_total": round(time.monotonic() - t0, 1)},
            "problems": self.problems[:50],
        }
        # for the dashboard: done or failed, how many new messages, and why it failed (the chat's own words)
        live = {"stage": "done" if status == "ok" else "failed", "new_items": self.new_in_chat,
                "note": None if status == "ok" else (self.told or _failure_note(status))}
        if self.store_ok:
            try:
                self.store.upsert("runs", [{**record, **live}])
            except Exception as e:
                try:                          # before Admin > apply-sql added the live columns
                    self.store.upsert("runs", [record])
                except Exception:
                    log(f"could not save the run record: {e}")
        if status == "ok":
            self._notify(profile, items)
        self._alerts(status)
        self._print_summary(record)
        return record

    def _notify(self, profile: dict, items: list[dict]) -> None:
        """Push (docs/PUSH.md): at most one notification for this run's most urgent new for-you message, test-day
        reminders queued for pg_cron, and the optional for-you email. Never fails the run."""
        from . import push, posting
        if not self.store_ok or posting.paused() or getattr(self, "silent_reasons", None):
            return
        new = getattr(self, "new_messages", [])
        try:
            rows = push.reminders(items, profile, self.now) + push.mail_reminders(items, profile, self.now)
            if rows:
                sent = {r["id"] for r in self.store.select("push_queue", {"kind": "eq.reminder", "sent_at": "not.is.null"})}
                rows = [r for r in rows if r["id"] not in sent]
                if rows:
                    try:
                        self.store.upsert("push_queue", rows)
                    except Exception:                 # push_queue without form_key yet (before apply-sql)
                        self.store.upsert("push_queue", [{k: v for k, v in r.items() if k != "form_key"} for r in rows])
            self.counts["push_reminders_queued"] = len(rows)
        except Exception as e:                        # e.g. before Admin > apply-sql made push_queue
            self.problems.append(f"queueing test reminders failed: {type(e).__name__}")
        # what a notification says: who and what to do in the title, only what's needed to act in the body
        roles = {r["id"]: r for r in self._rows("roles", REAL)}
        note = push.compose(new, roles, self.now)
        try:
            # the same, for everything still to do (not only new): Profile > Notifications > Send a test shows it
            example = push.compose(items, roles, self.now)
            self.store.set_state("push_example", example)
        except Exception:
            pass
        if note and self.secrets.supabase_url and self.secrets.supabase_key:
            try:
                res = push.send(self.secrets.supabase_url, self.secrets.supabase_key, note)
                self.counts["push"] = {k: res[k] for k in ("status", "sent", "devices", "ok", "why", "error") if k in res}
            except Exception as e:
                self.counts["push"] = {"error": type(e).__name__}
            log(f"push: {self.counts['push']}")
        chosen = push.pick(new, self.now)
        if chosen and profile.get("email_digests"):
            text = push.email_text(new, self.now, DASHBOARD_URL)
            if text:
                ok = notify.send_self(self.secrets.mail_address, self.secrets.mail_app_password, *text)
                self.counts["email_digest"] = bool(ok)

    # --------------------------------------------------------------- details
    def _role_details(self, r: dict) -> dict:
        out = {"details_fetched": False}
        try:
            pop = parse_role_popup(self.erp.role_popup(r["yop"], r["com_id"], r["jnf_id"]))
            out.update({k: pop.get(k) for k in ("form_type", "bond", "additional_criteria", "cgpa_cutoff",
                                                 "cgpa_cutoff_text", "job_description", "erp_messages",
                                                 "allowed", "has_more_details_link", "applied_resume_link")})
            out["details_fetched"] = True
        except Exception as e:
            self.c("role_popup_failed")
            self.problems.append(f"role {r['company']} / {r['designation']}: popup not read ({type(e).__name__})")
            return out
        try:
            more = parse_more_details(self.erp.role_more_details(r["yop"], r["com_id"], r["jnf_id"]))
            out["more_details"] = {"fields": more["fields"], "sections": more["sections"],
                                   "raw_text": more["raw_text"]}
            out["backlog_rule"] = more["backlog_rule"]
            out["cgpa_criteria"] = more["cgpa_criteria"]
            out["selection_details"] = more["selection_details"]
            out["has_written_test"] = more["has_written_test"]
            if not out.get("cgpa_cutoff") and more.get("min_cgpa"):
                try:  # popup said 0.0 but "more details" gives a minimum CGPA
                    out["cgpa_cutoff"] = float(re.findall(r"\d+(?:\.\d+)?", more["min_cgpa"])[0]) or None
                except (IndexError, ValueError):
                    pass
            if not more["fields"]:
                self.c("role_more_details_empty")
        except Exception as e:
            self.c("role_more_details_failed")
            self.problems.append(f"role {r['company']}: more details not read ({type(e).__name__})")
        return out

    def _jds(self, roles: list[dict], stored: dict) -> None:
        """Find each role's JD once, again only when the role's own JD information changes (jd_key)."""
        from .jd import clean, jd_key, links_in, resolve, usable
        ups, fetched, tally = [], 0, Counter()
        # open roles first (latest application end first): with more to fetch than one run allows, those matter now
        for r in sorted(roles, key=lambda r: str(r.get("apply_end") or ""), reverse=True):
            old = stored.get(r["id"]) or {}
            key = jd_key(r)
            if old.get("jd_key") == key and old.get("jd_source"):
                # stored before the glyph clean-up: the same text without boxes for bullets (no fetch)
                if old.get("jd_text") and clean(old["jd_text"]) != old["jd_text"]:
                    row = {"id": r["id"], "jd_text": clean(old["jd_text"])}
                    ups.append(row)
                    r.update(row)
                    tally["recleaned"] += 1
                continue
            inline = r.get("job_description") or ""
            # a request to the ERP or a link only when there is a file or a link to read
            needs_net = not usable(inline) and bool(r.get("has_form_doc") or r.get("has_company_doc") or links_in(inline))
            if needs_net and fetched >= JD_FETCH_PER_RUN:
                continue                                  # the rest next run (each file is a request to the ERP)
            fetched += needs_net
            res = resolve(r, lambda kind, r=r: self.erp.role_file(kind, r["yop"], r["com_id"], r["jnf_id"]))
            row = {"id": r["id"], "jd_key": key, "jd_text": clean(res["jd_text"]) if res.get("jd_text") else None,
                   "jd_source": res["jd_source"],
                   "jd_url": res.get("jd_url"), "jd_note": res.get("jd_note")}
            ups.append(row)
            r.update(row)
            tally[res["jd_source"]] += 1
        self.jd_updates = ups
        self.counts["jd_found"] = dict(tally)
        if ups:
            log(f"job descriptions: {dict(tally)}")

    def _notice_jds(self, roles: list[dict]) -> dict:
        """JD documents found on notices and in placement mail (ping/pdfs.py: kept whole, no students in them) fill
        the JD of the company's roles that have none of their own (ping/notice_jd.py)."""
        from . import notice_jd
        try:
            checks = {c["notice_id"]: c for c in self.store.select("pdf_checks", REAL) if c.get("status") == "jd"}
            mails = [m for m in self.store.select("emails", REAL) if (m.get("pdf") or {}).get("status") == "jd"]
        except Exception as e:
            self.problems.append(f"reading JD documents failed: {type(e).__name__}")
            return {}
        if not checks and not mails:
            return {}
        notices = {n["id"]: n for n in self.store.select("notices", REAL) if n["id"] in checks}
        index = CompanyIndex(roles)
        ups, stats = notice_jd.apply(checks, notices, roles, index, mails=mails)
        if ups:
            try:
                for i in range(0, len(ups), 10):
                    self.store.upsert("roles", ups[i:i + 10])
            except Exception as e:
                self.problems.append(f"saving JDs from notices failed: {type(e).__name__}")
        self.counts["notice_jds"] = {k: v for k, v in stats.items() if k != "companies"}
        return stats

    def _jd_summaries(self, roles: list[dict]) -> None:
        """A short summary per JD (role & team, what you'd do, must-haves, location, eligibility, anything unusual),
        made once per JD text: by Gemini when it answers, else from the JD's own labelled lines."""
        from .jd import RULES_VERSION, detail_text, rules_summary, summarise, text_key, usable
        todo, retry, todo_rules = [], [], []
        for r in roles:
            text = (r.get("jd_text") or "") + ("\n\n" + detail_text(r) if r.get("jd_source") == "inline" else "")
            if not usable(text):
                continue
            key = text_key(text)
            old = r.get("jd_summary") or {}
            if old.get("key") != key:
                todo.append((r, text, key))
            elif old.get("model") == "rules":
                if old.get("rules_version") != RULES_VERSION:
                    todo_rules.append((r, text, key))     # the rules changed: redo it now (no model call)
                retry.append((r, text, key))        # made by rules while Gemini was busy: Gemini gets another go
        # open roles first: those are the ones you might apply to
        order = lambda x: str(x[0].get("effective_deadline") or x[0].get("apply_end") or "")  # noqa: E731
        todo.sort(key=order, reverse=True)
        retry.sort(key=order, reverse=True)
        ups, made = [], Counter()
        t_end = time.monotonic() + JD_AI_SECONDS
        ai_ok = lambda: made["ai_failed"] < 3 and time.monotonic() < t_end  # noqa: E731
        # every JD gets a summary this run: Gemini for the first ones, the JD's own labelled parts for the rest
        # (Gemini gets those on later runs, below)
        for i, (r, text, key) in enumerate(todo):
            s = None
            if i < JD_SUMMARIES_PER_RUN and ai_ok():
                s = summarise(text, self.secrets.ai, timeout=20)
                if s is None:
                    made["ai_failed"] += 1
            if s is None:
                s = rules_summary(text, r.get("designation") or "")
            s["key"] = key
            made["rules" if s.get("model") == "rules" else "ai"] += 1
            ups.append({"id": r["id"], "jd_summary": s})
            r["jd_summary"] = s
        for r, text, key in todo_rules:
            s = {**rules_summary(text, r.get("designation") or ""), "key": key}
            made["rules_redone"] += 1
            ups.append({"id": r["id"], "jd_summary": s})
            r["jd_summary"] = s
        for r, text, key in retry[:max(0, JD_AI_UPGRADES_PER_RUN - made["ai"])]:
            if not ai_ok():
                break
            s = summarise(text, self.secrets.ai, timeout=20)
            if s is None:
                made["ai_failed"] += 1
                continue                              # the rules summary stays
            s["key"] = key
            made["ai_upgraded"] += 1
            ups.append({"id": r["id"], "jd_summary": s})
            r["jd_summary"] = s
        ups = list({u["id"]: u for u in ups}.values())     # one row per role (the last summary made wins)
        if ups:
            try:
                self.store.upsert("roles", ups)
            except Exception as e:
                self.problems.append(f"saving JD summaries failed: {e}")
        self.counts["jd_summaries"] = {k: v for k, v in made.items() if k != "ai_failed"}

    @staticmethod
    def _merge_roles(list_roles, stored_roles, new_roles) -> list[dict]:
        new = {r["id"]: r for r in new_roles}
        merged = []
        for r in list_roles:
            base = dict(stored_roles.get(r["id"], {}))
            base.update(r)
            base.update(new.get(r["id"], {}))
            merged.append(base)
        return merged

    def _check_attachments(self, notices, index, roles, profile, roll) -> dict:
        def priority(n):
            a = n["analysis"]
            mine = a.get("mentions_me")
            relevant = False
            for t in a["targets"]:
                picked, _ = roles_for_target(t, index, a["kind"], n["text"]) if t.get("company") else ([], "")
                if any(r.get("applied") or evaluate(r, profile)["eligible"] is not False for r in picked):
                    relevant = True
            if mine or relevant:
                return 0
            if a["kind"] in LIST_KINDS:
                return 1
            return None  # not yours and not a list: skip

        queue = []
        for n in notices:
            if not n.get("has_attachment"):
                continue
            p = priority(n)
            if p is None:
                self.c("pdfs_skipped_not_relevant")
                continue
            queue.append((p, n))
        queue.sort(key=lambda x: (x[0], x[1]["notice_time"] or ""))
        checks = {}
        for _, n in queue:
            self.c("pdfs_considered")
            try:
                data, ctype = self.erp.notice_attachment(n["year"], str(n["notice_id"]))
            except Exception as e:
                self.c("pdf_download_failed")
                self.problems.append(f"notice {n['notice_id']}: attachment not downloaded ({type(e).__name__})")
                continue
            res = check_attachment(data, roll, profile.get("name") or "", ctype, also=[self.secrets.roll],
                                   notice_kind=(n.get("analysis") or {}).get("kind"))
            res["checked_at"] = datetime.now(timezone.utc).isoformat()
            checks[n["id"]] = res
            self.c(f"pdf_{res['status']}")
            if res["status"] != "unknown":
                self.c("pdfs_read")
            if res["scanned"]:
                self.c("pdf_scanned")
            self.c(f"pdf_format_{res['format']}")
            if res["error"]:
                self.problems.append(f"notice {n['notice_id']} attachment: {res['error']}")
            # structure only, never contents
            log(f"  attachment {n['notice_id']} ({n['company'][:30]}): {res['format']}, {res['pages']}p, "
                f"{res['text_chars']} chars, scanned={res['scanned']}, roll-like={res['roll_like_count']} "
                f"-> {res['status']}" + (f" by {res['matched_by']}" if res['matched_by'] else "")
                + (f" | table heading {res['header']} | found {sorted(res['details'])}" if res["status"] == "yes"
                   else ""))
        return checks

    # ----------------------------------------------------------------- mail
    def _scan_mail(self, roles, profile: dict | None = None) -> list[dict]:
        """Placement mail since the last scan (ping/mail_source.py): headers of every mail, the body and
        attachments of placement mail only. The first scan with new mail rules looks back 14 days."""
        from . import mail_source
        out = []
        try:
            st = self.store if self.store_ok else None
            last = st.get_state("last_mail_scan") if st else None
            version = st.get_state("mail_rules_version") if st else None
            since = datetime.fromisoformat(last) if last else self.now - timedelta(days=3)
            if str(version) != str(mail_source.RULES_VERSION):
                since = min(since, self.now - timedelta(days=MAIL_LOOKBACK_DAYS))
                if version is not None:                      # an upgrade of the rules, not the first scan
                    self.silent_reasons = getattr(self, "silent_reasons", set()) | {"mail rules re-read"}
            profile = profile or {}
            extra = tuple(x.strip() for x in os.environ.get("PING_PLACEMENT_SENDERS", "").split(",") if x.strip())
            out, stats = mail_source.scan(self.mailbox, since, CompanyIndex(roles), profile.get("roll") or "",
                                          profile.get("name") or "", extra)
            self.c("mails_scanned", stats.headers_seen)
            self.c("mails_kept", stats.kept)
            self.c("mail_bodies_read", stats.bodies_read)
            self.c("mail_attachments_read", stats.attachments_read)
            self.c("mail_otp_skipped", stats.otp_skipped)
            self.counts["mail_dropped"] = stats.dropped
            self.counts["mail_kept_because"] = stats.kept_because
            if st:
                if str(version) != str(mail_source.RULES_VERSION):
                    # rows the old, looser scan stored (no rules version): gone; this scan stored the placement ones
                    # of the last 14 days again under today's filter
                    st.delete("emails", {"rules_version": "is.null", "is_sample": "is.false"})
                st.set_state("last_mail_scan", self.now.isoformat())
                st.set_state("mail_rules_version", mail_source.RULES_VERSION)
        except Exception as e:
            self.c("mail_scan_failed")
            self.problems.append(f"mailbox scan failed ({type(e).__name__}: {str(e)[:120]})")
        finally:
            self.mailbox.close()
        return out

    # ----------------------------------------------------------------- save
    def _save(self, list_roles, new_roles, notices, checks, emails, stored_roles) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        try:
            if list_roles:
                self.store.upsert("roles", [{**{k: r.get(k) for k in ROLE_LIST_COLUMNS}, "last_seen": stamp}
                                            for r in list_roles])
            if new_roles:
                keep = ROLE_LIST_COLUMNS + ("details_fetched", "form_type", "bond", "additional_criteria",
                                            "cgpa_cutoff", "cgpa_cutoff_text", "job_description", "erp_messages",
                                            "allowed", "has_more_details_link", "applied_resume_link",
                                            "more_details", "backlog_rule", "cgpa_criteria", "selection_details",
                                            "has_written_test")
                self.store.upsert("roles", [{k: r.get(k) for k in keep if k in r} for r in new_roles])
            if notices:
                self.store.upsert("notices", [{k: n.get(k) for k in (
                    "id", "year", "notice_id", "type", "subject", "company", "preview", "text", "notice_time",
                    "notice_time_text", "has_attachment", "analysis")} for n in notices])
                contacts = []
                for n in notices:
                    for c in n["analysis"].get("contacts", []):
                        contacts.append({"id": f"{n['id']}:{c['phone']}", "notice_id": n["notice_id"],
                                         "company": n["company"], "name": c["name"], "phone": c["phone"]})
                if contacts:
                    # one row per id: a notice that lists the same number twice can't fail the whole save
                    self.store.upsert("contacts", list({c["id"]: c for c in contacts}.values()))
            if checks:
                rows = [{"notice_id": k, **{f: v.get(f) for f in (
                    "status", "matched_by", "format", "pages", "text_chars", "scanned", "ocr", "roll_like_count",
                    "header", "my_row", "context", "details", "error", "checked_at")
                    if f != "checked_at" or v.get(f)}} for k, v in checks.items()]
                for i in range(0, len(rows), 5):              # a JD kept whole is big: a few rows per request
                    self.store.upsert("pdf_checks", rows[i:i + 5], key="notice_id")
        except Exception as e:
            self.problems.append(f"saving failed: {e}")
            log(f"saving failed: {e}")

        if emails:
            try:
                self.store.upsert("emails", emails)
            except Exception as e:                       # before Admin > apply-sql added the mail columns
                try:
                    self.store.upsert("emails", [{k: m.get(k) for k in (
                        "id", "received_at", "sender", "subject", "snippet", "company", "links")} for m in emails])
                    self.problems.append(f"emails saved without kind/dates (run Admin > apply-sql): {str(e)[:80]}")
                except Exception as e2:
                    self.problems.append(f"saving emails failed: {e2}")

    def _rebuild(self, profile) -> list[dict]:
        roles = self.store.select("roles", REAL)
        self._notice_jds(roles)
        self._jd_summaries(roles)
        notices = [n for n in self.store.select("notices", REAL) if n.get("analysis")]
        # Re-read stored notices with today's rules (cheap: text only), so fixes apply to past notices too.
        # Answers that came from the AI fallback are kept as they are.
        index = CompanyIndex(roles)
        for n in notices:
            if n["analysis"].get("method") != "ai" and (n.get("text") or n.get("preview")):
                n["analysis"] = analyze(n, n.get("text") or n.get("preview"), index, profile["roll"],
                                        profile.get("name") or "")
        checks = {}
        fixed = []
        for c in self.store.select("pdf_checks", REAL):
            before = c.get("details")
            checks[c["notice_id"]] = refresh_details(c, profile["roll"])
            if c.get("details") != before:
                fixed.append({"notice_id": c["notice_id"], "details": c["details"]})
        if fixed:
            try:
                self.store.upsert("pdf_checks", fixed, key="notice_id")
            except Exception as e:
                self.problems.append(f"saving re-read PDF details failed: {e}")
        self.counts["pdf_details_reread"] = len(fixed)
        emails = self.store.select("emails", REAL)
        corrections = {c["notice_id"]: c for c in self.store.select("corrections")} if self.store_ok else {}
        self._classify(roles, profile)
        dstats: dict = {}
        previous = {p["id"]: p for p in self.store.select("items", REAL)}
        # your form ticks (form_status: your own rows; a demo session's never count): a ticked form is done, so no
        # reminder is made for it (the digests read "done" from the last run's rows)
        from . import forms as forms_mod
        forms_prev = {f["key"]: f for f in self._rows("forms", REAL)}
        status_rows = self._rows("form_status", {"is_demo": "is.false"})
        filled = forms_mod.filled_keys(status_rows)
        not_for_me = forms_mod.not_for_me_items(status_rows, list(forms_prev.values()), roles)
        self.counts["not_for_me_items"] = len(not_for_me)
        filled_items = {iid for k in filled for iid in (forms_prev.get(k) or {}).get("item_ids") or [] if iid in previous}
        for_build = {**previous, **{iid: {**previous[iid], "done": True} for iid in filled_items}}
        items = build_items(roles, notices, checks, profile, self.now, emails, corrections, stats=dstats,
                            previous=for_build, not_for_me=not_for_me)
        # a role's deadline that moved since the last run becomes one "Update" message
        from .dedupe import changes_since_last_run
        moved = [u for u in changes_since_last_run(previous, items, self.now) if u["id"] not in previous]
        items += moved
        self.counts["dedupe"] = {k: v for k, v in dstats.items() if k != "examples"}
        self.counts["dedupe"]["deadline_moves_between_runs"] = len(moved)
        self.counts["dedupe_examples"] = dstats.get("examples", [])[:5]
        # the forms list: one row per form (ping/forms.py), and each form item learns its form and your tick.
        # Short links are followed and form pages read (closed? sign-in only? title, questions) within the run's
        # limits (ping/form_pages.py); what was read is kept in form_pages.
        try:
            merges = self._rows("form_merges", {"is_demo": "is.false"})
            pages = {p["key"]: p for p in self._rows("form_pages")}
            reader = None
            if self.read_form_pages:
                from .form_pages import Reader
                reader = Reader(pages, get=self.form_get, now=self.now)
            frows = forms_mod.build(items, forms_prev, merges, pages, fetch=reader.follow if reader else None, now=self.now)
            if reader:
                pages = reader.read_rows(frows)
                frows = forms_mod.build(items, forms_prev, merges, pages, fetch=reader.follow, now=self.now)
                if reader.saved:
                    try:
                        self.store.upsert("form_pages", reader.saved, key="key")
                    except Exception as e:
                        self.problems.append(f"saving form pages failed: {type(e).__name__}: {str(e)[:120]}")
                self.counts["form_pages"] = reader.stats
            # rows that were merged into another (the same notice, link, or companies + purpose): their ticks move
            # with them, the old rows and any pending "same form?" choices go (Ping doesn't ask any more)
            new_keys = {r["key"] for r in frows}
            moved = forms_mod.carry_ticks(self._rows("form_status", {"is_demo": "is.false"}), forms_prev, frows)
            if moved:
                self.store.upsert("form_status", moved, key="owner_id,form_key")
                filled = filled | {m["form_key"] for m in moved}
            forms_mod.mark_items(items, frows, filled)
            if frows:
                self.store.upsert("forms", [forms_mod.stored(r) for r in frows], key="key")
            stale = [k for k, r in forms_prev.items() if k not in new_keys and not r.get("is_sample")]
            for k in stale:
                self.store.delete("forms", {"key": f"eq.{k}", "is_sample": "is.false"})
            if stale or self._rows("form_merges", {"is_demo": "is.false"}):
                try:
                    self.store.delete("form_merges", {"is_demo": "is.false"})
                except Exception:
                    pass
            self.counts["forms_cleanup"] = {"rows_merged_away": len(stale), "ticks_moved": len(moved)}
            self.counts["forms"] = {"forms": len(frows), "filled": len(filled & {r["key"] for r in frows}),
                                    "from_several_postings": sum(1 for r in frows if len(r["sources"]) > 1),
                                    "deadlines_moved": sum(1 for r in frows if r["deadline_history"])}
        except Exception as e:                        # e.g. before Admin > apply-sql made the forms tables
            self.problems.append(f"forms list not built: {type(e).__name__}: {str(e)[:120]}")
        # the posting guard (ping/posting.py): what this run may post at all
        from . import posting
        try:
            # the same message twice (same key, same words) is one message, whatever its ids
            self.counts["repeats_collapsed"] = posting.collapse_repeats(items)
            items = posting.guard(items, previous, self.store, self.now, paused=posting.paused(),
                                  silent=sorted(getattr(self, "silent_reasons", set())), log=log)
        except Exception as e:                                     # never post when the guard itself fails
            self.problems.append(f"posting guard failed, nothing new posted: {type(e).__name__}: {e}")
            for it in items:
                if it["id"] not in previous and it.get("level") != "hidden":
                    it["level"] = "hidden"
                    it.setdefault("details", {})["hidden_because"] = "not posted: the posting guard failed"
        # what the chat shows that it didn't show before (role cards and reminders live inside the digests)
        self.new_messages = [it for it in items if it["id"] not in previous and it.get("level") != "hidden"
                             and it.get("category") not in ("apply", "reminder") and not it.get("dismissed")]
        self.new_in_chat = len(self.new_messages)
        self.counts["new_in_chat"] = self.new_in_chat
        stamp = datetime.now(timezone.utc).isoformat()
        # role eligibility + effective deadline, for the dashboard
        dls = effective_deadlines(roles, notices, CompanyIndex(roles))
        role_updates = []
        for r in roles:
            e = evaluate(r, profile)
            role_updates.append({"id": r["id"], "eligible": e["eligible"], "eligibility": e,
                                 "effective_deadline": dls[r["id"]]["at"], "deadline_source": dls[r["id"]]["source"]})
        try:
            if role_updates:
                self.store.upsert("roles", role_updates)
            if items:
                # first_seen is when a message was first sent: kept from the last run, else this run. Digests
                # and "new roles" messages carry their own (the run that made them).
                nowiso = self.now.astimezone(timezone.utc).isoformat()
                self.store.upsert("items", [{**it, "updated_at": stamp,
                                             "first_seen": (previous.get(it["id"]) or {}).get("first_seen")
                                             or it.get("first_seen") or nowiso} for it in items])
        except Exception as e:
            self.problems.append(f"saving the feed failed: {e}")
        return items

    def _rows(self, table: str, query: dict | None = None) -> list[dict]:
        """A table's rows, or none when it isn't there yet (a project that hasn't run apply-sql since)."""
        try:
            return self.store.select(table, query or {})
        except Exception:
            return []

    def _classify(self, roles: list[dict], profile: dict) -> None:
        """'For you' or not, for every role you could apply to (cached on the role; see ping/relevance.py)."""
        from . import relevance
        targets = "" if profile.get("feed_mode") == "all" else (profile.get("targets") or "")
        not_int = profile.get("not_interested_companies") or []
        open_ = [r for r in roles if evaluate(r, profile)["eligible"] is not False
                 and not any(n and n.lower() in (r.get("company") or "").lower() for n in not_int)]
        from . import cvs
        try:
            self.counts["cvs"] = cvs.summarise_new(self.store, self.secrets.supabase_url, self.secrets.supabase_key,
                                                   profile, self.secrets.ai)
        except Exception as e:
            self.problems.append(f"reading your CVs failed: {type(e).__name__}")
        try:
            self.counts["relevance"] = {"roles_checked": len(open_),
                                        **relevance.mark_roles(self.store, open_, targets, self.secrets.ai,
                                                               cvs.cvs_text(profile.get("cvs")))}
        except Exception as e:
            self.problems.append(f"marking roles 'for you' failed: {e}")

    @staticmethod
    def _item_counts(items) -> dict:
        out = {"always": 0, "show": 0, "hidden": 0, "review": 0}
        for it in items:
            out[it["level"]] = out.get(it["level"], 0) + 1
            if it.get("needs_review") and it["level"] != "hidden":
                out["review"] += 1
        return out

    # --------------------------------------------------------------- alerts
    def _login_failure_tracking(self, status: str) -> None:
        if not self.store_ok:
            return
        try:  # the dashboard login with this address may read your data
            self.store.upsert("allowed_users", [{"email": self.secrets.mail_address.strip().lower()}], key="email")
        except Exception as e:
            self.problems.append(f"could not register the dashboard login ({e})")
        kind = failure_kind(status)
        n = self.store.get_state("erp_failures_in_a_row", 0) or 0
        alerted = bool(self.store.get_state("erp_streak_alerted", False))
        paused = credentials_pause(self.store)
        last_error = self.problems[-1] if self.problems else status
        if kind == "credentials":
            # alert now, every time it happens (scheduled runs stop, so that's once, plus any run you start)
            self.store.set_state("paused_for_credentials", {"kind": status.removeprefix("failed: "),
                                                            "at": datetime.now(timezone.utc).isoformat(),
                                                            "error": last_error[:500]})
            self._tell(f"The ERP refused the login: {last_error.rstrip('.')}. I've paused the hourly checks. Fix it (GitHub "
                       "secrets ERP_USER_ID / ERP_PASSWORD / ERP_SECQ_1-3), then start a run yourself: Check now "
                       "(the chat's header, or Profile > Account), or Actions > Ping > Run workflow.",
                       "Login refused: hourly checks paused",
                       f"The ERP refused Ping's login ({status}).\n\n{last_error}\n\nHourly checks are paused so the "
                       "account isn't locked. Fix the secret, then start a run by hand (dashboard: Check now, "
                       "or GitHub Actions > Ping > Run workflow); that run resumes the schedule.")
        else:
            if paused:  # a run you started got past the credentials check: the schedule is back on
                self.store.set_state("paused_for_credentials", None)
                if kind is None:
                    self._tell("Logged in again; hourly checks are back on.")
            if kind is None:
                if alerted:
                    self._tell(BACK_ONLINE_MSG.format(n=n))
                n, alerted = 0, False
            else:
                n += 1
                if n >= STREAK_ALERT_AT and not alerted:
                    self._tell(UNREACHABLE_MSG, "Couldn't reach the ERP for 3 runs",
                               f"Ping's last {n} runs couldn't get into the ERP. This happens when the ERP is down "
                               f"or slow; Ping keeps trying every hour and will say when it's back.\n\n"
                               f"Last error: {last_error}")
                    alerted = True
            self.store.set_state("erp_failures_in_a_row", n)
            self.store.set_state("erp_streak_alerted", alerted)
        self.counts["erp_failures_in_a_row"] = n

    def _tell(self, chat_text: str, email_subject: str | None = None, email_body: str | None = None) -> None:
        """One message from Ping in the dashboard chat, and optionally one email."""
        self.told = chat_text
        try:
            self.store.insert("chat_messages", [{"role": "ping", "text": chat_text}])
        except Exception as e:
            self.problems.append(f"could not post to the chat ({e})")
        log(f"chat message: {chat_text}")
        if email_subject:
            ok = notify.send_self(self.secrets.mail_address, self.secrets.mail_app_password, email_subject,
                                  email_body or chat_text)
            log(f"alert '{email_subject}' emailed to you: {ok}")

    def _alerts(self, status: str) -> None:
        # login problems are handled in _login_failure_tracking (email + chat message, once per streak)
        if not self.store_ok and notify.should_alert(self.store, "db", self.store_ok):
            ok = notify.send_self(self.secrets.mail_address, self.secrets.mail_app_password, "Database not set up",
                                  "Ping ran but could not save anything: the Supabase tables don't exist yet.\n"
                                  "Run Actions > Admin > apply-sql (or paste sql/schema.sql in Supabase's SQL editor).")
            log(f"alert 'Database not set up' emailed to you: {ok}")

    def _print_summary(self, rec: dict) -> None:
        c = rec["counts"]
        it = c.get("items", {})
        lines = [
            "", "================ PING RUN SUMMARY ================",
            f"status            : {rec['status']}",
            f"login             : {rec['login_seconds']}s total, {rec['otp_seconds']}s waiting for OTP, "
            f"Get OTP pressed {rec['otp_requests']}x",
            f"roles             : {c.get('roles_seen', 0)} seen, {c.get('roles_new', 0)} new "
            f"(popup failures {c.get('role_popup_failed', 0)}, more-details empty {c.get('role_more_details_empty', 0)},"
            f" more-details failures {c.get('role_more_details_failed', 0)})",
            f"notices           : {c.get('notices_seen', 0)} seen, {c.get('notices_new', 0)} new "
            f"(rules unsure on {c.get('notices_rules_unsure', 0)}, text failures {c.get('notice_text_failed', 0)})",
            f"attachments       : {c.get('pdfs_considered', 0)} checked, {c.get('pdfs_read', 0)} read, "
            f"yes {c.get('pdf_yes', 0)} / no {c.get('pdf_no', 0)} / unknown {c.get('pdf_unknown', 0)}, "
            f"scanned {c.get('pdf_scanned', 0)}, skipped (not yours) {c.get('pdfs_skipped_not_relevant', 0)}",
            f"mailbox           : {c.get('mails_scanned', 0)} mails (headers only), {c.get('mails_kept', 0)} placement mails "
            f"kept and read, {c.get('mail_otp_skipped', 0)} OTP mails skipped; in the feed: "
            f"{c.get('dedupe', {}).get('mail_twins', 0)} also on the ERP, {c.get('dedupe', {}).get('mail_only', 0)} mail-only",
            f"job descriptions  : {c.get('jd_found') or 'none looked up (no role changed)'}; summaries "
            f"{c.get('jd_summaries') or 'none needed'}",
            f"AI fallback       : {c.get('ai', {}).get('calls', 0)} calls, {c.get('ai', {}).get('answers', 0)} answers, "
            f"{c.get('ai', {}).get('errors', 0)} errors (only for notices the rules couldn't read)"
            + (f"; last error: {c['ai']['last_error']}" if c.get('ai', {}).get('last_error') else ""),
            f"repeats merged    : {c.get('dedupe', {}).get('duplicates_merged', 0)} duplicates "
            f"({c.get('dedupe', {}).get('unsure_merges', 0)} of them unsure), {c.get('dedupe', {}).get('emails_merged', 0)}"
            f" emails, {c.get('dedupe', {}).get('updates', 0)} turned into updates, "
            f"{c.get('dedupe', {}).get('deadline_moves_between_runs', 0)} deadline moves since last run",
            f"feed              : always {it.get('always', 0)}, show {it.get('show', 0)}, hidden {it.get('hidden', 0)},"
            f" questions for you {it.get('review', 0)}",
            f"ERP requests      : {rec['gate_requests']} (all through the read-only gate)",
            "ERP addresses visited (every request this run, by address):",
            *[f"    {n:4d} x {path}" for path, n in sorted(rec.get("counts", {}).get("erp_addresses", {}).items())],
            f"total time        : {c.get('seconds_total')}s",
        ]
        if rec["problems"]:
            lines.append("problems:")
            lines += [f"  - {p}" for p in rec["problems"][:25]]
        lines.append("==================================================")
        print("\n".join(lines), flush=True)


# ---------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m ping.run")
    ap.add_argument("--mode", default=os.environ.get("PING_MODE") or "run",
                    choices=["run", "check", "probe", "load-sample", "remove-sample", "diagnose", "recheck", "rescan"])
    ap.add_argument("--company", default=os.environ.get("PING_COMPANY") or "",
                    help="diagnose / recheck: the company to read again from the ERP")
    ap.add_argument("--memory", help="use a local JSON file instead of Supabase (testing)")
    args = ap.parse_args(argv)
    load_dotenv()
    # 'schedule' for the hourly run (GitHub's cron, or Supabase's kick-run which passes source=schedule)
    trigger = os.environ.get("PING_TRIGGER") or os.environ.get("GITHUB_EVENT_NAME", "manual")

    if args.mode in ("load-sample", "remove-sample"):
        from . import sample
        secrets = load_secrets(require_erp=False, require_store=not args.memory)
        store = MemoryStore(args.memory) if args.memory else SupabaseStore(secrets.supabase_url, secrets.supabase_key)
        ok, msg = store.ready()
        if not ok:
            print(f"Database not ready: {msg}")
            return 2
        n = sample.load(store) if args.mode == "load-sample" else sample.remove(store)
        store.save()
        print(f"{args.mode}: {n} rows")
        return 0

    try:
        secrets = load_secrets(require_erp=True, require_store=not args.memory)
    except ConfigError as e:
        print(f"Setup problem: {e}")
        return 2
    store = MemoryStore(args.memory) if args.memory else SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    ok, msg = store.ready()
    if not ok:
        log(f"DATABASE NOT READY: {msg}")
        log("Continuing without saving (numbers below are still real). Run sql/schema.sql in Supabase.")
        store = MemoryStore()
    if args.mode == "check":
        print(f"secrets: ok ({len(secrets.security_answers)} security answers), database: {msg}")
        if not args.memory:
            from .authcheck import check_dashboard_auth
            print("\n---- dashboard login check ----")
            try:
                for line in check_dashboard_auth(secrets.supabase_url, secrets.supabase_key,
                                                 os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip(),
                                                 secrets.mail_address):
                    print(line)
            except Exception as e:
                print(f"dashboard login check failed: {type(e).__name__}: {e}")
        return 0 if ok else 2
    if args.mode == "probe":
        from .probe import probe
        return probe(secrets, store if ok else None)
    if args.mode == "rescan":
        from .recheck import rescan
        r = Runner(secrets, store, store_ok=ok, trigger=trigger)
        from .notice_jd import coverage
        before = coverage(store.select("roles", REAL), store)
        # every list notice, and every notice with a file about a company whose roles lack a JD, of the season so far
        changes = rescan(r, days=int(os.environ.get("PING_DAYS") or 120), jds=True)
        after = coverage(store.select("roles", REAL), store)
        print(f"\n==== re-scan: {r.rechecked['files']} files read again, {len(changes)} verdict(s) changed ====")
        jd_files = sum(1 for c in r.rechecked["checks"].values() if c.get("status") == "jd")
        print(f"JD documents found: {jd_files} on notices read now; roles with a real JD {before['jd']} -> {after['jd']} "
              f"(+{after['jd'] - before['jd']}); facts the documents add to roles without them: {after['doc_facts']}")
        for co, n in sorted(after["gained_by_company"].items()):
            print(f"  {co}: {n} role(s) now have a JD from a notice or mail document")
        for c in changes:
            print(f"  {c['company']} | {c['subject']} ({c['kind']}, posted {c['posted']}) | {c['old']} -> {c['new']}"
                  + (f" | {c['why']}" if c.get('why') else ""))
        store.save()
        return 0
    if args.mode == "recheck":
        from .recheck import recheck
        if not args.company:
            print("recheck needs --company")
            return 2
        res = recheck(Runner(secrets, store, store_ok=ok, trigger="manual"), args.company, os.environ.get("PING_RUN_ROW") or None)
        # what the page will show is built from this (your own lists' verdicts; nobody else's data is in it)
        print("RECHECK_RESULT " + json.dumps(res, default=str))
        store.save()
        return 0
    if args.mode == "diagnose":
        from .recheck import diagnose
        if not args.company:
            print("diagnose needs --company")
            return 2
        return diagnose(Runner(secrets, store, store_ok=ok, trigger=trigger), args.company)
    if not ok and trigger == "schedule":
        # Without a database every hourly run would be a full first run (~7 min of free
        # GitHub minutes and an OTP mail each). Remind instead; manual runs still go ahead.
        if notify.should_alert(store, "db", False):
            notify.send_self(secrets.mail_address, secrets.mail_app_password, "Database not set up",
                             "Ping is skipping its hourly runs until the database exists.\n"
                             "Open Supabase > SQL Editor > New query, paste sql/schema.sql from the repo, press Run.")
        log("Skipping this scheduled run: database not set up (see above).")
        return 2
    paused = credentials_pause(store) if ok else None
    if paused and trigger == "schedule":
        log(f"Skipping: the ERP refused the login ({paused.get('kind')}) at {paused.get('at')}. Hourly checks stay "
            "paused until you start a run yourself (dashboard Menu > Check now, or Actions > Ping > Run workflow).")
        return 0  # you were already told; a red run every hour would only add GitHub's own emails
    rec = Runner(secrets, store, store_ok=ok, trigger=trigger, read_form_pages=True).run()
    store.save()
    if rec["status"] == "ok":
        return 0
    # Scheduled runs: Ping already alerts on its own terms (above), so don't also make GitHub email a
    # "run failed" notice every hour the ERP is down. Runs you start yourself still show red.
    return 0 if trigger == "schedule" else 1


if __name__ == "__main__":
    sys.exit(main())
