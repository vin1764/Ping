# Facts for the 1-pager

Numbers only, each with where it comes from. Collected 21 Nov 2026.

## Problem framing (README)

| fact | value | source |
|---|---|---|
| sources read | 4: ERP companies list, CDC notice board, PDFs attached to notices, institute mailbox | README, first paragraph |
| what is kept | only what concerns the one student | README |
| WhatsApp groups | not a source | owner's instruction; nothing in the code reads them |

## Schedule

| fact | value | source |
|---|---|---|
| runs per day | 20 (every hour at :41 UTC, 00:41-19:41 UTC = 06:11-01:11 IST) | `sql/schedule.sql` (job `ping-hourly`, `41 0-19 * * *`), `.github/workflows/ping.yml` (backup cron) |
| what starts a run | Supabase pg_cron -> `kick-run` function -> workflow_dispatch; GitHub cron as backup | `sql/schedule.sql`, `supabase/functions/kick-run/` |
| guard against double runs | skip if a run is going or started < 50 min ago | `supabase/functions/kick-run/guard.ts`, `ping/schedule_guard.py` |
| first pg_cron-started run | 21 Nov 13:41:04 UTC (19:11 IST), Ping run #13, success, 57 s | GitHub Actions run 44910079892 |
| pg_cron ticks after the #14 fix | 15:41 UTC (21:11 IST): kick-run answered "a Ping run started 33 min ago", nothing started (the guard, after manual run #15); 16:41 UTC (22:11 IST): started run #16, success | Admin > schedule-status (cron.job_run_details, kick-run's replies) |

## Runs so far (GitHub Actions, Ping workflow, up to 21 Nov 17:40 UTC)

| fact | value | source |
|---|---|---|
| runs | 16 | Actions > Ping |
| succeeded | 8 (#2, #3, #9, #11, #12, #13, #15, #16) | same |
| failed | 7 (#1, #4-#8 before the login fixes of 20-21 Nov; #14 at 14:41 UTC on 21 Nov, a digest key-format bug, fixed in a95ce06 and verified by #15) | same |
| cancelled | 1 (#10) | same |
| success rate | 8 of 16 overall; 6 of 7 completed runs since #9 | same |
| first full run | 12.1 min; 201 roles, 1,624 notices seen, 260 read in full, 64 PDFs (64 read, 19 name the student), 84 mails looked at, 10 kept, 742 ERP requests | `evals/real_run.json` |
| later runs | under 1 min (run #13: 42.5 s, 9 new notices, 3 PDFs; run #15: 35.5 s, 16 ERP requests) | run #13 and #15 log summaries |
| login | 19.4 s, of which 12.7 s waiting for the OTP mail; Get OTP pressed once | run #13 log summary |
| repeats merged (14 days of notices) | 177 notice messages -> 162; 15 repeats merged, 39 changes sent as updates | `evals/real_run.json` |

## The chat

| fact | value | source |
|---|---|---|
| today's demo thread (21 Nov) | 38 messages before digests -> 3 after (one new-roles message, one 2-hour reminder, one message for 5 deadline extensions) | demo snapshot replay, commits cc62352 and c4ad1af; live screenshots `docs/screenshots/after-*` |
| reminder | 1 per deadline batch, default 2 h before close (profile setting) | `ping/digests.py` |
| messages per role in the chat | 0 (roles appear inside list messages) | `dashboard/app.js` (`inChat`) |

## Evals

| eval | result | source |
|---|---|---|
| parser, held-out real notices | 56 of 58 checks (97%) on 15 notices | `evals/PARSER_REPORT.md` |
| parser, development set | 143 of 143 checks (100%) on 31 notices + 7 attachment layouts | `evals/PARSER_REPORT.md` |
| Ask Ping, single questions | 38 of 42 (90%); failing: C2 (CG cut-off not quoted), D2 (company names), D3 (time), L1 (Others left out of a 'relevant to me' list) | `evals/ask_ping/REPORT.md` |
| Ask Ping, multi-turn conversations | 20 of 21 conversations, 38 of 39 turns (incl. 8 of 8 preference-by-chat conversations and the wrong-detection check) | `evals/ask_ping/REPORT.md` |
| Ask Ping, before conversation memory | 34 of 36 single; 4 of 9 conversations (13 of 18 turns) | `evals/REPORT.md` |
| relevance, demo persona (product / consulting / analyst / finance) | precision 93% (76 of 82), recall 97% (76 of 78), best CV right 96% (73 of 76) | `evals/relevance/REPORT.md` |
| relevance, core-software persona | precision 100% (28 of 28), recall 100% (28 of 28) | `evals/relevance/REPORT.md` |

## Latency

| what | value | source |
|---|---|---|
| Ask Ping answer, per model | gemini-flash-lite-latest: median 5.1 s, 90th percentile 11.4 s, max 49.1 s (70 answers); answers decided by rules (preferences, read-only): median 3.4 s, max 31.9 s incl. re-marking 197 roles (11 answers). All 81 answers came from these two; no fallback model was needed | `evals/ask_ping/results.json` |
| "For you" marks for the page | 2.4 s (197 roles, from the cache) | live call, 21 Nov 14:34 UTC |
| preference change incl. re-marking 197 roles in one Gemini call | 30.2 s | live call, 21 Nov 14:34 UTC |

## Cost

| item | cost | source |
|---|---|---|
| GitHub Actions (private repo) | free tier: 2,000 min/month; a run is about 1 min after the first | README "How it runs" |
| Supabase | free plan (database, functions, storage, pg_cron) | `docs/SECURITY.md` |
| Gemini | free tier; 5 models in fallback order | `docs/PROMPTS.md` |
| GitHub Pages | free | README "Live dashboard" |

## Read-only by construction

| fact | value | source |
|---|---|---|
| ERP requests | every request goes through one gate that allows only reading (GETs and the login/menu POSTs); 28 requests in run #13, all through the gate | `ping/gate.py`, `tests/test_gate.py`, run #13 summary |
| mailbox | read-only IMAP | `ping/mailbox.py` |
| Ask Ping | refuses requests to act ("Ping is read-only, so I can't ..."), decided by fixed patterns | `supabase/functions/ask-ping/wording.ts` |
| PDFs | only the student's row and the table heading are kept | `ping/pdfs.py` |

## Deferred

| item | status |
|---|---|
| WhatsApp delivery of messages | not built |
| hosted multi-user service | not built: each student runs their own copy under their own accounts (`docs/SETUP.md`) |
