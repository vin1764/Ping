# Placement mail on the real mailbox: last 14 days

Actions > Admin > `mail-coverage`, run 2026-11-22 05:48 IST (window 08 Nov to 22 Nov), read-only. Nothing was
stored by this run. The log, and this page, have counts, dates, kinds and company names only: no subject, sender or
mail text. The filter is the one in `docs/SECURITY.md` (Mailbox).

## Totals

| | mails |
|---|---|
| mails in the window (headers read) | **374** |
| placement mails (kept, read in full) | **59** |
| — already on the ERP (a notice says the same) | **51** |
| — mail-only (now in the feed, "via email") | **8** |
| not placement, never read beyond the headers | **315** |
| of which OTP login mails (never stored) | 75 |
| of which bulk / newsletters | 130 |
| of which job-board alerts | 18 |
| of which account or shopping mails | 5 |
| of which no placement signal in the headers | 87 |

Why the 59 placement mails were kept: 19 name a company on the ERP list, 14 come from the placement office, 26 have a
placement signal in the subject (a test platform, "interview", "shortlist" and similar).

Attachments read: 4 (PDF/Excel in placement mails); your roll number was found in none of them.

## Before and after

| | before (old scan) | after (this filter) |
|---|---|---|
| mails it kept, same 14 days, same headers | 67 | 59 |
| how it decided | a listed company's full name in the subject or sender, or "cdc" / "placement" / "erp" in the sender | the 9 rules in SECURITY.md, headers only |
| bodies read | all 374 (it fetched every message whole, then filtered) | 59 |
| in the feed | only mails about a company you had applied to | every mail-only placement mail (8), plus "also mailed to you" on the 51 ERP messages it repeated |

The old scan kept 8 more mails than the new one on the same headers. The coverage task doesn't list which ones (it
prints no subjects or senders); the rules that would drop a mail the old scan kept are the OTP/verification subjects,
account and shopping subjects, job-board senders, and bulk mail from a sender that isn't the placement office or a
listed company.

## The 8 mail-only placement mails

| received (IST) | kind | company |
|---|---|---|
| 08 Nov 10:45 | announcement | Route Mobile Limited |
| 09 Nov 08:27 | announcement | LTM |
| 09 Nov 13:07 | form | (placement office, no listed company) |
| 10 Nov 21:16 | announcement | Finarb |
| 11 Nov 03:35 | announcement | (placement office, no listed company) |
| 11 Nov 20:02 | announcement | Finarb |
| 17 Nov 17:29 | pre-placement talk | EY Parthenon |
| 20 Nov 18:43 | announcement | Cars24 |

4 of the 8 carry a deadline or a time and 2 a form or test link. In the feed, news older than 3 days and anything
whose date has passed are kept as past messages (the same rules as notices), so at the time of the run only Cars24
(20 Nov) was recent enough to be a current "via email" message, plus any of the others whose date is still ahead.
The hourly run stores all 8 on its first scan with the new rules (it looks back 14 days once).

## Notes

- 9 of the 51 "already on the ERP" mails are Phyagents form mails received within two minutes (11 Nov 03:09–03:10);
  each merged into the ERP notice that says the same.
- Of the 3 placement-office mails classified as forms without a listed company, 2 matched an ERP notice and 1 is
  mail-only (09 Nov).
