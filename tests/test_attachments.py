"""Audit of the notice-attachment reader (ping/pdfs.py): roll numbers in every form, names, your own row on
messy tables, negatives and size. Made-up files only (tests/attachment_fixtures.py)."""

import io
import time

import pytest

from attachment_fixtures import ME, others, roster_rows, table_pdf, text_pdf
from ping.pdfs import check_attachment


# ---------------------------------------------------------------- 1. file types

def test_types_read_and_types_reported_unreadable():
    import openpyxl
    wb = openpyxl.Workbook()
    for r in [["Roll", "Venue"], [others(1)[0], "NC 231"], [ME, "NC 232"]]:
        wb.active.append(r)
    x = io.BytesIO()
    wb.save(x)
    assert check_attachment(x.getvalue(), ME)["status"] == "yes"
    assert check_attachment(table_pdf(roster_rows(20, 5)), ME)["format"] == "pdf"
    # not read: CSV, Word, an image, a web page (e.g. a Drive link's page) -> "unknown" with the reason
    for data, ctype, fmt in [(f"Roll,Room\n{ME},NC 232\n".encode(), "text/csv", "text/csv"),
                             (b"PK\x03\x04" + b"\0" * 30, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", None),
                             (b"\x89PNG\r\n\x1a\n" + b"\0" * 40, "image/png", "image/png"),
                             (b"<!doctype html><title>Google Drive</title>", "text/html", "html")]:
        res = check_attachment(data, ME, content_type=ctype)
        assert res["status"] == "unknown" and res["error"], (ctype, res)
        if fmt:
            assert res["format"] == fmt


# ---------------------------------------------------------------- 2. matching

@pytest.mark.parametrize("cell", [ME, ME.lower(), "22 XY10042", "22-XY-10042", "22XY 10042", "22xy-10042"])
def test_roll_in_every_form_the_lists_use(cell):
    res = check_attachment(table_pdf(roster_rows(30, 12, me_cell=cell)), "22xy10042")
    assert res["status"] == "yes" and res["matched_by"] == "roll", cell
    assert res["details"]["room"] == "NR 422"


@pytest.mark.parametrize("cell", [f"{ME}@kgpian.iitkgp.ac.in", f"{ME}_DemoStudent", f"({ME})", f"Roll:{ME}"])
def test_roll_inside_a_longer_string_still_counts(cell):
    assert check_attachment(table_pdf(roster_rows(30, 9, me_cell=cell)), ME)["status"] == "yes", cell


@pytest.mark.parametrize("cell", [ME + "5", "1" + ME, ME[:-1] + "3"])
def test_a_different_longer_or_neighbouring_roll_is_not_you(cell):
    res = check_attachment(table_pdf(roster_rows(30, 9, me_cell=cell)), ME)
    assert res["status"] == "no", cell


def _names_pdf(name_cell):
    rows = [["S.No", "Name", "Room"], ["1", "Rahul Verma", "V1"], ["2", name_cell, "V3"], ["3", "Demo Studentson", "V2"]]
    return table_pdf(rows, title="Shortlist (names only)")


@pytest.mark.parametrize("cell", ["Demo Student", "DEMO STUDENT", "Student Demo", "Demo K. Student"])
def test_name_only_list_exact(cell):
    res = check_attachment(_names_pdf(cell), ME, name="Demo Student")
    assert res["status"] == "yes" and res["matched_by"] == "name" and res["details"]["room"] == "V3", cell


def test_name_only_list_one_letter_typo():
    res = check_attachment(_names_pdf("Demo Studnet"), ME, name="Demo Student")
    assert res["status"] == "yes" and res["matched_by"] == "name (close spelling)" and res["details"]["room"] == "V3"


def test_name_only_list_without_you():
    rows = [["S.No", "Name", "Room"], ["1", "Rahul Verma", "V1"], ["2", "Demo Studentson", "V2"], ["3", "Dema Stuart", "V3"]]
    assert check_attachment(table_pdf(rows), ME, name="Demo Student")["status"] == "no"


# ---------------------------------------------------------------- 3. your own row on messy tables

def test_two_students_per_line_takes_your_pair():
    a, b = others(2)
    rows = [["Roll No", "Room No", "", "Roll No", "Room No"], [a, "NR 324", "", ME, "NR 422"], [b, "NR 101", "", others(3)[2], "NR 102"]]
    res = check_attachment(table_pdf(rows), ME)
    assert res["details"]["room"] == "NR 422" and res["my_row"][3] == ME


def test_merged_room_cell_belongs_to_every_row_it_spans():
    rows = roster_rows(12, 6)
    for r in rows[1:]:
        r[3] = ""
    rows[1][3], rows[7][3] = "NC 231", "NC 342"               # rows 1-6 share NC 231, rows 7-13 share NC 342
    pdf = table_pdf(rows, spans=[((3, 1), (3, 6)), ((3, 7), (3, len(rows) - 1))])
    res = check_attachment(pdf, ME)
    assert res["status"] == "yes" and res["details"]["room"] == "NC 231"


def test_page_break_without_a_repeated_header():
    rows = roster_rows(120, 110)                             # you're on page 3; the header is only on page 1
    res = check_attachment(table_pdf(rows), ME)
    assert res["status"] == "yes"
    assert res["header"] == ["S.No", "Roll No", "Name", "Room", "Reporting Time"], res["header"]
    assert res["details"]["room"] == "NR 422" and res["details"]["time"] == "01:30 PM"
    assert res["my_row"][1] == ME


def test_section_rows_inside_the_table_are_slots_not_headers():
    rows = [["S.No", "Roll No", "Name", "Room"], ["Slot 1: 10:00 AM - 11:00 AM", "", "", ""]]
    rows += [[str(i), r, f"Student {i}", "V1"] for i, r in enumerate(others(8), 1)]
    rows += [["Slot 2: 2:00 PM - 3:00 PM", "", "", ""], ["9", ME, "DEMO STUDENT", "V3"], ["10", others(9)[8], "Student 10", "V3"]]
    res = check_attachment(table_pdf(rows, sections=[1, 10]), ME)
    assert res["header"] == ["S.No", "Roll No", "Name", "Room"]
    assert res["details"]["room"] == "V3"
    assert "Slot 2" in (res["details"].get("slot_from_heading") or "") or "2:00 PM" in (res["details"].get("time_from_heading") or "")
    assert "Slot 1" not in str(res["details"])


def test_only_your_row_and_the_heading_are_kept():
    rows = roster_rows(120, 110)
    res = check_attachment(table_pdf(rows), ME)
    kept = str({k: res[k] for k in ("header", "my_row", "context", "details")})
    assert not any(r in kept for r in others(120))


# ---------------------------------------------------------------- 4. negatives and size

def test_listed_for_another_company_on_the_same_day():
    lines = ["CDC Test Schedule - 21 November 2026", "", "Alpha Analytics - Online Test, 10:00 AM, Room NC 231"]
    lines += [f"{i} {r}" for i, r in enumerate(others(6), 1)]
    lines += ["", "Beta Bank - Written Test, 2:00 PM, Room NR 422"]
    lines += [f"{i} {r}" for i, r in enumerate(others(12)[6:], 7)] + [f"13 {ME}"]
    res = check_attachment(text_pdf(lines), ME)
    assert res["status"] == "yes"
    assert "Beta Bank" in (res.get("section") or "") and "Alpha" not in (res.get("section") or "")


def test_five_hundred_rows_in_seconds():
    rows = roster_rows(600, 553)
    pdf = table_pdf(rows)
    t = time.monotonic()
    res = check_attachment(pdf, ME)
    secs = time.monotonic() - t
    assert res["status"] == "yes" and res["details"]["room"] == "NR 422" and res["roll_like_count"] >= 600
    assert secs < 20, f"{secs:.1f} s"
    print(f"600-row PDF ({res['pages']} pages): {secs:.1f} s")


# ---------------------------------------------------------------- 5. what the feed says

def _feed(check, text, company="Multiple Companies", targets=("Alpha Analytics Private Limited", "Beta Bank Limited")):
    from datetime import datetime
    from ping.config import IST
    from ping.items import build_items
    from ping.matching import CompanyIndex
    from ping.notices import analyze
    profile = {"roll": ME, "name": "Demo Student", "cgpa": 8.0, "department": "COMPUTER SCIENCE AND ENGINEERING", "degree": "B.TECH"}
    roles = [{"id": f"r{i}", "company": c, "designation": "Analyst", "applied": True, "apply_end": "2026-11-10T20:00:00+05:30",
              "first_seen": "2026-11-01T09:00:00+05:30", "erp_messages": [],
              "allowed": [{"degree": "B.TECH", "department": "COMPUTER SCIENCE AND ENGINEERING"}]} for i, c in enumerate(targets)]
    n = {"id": "2026-2027:900", "notice_id": 900, "year": "2026-2027", "subject": "Test schedule", "company": company,
         "notice_time": "2026-11-20T18:00:00+05:30", "has_attachment": True, "text": text}
    n["analysis"] = analyze(n, text, CompanyIndex(roles), ME, "Demo Student")
    items = build_items(roles, [n], {n["id"]: check}, profile, datetime(2026, 11, 21, 8, 0, tzinfo=IST))
    return {it["company"]: it for it in items if it.get("notice_id") == 900}


def test_feed_says_on_it_only_for_the_company_whose_section_lists_you():
    lines = ["CDC Test Schedule - 21 November 2026", "", "Alpha Analytics - Online Test, 10:00 AM, Room NC 231"]
    lines += [f"{i} {r}" for i, r in enumerate(others(6), 1)] + ["", "Beta Bank - Written Test, 2:00 PM, Room NR 422"]
    lines += [f"{i} {r}" for i, r in enumerate(others(12)[6:], 7)] + [f"13 {ME}"]
    check = check_attachment(text_pdf(lines), ME)
    feed = _feed(check, "Alpha Analytics: online test on 21 November 2026 at 10:00 AM. Beta Bank: written test on "
                        "21 November 2026 at 2:00 PM. Room allocation attached.")
    alpha, beta = feed["Alpha Analytics Private Limited"], feed["Beta Bank Limited"]
    assert beta["pdf_status"] == "yes" and beta["title"].startswith("You're on the Beta Bank") and "NR 422" in beta["title"]
    assert alpha["pdf_status"] == "no" and "You're not on it (the file lists you under Beta Bank Limited)" in alpha["title"]
    assert "NR 422" not in alpha["title"]


def test_the_section_survives_saving_and_the_hourly_re_read():
    """The run saves only these fields (ping/run.py) and rebuilds the feed from them every hour."""
    from ping.pdfs import refresh_details
    lines = ["Alpha Analytics - Online Test, 10:00 AM, Room NC 231"] + [f"{i} {r}" for i, r in enumerate(others(4), 1)]
    lines += ["Beta Bank - Written Test, 2:00 PM, Room NR 422", f"5 {ME}"]
    res = check_attachment(text_pdf(lines), ME)
    saved = {f: res.get(f) for f in ("status", "matched_by", "format", "pages", "text_chars", "scanned", "ocr",
                                     "roll_like_count", "header", "my_row", "context", "details", "error")}
    again = refresh_details(saved, ME)
    assert again["details"]["section"].startswith("Beta Bank")
    from ping.items import listed_under
    assert listed_under(again, ["Alpha Analytics Private Limited", "Beta Bank Limited"]) == {1}


def test_feed_names_a_reporting_time_as_reporting():
    check = check_attachment(table_pdf(roster_rows(30, 12)), ME)
    feed = _feed(check, "Room allocation for the Alpha Analytics online test on 21 November 2026 at 2:00 PM is attached.",
                 company="ALPHA ANALYTICS", targets=("Alpha Analytics Private Limited",))
    t = feed["Alpha Analytics Private Limited"]["title"]
    assert t == ("You're on the Alpha Analytics Private Limited test room list (Analyst). "
                 "Test Sat 21 Nov 14:00, reporting 01:30 PM, room NR 422."), t


@pytest.mark.skipif(not __import__("shutil").which("tesseract"), reason="tesseract (OCR) not installed here")
def test_scanned_pdf_is_read_with_ocr():
    from attachment_fixtures import scanned_pdf
    t = time.monotonic()
    res = check_attachment(scanned_pdf(table_pdf(roster_rows(25, 11))), ME)
    assert res["scanned"] and res["ocr"], res
    assert res["status"] == "yes" and res["matched_by"] == "roll" and res["details"]["room"] == "NR 422", res
    print(f"scanned 1-page list read with OCR in {time.monotonic() - t:.1f} s; kept: {res['my_row']}")
    res = check_attachment(scanned_pdf(table_pdf(roster_rows(25, None))), ME)
    assert res["scanned"] and res["ocr"] and res["status"] == "no"
