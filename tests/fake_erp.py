"""A fake ERP that answers like the real one (formats copied from the real
captured pages), plus a fake mailbox. Used to test a full run offline."""

from __future__ import annotations

import io
import random
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlsplit

from ping.config import IST
from ping.gate import Reply
from ping.mailbox import Mail

ROLL = "22XY10042"
QUESTIONS = {"What is the name of your first pet?": "Bruno", "In which city were you born?": "Patna",
             "What is your favourite food?": "Dosa"}


def make_pdf(rows: list[list[str]], heading: str = "Slot 1: 10:00 AM - 11:00 AM  Venue: Nalanda") -> bytes:
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
    with pdf.table() as table:
        for r in rows:
            row = table.row()
            for c in r:
                row.cell(c)
    return bytes(pdf.output())


def roster(include_me: bool, n: int = 40) -> list[list[str]]:
    rows = [["S.No", "Roll No", "Name", "Room"]]
    rnd = random.Random(7)
    for i in range(1, n + 1):
        rows.append([str(i), f"22{rnd.choice(['CS', 'EE', 'ME', 'CH'])}{rnd.randint(10000, 39999)}",
                     f"Student {i}", rnd.choice(["V1", "V2", "V3"])])
    if include_me:
        rows.insert(18, ["17", ROLL, "DEMO STUDENT", "V2"])
    return rows


class FakeErp:
    def __init__(self, now: datetime, question: str = "What is the name of your first pet?"):
        self.now = now
        self.question = question
        self.mail = FakeMailbox(self)
        self.otp = None
        self.logged_in = False
        self.calls: list[str] = []
        d = lambda days, h=16: (now + timedelta(days=days)).replace(hour=h, minute=0)  # noqa: E731
        self.roles = [  # (com_id, jnf_id, company, designation, ctc, cur, applied, end)
            ("501", "1", "Accordion", "Data & AI Analyst", "2400000", "INR", "", d(2)),
            ("501", "2", "Accordion", "Business Analyst", "1800000", "INR", "", d(2)),
            ("501", "3", "Accordion", "Associate", "1500000", "INR", "Y", d(-3)),
            ("502", "1", "Pine Labs", "Software Development Engineer", "3200000", "INR", "Y", d(-4)),
            ("503", "1", "Sakura KK", "Global Engineer", "8214021", "JPY", "", d(5)),
        ]
        self.cutoffs = {("501", "1"): "7.0", ("502", "1"): "0.0", ("503", "1"): "9.5"}
        self.notices = [
            (1801, "Urgent", "PINE LABS", d(-1, 18), True,
             "PFA the test room allocation of shortlisted candidates for the Assessment of Pine Labs, scheduled "
             f"from 10:00 AM onwards on {d(1, 10).day}th {d(1, 10).strftime('%B, %Y')}.<br><br>Venue: Nalanda "
             "Classroom Complex<br><br>The test link has been shared on their Institute Email ID.<br><br>"
             "POCs: [name] (+91 90000 11111), [name] (+91 90000 22222)<br><br>CDC, IIT Kharagpur"),
            (1802, "Date extension", "ACCORDION", d(0, 0), False,
             "The CV Submission for Accordion for the role of Data &amp; AI Analyst has been extended till 4:00 PM, "
             f"{d(3).day}th {d(3).strftime('%B')}, {d(3).year}.<br>All candidates who are applying for the role, are "
             "required to kindly fill the Additional Details Form given below. Link: https://forms.gle/abc123<br>"
             f"Deadline: {d(3).day}th {d(3).strftime('%B')} {d(3).year}, 4:00 PM<br>Interested and eligible students "
             "are advised to apply on the portal and fill the form within the given deadline.<br>CDC, IIT Kharagpur"),
            (1700, "CV Submission", "OLD CO", d(-30), False, "Old notice, outside the first-run window."),
        ]
        self.pdfs = {1801: make_pdf(roster(include_me=True))}

    # -- transport interface used by the Gate
    def send(self, method: str, url: str, data: dict | None, headers: dict | None) -> Reply:
        parts = urlsplit(url)
        path = parts.path
        q = dict(parse_qsl(parts.query))
        data = data or {}
        self.calls.append(f"{method} {path}")
        html = lambda s, ct="text/html;charset=UTF-8": Reply(200, url, {"content-type": ct}, s.encode("utf-8"))  # noqa
        redirect = lambda loc: Reply(302, url, {"location": loc}, b"")  # noqa: E731
        if path == "/IIT_ERP3/" and "ssoToken" not in q:
            return redirect("https://erp.iitkgp.ac.in:443/SSOAdministration/login.htm?sessionToken=S1&"
                            "requestedUrl=https://erp.iitkgp.ac.in/IIT_ERP3/")
        if path == "/SSOAdministration/login.htm":
            return html('<form id="loginForm" role="form" action="auth.htm" method="post">'
                        '<input type="hidden" name="sessionToken" id="sessionToken" value="S1">')
        if path == "/SSOAdministration/getSecurityQues.htm":
            return html(self.question if data.get("user_id") == ROLL else "FALSE", "text/plain")
        if path == "/SSOAdministration/getEmilOTP.htm":
            if data.get("password") != "pw" or data.get("answer") != QUESTIONS.get(self.question):
                return html('{"msg":"Unable to send OTP"}', "application/json")
            self.otp = str(random.randint(100000, 999999))
            self.mail.deliver(self.otp)
            return html('{"msg":"OTP sent to your email"}', "application/json")
        if path == "/SSOAdministration/auth.htm":
            if data.get("email_otp") == self.otp and self.otp:
                self.logged_in = True
                return redirect("success.htm?reqType=REMOTE")
            return html('<div class="alert alert-danger">Invalid OTP</div>')
        if path == "/SSOAdministration/success.htm":
            return redirect("https://erp.iitkgp.ac.in/IIT_ERP3/?ssoToken=T1")
        if path == "/IIT_ERP3/":
            return redirect("/IIT_ERP3/home.htm")
        if path == "/IIT_ERP3/home.htm":
            return html('<a href="logout.htm">Logout</a>')
        if not self.logged_in:
            return html("session expired")
        if path == "/IIT_ERP3/showmenu.htm":
            return html("myform.elements['ssoToken'].value = 'TP-TOKEN';")
        if path == "/TrainingPlacementSSO/TPStudent.jsp":
            return html("<table id='grid37'></table>")
        if path == "/TrainingPlacementSSO/Notice.jsp":
            return html("<table id='grid54'></table>")
        if path == "/TrainingPlacementSSO/ERPMonitoring.htm":
            return html(self._grid37() if q.get("jqqueryid") == "37" else self._grid54())
        if path == "/TrainingPlacementSSO/TPJNFView.jsp":
            return html(self._popup(q["com_id"], q["jnf_id"]), "text/html;charset=ISO-8859-1")
        if path == "/TrainingPlacementSSO/JnfMoreDet.jsp":
            return html("<table><tr><td>Backlog Eligibility</td><td>No active backlogs</td></tr>"
                        "<tr><td>Is there a CGPA criteria</td><td>Yes</td></tr>"
                        "<tr><td colspan=2>Selection Details</td></tr>"
                        "<tr><td>Shortlist from Resumes</td><td>Yes</td></tr>"
                        "<tr><td>Written Test</td><td>Yes</td></tr></table>")
        if path == "/TrainingPlacementSSO/ShowContent.jsp":
            n = next(x for x in self.notices if str(x[0]) == q["id"])
            return html(f'<div id="printableArea">\n<b>Type</b>    : PLACEMENT<br>\n<b>Subject</b> : {n[1]}<br>\n'
                        f'<b>Company</b> : {n[2]}<br>\n<br>{n[5]}<br>\n</div>', "text/html;charset=ISO-8859-1")
        if path == "/TrainingPlacementSSO/AdmFilePDF.htm":
            return Reply(200, url, {"content-type": "application/pdf"}, self.pdfs[int(q["id"])])
        if path == "/IIT_ERP3/logout.htm":
            self.logged_in = False
            return html("bye")
        return Reply(404, url, {}, b"not found")

    def _grid37(self) -> str:
        rows = []
        for i, (cid, jid, comp, desig, ctc, cur, applied, end) in enumerate(self.roles):
            a = lambda t, call: f"<![CDATA[<a title='{t}' href='javascript:void(0);' onclick='{call}'>{t}</a>]]>"  # noqa
            cells = [a(comp, f'TPComView("2026-2027","{cid}");'), a("", f'TPComDescription("2026-2027","{cid}");'),
                     a("", f'TPPPTDescription("2026-2027","{cid}");'),
                     a(desig, f'TPJNFView("{jid}","{cid}","2026-2027");'),
                     a("Apply", f'TPJNFView("{jid}","{cid}","2026-2027");'), f"<![CDATA[{ctc}]]>",
                     f"<![CDATA[{cur}]]>", a("", f'TPJNFDescription("2026-2027","{cid}","{jid}");'),
                     f"<![CDATA[{applied}]]>", f"<![CDATA[{(end - timedelta(days=4)).strftime('%Y-%m-%d %H:%M')}]]>",
                     f"<![CDATA[{end.strftime('%Y-%m-%d %H:%M')}]]>", "<![CDATA[]]>", "<![CDATA[]]>"]
            rows.append(f"<row id='{i}'>" + "".join(f"<cell>{c}</cell>" for c in cells) + "</row>")
        return "<?xml version='1.0' encoding='utf-8'?>\n<rows><page>1</page>" + "".join(rows) + "</rows>"

    def _grid54(self) -> str:
        rows = []
        for i, (nid, subj, comp, when, pdf, text) in enumerate(self.notices):
            plain = text.replace("<br>", "")
            cells = [str(nid), "PLACEMENT", subj, comp,
                     f"<a title='{plain}' href='javascript:void(0);' onclick='ViewNotice(\"2026-2027\",\"{nid}\");'>"
                     f"{plain}</a>", "23XX00000", when.strftime("%d-%m-%Y %H:%M"),
                     f"<a title='{'Download' if pdf else ''}' href='javascript:void(0);' "
                     f"onclick='TPNotice(\"2026-2027\",\"{nid}\");'>{'Download' if pdf else ''}</a>",
                     f"<a title='Upload'  href='TPFile.jsp?file_for=NOTICE&year=2026-2027&id={nid}'>Upload</a>",
                     f"<a title='Deactivate' href='javascript:void(0);' onclick='deactive(\"2026-2027\",\"{nid}\");'>"
                     "Deactivate</a>"]
            rows.append(f"<row id='{i}'>" + "".join(f"<cell><![CDATA[{c}]]></cell>" for c in cells) + "</row>")
        return "<?xml version='1.0' encoding='utf-8'?>\n<rows><page>1</page>" + "".join(rows) + "</rows>"

    def _popup(self, cid: str, jid: str) -> str:
        role = next(r for r in self.roles if r[0] == cid and r[1] == jid)
        cut = self.cutoffs.get((cid, jid), "0.0")
        msg = "Company requirement has CGPA cut off greater than yours." if float(cut) > 8.5 else ""
        depts = "".join(
            f'<tr>\n<td colspan="6" style="background-color: lightgrey;">{d}\n</td>\n</tr>\n<tr>\n<tr>\n'
            f'<td colspan="6">B.TECH --- {d}(B.TECH 4Y)</td>\n</tr>\n'
            for d in ("COMPUTER SCIENCE AND ENGINEERING", "ELECTRICAL ENGINEERING"))
        return f"""<div id="printableArea">
<form action="TPJNFViewAction.jsp" id="ftpjnfvw" name="ftpjnfvw" method="post">
<table border="0" cellpadding="3" cellspacing="3">
<tr><td style="color: green;font-weight: bold;"></td></tr>
<tr><td>{msg}</td></tr>
<tr><td class="header" align="center">Company : {role[2]}</td></tr>
<tr><td class="header">Job Profile</td></tr>
<tr><td><table>
<tr><th>Form Type</th><th>Designation</th><th>Cost to Company per year</th><th>Bond / Service Contract</th>
<th>Additional Criteria</th><th>CGPA Cut-off</th></tr>
<tr><td>PLACEMENT</td><td>{role[3]}</td><td>{role[4]} {role[5]}</td><td></td><td></td><td>{cut}</td></tr>
</table></td></tr>
<tr><td colspan="6" class="header">Job Description</td></tr>
<tr><td colspan="6">Work on interesting things.</td></tr>
<tr><td colspan="6"><a href="javascript:void(0);" onclick="jnfMoreDet('2026-2027', '{ROLL}', '{cid}', '{jid}')">Click Here for more details</a></td></tr>
<tr><td colspan="6" class="header">Allowed Departments and degrees</td></tr>
{depts}
</table></form></div>"""


class FakeMailbox:
    def __init__(self, erp: FakeErp):
        self.erp = erp
        self.mails: list[Mail] = []

    def deliver(self, otp: str) -> None:
        self.mails.append(Mail(str(len(self.mails) + 1), datetime.now(IST), "erp@iitkgp.ac.in",
                               "OTP for Sign In in ERP Portal", f"Your OTP is {otp}. Valid for 5 minutes."))

    def wait_for_otp(self, clicked_at, timeout, poll=5.0, ignore_uids=None):
        for m in reversed(self.mails):
            if m.received >= clicked_at - timedelta(seconds=30) and m.uid not in (ignore_uids or set()):
                return m.text.split("OTP is ")[1][:6], m.uid
        return None, None

    def mails_after(self, after, words=""):
        extra = Mail("99", datetime.now(IST), "Pine Labs Hiring <jobs@pinelabs.example>",
                     "Pine Labs online assessment link", "Your link: https://assess.example.com/pl/xyz",
                     ["https://assess.example.com/pl/xyz"])
        return [m for m in self.mails + [extra] if m.received >= after]

    def close(self):
        pass
