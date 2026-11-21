#!/usr/bin/env python3
"""
Ping evals: does Ping read real placement notices and PDFs the way a careful person would?

    python evals/run_evals.py

Prints the results and writes evals/REPORT.md (plain English, for reviewers).

What is tested
  - 31 real CDC notices from 7-21 Nov 2026 (other students' details removed). For each, a person's
    expected answer: which company (from the student's companies list), what kind of notice, the
    deadline, and the test/talk time. Ping's answer comes from the same code the hourly run uses.
  - 7 attachments rebuilt in the table layouts seen in the real run (fake roll numbers and names,
    because real shortlists contain hundreds of other students). For each: is the student on it,
    and which room.
  - The real run's numbers (PDFs read, duplicates merged), which have no right/wrong answer key.
"""

from __future__ import annotations

import io
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ping.config import IST  # noqa: E402
from ping.matching import CompanyIndex  # noqa: E402
from ping.notices import analyze  # noqa: E402
from ping.pdfs import check_attachment  # noqa: E402

KIND = {"apply_open": "apply", "deadline_extended": "deadline moved", "form": "form", "test": "test",
        "test_rooms": "test rooms", "shortlist": "shortlist", "result": "result", "ppt": "talk", "ppo": "offer",
        "schedule": "schedule", "info": "info"}
ME = "22XY10042"
FIRST_PASS = "126 of 138 checks (91%)"
CAUGHT = [
    "Day schedules written without a profile ('1. [PPT] OLA (6:00 PM - 7:00 PM)') were skipped, so those companies and times were lost.",
    "A schedule entry tagged [PPT] was reported as a test.",
    "Room lists with two students per line ('Roll No | Room No | | Roll No | Room No') gave the room from the wrong column, i.e. another student's room.",
    "'No further extensions will be given' made a form notice look like a deadline extension.",
    "'Room allocations will be communicated' was read as 'here are the rooms'.",
    "'List of students eligible for the assessment' wasn't recognised as a shortlist.",
    "A test date without a time ('scheduled for 14th November') was dropped.",
    "In plain-text lists, the room on your own line wasn't picked up; in role-per-column shortlists, the role you're listed under wasn't reported.",
]


def minute(v):
    return v[:16] if v else None


def same_time(expected, got):
    if expected is None:
        return got is None
    if got is None:
        return False
    return got[:len(expected)] == expected if len(expected) == 10 else minute(got) == expected


# --------------------------------------------------------------------------- notices
def ping_answer(case, index):
    n = {"subject": case["subject"], "company": case["company_column"], "notice_time": case["posted"]}
    a = analyze(n, case["text"], index, ME, "")
    deadlines = sorted(d["at"] for d in a["deadlines"])
    events = [e["at"] for e in a["events"]] + [e["at"][:10] for e in a.get("event_dates", [])]
    entries = []
    for t in a["targets"]:
        tag = (t.get("tag") or "").upper()
        kind = "talk" if tag.startswith("PPT") else "test" if tag.startswith("TEST") else KIND[a["kind"]]
        entries.append({"company": t.get("company"), "kind": kind, "when": t.get("start")})
    for u in a["unsure"]:
        entries.append({"company": "?", "kind": KIND[a["kind"]], "when": None})
    return {"companies": sorted({e["company"] for e in entries if e["company"] and e["company"] != "?"}),
            "asks": bool(a["unsure"]), "kind": KIND[a["kind"]], "deadline": deadlines[0] if deadlines else None,
            "when": events[0] if events else None, "venue": a.get("venue"), "form": bool(a.get("forms")),
            "entries": entries}


def score_notice(case, got):
    exp = case["expected"]
    checks = []
    if "entries" in exp:
        for e in exp["entries"]:
            if e["company"] == "?":
                ok = got["asks"]
                checks.append(("company", ok, "asks which company" if ok else "guessed instead of asking"))
                continue
            match = [g for g in got["entries"] if g["company"] == e["company"] and same_time(e["when"], g["when"])]
            checks.append((f"{e['company']}: found", bool(match), "" if match else "not found with the right time"))
            if match:
                checks.append((f"{e['company']}: kind", match[0]["kind"] == e["kind"],
                               f"said {match[0]['kind']}, expected {e['kind']}"))
        extra = [g["company"] for g in got["entries"] if g["company"] and g["company"] != "?" and
                 g["company"] not in {e["company"] for e in exp["entries"]}]
        if not exp.get("allow_extra"):
            checks.append(("no extra companies", not extra, f"also matched {extra}" if extra else ""))
        return checks
    checks.append(("company", got["companies"] == sorted(exp["companies"]),
                   f"said {got['companies'] or 'none'}, expected {exp['companies'] or 'none'}"))
    checks.append(("kind", got["kind"] == exp["kind"], f"said {got['kind']}, expected {exp['kind']}"))
    checks.append(("deadline", same_time(exp.get("deadline"), got["deadline"]),
                   f"said {minute(got['deadline']) or 'none'}, expected {exp.get('deadline') or 'none'}"))
    if exp.get("when"):
        checks.append(("time", same_time(exp["when"], got["when"]),
                       f"said {minute(got['when']) or 'none'}, expected {exp['when']}"))
    if exp.get("venue"):
        checks.append(("venue", (got["venue"] or "").lower() == exp["venue"].lower(),
                       f"said {got['venue'] or 'none'}, expected {exp['venue']}"))
    if exp.get("form"):
        checks.append(("form link", got["form"], "missed the form link"))
    return checks


# --------------------------------------------------------------------------- PDFs
def pdf(rows, heading="Assessment room allocation"):
    from fpdf import FPDF
    doc = FPDF()
    doc.add_page()
    doc.set_font("Helvetica", size=9)
    doc.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
    with doc.table() as t:
        for r in rows:
            row = t.row()
            for c in r:
                row.cell(c)
    return bytes(doc.output())


def text_pdf(lines):
    from fpdf import FPDF
    doc = FPDF()
    doc.add_page()
    doc.set_font("Helvetica", size=10)
    for line in lines:
        doc.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(doc.output())


def xlsx(rows):
    import openpyxl
    wb = openpyxl.Workbook()
    for r in rows:
        wb.active.append(r)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def roll(i, dept="CS"):
    return f"23{dept}{10000 + i}"


def pdf_cases():
    pairs = [[roll(i), f"NC {140 + i % 3}", "", roll(i + 50, "EE"), f"NC {240 + i % 3}"] for i in range(1, 30)]
    pairs[11][3], pairs[11][4] = ME, "NC 242"  # the student is in the right-hand pair; the left one is in NC 140
    roles = [[roll(i), "", roll(i + 40, "ME"), "", roll(i + 80, "EC")] for i in range(1, 25)]
    roles[7][2] = ME
    std = [["S.No", "Roll No", "Name", "Room", "Slot"]] + [[str(i), roll(i), f"Student {i}", "V1", "Slot 1"] for i in range(1, 40)]
    std.insert(20, ["20", ME, "DEMO STUDENT", "V2", "Slot 2"])
    absent = [["S.No", "Roll No", "Name"]] + [[str(i), roll(i), f"Student {i}"] for i in range(1, 60)]
    names = [["S.No", "Name", "Room"]] + [[str(i), f"Student {i}", "NR 121"] for i in range(1, 30)] + [["30", "Demo Student", "NR 122"]]
    lines = ["Shortlist for the Interview round", "Room allocation:"] + \
            [f"{roll(i)} STUDENT {i} NC {300 + i % 4}" for i in range(1, 40)] + [f"{ME} DEMO STUDENT NC 331"]
    return [
        dict(name="Room list in two column pairs (layout of the real Eternal room list)",
             data=pdf([["Roll No", "Room No", "", "Roll No", "Room No"]] + pairs), expect="yes", room="NC 242"),
        dict(name="Shortlist with one column per role (layout of the real Eternal shortlist)",
             data=pdf([["PA", "", "SDE-1", "", "MLE"]] + roles, "Test shortlist"), expect="yes", listed_under="SDE-1"),
        dict(name="Standard table: S.No, Roll No, Name, Room, Slot", data=pdf(std), expect="yes", room="V2"),
        dict(name="Shortlist the student is not on", data=pdf(absent), expect="no"),
        dict(name="Names only, no roll numbers (matched on the profile name)", data=pdf(names), expect="yes",
             room="NR 122", by_name=True),
        dict(name="Plain text lines, no table borders", data=text_pdf(lines), expect="yes", room="NC 331"),
        dict(name="Excel room list", data=xlsx([["Roll No", "Name", "Venue"]] + [[roll(i), f"S {i}", "NC 231"] for i in range(1, 20)]
                                               + [[ME, "DEMO STUDENT", "NC 232"]]), expect="yes", room="NC 232"),
    ]


def score_pdf(case):
    res = check_attachment(case["data"], ME, "Demo Student" if case.get("by_name") else "")
    d = res.get("details") or {}
    room = d.get("room") or d.get("room_or_venue_from_heading")
    checks = [("on the list?", res["status"] == case["expect"], f"said {res['status']}, expected {case['expect']}")]
    if case.get("room"):
        checks.append(("room", (room or "").replace(" ", "") == case["room"].replace(" ", ""),
                       f"said {room or 'none'}, expected {case['room']}"))
    if case.get("listed_under"):
        checks.append(("listed under", d.get("column") == case["listed_under"],
                       f"said {d.get('column') or 'none'}, expected {case['listed_under']}"))
    return checks


# --------------------------------------------------------------------------- report
def main():
    notices = json.loads((HERE / "notices.json").read_text())["notices"]
    roles = json.loads((HERE / "companies.json").read_text())["roles"]
    real = json.loads((HERE / "real_run.json").read_text())
    index = CompanyIndex([{"id": f"r{i}", **r} for i, r in enumerate(roles)])

    by_check: dict[str, list[bool]] = {}
    held: dict[str, list[bool]] = {}
    misses = []
    notice_rows = []
    for case in notices:
        got = ping_answer(case, index)
        checks = score_notice(case, got)
        ok_all = all(ok for _, ok, _ in checks)
        bucket = held if case.get("held_out") else by_check
        for name, ok, why in checks:
            key = name.split(": ")[-1] if ": " in name else name
            bucket.setdefault(f"notices: {key}", []).append(ok)
            if not ok:
                tag = "held-out " if case.get("held_out") else ""
                misses.append(f"{tag}Notice {case['notice_id']} ({case['subject']}, {case['company_column']}): {name}: {why}")
        notice_rows.append((case, ok_all))
    pdf_rows = []
    for case in pdf_cases():
        checks = score_pdf(case)
        for name, ok, why in checks:
            by_check.setdefault(f"PDFs: {name}", []).append(ok)
            if not ok:
                misses.append(f"PDF '{case['name']}': {name}: {why}")
        pdf_rows.append((case["name"], all(ok for _, ok, _ in checks)))

    total = [ok for v in by_check.values() for ok in v]
    held_total = [ok for v in held.values() for ok in v]
    n_tuned = sum(1 for c in notices if not c.get("held_out"))
    pct = lambda xs: f"{100 * sum(xs) / len(xs):.0f}%" if xs else "n/a"  # noqa: E731
    lines = ["# Ping evals", "",
             f"_Run on {datetime.now(IST).strftime('%d %b %Y, %H:%M IST')}. Re-run with `python evals/run_evals.py`._", "",
             "## In short", "",
             f"- **Held-out real notices (never used to tune Ping): {sum(held_total)} of {len(held_total)} checks right "
             f"({pct(held_total)})** on {len(notices) - n_tuned} notices. This is the fairest number.",
             f"- Development set: {sum(total)} of {len(total)} checks right ({pct(total)}) on {n_tuned} real notices and "
             f"{len(pdf_rows)} attachments in real layouts. Ping was fixed using these, so this number is optimistic. "
             f"Its first run, before the fixes, was {FIRST_PASS}.", "",
             "## Held-out notices, by question", "", "| question | right | out of | score |", "|---|---|---|---|"]
    for name, oks in held.items():
        lines.append(f"| {name} | {sum(oks)} | {len(oks)} | {pct(oks)} |")
    lines += ["", "## Development set, by question", "", "| question | right | out of | score |", "|---|---|---|---|"]
    for name, oks in by_check.items():
        lines.append(f"| {name} | {sum(oks)} | {len(oks)} | {pct(oks)} |")
    lines += ["", "## What Ping got wrong", ""]
    lines += [f"- {m}" for m in misses] or ["- Nothing."]
    lines += ["", "## What the first run of these evals caught (and was fixed in Ping)", ""] + [f"- {x}" for x in CAUGHT]
    lines += ["", "## Notices tested", "", "| notice | set | subject | company column | all checks right? |",
              "|---|---|---|---|---|"]
    lines += [f"| {c['notice_id']} | {'held-out' if c.get('held_out') else 'development'} | {c['subject']} | "
              f"{c['company_column']} | {'yes' if ok else 'no'} |" for c, ok in notice_rows]
    lines += ["", "## Attachments tested", "", "| layout | right? |", "|---|---|"]
    lines += [f"| {n} | {'yes' if ok else 'no'} |" for n, ok in pdf_rows]
    r, dd = real["first_full_run"], real["duplicate_merging_last_14_days"]
    lines += ["", "## Numbers from the real run (21 Nov 2026)", "",
              "These come from Ping's own logs. There is no answer key for them, so they show what Ping did, "
              "not whether each answer was right.", "",
              f"- Logged in to the ERP in {r['login_seconds']} s (the OTP email took {r['otp_wait_seconds']} s).",
              f"- Read {r['roles_seen']} roles and {r['notices_read_in_full']} new notices out of {r['notices_seen']}.",
              f"- Checked {r['pdfs_checked']} attachments: read {r['pdfs_read']}, the student was on "
              f"{r['pdfs_you_are_in']} and not on {r['pdfs_you_are_not_in']}; {r['pdfs_unreadable']} couldn't be read, "
              f"{r['pdfs_scanned']} were scanned images.",
              f"- Made {r['erp_requests']} requests to the ERP, every one through the read-only allow list.",
              f"- Feed after the run: {r['feed']['always_show']} always-show, {r['feed']['apply_by']} apply-by, "
              f"{r['feed']['hidden']} kept hidden, {r['feed']['questions_for_you']} questions for the student.", "",
              "**Duplicate merging, on the real notices of the last 14 days:** "
              f"{dd['notice_messages_without_merging']} messages without merging; {dd['repeats_merged']} repeats merged "
              f"and {dd['changes_sent_as_updates']} real changes sent as updates ({dd['of_which_deadline_moves']} deadline "
              f"moves, {dd['of_which_time_changes']} time changes). Unsure merges: {dd['unsure_merges']}.", "",
              f"**Rooms already saved by the real run:** of {real['saved_rooms_reread']['room_matches_saved']} room "
              f"matches saved before the two-students-per-line fix, {real['saved_rooms_reread']['were_another_students_room']} "
              "showed the neighbouring student's room. Every run now re-reads saved rows with the current rules, so "
              "these are corrected.", "",
              f"**AI fallback:** the rules couldn't read {real['ai_fallback']['notices_rules_could_not_read']} notice; "
              f"Gemini got it right ({real['ai_fallback']['example']}).", "",
              "## How this was made", "",
              "- Notices: real CDC notices; other students' names, roll numbers and phone numbers were removed first. "
              "The expected answers were written by reading each notice. Ping's answers come from the same code the "
              "hourly run uses (`ping/notices.py`).",
              "- Attachments: real shortlists list hundreds of other students, so they can't be shared. The cases "
              "rebuild the table layouts seen in the real run with made-up roll numbers and names.",
              "- Company answers use the student's real companies list (company and role names only)."]
    report = "\n".join(lines) + "\n"
    (HERE / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
