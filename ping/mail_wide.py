"""A wider placement-mail filter, for a read-only dry run first (Admin > mail-audit). The hourly run does NOT use
this yet: it is switched on only after the dry run's list has been looked at (docs/DECISIONS.md, 24 Nov).

On top of today's filter (ping/mail_source.py scope), a mail is placement mail when
  - its sender's domain or name is a company on the companies list, short names included ("JPMC" for JP Morgan
    Chase, "zs.com" for ZS Associates);
  - its subject or body names a listed company together with a placement word (application, assessment, test,
    interview, shortlist, offer, PPO, slot, round, JD);
  - it comes from a test or hiring platform (HackerRank, HackerEarth, Mettl/Mercer, SHL, Unstop, Codility, iMocha,
    AMCAT, Aon, Talview, HireVue, Superset, Workday, Greenhouse, Lever, SuccessFactors...) or from a sender that
    sent a test link before;
  - it is in a thread with a kept mail, or with a mail you sent about an application.
Never: OTP mails, account / shopping mail, newsletters and promotions, job-board alerts (LinkedIn, Naukri,
Internshala...) unless they name a listed company with a deadline.
The body of a mail the headers don't settle is read in memory only, to decide; nothing of a mail that isn't kept
is stored or printed.
"""

from __future__ import annotations

import re

from .mail_source import (COMMON, JOB_BOARDS, NOT_PLACEMENT, OTP_RE, TEST_PLATFORMS, Verdict, _address, _domain_words,
                          find_companies, scope)
from .matching import CompanyIndex, compact, tokens

PLATFORMS = tuple(dict.fromkeys(TEST_PLATFORMS + (
    "unstop", "dare2compete", "workday", "myworkday", "myworkdayjobs", "greenhouse", "lever", "successfactors", "sapsf",
    "mercer", "mettl", "shl", "talview", "hirevue", "imocha", "amcat", "codility", "hackerrank", "hackerearth",
    "superset", "joinsuperset", "aon", "cut-e", "cute", "smartrecruiters", "icims", "taleo", "oraclecloud")))
PLACEMENT_WORD = re.compile(r"\b(applications?|applied|assessments?|tests?|interviews?|shortlist(?:ed)?|offers?|ppo|"
                            r"slots?|rounds?|jd|job description)\b", re.I)
DEADLINE_WORD = re.compile(r"deadline|last date|apply by|closes?|before \d|by \d{1,2}(?:st|nd|rd|th)?\s+[a-z]{3}", re.I)
APPLIED_WORD = re.compile(r"\bappl(?:y|ied|ication)\b|\bresume\b|\bcv\b", re.I)


def _initials(core: list[str]) -> str:
    """'JP Morgan Chase' -> 'jpmc': short words whole, others by their first letter."""
    return "".join(w if len(w) <= 3 else w[0] for w in core)


class Names:
    """Each listed company's ways of being written in a sender: its compact name, a distinctive first word, its
    initials ("jpmc"), and a short first word when a domain label is exactly that ("zs")."""

    def __init__(self, index: CompanyIndex):
        self.index = index
        self.by_label: dict[str, str] = {}
        for c in index.by_company:
            core = tokens(c)
            if not core:
                continue
            labels = {compact(c)}
            if len(core[0]) >= 5 and core[0] not in COMMON:
                labels.add(core[0])
            ini = _initials(core)
            if len(core) > 1 and len(ini) >= 3:
                labels.add(ini)
            # initials then the rest written out: "jpmchase" for JP Morgan Chase
            for k in range(1, len(core)):
                v = _initials(core[:k]) + "".join(core[k:])
                if len(v) >= 6:
                    labels.add(v)
            if 2 <= len(core[0]) <= 4 and core[0] not in COMMON:
                labels.add(core[0])          # "zs", "ey": only ever an exact domain label / word, never a part
            for l in labels:
                if len(l) >= 2:
                    self.by_label.setdefault(l, c)

    def in_sender(self, name: str, domain: str) -> str | None:
        labels = [w for w in re.split(r"[.\-]", domain or "") if w]
        for l in labels:
            if l in self.by_label and l not in ("com", "co", "in", "org", "net", "io", "mail", "email", "gmail"):
                return self.by_label[l]
            hit = next((c for lab, c in self.by_label.items() if len(lab) >= 6 and (l.startswith(lab) or lab.startswith(l) and len(l) >= 6)), None)
            if hit:
                return hit
        found = find_companies(name, self.index, [])
        if found:
            return found[0]
        words = set(tokens(name, keep_stop=True))
        return next((c for lab, c in self.by_label.items() if len(lab) >= 3 and lab in words), None)

    def in_text(self, text: str) -> list[str]:
        found = list(dict.fromkeys(find_companies(text, self.index, [])))
        words = set(tokens(text, keep_stop=True))
        found += [c for lab, c in self.by_label.items() if len(lab) >= 4 and lab in words and c not in found]
        return found


def platform_of(name: str, domain: str) -> str | None:
    words = set(_domain_words(domain)) | set(re.split(r"[^a-z0-9]+", (name or "").lower()))
    return next((p for p in PLATFORMS if p in words), None)


def wide_scope(head, index: CompanyIndex, names: Names, *, extra_senders=(), test_senders=frozenset(), threads=frozenset(),
               thread_of=None) -> Verdict:
    """The wider rule from headers. 'body' as the reason: read the body (in memory) to decide."""
    base = scope(head, index, extra_senders)
    if base.because == "otp" or OTP_RE.search(head.subject or ""):
        return Verdict(False, "otp")
    if base.keep:
        return base
    name, local, domain = _address(head.sender)
    addr = f"{local}@{domain}"
    plat = platform_of(name, domain)
    if plat:
        return Verdict(True, f"platform:{plat}")
    if addr in test_senders:
        return Verdict(True, "sent a test link before")
    if thread_of and thread_of(head) in threads:
        return Verdict(True, "thread")
    if base.because == "not_placement":
        return base
    co = names.in_sender(name, domain)
    if co and base.because != "job_board":
        return Verdict(True, "company_sender", co)
    if base.because == "job_board":
        cos = names.in_text(head.subject or "")
        if cos and DEADLINE_WORD.search(head.subject or ""):
            return Verdict(True, "job_board_company_deadline", cos[0])
        return Verdict(False, "job_board", signal="body")      # the body may name a listed company with a deadline
    if head.bulk:
        return Verdict(False, "bulk")
    return Verdict(False, base.because, signal="body")


def body_decides(head, text: str, names: Names, job_board: bool) -> Verdict:
    """For a mail the headers didn't settle: a listed company together with a placement word (a job-board alert:
    with a deadline)."""
    blob = f"{head.subject}\n{text[:20000]}"
    cos = names.in_text(blob)
    if not cos:
        return Verdict(False, "no listed company in the body")
    if job_board:
        return Verdict(True, "job_board_company_deadline", cos[0]) if DEADLINE_WORD.search(blob) else \
            Verdict(False, "job board, no deadline")
    if PLACEMENT_WORD.search(blob):
        return Verdict(True, "company_in_body", cos[0] if len(cos) == 1 else None)
    return Verdict(False, "company named, no placement word")
