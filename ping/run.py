"""One Ping run, start to finish.

  python -m ping.run                  real run (needs the secrets)
  python -m ping.run --mode check     only check secrets + database, no ERP login
  python -m ping.run --mode load-sample / remove-sample   demo data for the dashboard
"""

from __future__ import annotations

import argparse
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
                 trigger: str = "manual"):
        self.secrets = secrets
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

    # ------------------------------------------------------------------ helpers
    def c(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    def profile(self) -> dict:
        rows = self.store.select("profile") if self.store_ok else []
        prof = dict(PROFILE_DEFAULTS)
        if rows:
            prof.update({k: v for k, v in rows[0].items() if v is not None})
        prof["roll"] = (prof.get("roll") or self.secrets.roll).upper()
        return prof

    # --------------------------------------------------------------------- run
    def run(self) -> dict:
        started = datetime.now(timezone.utc)
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
            checks = self._check_attachments(fresh_notices, index, all_roles, profile, roll)
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
            emails = self._scan_mail(list_roles or list(stored_roles.values()))

        # ---- save + rebuild the feed
        self._save(list_roles, new_roles, fresh_notices, checks, emails, stored_roles)
        items = self._rebuild(profile)
        self._login_failure_tracking(status)

        finished = datetime.now(timezone.utc)
        ls = self.login_stats
        record = {
            "id": started.strftime("%Y%m%dT%H%M%S") + "-" + hashlib.sha1(os.urandom(8)).hexdigest()[:6],
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
        if self.store_ok:
            try:
                self.store.upsert("runs", [record])
            except Exception as e:
                log(f"could not save the run record: {e}")
        self._alerts(status)
        self._print_summary(record)
        return record

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
            res = check_attachment(data, roll, profile.get("name") or "", ctype)
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
    def _scan_mail(self, roles) -> list[dict]:
        out = []
        try:
            last = self.store.get_state("last_mail_scan") if self.store_ok else None
            since = datetime.fromisoformat(last) if last else self.now - timedelta(days=3)
            index = CompanyIndex(roles)
            mails = self.mailbox.mails_after(since)
            self.c("mails_scanned", len(mails))
            for m in mails:
                if "otp" in m.subject.lower():
                    continue
                head = f"{m.subject} {m.sender}"
                found = index.scan_text(head)
                cdc = any(w in m.sender.lower() for w in ("cdc", "placement", "erp"))
                if not found and not cdc:
                    continue
                out.append({
                    "id": hashlib.sha1(f"{m.received.isoformat()}|{m.sender}|{m.subject}".encode()).hexdigest()[:20],
                    "received_at": m.received.isoformat(), "sender": m.sender[:200], "subject": m.subject[:300],
                    "snippet": " ".join(m.text.split())[:300], "company": found[0] if found else None,
                    "links": m.links[:15]})
            self.c("mails_kept", len(out))
            if self.store_ok:
                self.store.set_state("last_mail_scan", self.now.isoformat())
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
                    self.store.upsert("contacts", contacts)
            if checks:
                self.store.upsert("pdf_checks", [{"notice_id": k, **{f: v.get(f) for f in (
                    "status", "matched_by", "format", "pages", "text_chars", "scanned", "ocr", "roll_like_count",
                    "header", "my_row", "context", "details", "error")}} for k, v in checks.items()],
                    key="notice_id")
            if emails:
                self.store.upsert("emails", emails)
        except Exception as e:
            self.problems.append(f"saving failed: {e}")
            log(f"saving failed: {e}")

    def _rebuild(self, profile) -> list[dict]:
        roles = self.store.select("roles", REAL)
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
        dstats: dict = {}
        previous = {p["id"]: p for p in self.store.select("items", REAL)}
        items = build_items(roles, notices, checks, profile, self.now, emails, corrections, stats=dstats,
                            previous=previous)
        # a role's deadline that moved since the last run becomes one "Update" message
        from .dedupe import changes_since_last_run
        moved = [u for u in changes_since_last_run(previous, items, self.now) if u["id"] not in previous]
        items += moved
        self.counts["dedupe"] = {k: v for k, v in dstats.items() if k != "examples"}
        self.counts["dedupe"]["deadline_moves_between_runs"] = len(moved)
        self.counts["dedupe_examples"] = dstats.get("examples", [])[:5]
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
                       "secrets ERP_USER_ID / ERP_PASSWORD / ERP_SECQ_1-3), then start a run yourself: Menu > Check "
                       "now, or Actions > Ping > Run workflow.",
                       "Login refused: hourly checks paused",
                       f"The ERP refused Ping's login ({status}).\n\n{last_error}\n\nHourly checks are paused so the "
                       "account isn't locked. Fix the secret, then start a run by hand (dashboard Menu > Check now, "
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
            f"mailbox           : {c.get('mails_scanned', 0)} mails looked at, {c.get('mails_kept', 0)} kept",
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
                    choices=["run", "check", "probe", "load-sample", "remove-sample"])
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
        return probe(secrets)
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
    rec = Runner(secrets, store, store_ok=ok, trigger=trigger).run()
    store.save()
    if rec["status"] == "ok":
        return 0
    # Scheduled runs: Ping already alerts on its own terms (above), so don't also make GitHub email a
    # "run failed" notice every hour the ERP is down. Runs you start yourself still show red.
    return 0 if trigger == "schedule" else 1


if __name__ == "__main__":
    sys.exit(main())
