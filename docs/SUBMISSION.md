# Ping: submission

**Live:** https://vin1764.github.io/ping-dashboard/ → sign in with the credentials in the submission note.

Ping reads one student's placement ERP every hour (the companies list, the notice board, the PDFs attached to
notices) and the placement mail in their institute mailbox, keeps only what concerns that student, and tells them
in a chat. It only reads: it cannot apply, submit, upload or accept anything. You sign in to the real account of
the student who built it, so what you see is their live placement season; anything you change there (preferences,
reminders) is put back after judging.

## 10 minutes: what to try

1. **Sign in** with the credentials in the submission note. The thread is today's: digests per closing time with
   **For you** first (each with the CV to apply with) and Others collapsed; **Today** on the right (on a phone, the
   Today tab) with countdowns that tick.
2. **Ask a fact**: `what's due tonight?`, `<company> ctc breakdown`, `which cv for <company>`. These are answered in
   your browser, from the data the page already has, in well under a second (no typing bubble).
3. **Ask something open**: `should I apply to <company>?`. This goes to the model (Gemini), with only the facts it
   needs; any number it writes must be in those facts or the rules answer is shown instead.
4. **Placement mail**: messages tagged **via email**, with **Open form / Open test / Join** on them; ask
   `what's due from mail`.
5. **Change what you see by saying it**: `only show me product and consulting roles` (the lists re-split at once),
   then `help`, `how do I install Ping?` (steps for your device).
6. **Read-only**: `apply for me` → "Ping is read-only, so I can't apply for you".
7. **Companies** tab: every role with pay, deadline and eligibility; tap one for the JD summary and "Apply with".

## How good is it (numbers, each with its source)

| | result | where |
|---|---|---|
| parser, held-out real notices | 56 of 58 checks (97%) | [evals/PARSER_REPORT.md](../evals/PARSER_REPORT.md) |
| Ask Ping, single questions (live function, evals key) | 70 of 70 (100%); the main model was out of quota on the evals key, so the 3 that needed a model got the lighter one | [evals/ask_ping/REPORT.md](../evals/ask_ping/REPORT.md) |
| Ask Ping, conversations | 21 of 21 (39 of 39 turns) | same |
| Ask Ping typed into the live page | FACT: 65 of 65 answered in the page, median 16 ms, 64 of 65 pass; OPEN: 5 of 5, median 9.4 s | [evals/ask_ping/PAGE_RUN.md](../evals/ask_ping/PAGE_RUN.md) |
| "For you" relevance | main model: precision 93%, recall 97%, right CV 96% (demo persona), 100% / 100% (core-software persona); lighter model: 90% / 99% / 92% and 100% / 100% | [evals/relevance/REPORT.md](../evals/relevance/REPORT.md) |
| placement mail, 20-mail fixture | 9 of 9 checks (no other mail stored or read, OTP never stored) | [evals/mail/REPORT.md](../evals/mail/REPORT.md) |
| placement mail, the real mailbox (14 days) | 374 mails; 59 placement mails read, 51 already on the ERP, 8 mail-only; 315 never read beyond headers | [evals/mail/REAL_COVERAGE.md](../evals/mail/REAL_COVERAGE.md) |
| attachments (messy real layouts) | 31 of 31 | [evals/REPORT.md](../evals/REPORT.md) |
| Ask Ping with the model switched off (what a student gets when Gemini is busy) | 8 of 8 | [evals/ask_ping/FALLBACK_REPORT.md](../evals/ask_ping/FALLBACK_REPORT.md) |
| security re-check (22 Nov) | a demo session sees 0 real rows in every table; every copy of the demo passes the anonymiser; no secret in the last 20 runs' logs | [docs/SECURITY.md](SECURITY.md) |
| Lighthouse (mobile) | landing page 100 / 100 / 100; demo 91-96 / 100 / 100; installable; demo chat on screen in 1.5-1.8 s on 4G with a phone's CPU | [docs/ONE_PAGER_FACTS.md](ONE_PAGER_FACTS.md) |
| real runs | 33, the last 19 in a row succeeded; started by Supabase's scheduler on the student's own hours (every tick of 21-22 Nov night accounted for) | same |

## Documents

| document | what's in it |
|---|---|
| [README.md](../README.md) | what Ping is, the architecture diagram, honest status, how it runs |
| [docs/SECURITY.md](SECURITY.md) | who can read and write what, the exact mail filter, secrets, limits, the live proofs |
| [docs/PROMPTS.md](PROMPTS.md) | every prompt Ping sends to a model, verbatim, generated from the source |
| [evals/REPORT.md](../evals/REPORT.md) | every eval suite and its score |
| [docs/ONE_PAGER_FACTS.md](ONE_PAGER_FACTS.md) | the numbers, each with its source: runs, evals, latency, performance, cost |
| [docs/SETUP.md](SETUP.md) | how another student sets up their own copy, and the measured time to a first feed |
| [docs/DECISIONS.md](DECISIONS.md) | every judgement call, with the reason |
| [docs/BUILD_PROMPTS.md](BUILD_PROMPTS.md) | every prompt given to the coding agent while building Ping, in order, with times |
| [docs/REVIEWER_RUN.md](REVIEWER_RUN.md) | a stranger's run of the live demo, answers verbatim |

Source: a public copy of this repository's full history, with every real value replaced and checked blob by blob, is built by Actions > Admin > `public-copy` (`ping/public_copy.py`); its public address goes here once the owner has created the repository. Until then: available on request.
