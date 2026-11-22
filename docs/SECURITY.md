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

**Step 1, every new mail: headers only.** `BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE LIST-UNSUBSCRIBE PRECEDENCE)]`.
The filter decides from these alone, in this order:

| # | rule | result |
|---|---|---|
| 1 | subject says OTP / one-time password / verification code / login, security or sign-in code | **dropped**: OTP mails are used for the ERP login only (searched separately by the word "OTP" during login), never stored or shown |
| 2 | sender is a job board (LinkedIn, Naukri, Indeed, Glassdoor, Internshala, Instahyre, Foundit, Monster, Apna, Cutshort, Wellfound, Angel, TimesJobs, Shine, IIMJobs, Hirist) and not the placement office | dropped |
| 3 | subject is an account or shopping mail (security alert, sign-in, password, "verify your email/account", receipt, invoice, order shipped/delivered, refund, payment, subscription, newsletter, unsubscribe, % off, sale, cashback, coupon) and the sender isn't the placement office | dropped |
| 4 | sender is the placement office: the name, address or domain has CDC, placement(s), placement cell, career development, TnP, T&P, training and/or placement, recruitment cell; or the address/domain is in `PING_PLACEMENT_SENDERS` (comma-separated, optional) | **kept** |
| 5 | subject, sender name or sender domain names a company in the ERP companies list (whole name, name written together, its distinctive first word, or one typo in a word of 6+ letters, as notices are matched); a bulk mail (List-Unsubscribe / Precedence: bulk) from it only with a hiring word in the subject | **kept** |
| 6 | sender domain is an online-test platform (HackerRank, HackerEarth, Mettl, Codility, CodeSignal, iMocha, SHL, Aon, Talview, HirePro, AMCAT, CoCubes, Glider, TestGorilla, Karat, Mercer, Superset, HireVue, InterviewBit, MyAnatomy, Eklavvya) | **kept** |
| 7 | any other bulk mail | dropped |
| 8 | subject has a placement signal: test link, assessment, online/coding/aptitude/written test, shortlist, interview, pre-placement talk, offer letter, job offer, pre-placement offer, placement, recruitment, campus drive/hiring/recruitment, hiring process, selection process. Weaker words (form, deadline, offer, registration, last date, due, and PPT / PPO in capitals) count only next to internship, job, role, hiring, campus, CV, resume, candidate, selection, recruit, drive, CTC, stipend or profile | **kept** |
| 9 | everything else | dropped |

A dropped mail is never read beyond those headers and nothing of it is stored (the run log keeps only counts:
how many were dropped and by which rule).

**Step 2, kept mails only: the whole message.** Text, links and PDF / Excel attachments (in memory; never written
to disk). If the body turns out to carry an OTP the mail is dropped after all. Stored in `emails` (owner only, see
Tables): sender, subject, the first 300 characters, company, kind (form / test / interview / shortlist / PPT / offer
/ announcement), deadline and date-time, links (no unsubscribe or tracking links), why it was kept, and for an
attachment only what the notice attachment check keeps: status, the table heading and your own row. Nothing from a
mail ever changes "applied": that comes from the ERP alone.

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
| eval traffic on the evals key | every eval and Admin call to a model used GEMINI_API_KEY_EVALS; ask-ping logged `key: "evals"` for them and refused eval requests without the proof (403) | Admin > `functions-check` |

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
| PING_AI_LITE_MODEL = `gemini-3.1-flash-lite` (a setting, not a secret) | Supabase function secret, set by the deploy (`dashboard.yml`) | Ask Ping's lighter model: main model with retries, then this once, then the rules answer | yes (the value is in `dashboard.yml`) |
| PING_GITHUB_TOKEN | GitHub Actions secret; Supabase function secret | Check now and kick-run (start the Ping workflow) | no |
| DASHBOARD_DEPLOY_TOKEN | GitHub Actions secret | pushes the built dashboard to the public repo | no |
| PING_CRON_SECRET | Supabase function secret + Vault (`ping_cron_secret`) | pg_cron's calls to kick-run and send-push | no |
| VAPID_PRIVATE_KEY | Supabase function secret only, set by Admin > `push-setup` (made on GitHub's runner, sent straight there, never printed) | send-push (signs every push) | no |
| VAPID_PUBLIC_KEY, VAPID_SUBJECT | Supabase function secrets; the public key also in `dashboard/push-public-key.txt` and `config.js` (public by design) | send-push; the page subscribing | the public key only |

Checks: `git log --all -p` has no Supabase secret key, access token, Google key or GitHub token (the one
`sb_secret_` match is the fake `sb_secret_test...` in a test), and no `.env` file was ever committed. Actions >
Admin > `log-scan` downloads the logs of the last 20 workflow runs and searches them for the values of the
secrets above and for key-shaped text; it prints counts only.

## Limits and timeouts

| what | limit |
|---|---|
| demo questions | 15 per session per hour, 100 per hour for all demo sessions (`demo_take_question()`); a preference change counts as one more |
| Ask Ping | FACT questions (due, tests, CTC, eligibility, CV, lists, mail, help): answered in the page itself from the data it has loaded (the same rules file), no call and no model; the function answers them instead when a check has finished since the page loaded its messages, or the "For you" marks aren't in yet. Preference changes and OPEN questions go to the function. OPEN questions: the main model 10 s in all with one retry when busy, then the lighter model once with 5 s, then the rules answer; the page's typing bubble says "still thinking…" after 4 s. Every number in a model reply must be in its FACTS or the rules answer replaces it; classification from the chat: 60 s |
| hourly run, AI | notice reader: at most 20 calls and 300 s a run; classifier: 240 s a run; CV summary: 60 s per model |
| models, in order | Ask Ping: gemini-flash-latest, then gemini-3.1-flash-lite (`PING_AI_LITE_MODEL`). Role marks and the hourly run: gemini-flash-latest, gemini-flash-lite-latest, gemini-3.5-flash-lite, gemini-3.1-flash-lite, gemma-4-31b-it |
| CV upload | PDF only, 5 MB, 3 CVs |
| push | at most 1 per check (the most urgent new for-you message) plus test-day reminders; never twice for a message; nothing outside the check window; a notification older than 6 h isn't shown (TTL); dead subscriptions (404/410) are removed |
| JD files and links | ERP JD files: `AdmFilePDF.htm` type JNF/COM only, through the gate. Links in a JD: GET only, public hosts only (no IPs, no ERP or internal names), 3 redirects, 20 s, 12 MB, no cookies, YouTube skipped; a sign-in page counts as unreadable. At most 40 roles with a file or link a run, again only when the role's JD information changes. 40 summaries a run |

## Cleanup

`cleanup_demo_sessions(7)` deletes anonymous users older than 7 days (their chat and session preferences go with
them) and old demo question counts. It runs daily at 21:23 UTC from Supabase's own scheduler (pg_cron job
`ping-demo-cleanup`, `sql/schedule.sql`); Actions > Admin > `schedule-status` lists the job and its last runs.
