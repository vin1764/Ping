"""A made-up institute mailbox of 20 mails (10 about placements, 10 not), served by a fake IMAP server that records
what Ping fetched: headers only, or the whole message. No real person, address or company mail appears here; the
companies are the ERP list's own made-up entries below.

Used by evals/mail/run_mail_evals.py and tests/test_mail_source.py.
"""

from __future__ import annotations

import email.policy
import re
import sys
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from ping.config import IST  # noqa: E402

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=IST)
ROLL = "22XY10042"
NAME = "Demo Student"
PROFILE = {"roll": ROLL, "name": NAME, "cgpa": 8.0, "department": "COMPUTER SCIENCE AND ENGINEERING",
           "degree": "B.TECH", "reminder_hours": 2}
CDC = "CDC Placement Office <cdc@institute.example>"
OTP_CODE = "482913"


def role(i, company, designation="Analyst", applied=False, due=NOW + timedelta(days=3)):
    return {"id": f"r{i}", "company": company, "designation": designation, "applied": applied,
            "apply_end": due.isoformat(), "first_seen": (NOW - timedelta(days=5)).isoformat(), "erp_messages": [],
            "allowed": [{"degree": "B.TECH", "department": "COMPUTER SCIENCE AND ENGINEERING"}]}


ROLES = [role(1, "Pine Labs Private Limited", "Software Engineer"), role(2, "Groww", "Product Analyst", applied=True),
         role(3, "Accenture Solutions Private Limited", "Associate"), role(4, "Goldman Sachs", "Analyst", applied=True),
         role(5, "Navi Limited", "Data Scientist", applied=True), role(6, "Atlassian", "SDE", applied=True)]

# the ERP notice that one mail repeats (Groww's test), as the notice board shows it
NOTICES = [{"id": "2026-2027:901", "year": "2026-2027", "notice_id": 901, "type": "PLACEMENT",
            "subject": "Schedule", "company": "GROWW", "notice_time": (NOW - timedelta(hours=1)).isoformat(),
            "text": "The online test of GROWW (Profile: Product Analyst) is scheduled on 23rd November 2026 "
                    "from 3:00 PM onwards. Test link will be shared over mail.", "has_attachment": False}]


def _pdf_shortlist(with_me: bool) -> bytes:
    from attachment_fixtures import roster_rows, table_pdf
    rows = roster_rows(30, 11 if with_me else None)
    return table_pdf(rows, title="Goldman Sachs - shortlist for interviews")


def _mail(uid, sender, subject, body, *, hours_ago, html=False, bulk=False, attach=None):
    m = EmailMessage(policy=email.policy.SMTP)
    m["From"], m["To"], m["Subject"] = sender, "student@institute.example", subject
    m["Date"] = format_datetime(NOW - timedelta(hours=hours_ago))
    m["Message-ID"] = f"<fixture-{uid}@institute.example>"
    if bulk:
        m["List-Unsubscribe"] = "<https://lists.example/unsub?u=1>"
    if html:
        m.set_content(re.sub(r"<[^>]+>", " ", body))
        m.add_alternative(body, subtype="html")
    else:
        m.set_content(body)
    if attach:
        name, data = attach
        m.add_attachment(data, maintype="application", subtype="pdf", filename=name)
    return m.as_bytes()


def mails() -> list[dict]:
    """[{uid, raw, placement, label, expect}]: the 20 fixture mails, oldest first."""
    P, N = True, False
    spec = [
        # -------- placement (10)
        ("1", P, "shortlist PDF names you", CDC, "Goldman Sachs: shortlist for interviews",
         "Dear students,\nPlease find attached the list of students shortlisted for Goldman Sachs interviews. "
         "Interviews will be held on 24th November 2026 from 9:00 AM onwards.\nCDC",
         {"attach": ("GS_shortlist.pdf", "with_me")}, {"kind": "shortlist", "company": "Goldman Sachs", "pdf": "yes"}),
        ("2", P, "Google Form with a deadline", "Pine Labs Campus Team <campus@pinelabs.example>",
         "Pine Labs: fill the pre-assessment form",
         "Hi,\nPlease fill this Google Form before the assessment: https://forms.gle/PineLabsPre2026 \n"
         "Deadline: 5:00 PM, 22nd November 2026.\nRegards, Pine Labs Campus Team", {},
         {"kind": "form", "company": "Pine Labs Private Limited", "due_at": "2026-11-22T17:00:00+05:30",
          "main_link": "https://forms.gle/PineLabsPre2026"}),
        ("3", P, "repeats the ERP notice (Groww test)", CDC, "Groww online test on 23rd November",
         "Dear students,\nThe online test of Groww (Product Analyst) is scheduled on 23rd November 2026 from 3:00 PM "
         "onwards. Test link: https://www.hackerrank.com/tests/groww-pa-2026 \nCDC", {},
         {"kind": "test", "company": "Groww", "twin": "2026-2027:901"}),
        ("4", P, "test platform invite", "HackerRank <support@hackerrank.com>",
         "Invitation: Atlassian Online Assessment",
         "<p>Hello,</p><p>You have been invited to the Atlassian online assessment.</p>"
         "<p><a href=\"https://www.hackerrank.com/tests/atl-sde-77\">Start test</a></p>"
         "<p>Complete it by 11:59 PM, 25th November 2026.</p>"
         "<img src=\"https://track.hackerrank.com/open?id=9\">",
         {"html": True, "bulk": True}, {"kind": "test", "company": "Atlassian", "due_at": "2026-11-25T23:59:00+05:30",
                                        "main_link": "https://www.hackerrank.com/tests/atl-sde-77"}),
        ("5", P, "interview slot", "Navi Talent <talent@navi.example>", "Interview schedule - Navi Data Scientist",
         "Hi,\nYour interview is scheduled on 24th November 2026 at 11:00 AM.\n"
         "Join: https://meet.google.com/abc-defg-hij", {},
         {"kind": "interview", "company": "Navi Limited", "event_at": "2026-11-24T11:00:00+05:30"}),
        ("6", P, "pre-placement talk", CDC, "Pre-Placement Talk by Accenture on 21st November",
         "Dear students,\nAccenture will hold a pre-placement talk at 6:00 PM on 21st November 2026. "
         "Venue: Main Auditorium.\nCDC", {},
         {"kind": "ppt", "company": "Accenture Solutions Private Limited", "event_at": "2026-11-21T18:00:00+05:30"}),
        ("7", P, "offer letter", "Groww HR <hr@groww.example>", "Offer letter - Groww Product Analyst",
         "Dear candidate,\nWe are pleased to offer you the role of Product Analyst. Please accept the offer by "
         "30th November 2026.\nGroww HR", {}, {"kind": "offer", "company": "Groww"}),
        ("8", P, "placement-office announcement", CDC, "Placement season 2026-27: guidelines for students",
         "Dear students,\nPlease read the attached placement guidelines. Dress code is formal for all interviews.\nCDC",
         {}, {"kind": "announcement", "company": None}),
        ("9", P, "company with a typo, form link", "Campus Coordinator <coordinator@example.com>",
         "Acenture hiring: registration deadline for campus drive",
         "Register for the Accenture campus drive at https://forms.office.com/r/AccDrive26 before 10:00 AM, "
         "23rd November 2026.", {},
         {"kind": "form", "company": "Accenture Solutions Private Limited", "due_at": "2026-11-23T10:00:00+05:30"}),
        ("10", P, "signal only, company not on the ERP list", "Zeta Recruiting <recruit@zetaworks.example>",
         "Interview invitation: Zeta Works graduate programme",
         "Hi,\nThanks for applying. Your interview is on 26th November 2026 at 2:00 PM.", {},
         {"kind": "interview", "company": None}),
        # -------- not placement (10): only their headers may be read
        ("11", N, "OTP", "ERP Portal <erp@institute.example>", "OTP for Sign In in ERP Portal",
         f"Your OTP is {OTP_CODE}. Valid for 5 minutes.", {}, {"because": "otp"}),
        ("12", N, "job-board alert naming a listed company", "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>",
         "Groww is hiring: Product Analyst and 9 more jobs", "Groww interview tips...", {"bulk": True},
         {"because": "job_board"}),
        ("13", N, "shopping", "Shop <orders@shop.example>", "Your order has been delivered",
         "Your order 123 has been delivered. Rate your interview experience? no.", {}, {"because": "not_placement"}),
        ("14", N, "newsletter", "Hackathons Weekly <newsletter@contests.example>", "Weekly digest: 10 hackathons",
         "Shortlist announced for ...", {"bulk": True}, {"because": "bulk"}),
        ("15", N, "course deadline", "Prof. Course Office <course@institute.example>", "Assignment 3 deadline extended",
         "The assignment deadline is now 25th November 2026.", {}, {"because": "no_placement_signal"}),
        ("16", N, "fest registration", "Spring Fest <fest@institute.example>", "Spring Fest 2027: registrations open",
         "Register now, test your skills!", {}, {"because": "no_placement_signal"}),
        ("17", N, "library", "Central Library <library@institute.example>", "Library book due reminder",
         "Your book is due on 22nd November 2026.", {}, {"because": "no_placement_signal"}),
        ("18", N, "account security", "Google <no-reply@accounts.google.com>", "Security alert",
         "A new sign-in on Linux.", {}, {"because": "not_placement"}),
        ("19", N, "hostel, placement words only in the body", "Hall Office <hall@institute.example>",
         "Mess menu for next week", "Interview candidates may take packed lunch. Shortlist of menu items attached.",
         {}, {"because": "no_placement_signal"}),
        ("20", N, "lecture slides", "Course TA <ta@institute.example>", "Lecture 7 PPT uploaded",
         "Slides are on the course page.", {}, {"because": "no_placement_signal"}),
    ]
    out = []
    for i, (uid, placement, label, sender, subject, body, opts, expect) in enumerate(spec):
        attach = None
        if opts.get("attach"):
            name, which = opts["attach"]
            attach = (name, _pdf_shortlist(which == "with_me"))
        raw = _mail(uid, sender, subject, body, hours_ago=40 - 2 * i, html=opts.get("html", False),
                    bulk=opts.get("bulk", False), attach=attach)
        out.append({"uid": uid, "raw": raw, "placement": placement, "label": label, "subject": subject,
                    "expect": expect})
    return out


class FakeIMAP:
    """Answers the few IMAP commands Mailbox uses and records, per mail, whether Ping fetched the headers only
    or the whole message (body and attachments)."""

    capabilities = (b"IMAP4REV1", b"X-GM-EXT-1")

    def __init__(self, fixture: list[dict]):
        self.by_uid = {m["uid"]: m["raw"] for m in fixture}
        self.headers_read: list[str] = []
        self.bodies_read: list[str] = []
        self.writes: list[str] = []          # anything that would change the mailbox (must stay empty)

    def noop(self):
        return "OK", [b""]

    def logout(self):
        return "BYE", [b""]

    def uid(self, cmd, *args):
        cmd = cmd.upper()
        if cmd == "SEARCH":
            return "OK", [" ".join(self.by_uid).encode()]
        if cmd == "FETCH" and "," in args[0]:       # a page of uids ("1,2,3"), as a real server answers it
            out = []
            for u in args[0].split(","):
                typ, data = self.uid("FETCH", u, args[1])
                if typ == "OK":
                    out += data
            return "OK", out
        if cmd == "FETCH":
            uid, what = args[0], args[1]
            raw = self.by_uid.get(uid)
            if raw is None:
                return "NO", [None]
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            internal = datetime.fromisoformat(
                email.utils.parsedate_to_datetime(str(msg["date"])).isoformat()).strftime("%d-%b-%Y %H:%M:%S %z")
            meta = f'{uid} (UID {uid} INTERNALDATE "{internal}" BODY[] {{{len(raw)}}}'.encode()
            if "HEADER.FIELDS" in what:
                fields = re.search(r"HEADER\.FIELDS \(([^)]*)\)", what).group(1).lower().split()
                head = raw.split(b"\r\n\r\n", 1)[0].split(b"\n\n", 1)[0].decode(errors="replace")
                keep, on = [], False
                for line in head.splitlines():
                    if line[:1] in (" ", "\t"):
                        if on:
                            keep.append(line)
                        continue
                    on = line.split(":", 1)[0].strip().lower() in fields
                    if on:
                        keep.append(line)
                self.headers_read.append(uid)
                return "OK", [(meta, ("\r\n".join(keep) + "\r\n\r\n").encode()), b")"]
            if "BODY.PEEK[]" in what:
                self.bodies_read.append(uid)
                return "OK", [(meta, raw), b")"]
            if "BODY[" in what or "STORE" in what:
                self.writes.append(f"{cmd} {what}")
            return "NO", [None]
        self.writes.append(cmd)
        return "NO", [None]


def mailbox(fixture: list[dict]):
    """A real ping.mailbox.Mailbox talking to FakeIMAP."""
    from ping.mailbox import Mailbox
    mb = Mailbox("student@institute.example", "not-a-password")
    fake = FakeIMAP(fixture)
    mb.imap, mb.gmail, mb.folder = fake, True, "[Gmail]/All Mail"
    mb.close = lambda: None
    return mb, fake
