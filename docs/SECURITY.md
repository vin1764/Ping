# Security: who can read and write what

Everything below is defined in `sql/schema.sql` (applied with Actions > Admin > `apply-sql`) and checked live by
Actions > Admin > `ask-ping-page` (`setup/ask_ping_page_test.py`) from a one-click demo session.

## Logins

| who | how they sign in | what decides it |
|---|---|---|
| **owner** | email + password on the dashboard | `is_ping_owner()`: the login's email is in `allowed_users` (the hourly run puts `MAIL_ADDRESS` there) |
| **demo session** | "View demo" (Supabase anonymous sign-in) | `is_ping_demo()`: the token says `is_anonymous` |
| **server** | the service key (`SUPABASE_SERVICE_KEY` / function secret `PING_SERVICE_KEY`) | bypasses Row Level Security; used only by the hourly run, Admin tasks and the functions |
| anyone else | the publishable key alone | no policy grants them anything |

## Tables

Row Level Security is on for every table. "Real rows" are rows with `is_sample` false.

| table | owner | demo session | server only / notes |
|---|---|---|---|
| profile | read real row; update listed columns (roll, name, department, degree, cgpa, backlogs, CV names, interested / not interested, notice types, reminder hours, targets, list-others, CVs, chat read time) | read the demo row only | |
| roles, notices, pdf_checks, emails, contacts, runs | read real rows | read demo rows only | written by the hourly run |
| items | read real rows; update `dismissed`, `done` | read demo rows only | written by the hourly run |
| corrections | read, insert, update, delete | nothing | |
| chat_messages | read and insert its own (real) thread | read and insert its own messages only (`owner_id = auth.uid()`, `is_sample` true); never another session's | |
| session_prefs | nothing | read / write its own row only | deleted with the session (cascade on the anonymous user) |
| role_marks ("For you" cache) | nothing | nothing | server only; hashes and yes/no only |
| demo_questions (demo rate limit) | nothing | nothing (through `demo_take_question()` only) | |
| allowed_users, state | nothing | nothing | server only |

Functions: `is_ping_owner()`, `is_ping_demo()` and `demo_take_question()` run with definer rights and are callable
by signed-in users; `cleanup_demo_sessions()` only by the server.

## Storage

| bucket | owner | demo session / anyone else |
|---|---|---|
| `cvs` (private, PDF only, 5 MB) | upload, list, download, replace, delete (`is_ping_owner()`) | nothing: listing returns no objects, downloading is refused |

The hourly run downloads new CVs with the service key to summarise them; only a one-line summary is kept
(`profile.cvs`), never the text. CV files are never in git.

## Proven live (from a demo session)

`ask-ping-page` signs in as a fresh demo session and asserts: 0 real rows in each of profile, roles, notices,
pdf_checks, items, emails, contacts, runs, chat_messages, corrections, state, allowed_users, role_marks,
demo_questions and session_prefs; the CV bucket lists 0 objects and refuses a download; the owner sign-in screen
answers a wrong password with "Invalid login credentials". The result of the latest run is in
`docs/REVIEWER_RUN.md`.

## Secrets

| secret | lives in | used by | in git? |
|---|---|---|---|
| ERP_USER_ID, ERP_PASSWORD, ERP_SECQ_1..3 | GitHub Actions secrets | the hourly run (ERP login) | no |
| MAIL_ADDRESS, MAIL_APP_PASSWORD | GitHub Actions secrets | the hourly run (OTP mail, read-only IMAP; alerts) | no |
| SUPABASE_URL, SUPABASE_SERVICE_KEY | GitHub Actions secrets; the service key also as function secret PING_SERVICE_KEY | hourly run, Admin tasks; ask-ping (cache, first profile row) | no |
| SUPABASE_PUBLISHABLE_KEY | GitHub secret; also in the public dashboard's `config.js` (public by design) and function secret PING_PUBLISHABLE_KEY | the browser and the functions (with the caller's own login) | only in the built `config.js` of the public repo |
| SUPABASE_ACCESS_TOKEN | GitHub Actions secret | deploys the functions; Admin tasks (SQL, auth settings, logs) | no |
| GEMINI_API_KEY (the live key) | GitHub Actions secret; Supabase function secret | the hourly run (notice reader fallback, classifier, CV summaries); Ask Ping for the owner and demo visitors | no |
| GEMINI_API_KEY_EVALS (a second key, its own quota) | GitHub Actions secret; Supabase function secret | every Admin task (Ask Ping and relevance evals, demo-refeed, gemini-check, the page and function checks): Admin's `GEMINI_API_KEY` is this key; calls through ask-ping send `x-ping-evals`, an HMAC of "ping-evals" made with it, and the function then answers with it and logs `key: "evals"`. An eval request without a valid proof is refused (HTTP 403), never answered on the live key | no |
| PING_AI_LITE_MODEL = `gemini-3.1-flash-lite` (a setting, not a secret) | Supabase function secret, set by the deploy (`dashboard.yml`) | Ask Ping's lighter model: main model with retries, then this once, then the rules answer | yes (the value is in `dashboard.yml`) |
| PING_GITHUB_TOKEN | GitHub Actions secret; Supabase function secret | Check now and kick-run (start the Ping workflow) | no |
| DASHBOARD_DEPLOY_TOKEN | GitHub Actions secret | pushes the built dashboard to the public repo | no |
| PING_CRON_SECRET | Supabase function secret + Vault (`ping_cron_secret`) | pg_cron's call to kick-run | no |

Checks: `git log --all -p` has no Supabase secret key, access token, Google key or GitHub token (the one
`sb_secret_` match is the fake `sb_secret_test...` in a test), and no `.env` file was ever committed. Actions >
Admin > `log-scan` downloads the logs of the last 20 workflow runs and searches them for the values of the
secrets above and for key-shaped text; it prints counts only.

## Limits and timeouts

| what | limit |
|---|---|
| demo questions | 15 per session per hour, 100 per hour for all demo sessions (`demo_take_question()`); a preference change counts as one more |
| Ask Ping | 100 s for the whole answer, 45 s per call; the main model again after 1 s, 3 s and 6 s when busy, then the lighter model once (20 s kept for it), then the rules answer (Supabase stops a function at 150 s); classification from the chat: 60 s |
| hourly run, AI | notice reader: at most 20 calls and 300 s a run; classifier: 240 s a run; CV summary: 60 s per model |
| models, in order | Ask Ping: gemini-flash-latest, then gemini-3.1-flash-lite (`PING_AI_LITE_MODEL`). Role marks and the hourly run: gemini-flash-latest, gemini-flash-lite-latest, gemini-3.5-flash-lite, gemini-3.1-flash-lite, gemma-4-31b-it |
| CV upload | PDF only, 5 MB, 3 CVs |

## Cleanup

`cleanup_demo_sessions(7)` deletes anonymous users older than 7 days (their chat and session preferences go with
them) and old demo question counts. It runs daily at 21:23 UTC from Supabase's own scheduler (pg_cron job
`ping-demo-cleanup`, `sql/schedule.sql`); Actions > Admin > `schedule-status` lists the job and its last runs.
