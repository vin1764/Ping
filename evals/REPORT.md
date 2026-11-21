# Ping evals

Three eval suites and one audit, each repeatable, each with expected answers written by reading the data (never by running
the model being tested).

| suite | what it measures | current score | report | re-run |
|---|---|---|---|---|
| **Parser evals** | How Ping reads the ERP's notices and PDFs with rules: company, kind of notice, deadline, test time, venue, form link, "are you in this PDF", your room. 31 development + 15 held-out real CDC notices (other students' details removed) and 7 PDF/Excel layouts seen in the real run. | **Held-out: 56 of 58 checks (97%)**, the fair number. Development: 143 of 143 (100%), optimistic because Ping was fixed using these. | [PARSER_REPORT.md](PARSER_REPORT.md) | `python evals/run_evals.py` |
| **Ask Ping evals** | The chat's answers from the deployed `ask-ping` function, from one-click demo sessions (anonymised demo data, the demo persona's targets and made-up CVs), with the snapshot time fixed: company facts, deadlines, notices and tests, refusing to invent things, refusing actions only when asked to act, times today, role lists in one format, the CV to apply with, and typos / two questions in one. 42 single questions and 21 conversations: 13 follow-up conversations ("nothing else?", "and slice?", "ok") and 8 preference-by-chat conversations (set, append, exclude, reminder hours, list others, reset, show, and a question that must NOT change anything). Deterministic checks. | **Single questions: 37 of 42 (88%). Conversations: 21 of 21 (39 of 39 turns).** Before conversation memory: 34 of 36 single, 4 of 9 conversations. | [ask_ping/REPORT.md](ask_ping/REPORT.md) | Actions > Admin > `ask-ping-evals` |
| **Attachment audit** | The notice-attachment reader end to end on made-up files in messy real layouts (`tests/test_attachments.py`, fixtures in `tests/attachment_fixtures.py`): file types, your roll in every form and inside longer strings, a different longer roll that is not you, names exact and with a typo, your own row on merged cells / two students per line / a table broken across pages / section rows, a file listing several companies, 600 rows, a scanned list read with OCR, and what the feed says. | **31 of 31 tests pass** (10 of the first 27 failed before the fixes of 22 Nov). 600-row PDF read in about 1 s; a scanned page with OCR in about 2 s. | [below](#attachments-audit-22-nov) | `python -m pytest tests/test_attachments.py` |
| **Job description coverage** | Whether each role has a JD Ping can read, on the real companies list (Admin > `jd-report`), and whether Ask Ping's JD answers are right (`ask_ping/cases.json` J1-J5, on the demo snapshot, which carries the real roles' JDs). | **199 of 210 roles have a usable JD (was 177 from the ERP's JD field alone); "(JD missing)" 31 -> 11. J1-J5: 5 of 5.** | [below](#job-descriptions-22-nov) | Admin > `jd-report`; `run_ask_ping_evals.py --only J` |
| **Role relevance evals** | Whether "For you" (and the CV to apply with) follows the student's stated targets: two made-up personas with opposite targets (`relevance/personas.json`), 201 + 48 demo roles labelled for each persona's text, each persona's roles marked in one classifier call. | **demo persona: precision 93% (76 of 82), recall 97% (76 of 78), best CV right 96% (73 of 76). core-software persona: precision 100% (28 of 28), recall 100% (28 of 28).** | [relevance/REPORT.md](relevance/REPORT.md) | Actions > Admin > `relevance-evals` |

Also in this folder: `real_run.json` (numbers from the real runs: login time, notices, PDFs, merged repeats),
`notices.json` and `companies.json` (the parser eval inputs), `ask_ping/cases.json` (the Ask Ping questions,
checks and where each expected answer comes from).

## Job descriptions (22 Nov)

Bug: "summarise JPMC's JD" answered "I don't have the JD". JPMC did have one (147 characters in the ERP's JD field,
plus "Required Skill Set" and "Additional Information" in the role's details), but Ask Ping never received it. The
fix is in the pipeline: Ping now looks for each role's JD wherever the ERP keeps it (`ping/jd.py`), stores it on the
role (`jd_text`, `jd_source`, `jd_url`, `jd_note`, `jd_summary`), and answers from that.

Real companies list, 210 roles (Admin > `jd-report`, 22 Nov 03:20 IST):

| where the JD was found | roles |
|---|---|
| the ERP's JD field (already usable before) | 177 |
| the role's JD file on the ERP (Arihant x7, Eternal x3, IQVIA x2, TATA AIG) or the company's file (Purplle) | 14 |
| the role's details on the ERP (JPMC, ExxonMobil, MathWorks Engineer, Searce x4; Searce and MathWorks also keep a link Ping couldn't open) | 7 |
| a public link (Pocket FM, a Google Drive PDF) | 1 |
| only a link Ping can't open (LTM: Drive file over the size limit / not public; MathWorks Technical Writer: the careers site refuses) | 2 |
| nowhere on the ERP ("-", ".", "NA", "PFA the JD" with no file, "As mentioned in Registration Email", "Will be shared at the time of opening applications") | 9 |
| **usable JD** | **199 of 210** (before: 177) |

"For you" marks are keyed on the JD text, so the 22 roles whose JD appeared were marked again on the same run:
"(JD missing)" went from 31 roles to 11 (the 9 with none and the 2 links). Each JD has a summary (role & team, what
you'd do, must-haves, location, eligibility, anything unusual): Gemini where it answered within the run's 90 seconds,
the JD's own labelled parts otherwise, redone by Gemini on later runs (78 by Gemini and 121 by rules after the first
runs; 20 more by Gemini each run).

Ask Ping JD cases (deployed function, demo session, no model call: answered from the stored summary):

| case | question | result |
|---|---|---|
| J1 | summarise JPMC's JD | PASS: what you'd do (3), must-haves, CG cut-off, "(From the ERP's role details.)", 87 words |
| J2 | what's the JD for LTM | PASS: "The JD is a link I can't open: https://drive.google.com/..." |
| J3 | what do they want for cars24 data science | PASS: "Cars24 (Data Science): no JD on the ERP." |
| J4 | what's the JD for searce associate data engineer | PASS: summary from the details, then "The full JD is a link I can't open: https://docs.google.com/..." |
| J5 | what do they want for arihant product manager | PASS: from the JNF file on the ERP; location Mumbai / Indore |

J5 failed on its first run: Arihant's stored rules summary listed a lead-in ("We are looking for candidates who
demonstrate") as a must-have after the rules had been fixed, because summaries are cached by JD text. Rules
summaries now carry a version and are redone when the rules change.

Role sheet: [JPMC](../docs/screenshots/jd-390x844-jpmc.png), [JPMC, full JD open](../docs/screenshots/jd-1280x800-jpmc-full-jd.png),
[Searce, private link kept](../docs/screenshots/jd-390x844-searce-private-link.png),
[LTM, link Ping can't open](../docs/screenshots/jd-390x844-ltm-unreadable.png).

## Attachments audit (22 Nov)

How a notice's attachment (shortlist, room list, schedule) is read for you: `ping/pdfs.py` reads it, keeps only your
row and the table heading, and `ping/items.py` turns the result into the feed message. All cases use made-up files
(no real student); real layouts are also in the parser evals above (7 of 7, unchanged after the fixes).

### 1. File types

| type | handled? | what the student sees |
|---|---|---|
| PDF with text (tables or plain lines) | yes (pdfplumber) | "You're on the X list ... room NR 422" / "X list is out. You're not on it." |
| Scanned PDF (images only) | yes: OCR with Tesseract, installed on the GitHub runner the first time a scanned file appears (~30 s); tested here: 1 page in ~2 s, roll and room found | the same messages; if OCR can't run: as for unreadable files below |
| Excel (.xlsx) | yes (openpyxl) | the same messages |
| CSV, Word (.docx), an image file (PNG/JPEG), a web page (e.g. a Google Drive link page), anything else | not read: status "unknown" with the reason (e.g. "not a PDF or Excel file (text/csv)") in the run's problems | "X list is out but the file couldn't be read. Check it yourself." with the ERP link to the file (marked "unread"); Ask Ping is told "list not readable" |
| Google Drive / form links inside a notice's text | not followed (they need your own Google login, and Ping only reads the ERP) | the link is shown on the message ("Open form", "Link from your mail") |

None of the 64 attachments in the real run of 21 Nov was CSV, Word, an image or scanned: 64 of 64 were read.

### 2. Matching

| case | test | result |
|---|---|---|
| roll as `22XY10042`, `22xy10042`, `22 XY10042`, `22-XY-10042`, `22XY 10042`, `22xy-10042` (profile roll in any case) | `test_roll_in_every_form_the_lists_use` | yes, with the right room. **Fixed:** forms with dashes weren't found |
| roll inside a longer string: `22XY10042@kgpian.iitkgp.ac.in`, `22XY10042_DemoStudent`, `(22XY10042)`, `Roll:22XY10042` | `test_roll_inside_a_longer_string_still_counts` | yes |
| a different, longer roll: `22XY100425`, `122XY10042`, and a neighbouring roll `22XY10043` | `test_a_different_longer_or_neighbouring_roll_is_not_you` | no. **Fixed:** the first two used to count as you (a substring match) |
| names only: `Demo Student`, `DEMO STUDENT`, `Student Demo`, `Demo K. Student` | `test_name_only_list_exact` | yes, matched by name, right room |
| names only with one typo: `Demo Studnet` | `test_name_only_list_one_letter_typo` | yes, reported as "name (close spelling)". **Added:** one typo per name part of 5+ letters; shorter parts must be exact |
| names only, not you: `Demo Studentson`, `Dema Stuart` | `test_name_only_list_without_you` | no |
| earlier tests: standard roster, not on it, name fallback, Excel, unreadable files, a saved two-column row re-read | `tests/test_rules.py` | pass |

### 3. Your own row, on messy tables

| layout | test | result |
|---|---|---|
| two students per line (`Roll / Room / / Roll / Room`) | `test_two_students_per_line_takes_your_pair` | your pair's room (NR 422), not the left student's |
| room in a merged cell spanning 6 rows | `test_merged_room_cell_belongs_to_every_row_it_spans` | the merged room. **Fixed:** your row had no room. Only cells the PDF really merged are filled; an empty cell stays empty |
| a table broken across pages, header only on page 1, you on page 3 | `test_page_break_without_a_repeated_header` | the page-1 header, your room and reporting time. **Fixed:** another student's row was used as the "header" and saved |
| section rows inside the table ("Slot 2: 2:00 PM - 3:00 PM") | `test_section_rows_inside_the_table_are_slots_not_headers` | your slot from the section row, the real header kept. **Fixed:** the section row was taken for the header |
| only your row and the heading are kept | `test_only_your_row_and_the_heading_are_kept` | no other roll number in what's kept. **Fixed** with the page-break case above |
| a first row of column titles without the usual words ("PA / SDE-1 / MLE") | parser evals | still read as the header (the role you're listed under) |

### 4. Negatives and size

| case | test | result |
|---|---|---|
| a day's schedule listing you under Beta Bank, not Alpha Analytics | `test_listed_for_another_company_on_the_same_day`, `test_feed_says_on_it_only_for_the_company_whose_section_lists_you` | Beta Bank: "You're on the Beta Bank ... room NR 422"; Alpha: "You're not on it (the file lists you under Beta Bank Limited)". **Fixed:** both said "you're on it", Alpha with Beta's room |
| that section kept through saving and the hourly re-read | `test_the_section_survives_saving_and_the_hourly_re_read` | kept (inside the stored details) |
| 600 rows over 15 pages, you near the end | `test_five_hundred_rows_in_seconds` | found, right room, about 1 s |
| a scanned list (no text layer) | `test_scanned_pdf_is_read_with_ocr` | found with OCR, room NR 422; a scanned list without you: "no" (skipped where Tesseract isn't installed) |

Not changed, worth knowing: the test time in a message comes from the notice's text; when a day's schedule file gives
a different time in your section, that time is shown next to it ("Test Sat 21 Nov 10:00, 2:00 PM") rather than
replacing it.

### 5. What the student sees (generated by the real code, made-up file)

| state | feed message | what Ask Ping's model is given | Ask Ping without the model (rules) |
|---|---|---|---|
| on the list, with a room | You're on the Alpha Analytics Private Limited test room list (Data Analyst). Test Sat 21 Nov 14:00, reporting 01:30 PM, room NR 422. | the message + `[you ARE on this list] [your row in the PDF: S.No: 12, Roll No: 22XY10042, Name: DEMO STUDENT, Room: NR 422, Reporting Time: 01:30 PM]` | the message, then the last Alpha notice and "You applied to: Data Analyst." |
| on the list, no room in the file | You're on the Alpha Analytics Private Limited test room list (Data Analyst). Test Sat 21 Nov 14:00. | the message + `[you ARE on this list] [your row in the PDF: S.No: 8, Roll No: 22XY10042, Name: DEMO STUDENT]` | the same pattern |
| not on the list | Alpha Analytics Private Limited test room list is out (Data Analyst). You're not on it. (Kept in the feed because you applied; hidden otherwise.) | the message + `[you are NOT on this list]` | the same pattern |

**Fixed (wording):** a "Reporting Time" column is now shown as "reporting 01:30 PM"; it read like a second test time.

## Ask Ping: what changed between the two runs

The first run (15 of 36) showed that the function wasn't giving Gemini the data some questions need (CG
cut-off, departments, your shortlist / room results, the latest notices) and that the prompt never said Ping is
read-only. Both were fixed in `supabase/functions/ask-ping/index.ts`. Separately, two shared phrase lists in the
checks missed "does not contain" / "does not show any" although those answers correctly said there was nothing;
that change is recorded in `ask_ping/cases.json` (`check_changes`). No other check was changed.

The 4 failures left are the model's: a "Yes." that contradicts "Bonds: No" (C7), a missing room number (N2),
and two answers over the word limit or quoting other companies' pay when asked about one that isn't in the data
(X3, X5). X5 is arguable: nothing about the missing company was invented. See [ask_ping/REPORT.md](ask_ping/REPORT.md).

## Ask Ping: conversation memory (21 Nov)

Ask Ping now reads the last 10 messages of the thread (about 2,000 tokens) in the function. Three runs, checks
unchanged:

| run | single questions | conversations |
|---|---|---|
| before memory | 34 of 36 | 4 of 9 (13 of 18 turns) |
| with memory, the read-only refusal only for requests to act, times today | 35 of 39 | 8 of 13 (19 of 26 turns) |
| after one prompt fix (counted "today and this week" summary, name the company, "I don't have" first) and working fallback models | **35 of 39** | **13 of 13 (26 of 26 turns)** |

The 4 single-question failures left: "am I eligible for Harness" doesn't quote the 7.5 cut-off (C2); "anything due
today" gives the count (48 roles at 23 companies close at 20:00) but not the company names the check asks for (D2);
"what's due on 25 / 30 November" answer "I don't have any deadlines for 25 November" where the check expects
"nothing / no deadline" (D8, X2): a side effect of the fix's "start with I don't have" rule. Not changed after the
one allowed fix round.

## Ask Ping: preferences, list format and CVs (21 Nov, evening)

| run | single questions | conversations |
|---|---|---|
| with preferences by chat, ready-made role lists, CVs | 34 of 42 | 20 of 21 (38 of 39 turns) |
| after one fix (lists only for deadline/role questions, date in the list heading, "Nothing is due on <day>") | **38 of 42** | **20 of 21 (38 of 39 turns)** |

Still failing: C2 (doesn't quote the 7.5 cut-off), D2 (gives counts, not the company names), D3 (the week's list
without the time), L1 (a "relevant to me" list without Others: treated as narrowing, see docs/DECISIONS.md), and
M8 turn 2. Checks unchanged.

## Ask Ping: closing round (21 Nov, 23:11 IST)

The 4 failures left after the evening runs were fixed, checks unchanged: C2 (eligibility now quotes the CG cut-off and
your CGPA), D2 (what's due names the companies), D3 and M8 turn 2 (the week summary carries times; "this week"
includes today). All four pass, and conversations are **21 of 21 (39 of 39 turns)**. Single questions: **37 of 42**.
Four other cases that passed in the previous run failed in this one: N2 (room number left out), X2 ("I don't have
any notice" instead of "nothing"), B2 and B3 (one CTC figure left out each). In this run Gemini's free tier
answered 11 questions from fallback models (gemini-3.5-flash-lite, gemini-3.1-flash-lite) after rate-limiting
the main one; B2 was answered by a fallback. L1 is as decided in docs/DECISIONS.md. No further fix round.
