# Mailbox as a source: fixture eval

20 made-up mails (`evals/mail/fixture.py`) served by a fake IMAP server that records what Ping fetched. Run: `python evals/mail/run_mail_evals.py`. The exact filter is in `docs/SECURITY.md` (Mailbox).

| check | result |
|---|---|
| no noise stored | pass |
| no noise body fetched | pass |
| OTP never stored | pass |
| read-only (no IMAP writes) | pass |
| ERP duplicate deduped | pass |
| form deadline extracted | pass |
| roll found in the PDF | pass |
| all 10 placement mails kept | pass |
| extraction matches the labels | pass |

Scan: 20 mails' headers read, 10 kept and read in full, 10 bodies fetched, 1 attachment(s), 1 OTP mail skipped. Dropped by rule: bulk 1, job_board 1, no_placement_signal 5, not_placement 2, otp 1.
Feed: 1 mail repeated an ERP notice (also mailed to you), 9 became messages via email.

| # | mail | kept (why) | body read | kind | company | due / when | in the feed |
|---|---|---|---|---|---|---|---|
| 1 | shortlist PDF names you | yes (placement_office) | yes | shortlist | Goldman Sachs | 2026-11-24T09:00 | Goldman Sachs shortlist is out. You're on it (room NR 422, 01:30 PM). |
| 2 | Google Form with a deadline | yes (company:assessment) | yes | form | Pine Labs Private Limited | 2026-11-22T17:00 | Pine Labs Private Limited: fill the form by Sun 22 Nov 17:00. |
| 3 | repeats the ERP notice (Groww test) | yes (placement_office) | yes | test | Groww | 2026-11-23T15:00 | also mailed to you on the ERP notice |
| 4 | test platform invite | yes (company:assessment) | yes | test | Atlassian | 2026-11-25T23:59 | Atlassian: take the online test by Wed 25 Nov 23:59. |
| 5 | interview slot | yes (company:interview) | yes | interview | Navi Limited | 2026-11-24T11:00 | Navi Limited interview: Tue 24 Nov 11:00. |
| 6 | pre-placement talk | yes (placement_office) | yes | ppt | Accenture Solutions Private Limited | 2026-11-21T23:59 | Accenture Solutions Private Limited pre-placement talk: Sat 21 Nov 18:00. |
| 7 | offer letter | yes (company:offer letter) | yes | offer | Groww | 2026-11-30T23:59 | Groww: Offer letter - Groww Product Analyst |
| 8 | placement-office announcement | yes (placement_office) | yes | announcement |  |  | CDC Placement Office: Placement season 2026-27: guidelines for students |
| 9 | company with a typo, form link | yes (company:campus drive) | yes | form | Accenture Solutions Private Limited | 2026-11-23T10:00 | Accenture Solutions Private Limited: fill the form by Mon 23 Nov 10:00. |
| 10 | signal only, company not on the ERP list | yes (signal:interview) | yes | interview |  | 2026-11-26T14:00 | Zeta Recruiting interview: Thu 26 Nov 14:00. |
| 11 | OTP | no (otp) | no |  |  |  |  |
| 12 | job-board alert naming a listed company | no (job_board) | no |  |  |  |  |
| 13 | shopping | no (not_placement) | no |  |  |  |  |
| 14 | newsletter | no (bulk) | no |  |  |  |  |
| 15 | course deadline | no (no_placement_signal) | no |  |  |  |  |
| 16 | fest registration | no (no_placement_signal) | no |  |  |  |  |
| 17 | library | no (no_placement_signal) | no |  |  |  |  |
| 18 | account security | no (not_placement) | no |  |  |  |  |
| 19 | hostel, placement words only in the body | no (no_placement_signal) | no |  |  |  |  |
| 20 | lecture slides | no (no_placement_signal) | no |  |  |  |  |
