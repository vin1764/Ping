# Handoff — 22 Nov 2026

Live: https://vin1764.github.io/ping-dashboard/ (deployed from `claude/fervent-archimedes-42mus8`; live build = HEAD).
Every check below was run against the live site after the last deploy.

## Done today

| what | state | proof |
|---|---|---|
| **P0 FirstClub "You're not on it"** | Fixed. The run read the demo's profile row (fake roll) since 21 Nov 18:04; it now reads only yours and also searches every list for your ERP login id. FirstClub (notice 1817) → "You're on the FirstClub shortlist (Product Management)". 14-day re-scan of 61 list files: 1 verdict changed (FirstClub). | `tests/test_firstclub_regression.py`, docs/DECISIONS.md |
| Never assert absence | "I couldn't find your roll number … check the list yourself" / "I couldn't read … reliably"; a test fails if any "not on it" phrasing is in the code | same |
| 13:41 run skipped | Fixed: a backup-cron run that stood down no longer counts as a run | `tests/test_schedule_guard.py` |
| "check X again" | Live, read-only ERP re-check of that company (once per company per 5 min), answer with the read time; ERP down → says so + link | `tests/js/recheck.test.js`, `evals/ask_ping/MULTITURN.md` (14/14 live, model on and off) |
| Conversation topic | Corrections and "latest / don't use old data" re-check the active topic; a new question switches | same |
| Preferences | Yours intact (never changed by a test or eval); AiPrise / Astera Labs now "Other" | Admin > `prefs-report` |
| Reply to a message | Swipe / long-press / arrow / right-click, quote in the bubble, tap → original flashes; the quoted message is the topic | `setup/reply_check.js` (live, model on and off: 0 problems), `tests/js/reply.test.js` |
| Forms smart + **dedupe fix** | One posting = one row; merged silently (same notice / mail / form link / companies + purpose + same-or-later deadline); no merge prompts; ticks carried. Live: 25 rows, notice 1815 = 1 row (11 companies), 0 prompts, 0 duplicates | `tests/test_forms.py`, `evals/forms/REPORT.md` (15/15), Admin > `forms-report` |
| Ask Ping evals (quota reset) | 70/70 single, 21/21 conversations (39/39 turns); all 44 calls on the evals key, 0 on live; main model only n/a (busy every time) | `evals/ask_ping/REPORT.md` |
| Visual polish | Bubble mark everywhere, accent #0d6b61, warm dark mode, red only < 1 h / past due, finishing details; contrast ≥ 5.3:1 | `docs/screenshots/logo/`, `docs/screenshots/polish/{before,after}/`, PWA check 0 problems |

## For you to do

- **iPhone**: remove Ping from the Home Screen and add it again to get the new icon (iOS copies the icon at add
  time). Android updates by itself within about a day.
- **Installed app**: close and reopen it once; from now on a new deploy takes over at once.
- Judging: set `DASHBOARD_PASSWORD`, run Admin › `set-dashboard-password`; afterwards a new password, then
  `end-reviewer-sessions` and `profile-restore` (unchanged from yesterday).

## Known limits

- The main Gemini model was busy or timed out on every eval call today; the lighter model and the rules answered.
- The demo snapshot is the 21 Nov one (the evals are written for it), with today's wording.
- Company names in Forms keep 1–3 letter acronyms in capitals and title-case longer shouted words ("Icici Lombard").
