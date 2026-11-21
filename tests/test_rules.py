"""Rules for dates, notices, eligibility and attachments, on wording taken from real notices
(phone numbers replaced)."""

from datetime import datetime

import pytest

from fake_erp import ROLL, make_pdf, roster
from ping.config import IST
from ping.dates import find_moments, fmt_when
from ping.eligibility import backlog_allows, evaluate
from ping.matching import CompanyIndex
from ping.notices import analyze, classify
from ping.pdfs import check_attachment

REF = datetime(2026, 11, 21, 0, 7, tzinfo=IST)

ICICI = ("The CV Submission for ICICI Lombard for the role of Actuarial Analyst has been opened till 4:00 PM, "
         "21st November, 2026.\nAll candidates who are applying for the role, are required to kindly fill the "
         "Additional Details Form given below. Link: https://forms.gle/Di2j1Sw7VyCurUud7\nDeadline: 21st November "
         "2026, 4:00 PM\nInterested and eligible students are advised to apply on the portal and fill the form "
         "within the given deadline. No further extensions will be given.")
ETERNAL = ("PFA the test room allocation of shortlisted candidates for the Assessment of Eternal, scheduled from "
           "7:15 PM onwards on 19th November, 2026.\n\nVenue: Nalanda Classroom Complex\n\nStudents are required to "
           "carry their original Institute ID card.\n\nThe test link has been shared on their Institute Email ID.\n\n"
           "POCs: [name] (+91 90000 11111), [name] (+91 90000 22222)\n\nCDC, IIT Kharagpur")
MULTI = ("The CV Submissions for the following companies have been extended till 8:00 PM, 21st November, 2026.\n"
         "1. ATHER ENERGY (Profile: All)\n2. BLACKBUCK  (Profile: Associate Manager)\n"
         "3. LTM  (Profile: Graduate Engineer Trainee, Post-Graduate Engineer Trainee)\n")
SCHEDULE = ("All students eligible for placement are advised to take note of the placement schedule for Saturday, "
            "21st November 2026.\n1. [TEST] GROWW (Profile: Associate Product Manager) (3:00 PM  4:00 PM)\n"
            "2. [TEST] URBAN COMPANY (Profile : Senior Category Manager) (12:30 AM  1:30 AM, 22nd November)")


def role(company, designation, applied=False, **kw):
    return {"id": f"x:{company}:{designation}", "company": company, "designation": designation,
            "applied": applied, **kw}


@pytest.mark.parametrize("text,kind,expected", [
    ("has been opened till 4:00 PM, 21st November, 2026", "deadline", "2026-11-21 16:00"),
    ("Deadline: 21st November 2026, 4:00 PMInterested", "deadline", "2026-11-21 16:00"),
    ("scheduled from 7:15 PM onwards on 19th November, 2026.", "event", "2026-11-19 19:15"),
    ("Submission Deadline: 22nd November 2026, 8:00 PM IST.", "deadline", "2026-11-22 20:00"),
    ("by 5:00 PM today", "deadline", "2026-11-21 17:00"),
    ("Test Window: Until 11:59 AM, August 6, 2027", "deadline", "2027-08-06 11:59"),
    ("must be completed by 9:00 AM IST on 23 November 2026", "deadline", "2026-11-23 09:00"),
    ("Date: 24-11-2026 Reporting Time: 5:45 PM", "event", "2026-11-24 17:45"),
])
def test_dates(text, kind, expected):
    ms = find_moments(text, REF)
    assert ms, text
    assert ms[0].kind == kind
    assert ms[0].at.strftime("%Y-%m-%d %H:%M") == expected


def test_relative_word_next_to_real_date_is_not_double_counted():
    ms = find_moments("register before 10:00 PM, 27th November (today) to appear", REF)
    assert len(ms) == 1 and ms[0].at.day == 27


def test_fmt_when():
    assert fmt_when(datetime(2026, 11, 22, 16, 0, tzinfo=IST), REF) == "Sun 22 Nov 16:00"
    assert fmt_when(datetime(2026, 12, 5, 9, 30, tzinfo=IST), REF) == "Sat 05 Dec 09:30"


@pytest.mark.parametrize("subject,text,kind", [
    ("Date extension", ICICI, "deadline_extended"),
    ("Urgent", ETERNAL, "test_rooms"),
    ("Shortlist", "PFA the test shortlist ... The room allocation for the test will be released shortly.", "shortlist"),
    ("CV Submission", MULTI, "apply_open"),
    ("Schedule", SCHEDULE, "test"),
    ("PPO", "Accenture has extended the offer to the following student(s)", "ppo"),
    ("Urgent", "The CV submission for X has been extended till 8 PM, 21st November 2026", "deadline_extended"),
])
def test_classify(subject, text, kind):
    assert classify(subject, text) == kind


def test_icici_notice_gives_two_todos():
    idx = CompanyIndex([role("ICICI LOMBARD", "Actuarial Analyst")])
    a = analyze({"subject": "Date extension", "company": "ICICI LOMBARD", "notice_time": REF.isoformat()},
                ICICI, idx)
    assert [t["action"] for t in a["todos"]] == ["apply", "fill_form"]
    assert all(t["due"].startswith("2026-11-21T16:00") for t in a["todos"])
    assert a["forms"] == ["https://forms.gle/Di2j1Sw7VyCurUud7"]
    assert a["targets"][0]["company"] == "ICICI LOMBARD"
    assert "Actuarial Analyst" in a["targets"][0]["profiles"]


def test_eternal_notice_venue_contacts_and_email_hint():
    idx = CompanyIndex([role("Eternal", "Product Analyst", applied=True)])
    a = analyze({"subject": "Urgent", "company": "ETERNAL", "notice_time": REF.isoformat()}, ETERNAL, idx)
    assert a["venue"] == "Nalanda Classroom Complex"
    assert [c["name"] for c in a["contacts"]] == ["[name]", "[name]"]
    assert a["email_hint"]
    assert a["events"][0]["at"].startswith("2026-11-19T19:15")


def test_multiple_companies_one_target_each():
    idx = CompanyIndex([role("Ather Energy", "Engineer"), role("BlackBuck", "Associate Manager"),
                        role("LTM", "Graduate Engineer Trainee")])
    a = analyze({"subject": "Date extension", "company": "Multiple Companies", "notice_time": REF.isoformat()},
                MULTI, idx)
    assert [t["company"] for t in a["targets"]] == ["Ather Energy", "BlackBuck", "LTM"]
    assert a["targets"][2]["profiles"] == ["Graduate Engineer Trainee", "Post-Graduate Engineer Trainee"]


def test_schedule_times_per_company_including_next_day():
    idx = CompanyIndex([role("Groww", "Associate Product Manager"), role("Urban Company", "Senior Category Manager")])
    a = analyze({"subject": "Schedule", "company": "CDC Placement Schedule for 21st November 2026",
                 "notice_time": REF.isoformat()}, SCHEDULE, idx)
    starts = [t["start"][:16] for t in a["targets"]]
    assert starts == ["2026-11-21T15:00", "2026-11-22T00:30"]


def test_ambiguous_company_is_not_guessed():
    idx = CompanyIndex([role("Accenture India Private Limited", "Analyst"),
                        role("Accenture Japan", "Digital Consultant")])
    a = analyze({"subject": "Urgent", "company": "Accenture", "notice_time": REF.isoformat()}, "Some text.", idx)
    assert not a["targets"] and a["unsure"][0]["name"] == "Accenture"


def test_notice_naming_my_roll():
    idx = CompanyIndex([])
    a = analyze({"subject": "PPO", "company": "Acme", "notice_time": REF.isoformat()},
                f"Acme has extended the offer to: Demo Student - {ROLL}. Accept by 19.11.2026.", idx, ROLL)
    assert a["mentions_me"]


# ---------------------------------------------------------------- eligibility

ALLOWED = [{"department": "COMPUTER SCIENCE AND ENGINEERING", "degree": "B.TECH",
            "programme": "COMPUTER SCIENCE AND ENGG.(B.TECH 4Y)"}]
ME = {"department": "Computer Science and Engineering", "degree": "B.Tech", "cgpa": 8.1, "active_backlogs": False}


def test_eligible_and_not():
    base = {"details_fetched": True, "allowed": ALLOWED}
    assert evaluate({**base, "cgpa_cutoff": 7.0}, ME)["eligible"] is True
    assert evaluate({**base, "cgpa_cutoff": 8.5}, ME)["eligible"] is False
    assert evaluate({**base, "cgpa_cutoff": None}, ME)["eligible"] is True
    assert evaluate({**base, "allowed": [{"department": "MECHANICAL ENGINEERING", "degree": "B.TECH",
                                         "programme": "MECHANICAL ENGINEERING(B.TECH 4Y)"}]}, ME)["eligible"] is False
    empty = evaluate({"details_fetched": True, "allowed": []}, ME)
    assert empty["eligible"] is True and "no department list on this role" in empty["flags"]
    erp = evaluate({**base, "erp_messages": ["Company requirement has CGPA cut off greater than yours."]}, ME)
    assert erp["eligible"] is False


def test_backlogs():
    assert backlog_allows("No active backlogs allowed") is False
    assert backlog_allows("Students with backlogs are allowed") is True
    r = {"details_fetched": True, "allowed": ALLOWED, "backlog_rule": "No active backlog"}
    assert evaluate(r, {**ME, "active_backlogs": True})["eligible"] is False
    assert evaluate(r, ME)["eligible"] is True


# ---------------------------------------------------------------- attachments

def test_pdf_finds_my_row_only():
    res = check_attachment(make_pdf(roster(include_me=True)), ROLL)
    assert res["status"] == "yes" and res["matched_by"] == "roll"
    assert res["my_row"] == ["17", ROLL, "DEMO STUDENT", "V2"]
    assert res["header"] == ["S.No", "Roll No", "Name", "Room"]
    assert res["details"]["room"] == "V2"
    assert "Student 5" not in str(res)


def test_pdf_not_on_it():
    res = check_attachment(make_pdf(roster(include_me=False)), ROLL)
    assert res["status"] == "no" and res["roll_like_count"] >= 30


def test_pdf_name_fallback():
    rows = [["S.No", "Name", "Room"], ["1", "Someone Else", "V1"], ["2", "Demo Student", "V3"]]
    res = check_attachment(make_pdf(rows), ROLL, name="Demo Student")
    assert res["status"] == "yes" and res["matched_by"] == "name" and res["details"]["room"] == "V3"


def test_unreadable_files_are_unknown():
    assert check_attachment(b"<!doctype html><html></html>", ROLL)["status"] == "unknown"
    assert check_attachment(b"%PDF-1.4 garbage", ROLL)["status"] == "unknown"


def test_excel_attachment():
    import io
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in [["Roll", "Name", "Venue"], ["22AB12345", "X", "NC231"], [ROLL, "DEMO", "NC232"]]:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    res = check_attachment(buf.getvalue(), ROLL)
    assert res["status"] == "yes" and res["format"] == "xlsx" and res["details"]["room"] == "NC232"


def test_sample_data_builds():
    from ping.sample import build
    data = build(REF)
    levels = {i["level"] for i in data["items"]}
    assert levels == {"always", "show", "hidden"}
    assert all(len(i["title"]) <= 160 for i in data["items"])
    assert any(i["needs_review"] for i in data["items"])


def test_exact_company_name_wins_before_loose_matching():
    idx = CompanyIndex([role("Accenture Solutions Private Limited", "AI and Data"),
                        role("Accenture India Private Limited", "Analyst"), role("Navi Limited", "SDE")])
    assert idx.match("Accenture Solutions Private Limited").company == "Accenture Solutions Private Limited"
    assert idx.match("ACCENTURE INDIA PRIVATE LIMITED").company == "Accenture India Private Limited"
    assert idx.match("NAVI").company == "Navi Limited"          # shortened name: loose match
    assert idx.match("Accenture").company is None                # really ambiguous: ask, don't guess


def test_saved_room_from_an_older_reading_is_corrected():
    """Real case: a room list with two students per line. An older reading took the left student's room;
    every run now re-reads the saved row (yours + heading only) with today's rules."""
    from ping.pdfs import refresh_details
    saved = {"status": "yes", "matched_by": "roll", "header": ["Roll No", "Room No", "", "Roll No", "Room No"],
             "my_row": ["21AB10001", "NR 324", "", "22XY10042", "NR 422"], "context": "Roll No Room No",
             "details": {"room": "NR 324", "room_or_venue_from_heading": "Roll No Room No"}}
    assert refresh_details(saved, "22xy10042")["details"] == {"room": "NR 422"}
    assert refresh_details({"status": "no", "details": {}}, "22XY10042") == {"status": "no", "details": {}}
