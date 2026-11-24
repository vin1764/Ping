# Security: who can read and write what

Everything below is defined in `sql/schema.sql` (applied with Actions > Admin > `apply-sql`) and checked live by
Actions > Admin > `ask-ping-page` (`setup/ask_ping_page_test.py`) from a one-click demo session.

## Logins

| who | how they sign in | what decides it |
|---|---|---|
| **owner** | email + password on the dashboard | `is_ping_owner()`: the login's email is in `allowed_users` (the hourly run puts `MAIL_ADDRESS` there) |
| **demo session** | View demo on the sign-in screen (and the checks' `?anon-demo=1`): an anonymous sign-in | `is_ping_demo()`: the token says `is_anonymous` |
| **server** | the service key (`SUPABASE_SERVICE_KEY` / function secret `PING_SERVICE_KEY`) | bypasses Row Level Security; used only by the hourly run, Admin tasks and the functions |
| anyone else | the publishable key alone | no policy grants them anything |

### Judging (reviewers sign in with the owner's login)

Before: `profile-snapshot` (Actions > Admin) keeps the profile row, push subscriptions and CV files server-side
(`profile_snapshots`, readable by the service key only; the files copied under `snapshots/<id>/` in the private
bucket). Then a password used nowhere else: save it as the repo secret `DASHBOARD_PASSWORD` and run
`set-dashboard-password`; it sets the password through Supabase Auth's admin API, proves it with one sign-in and
signs that check out again; the value is masked in logs and never printed. Your own phone stays signed in
(sign-outs and new sign-ins elsewhere never end it).

After: a new `DASHBOARD_PASSWORD` and `set-dashboard-password` again; `end-reviewer-sessions` ends the login's
sessions that started after the snapshot (the reviewers' devices; yours started before it and stay);
`profile-restore` puts the profile, push subscriptions (a reviewer's device is removed) and CV files back exactly.

### Staying signed in (sessions)

- **Never the password.** The dashboard keeps only Supabase's session: an access token (1 hour) and a single-use
  refresh token. Password managers (iCloud Keychain, Google Password Manager) may keep the password if you let them;
  Ping doesn't.
- **Where:** this device's localStorage under the fixed key `ping-auth`, plus a second copy in IndexedDB
  (`ping-session`); reading takes the newer one. Never sessionStorage, never a cookie. An anonymous demo session has its
  own key (`ping-demo-auth`) and its own client, so it can't replace or sign out the owner's session.
- **How long:** until you sign out on that device. Auth settings (Admin > `auth-config` sets them, `auth-sessions`
  shows them): `sessions_timebox = 0` and `sessions_inactivity_timeout = 0` (no time limit, no inactivity limit),
  `jwt_exp = 3600`, `refresh_token_rotation_enabled = true`, `security_refresh_token_reuse_interval = 10` (a used refresh
  token is accepted again only within 10 s, for a retry; after that the whole session is revoked, so an old stolen
  one is useless).
- **Refresh:** on opening the app (before deciding whether to show sign-in), before the access token runs out, and
  when the app comes back to the screen; nothing is refreshed while it's in the background.
- **Sign out** ends that device's session only (`scope: "local"`). The nightly demo cleanup deletes anonymous users
  only.
- **Tested** in WebKit (iPhone) and Chromium (Android) against the local replica: `setup/stay_signed_in.py`.

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
| push_subscriptions (docs/PUSH.md) | add, read, remove (each device that said yes: push endpoint + the browser's public keys) | nothing (can't subscribe) | read by send-push with the service key |
| push_queue | nothing | nothing | server only: pushes sent (never twice) and test-day reminders waiting |

Functions: `is_ping_owner()`, `is_ping_demo()` and `demo_take_question()` run with definer rights and are callable
by signed-in users; `cleanup_demo_sessions()` only by the server.

**Realtime (live updates):** `chat_messages` and `runs` are in Supabase's Realtime publication. Realtime sends a
change only to the logins whose read rules let them see that row, so a demo session receives its own chat rows and
the demo's runs, never the owner's. Checked live by Admin > `live-page` (`setup/live_page_test.py`): another demo
session's message and an owner message (posted with the service key, deleted right after) never reach a demo session.

## Mailbox (read-only, placement mail only)

The institute mailbox is opened read-only (IMAP `EXAMINE`, every fetch is `BODY.PEEK`: nothing is marked read,
moved, flagged or deleted). Ping reads it in two steps (`ping/mail_source.py`, `ping/mailbox.py`):

**Step 1, every new mail: headers only** (rules v3, 24 Nov). `BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE
LIST-UNSUBSCRIBE PRECEDENCE)]` and Gmail's thread id, fetched in pages with no cap. In this order:

| # | rule | result |
|---|---|---|
| 1 | subject says OTP / one-time password / verification code / login, security or sign-in code | **dropped**: OTP mails are used for the ERP login only, never stored or shown |
| 2 | a mail you sent | not kept (its thread counts, rule 7) |
| 3 | sender is the placement office (CDC, placement(s), placement cell, career development, TnP, T&P, training and placement, recruitment cell; or `PING_PLACEMENT_SENDERS`) | **kept**, bulk or not |
| 4 | sender is a job board (LinkedIn, Naukri, Indeed, Internshala, ...) | dropped |
| 5 | subject is an account or shopping mail (security alert, password, receipt, order shipped, newsletter, % off...) | dropped |
| 6 | sender is a test / hiring platform (HackerRank, HackerEarth, Mettl/Mercer, SHL, Unstop, Codility, iMocha, AMCAT, Aon, Talview, HireVue, Superset, Workday, Greenhouse, Lever, SuccessFactors, ...) or a sender that sent you a test link before | **kept**; a bulk one only with a test link in it (step 1b) |
| 7 | **any other bulk mail** (List-Unsubscribe / Precedence: bulk, or a newsletter / marketing sender: news@, offers@, *.news) | dropped |
| 8 | in a Gmail thread with a kept mail, or with a mail you sent about an application | **kept** |
| 9 | a listed company by its own domain (in.ey.com, zs.com, jpmchase.com) or its full name in the sender's name or the subject (never a parent company or a first word alone: ICICI Bank is not ICICI Lombard) | **kept** |
| 10 | subject has a placement signal (test link, assessment, shortlist, interview, pre-placement talk, offer letter, placement, recruitment, campus drive...; form / deadline / registration only next to a hiring word) | **kept** |
| 11 | anything else, not bulk | **step 1b**: the body is read in memory to decide |

**Step 1b, undecided personal mail: the body in memory, to decide.** Kept only if it names a listed company by its
full name together with a placement word (application, assessment, test, interview, shortlist, offer, PPO, slot,
round, JD); a platform's bulk mail only with a link to a test on that platform. Otherwise dropped: nothing of it is
stored or logged beyond the count. OTP, account, shopping, job-board and bulk mail is never opened.

**Step 2, kept mails: the whole message.** Text, links and PDF / Excel attachments (in memory; never written to
disk). If the body turns out to carry an OTP the mail is dropped after all. Stored in `emails` (owner only): sender,
subject, **a short summary, never the body** ("Interview · Navi Limited · 2026-11-24 11:00", then at most two
sentences with facts that matter: CTC, eligibility, venue, slot), company, where it came from ("mail from EY GDS"),
kind, deadline and date-time, links (no unsubscribe or tracking links), why it was kept, and for an attachment only what the notice attachment check keeps: status, the table heading and your own row. Nothing from a
mail ever changes "applied": that comes from the ERP alone.

A job description (a notice's or a mail's attachment, or a mail that is itself a JD) is not a list of students: it is
kept whole so Ask Ping and the Companies tab can use it, with every phone number and email address taken out first.
A file is a JD only if it has no roll number and doesn't read like a list of students (ping/pdfs.py `classify`); a
shortlist, test or room list, result, or anything else naming students keeps only your row and the heading, as above.

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

### Re-check of 22 Nov 2026, 07:00-07:30 IST

| check | result | how |
|---|---|---|
| row rules from a demo session | all checks passed: 0 real rows in every table above, the CV bucket empty and closed, wrong password refused | Admin > `ask-ping-page`, 07:00 IST |
| demo rows a demo session can read | profile 1, roles 201, notices 261, pdf_checks 64, items 447, all sample rows (0 real); emails and runs: 0 visible | a fresh anonymous session, REST with its own token |
| anonymiser on every copy of the demo | clean: the repo's `dashboard/demo-data.json`, the built `demo-data.json` and `demo-details.json`, the same two files on the live site, and the database's demo rows | `final_check()` (no 10-digit number, no "+91", no name from the denylist) |
| secrets in workflow logs | the last 20 runs (17 had logs; 3 were still running), the values of 11 secrets and key-shaped text: nothing found | Admin > `log-scan`, 07:15 IST |
| secrets in git | no secret value or key-shaped text in tracked files or history (`git log --all -p`), no `.env` ever committed | as above |
| the banned word | 0 in this repository's tracked files; 0 in every file of the live site, which is the public dashboard repository's only commit (each deploy replaces its history). 7 old commits of this private repository still have it; the public source copy rewrites them | `git grep -i`, curl of each live file |
| public source copy | Admin > `public-copy` rewrote all 252 commits on GitHub's runner: mailbox, roll (any case, with or without separators) and project address replaced, 7 denylisted names and 6 history-only ten-digit numbers replaced, every old demo snapshot swapped for today's clean one; then 872 text blobs checked (no secret value, key-shaped text, denylisted name, banned word or unknown ten-digit number): passed. Not yet public: there is no public repository to push to (the owner creates it), so it waits as a 1-day private artifact. This repository's history is untouched | Admin > `public-copy`, 07:25 IST |
| eval traffic on the evals key | the function's own log, last 23 h, answers by key: evals: 15 with a model call (every one), 95 without; live: 2 demo answers with a model call (browser sessions on the live site, which can't carry the evals proof; not an eval runner) and 5 for the owner; 116 demo answers labelled live never called a model (rules-only checks run from outside the runner, e.g. the fallback set with `no_ai`). An eval request without a valid proof is refused (403), so an eval runner can't reach the live key | Admin > `functions-check`, 07:26 IST |

## Secrets

| secret | lives in | used by | in git? |
|---|---|---|---|
| ERP_USER_ID, ERP_PASSWORD, ERP_SECQ_1..3 | GitHub Actions secrets | the hourly run (ERP login) | no |
| MAIL_ADDRESS, MAIL_APP_PASSWORD | GitHub Actions secrets | the hourly run (OTP mail for the login and placement mail, read-only IMAP: see Mailbox; alerts) | no |
| SUPABASE_URL, SUPABASE_SERVICE_KEY | GitHub Actions secrets; the service key also as function secret PING_SERVICE_KEY | hourly run, Admin tasks; ask-ping (cache, first profile row) | no |
| SUPABASE_PUBLISHABLE_KEY | GitHub secret; also in the public dashboard's `config.js` (public by design) and function secret PING_PUBLISHABLE_KEY | the browser and the functions (with the caller's own login) | only in the built `config.js` of the public repo |
| SUPABASE_ACCESS_TOKEN | GitHub Actions secret | deploys the functions; Admin tasks (SQL, auth settings, logs) | no |
| GEMINI_API_KEY (the live key) | GitHub Actions secret; Supabase function secret | the hourly run (notice reader fallback, classifier, CV summaries); Ask Ping for the owner and demo visitors | no |
| GEMINI_API_KEY_EVALS (a second key, its own quota) | GitHub Actions secret; Supabase function secret | every Admin task (Ask Ping and relevance evals, demo-refeed, gemini-check, the page and function checks): Admin's `GEMINI_API_KEY` is this key; calls through ask-ping send `x-ping-evals`, an HMAC of "ping-evals" made with it, and the function then answers with it and logs `key: "evals"`. An eval request without a valid proof is refused (HTTP 403), never answered on the live key | no |
| GROQ_API_KEY (the live key) | GitHub Actions secret; Supabase function secret (the deploy copies it) | Ask Ping's first model for the owner and demo visitors | no |
| GROQ_API_KEY_EVALS (a second Groq key) | GitHub Actions secret; Supabase function secret | Ask Ping eval requests (the same `x-ping-evals` proof as Gemini's); without it, evals skip Groq, never use the live key | no |
| PING_GITHUB_TOKEN | GitHub Actions secret; Supabase function secret | Check now and kick-run (start the Ping workflow) | no |
| DASHBOARD_DEPLOY_TOKEN | GitHub Actions secret | pushes the built dashboard to the public repo | no |
| PING_CRON_SECRET | Supabase function secret + Vault (`ping_cron_secret`) | pg_cron's calls to kick-run and send-push | no |
| VAPID_PRIVATE_KEY | Supabase function secret only, set by Admin > `push-setup` (made on GitHub's runner, sent straight there, never printed) | send-push (signs every push) | no |
| VAPID_PUBLIC_KEY, VAPID_SUBJECT | Supabase function secrets; the public key also in `dashboard/push-public-key.txt` and `config.js` (public by design) | send-push; the page subscribing | the public key only |

Checks: `git log --all -p` has no Supabase secret key, access token, Google key or GitHub token (the one
`sb_secret_` match is the fake `sb_secret_test...` in a test), and no `.env` file was ever committed. Actions >
Admin > `log-scan` downloads the logs of the last 20 workflow runs and searches them for the values of the
secrets above and for key-shaped text; it prints counts only.

## What each AI provider receives

Only the function (server side) talks to a model; the browser never holds a model key. Nothing is sent for FACT
questions, feedback, requests to act or "ok": the rules answer those.

| provider | used for | receives | never receives |
|---|---|---|---|
| Groq (`api.groq.com`, `GROQ_API_KEY`) | Ask Ping's OPEN questions, first | the compact chat prompt: the question (and the message it replies to), the last 12 chat messages, your profile fields (department, degree, CGPA, backlogs, targets, interested / hidden companies), the roles of the companies in the question with their details and JD text, deadlines due in the next 7 days, the newest 25 feed lines, your own row in list PDFs (room, slot), the latest 3 notices of the companies asked about | your ERP login, password, security answers, mail password, roll number or name as an identifier, CV files, PDFs, other students' rows |
| Google Gemini (`GEMINI_API_KEY`) | Ask Ping's OPEN questions when Groq doesn't answer; marking roles For you; the hourly run's notice-reader fallback; CV summaries | the full chat prompt (as above, with every role's line instead of only the asked companies'); for role marks, each role's title, details and JD text with your targets and CV summaries; for the notice fallback, a notice's text; for CV summaries, the text of your CV | the same as Groq: no logins, passwords or other students' rows |

## Limits and timeouts

| what | limit |
|---|---|
| demo questions | 15 per session per hour, 100 per hour for all demo sessions (`demo_take_question()`); a preference change counts as one more |
| Ask Ping | FACT questions (due, tests, CTC, eligibility, CV, lists, mail, help): answered in the page itself from the data it has loaded (the same rules file), no call and no model; the function answers them instead when a check has finished since the page loaded its messages, or the "For you" marks aren't in yet. Preference changes and OPEN questions go to the function. Feedback ("X not relevant", "show X again", "undo") is saved by rules, no model. OPEN questions: Groq once (6 s), then Gemini flash-lite (one retry when busy), 15 s in all, then the rules answer; the page's typing bubble says "still thinking…" after 4 s. Every number in a model reply must be in its FACTS or the rules answer replaces it; classification from the chat: 60 s |
| hourly run, AI | notice reader: at most 20 calls and 300 s a run; classifier: 240 s a run; CV summary: 60 s per model |
| models, in order | Ask Ping's chat: Groq `openai/gpt-oss-120b` (6 s), then Gemini `gemini-3.1-flash-lite` (one retry when busy), 15 s in all, then the rules answer. Role marks from the chat: gemini-3.1-flash-lite, gemini-flash-latest, gemini-flash-lite-latest, gemini-3.5-flash-lite, gemma-4-31b-it (one call for every role). The hourly run (notice fallback, classifier, CV summaries): Gemini only |
| CV upload | PDF only, 5 MB, 3 CVs |
| push | at most 1 per check (the most urgent new for-you message) plus test-day reminders; never twice for a message; nothing outside the check window; a notification older than 6 h isn't shown (TTL); dead subscriptions (404/410) are removed |
| JD files and links | ERP JD files: `AdmFilePDF.htm` type JNF/COM only, through the gate. Links in a JD: GET only, public hosts only (no IPs, no ERP or internal names), 3 redirects, 20 s, 12 MB, no cookies, YouTube skipped; a sign-in page counts as unreadable. At most 40 roles with a file or link a run, again only when the role's JD information changes. 40 summaries a run |

## Cleanup

`cleanup_demo_sessions(7)` deletes anonymous users older than 7 days (their chat and session preferences go with
them) and old demo question counts. It runs daily at 21:23 UTC from Supabase's own scheduler (pg_cron job
`ping-demo-cleanup`, `sql/schedule.sql`); Actions > Admin > `schedule-status` lists the job and its last runs.
