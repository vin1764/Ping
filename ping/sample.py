"""Demo data so the dashboard works for someone with no ERP access.

All companies, people and numbers here are made up. Dates are set relative
to the moment you load it, so the demo always looks current. Every row is
marked is_sample = true and has an id starting with "sample", so
`remove-sample` takes out exactly what `load-sample` put in.

  python -m ping.run --mode load-sample      (or the GitHub "Run workflow" button, mode load-sample)
  python -m ping.run --mode remove-sample
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import IST
from .eligibility import evaluate
from .items import build_items, effective_deadlines
from .matching import CompanyIndex
from .notices import analyze

TABLES = ("items", "pdf_checks", "contacts", "emails", "notices", "roles", "runs")
YOP = "sample"

ALL_DEPTS = [{"department": d, "degree": "B.TECH", "programme": f"{d}(B.TECH 4Y)"} for d in (
    "AEROSPACE ENGINEERING", "CHEMICAL ENGINEERING", "CIVIL ENGINEERING", "COMPUTER SCIENCE AND ENGINEERING",
    "ELECTRICAL ENGINEERING", "ELECTRONICS AND ELECTRICAL COMMUNICATION ENGINEERING", "MECHANICAL ENGINEERING",
    "METALLURGICAL AND MATERIALS ENGINEERING", "MINING ENGINEERING", "OCEAN ENGG AND NAVAL ARCHITECTURE",
    "INDUSTRIAL AND SYSTEMS ENGINEERING", "BIOTECHNOLOGY", "AGRICULTURAL AND FOOD ENGINEERING",
    "ARCHITECTURE", "GEOLOGY AND GEOPHYSICS", "MATHEMATICS")]
CIRCUIT_DEPTS = [a for a in ALL_DEPTS if a["department"].startswith(("ELECTRICAL", "ELECTRONICS", "COMPUTER"))]

PROFILE = {"roll": "22XY10042", "name": "Demo Student", "department": "COMPUTER SCIENCE AND ENGINEERING",
           "degree": "B.TECH", "cgpa": 8.12, "active_backlogs": False,
           "cv_names": ["Software CV", "Data CV", "Product CV"],
           "interested_companies": ["Northwind Analytics", "Lumen Payments"],
           "not_interested_companies": ["Tidewater Energy"], "notice_types": ["PLACEMENT"]}


def _role(cid, jid, company, designation, ctc, applied, start, end, *, cut=None, allowed=None, written=True,
          backlog="No active backlogs allowed", currency="INR", erp_messages=None):
    return {"id": f"{YOP}:{cid}:{jid}", "yop": YOP, "com_id": str(cid), "jnf_id": str(jid), "company": company,
            "designation": designation, "ctc": ctc, "ctc_text": str(int(ctc)), "currency": currency,
            "has_company_doc": False, "has_ppt_doc": False, "has_form_doc": True, "applied": applied,
            "apply_start": start.isoformat(), "apply_end": end.isoformat(),
            "apply_end_text": end.strftime("%Y-%m-%d %H:%M"), "interview_date": None, "contract": None,
            "details_fetched": True, "form_type": "PLACEMENT", "bond": None, "additional_criteria": None,
            "cgpa_cutoff": cut, "cgpa_cutoff_text": f"{cut or 0.0}", "job_description": f"{designation} at {company}.",
            "erp_messages": erp_messages or [], "allowed": ALL_DEPTS if allowed is None else allowed,
            "has_more_details_link": True, "applied_resume_link": applied,
            "more_details": {"fields": {"Backlog Eligibility": backlog,
                                        "Is there a CGPA criteria": "Yes" if cut else "No"},
                             "sections": {"Selection Details": {"Shortlist from Resumes": "Yes",
                                                                "Written Test": "Yes" if written else "No",
                                                                "Mode": "Offline"}},
                             "raw_text": "sample"},
            "backlog_rule": backlog, "cgpa_criteria": "Yes" if cut else "No",
            "selection_details": {"Shortlist from Resumes": "Yes", "Written Test": "Yes" if written else "No"},
            "has_written_test": written, "is_sample": True}


def build(now: datetime | None = None) -> dict:
    now = (now or datetime.now(IST)).astimezone(IST).replace(second=0, microsecond=0)
    d = lambda days, h=16, m=0: (now + timedelta(days=days)).replace(hour=h, minute=m)  # noqa: E731
    roles = [
        _role(901, 1, "Northwind Analytics", "Data & AI Analyst", 2400000, False, d(-1), d(2, 16), cut=7.0),
        _role(901, 2, "Northwind Analytics", "Business Analyst", 1800000, False, d(-1), d(2, 16), cut=7.0),
        _role(901, 3, "Northwind Analytics", "Product Engineer", 3000000, True, d(-6), d(-3, 18)),
        _role(902, 1, "Bluefin Capital", "Quant Researcher", 4500000, True, d(-8), d(-5, 20), cut=8.0),
        _role(902, 2, "Bluefin Capital", "Software Engineer", 3800000, True, d(-8), d(-5, 20), cut=7.5),
        _role(903, 1, "Kestrel Robotics", "Embedded Engineer", 2000000, False, d(-2), d(0, 23, 59),
              allowed=CIRCUIT_DEPTS),
        _role(904, 1, "Orchid Health", "Associate Product Manager", 2600000, False, d(-1), d(3, 12), cut=8.5,
              erp_messages=["Company requirement has CGPA cut off greater than yours."]),
        _role(905, 1, "Lumen Payments", "Software Development Engineer", 3200000, True, d(-9), d(-6, 16)),
        _role(905, 2, "Lumen Payments", "Data Scientist", 2900000, False, d(-1), d(4, 20), cut=7.5),
        _role(906, 1, "Tidewater Energy", "Graduate Engineer Trainee", 1400000, False, d(-1), d(2, 18)),
        _role(907, 1, "Quartzline Semiconductors", "Design Engineer", 2500000, True, d(-7), d(-4, 16),
              allowed=CIRCUIT_DEPTS),
        _role(908, 1, "Sakura Systems KK", "Global Engineer", 9000000, False, d(-1), d(5, 10), currency="JPY"),
    ]
    t = lambda days, h, m=0: (now + timedelta(days=days)).replace(hour=h, minute=m)  # noqa: E731
    on = lambda dt: dt.strftime(f"%-I:%M %p, {dt.day}{_sfx(dt.day)} %B %Y")  # noqa: E731
    notices = [
        (1, "Shortlist", "BLUEFIN CAPITAL", t(-1, 18, 30), True,
         f"PFA the test shortlist for the Assessment of Bluefin Capital for the roles of (Quant Researcher, "
         f"Software Engineer), scheduled from 10:00 AM onwards on {t(1, 10).day}{_sfx(t(1, 10).day)} "
         f"{t(1, 10).strftime('%B %Y')}.\nVenue: Nalanda Classroom Complex\n"
         f"The room allocation for the test will be released shortly.\nPOCs: Asha (+91 90000 00001), "
         f"Ravi (+91 90000 00002)\nCDC, IIT Kharagpur"),
        (2, "Urgent", "LUMEN PAYMENTS", t(-1, 21, 0), True,
         "PFA the test room allocation of shortlisted candidates for the Assessment of Lumen Payments, scheduled "
         f"from 7:15 PM onwards on {t(1, 19).day}{_sfx(t(1, 19).day)} {t(1, 19).strftime('%B, %Y')}.\n\n"
         "Venue: Nalanda Classroom Complex\n\nStudents are required to carry their original Institute ID card.\n\n"
         "The test link has been shared on their Institute Email ID.\n\n"
         "POCs: Meera (+91 90000 00003), Kabir (+91 90000 00004)\n\nCDC, IIT Kharagpur"),
        (3, "Result", "QUARTZLINE SEMICONDUCTORS", t(-1, 12, 0), True,
         "PFA the list of students shortlisted for interviews by Quartzline Semiconductors.\nCDC, IIT Kharagpur"),
        (4, "Date extension", "NORTHWIND ANALYTICS", t(0, 0, 5), False,
         f"The CV Submission for Northwind Analytics for the role of Data & AI Analyst has been extended till "
         f"{on(t(3, 16))}.\nAll candidates who are applying for the role are required to fill the Additional "
         f"Details Form given below.\nLink: https://forms.gle/sampleForm123\nDeadline: {on(t(3, 16))}\n"
         "Interested and eligible students are advised to apply on the portal and fill the form within the given "
         "deadline.\nCDC, IIT Kharagpur"),
        (5, "CV Submission", "Multiple Companies", t(-1, 0, 2), False,
         f"The following companies are open for CV Submission till {on(t(0, 23, 59))}.\n"
         "1. KESTREL ROBOTICS (Profile: All)\n2. LUMEN PAYMENTS (Profile: Data Scientist)\n"
         "3. TIDEWATER ENERGY (Profile: Graduate Engineer Trainee)\n"
         "Interested and eligible students are advised to apply within the given deadline.\nCDC, IIT Kharagpur"),
        (6, "Schedule", "CDC Placement Schedule", t(0, 20, 12), False,
         f"All students eligible for placement are advised to take note of the placement schedule for "
         f"{t(1, 9).strftime('%A')}, {t(1, 9).day}{_sfx(t(1, 9).day)} {t(1, 9).strftime('%B %Y')}.\n"
         "1. [TEST] NORTHWIND ANALYTICS (Profile: Product Engineer) (3:00 PM - 4:00 PM)\n"
         "2. [TEST] ORCHID HEALTH (Profile: Associate Product Manager) (6:00 PM - 7:00 PM)\n"
         "Note: The schedule is tentative and subject to changes.\nCDC, IIT Kharagpur"),
        (7, "Urgent", "Acme", t(0, 9, 0), False,
         "The pre-placement talk for Acme Group for all roles will be held tomorrow from 5:00 PM onwards.\n"
         "CDC, IIT Kharagpur"),
        (8, "PPT/Workshop/Seminars etc", "ORCHID HEALTH", t(-2, 15, 0), False,
         f"The Pre-Placement Talk (PPT) for Orchid Health for all the roles is scheduled on "
         f"{t(1, 17).day}{_sfx(t(1, 17).day)} {t(1, 17).strftime('%B %Y')} from 5:00 PM onwards in an offline "
         "mode.\nVenue: Netaji Auditorium\nCDC, IIT Kharagpur"),
    ]
    notice_rows = []
    for nid, subject, company, when, has_pdf, text in notices:
        notice_rows.append({"id": f"{YOP}:{nid}", "year": YOP, "notice_id": 900000 + nid, "type": "PLACEMENT",
                            "subject": subject, "company": company, "preview": text.replace("\n", ""),
                            "text": text, "notice_time": when.isoformat(),
                            "notice_time_text": when.strftime("%d-%m-%Y %H:%M"), "has_attachment": has_pdf,
                            "is_sample": True})
    # Acme is deliberately ambiguous: there are two Acme entities in the companies list
    roles += [_role(909, 1, "Acme Group India", "Analyst", 1600000, True, d(-9), d(-6, 16)),
              _role(910, 1, "Acme Group Japan", "Analyst", 7000000, False, d(-1), d(6, 16), currency="JPY")]
    index = CompanyIndex(roles)
    for n in notice_rows:
        n["analysis"] = analyze(n, n["text"], index, PROFILE["roll"], PROFILE["name"])
    checks = {
        f"{YOP}:1": {"notice_id": f"{YOP}:1", "status": "yes", "matched_by": "roll", "format": "pdf", "pages": 3,
                     "text_chars": 5200, "scanned": False, "ocr": False, "roll_like_count": 140,
                     "header": ["S.No", "Roll No", "Name", "Room", "Slot"],
                     "my_row": ["57", PROFILE["roll"], PROFILE["name"].upper(), "V2", "Slot 1"],
                     "context": "Slot 1: 10:00 AM - 11:00 AM", "details": {"room": "V2", "slot": "Slot 1"},
                     "error": None, "is_sample": True},
        f"{YOP}:2": {"notice_id": f"{YOP}:2", "status": "no", "matched_by": None, "format": "pdf", "pages": 4,
                     "text_chars": 6100, "scanned": False, "ocr": False, "roll_like_count": 188, "header": None,
                     "my_row": None, "context": None, "details": {}, "error": None, "is_sample": True},
        f"{YOP}:3": {"notice_id": f"{YOP}:3", "status": "unknown", "matched_by": None, "format": "pdf",
                     "pages": 2, "text_chars": 0, "scanned": True, "ocr": False, "roll_like_count": 0,
                     "header": None, "my_row": None, "context": None, "details": {},
                     "error": "scanned PDF and OCR is not available here", "is_sample": True},
    }
    emails = [{"id": "sample-mail-1", "received_at": t(-1, 21, 30).isoformat(),
               "sender": "Lumen Payments Hiring <hiring@lumen.example>", "subject": "Lumen Payments online test link",
               "snippet": "Your test link for the Lumen Payments assessment is below.",
               "company": "Lumen Payments", "links": ["https://assess.example.com/lumen/abc123"], "is_sample": True}]
    contacts = [{"id": f"{n['id']}:{c['phone']}", "notice_id": n["notice_id"], "company": n["company"],
                 "name": c["name"], "phone": c["phone"], "is_sample": True}
                for n in notice_rows for c in n["analysis"]["contacts"]]
    items = build_items(roles, notice_rows, checks, PROFILE, now, emails)
    for it in items:
        it["id"] = it["id"] if it["id"].startswith(("sample", "role:sample", "notice:sample")) else f"sample:{it['id']}"
        it["is_sample"] = True
    dls = effective_deadlines(roles, notice_rows, index)
    for r in roles:
        e = evaluate(r, PROFILE)
        r.update({"eligible": e["eligible"], "eligibility": e, "effective_deadline": dls[r["id"]]["at"],
                  "deadline_source": dls[r["id"]]["source"]})
    run = {"id": "sample-run", "started_at": (now - timedelta(minutes=3)).isoformat(),
           "finished_at": now.isoformat(), "trigger": "sample", "mode": "run", "status": "ok",
           "login_seconds": 41.2, "otp_seconds": 22.5, "otp_requests": 1, "gate_requests": 63,
           "counts": {"roles_seen": len(roles), "notices_new": len(notice_rows)}, "problems": [], "is_sample": True}
    return {"profile": PROFILE, "roles": roles, "notices": notice_rows, "pdf_checks": list(checks.values()),
            "items": items, "emails": emails, "contacts": contacts, "runs": [run]}


def _sfx(day: int) -> str:
    return "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def load(store) -> int:
    data = build()
    n = 0
    for table in ("roles", "notices", "pdf_checks", "emails", "contacts", "items", "runs"):
        key = "notice_id" if table == "pdf_checks" else "id"
        n += store.upsert(table, data[table], key=key)
    prof = (store.select("profile") or [{}])[0]
    real = any(prof.get(k) for k in ("department", "degree", "cgpa", "roll")) and not prof.get("is_sample")
    if not real:  # never overwrite a real profile with the demo one
        store.upsert("profile", [{"id": 1, **data["profile"], "is_sample": True,
                                  "updated_at": datetime.now(timezone.utc).isoformat()}])
        n += 1
    return n


def remove(store) -> int:
    n = 0
    for table in TABLES:
        key = "notice_id" if table == "pdf_checks" else "id"
        rows = store.select(table, {"is_sample": "is.true"}, columns=key)
        if rows:
            store.delete(table, {"is_sample": "is.true"})
            n += len(rows)
    prof = (store.select("profile") or [{}])[0]
    if prof.get("is_sample"):
        store.upsert("profile", [{"id": 1, **{k: None for k in PROFILE}, "notice_types": ["PLACEMENT"],
                                  "cv_names": [], "interested_companies": [], "not_interested_companies": [],
                                  "active_backlogs": False, "is_sample": False}])
        n += 1
    return n
