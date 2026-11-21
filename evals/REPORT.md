# Ping evals

_Run on 21 Nov 2026, 12:44 IST. Re-run with `python evals/run_evals.py`._

## In short

- **Held-out real notices (never used to tune Ping): 56 of 58 checks right (97%)** on 15 notices. This is the fairest number.
- Development set: 143 of 143 checks right (100%) on 31 real notices and 7 attachments in real layouts. Ping was fixed using these, so this number is optimistic. Its first run, before the fixes, was 126 of 138 checks (91%).

## Held-out notices, by question

| question | right | out of | score |
|---|---|---|---|
| notices: company | 12 | 14 | 86% |
| notices: kind | 16 | 16 | 100% |
| notices: deadline | 14 | 14 | 100% |
| notices: time | 6 | 6 | 100% |
| notices: venue | 4 | 4 | 100% |
| notices: form link | 2 | 2 | 100% |
| notices: found | 2 | 2 | 100% |

## Development set, by question

| question | right | out of | score |
|---|---|---|---|
| notices: company | 29 | 29 | 100% |
| notices: kind | 37 | 37 | 100% |
| notices: deadline | 28 | 28 | 100% |
| notices: form link | 8 | 8 | 100% |
| notices: time | 12 | 12 | 100% |
| notices: venue | 4 | 4 | 100% |
| notices: found | 9 | 9 | 100% |
| notices: no extra companies | 3 | 3 | 100% |
| PDFs: on the list? | 7 | 7 | 100% |
| PDFs: room | 5 | 5 | 100% |
| PDFs: listed under | 1 | 1 | 100% |

## What Ping got wrong

- held-out Notice 1305 (Shortlist, ACCENTURE AEH): company: said none, expected ['Accenture India Private Limited']
- held-out Notice 1465 (Shortlist, JPMC): company: said none, expected ['JP MorganChase']

## What the first run of these evals caught (and was fixed in Ping)

- Day schedules written without a profile ('1. [PPT] OLA (6:00 PM - 7:00 PM)') were skipped, so those companies and times were lost.
- A schedule entry tagged [PPT] was reported as a test.
- Room lists with two students per line ('Roll No | Room No | | Roll No | Room No') gave the room from the wrong column, i.e. another student's room.
- 'No further extensions will be given' made a form notice look like a deadline extension.
- 'Room allocations will be communicated' was read as 'here are the rooms'.
- 'List of students eligible for the assessment' wasn't recognised as a shortlist.
- A test date without a time ('scheduled for 14th November') was dropped.
- In plain-text lists, the room on your own line wasn't picked up; in role-per-column shortlists, the role you're listed under wasn't reported.

## Notices tested

| notice | set | subject | company column | all checks right? |
|---|---|---|---|---|
| 1733 | development | CV Submission | Intel | yes |
| 1716 | development | CV Submission | SLB | yes |
| 1761 | development | CV Submission | Flipspaces Technology Labs Pvt. Ltd. | yes |
| 1587 | development | CV Submission | TOLARAM GROUP | yes |
| 1692 | development | CV Submission | D.E. Shaw | yes |
| 1649 | development | Date extension | Arihant Capital Markets Limited | yes |
| 1759 | development | Date extension | INTEL | yes |
| 1787 | development | Date extension | Nation with Namo | yes |
| 1797 | development | Date extension | ICICI LOMBARD | yes |
| 1689 | development | Date extension | Multiple Companies | yes |
| 1597 | development | Urgent | Accenture Solutions Private Limited | yes |
| 1675 | development | Urgent | Tolaram Group | yes |
| 1513 | development | Urgent | BLACKROCK | yes |
| 1526 | development | Urgent | EXL | yes |
| 1775 | development | Urgent | ETERNAL | yes |
| 1687 | development | Urgent | Tekion India Pvt Ltd | yes |
| 1601 | development | Urgent | HAKIMO.AI | yes |
| 1599 | development | Urgent | Accenture Solutions Private Limited | yes |
| 1646 | development | Shortlist | MathWorks India Private Limited | yes |
| 1651 | development | Shortlist | Airbus | yes |
| 1640 | development | Shortlist | PHYAGENTS | yes |
| 1732 | development | Schedule | CDC Placement Schedule for 18th November 2026 | yes |
| 1760 | development | Schedule | CDC Placement Schedule for 19th November 2026 | yes |
| 1537 | development | Re-schedule | CDC Placement Schedule for 9th November 2026 | yes |
| 1721 | development | PPT/Workshop/Seminars etc | Paytm | yes |
| 1768 | development | PPT/Workshop/Seminars etc | OLA | yes |
| 1700 | development | PPO | INTEL | yes |
| 1555 | development | PPO | Sarvam | yes |
| 1782 | development | Additional requirement | OLA | yes |
| 1783 | development | Additional requirement | AIRAMATRIX | yes |
| 1658 | development | General | Important Instructions for Identity Verification | yes |
| 1517 | held-out | CV Submission | NoBroker | yes |
| 1520 | held-out | CV Submission | IQVIA | yes |
| 1664 | held-out | CV Submission | D. E. Shaw India | yes |
| 1647 | held-out | Date extension | ETERNAL | yes |
| 1625 | held-out | Date extension | ETERNAL | yes |
| 1620 | held-out | Date extension | Multiple Companies | yes |
| 1676 | held-out | Urgent | Mathworks india private limited | yes |
| 1241 | held-out | Urgent | AMERICAN EXPRESS | yes |
| 1712 | held-out | Urgent | CARS24 | yes |
| 1598 | held-out | Urgent | Insurity Solutions India Private Limited | yes |
| 1305 | held-out | Shortlist | ACCENTURE AEH | no |
| 1465 | held-out | Shortlist | JPMC | no |
| 1350 | held-out | Schedule | CDC Placement Schedule for 2nd7th November 2026 | yes |
| 1281 | held-out | PPT/Workshop/Seminars etc | TIGER ANALYTICS | yes |
| 1731 | held-out | Additional requirement | OLA | yes |

## Attachments tested

| layout | right? |
|---|---|
| Room list in two column pairs (layout of the real Eternal room list) | yes |
| Shortlist with one column per role (layout of the real Eternal shortlist) | yes |
| Standard table: S.No, Roll No, Name, Room, Slot | yes |
| Shortlist the student is not on | yes |
| Names only, no roll numbers (matched on the profile name) | yes |
| Plain text lines, no table borders | yes |
| Excel room list | yes |

## Numbers from the real run (21 Nov 2026)

These come from Ping's own logs. There is no answer key for them, so they show what Ping did, not whether each answer was right.

- Logged in to the ERP in 19.8 s (the OTP email took 12.6 s).
- Read 201 roles and 260 new notices out of 1624.
- Checked 64 attachments: read 64, the student was on 19 and not on 45; 0 couldn't be read, 0 were scanned images.
- Made 742 requests to the ERP, every one through the read-only allow list.
- Feed after the run: 14 always-show, 43 apply-by, 331 kept hidden, 3 questions for the student.

**Duplicate merging, on the real notices of the last 14 days:** 177 messages without merging; 15 repeats merged and 39 real changes sent as updates (29 deadline moves, 10 time changes). Unsure merges: 0.

## How this was made

- Notices: real CDC notices; other students' names, roll numbers and phone numbers were removed first. The expected answers were written by reading each notice. Ping's answers come from the same code the hourly run uses (`ping/notices.py`).
- Attachments: real shortlists list hundreds of other students, so they can't be shared. The cases rebuild the table layouts seen in the real run with made-up roll numbers and names.
- Company answers use the student's real companies list (company and role names only).
