# Ping

Ping logs into the IIT Kharagpur ERP for you every hour, reads the placement
companies list, the CDC notice board, the PDFs attached to notices and your
institute mailbox, and keeps only what is about **you**. It tells you in a
chat, like WhatsApp:

- "Accordion opened, eligible for Data & AI Analyst (CG 7+, all depts). Apply by Fri 27 Nov 16:00."
- "You're on the Eternal test room list (Product Analyst). Test Thu 19 Nov 19:15, Nalanda Classroom Complex, room NR 121."
- "Update - Ather Energy deadline: deadline moved from Fri 20 Nov 18:00 to Sat 21 Nov 20:00."
- "Reminder: 38 applications you haven't applied to close tonight, Sat 21 Nov 20:00 — 11 for you" (then the list: For you first, with the CV to apply with; Others collapsed)

It **only reads**. It cannot apply, submit, upload or accept anything (see [Safety](#safety)).

**Live dashboard:** https://vin1764.github.io/ping-dashboard/ (sign in as the
owner, or press **View demo**: no account needed). How it gets there: see
[Live dashboard](#live-dashboard).

**One-click demo:** the **View demo** button on the sign-in screen opens an
anonymous, read-only session on the live dashboard. It is an anonymised snapshot of a real run on
21 Nov 2026: real companies, roles, pay, deadlines and notice wording; fake roll
number, name and CGPA; every other student's name, roll number and phone number
and everything from the mailbox removed. It shows the feed as it was at that
moment, so it doesn't go stale. The database only lets a demo session read the
demo rows and its own chat; it can't change anything. Ask Ping answers it too,
up to 15 questions per visitor per hour and 100 per hour for all visitors
together. A static copy with no login is also at
https://claude.ai/artifact/TWGCZxEawg7zZrrjSDnur7 (the owner shares it from its Share menu).

**Submission:** [`docs/SUBMISSION.md`](docs/SUBMISSION.md) (the live link, what to try, every document). Evals: [`evals/REPORT.md`](evals/REPORT.md), the index of all three suites in plain words:
parser evals (`python evals/run_evals.py`), Ask Ping evals (Actions > Admin > `ask-ping-evals`) and role relevance
evals per persona (Actions > Admin > `relevance-evals`). Security: [`docs/SECURITY.md`](docs/SECURITY.md); setup for a
new student: [`docs/SETUP.md`](docs/SETUP.md).
The exact prompts Ping sends to a model: [`docs/PROMPTS.md`](docs/PROMPTS.md), generated from the source.

---

## First 5 minutes (a new student)

1. **Run the setup** on your own copy of this repo: `python -m pip install --user -r requirements.txt`, then
   `python setup/new_student_setup.py`. It asks for your ERP login, mailbox app password and Supabase project,
   creates the tables (with an **empty profile**: nothing about you is pre-filled), your dashboard login, and
   the GitHub secrets. Details: [docs/SETUP.md](docs/SETUP.md).
2. **Open the dashboard** link it prints and sign in with the email it shows.
3. **Tell Ping what you're looking for**, as your first chat message, in your own words, for example
   "only show me <the kinds of roles you want>", "don't count <a kind you don't want> as relevant",
   "remind me 3 hours before deadlines". Ping answers with one line saying exactly what it saved, and marks
   every role "For you" or not. "what are my preferences?" shows them; "reset my preferences" clears them.
   The Profile page shows the same fields (plus CGPA, department and degree for eligibility).
4. **Done.** The first hourly run reads the last 14 days of notices; after that, only what's new.

## Architecture

```mermaid
flowchart LR
  cron["Supabase pg_cron<br/>:41 every hour, 06:11-01:11 IST"] -->|kick-run function| gha
  ghcron["GitHub cron (backup,<br/>skips if a run started &lt;50 min ago)"] --> gha
  check["Dashboard: Check now"] -->|check-now function| gha
  gha["GitHub Actions: Ping run<br/>python -m ping.run"] -->|GET pages and PDFs only,<br/>through the read-only gate| erp["IIT KGP ERP"]
  gha -->|read-only IMAP: OTP + placement mail| mail["Institute mailbox"]
  gha -->|notice fallback, 'For you' marks,<br/>CV summaries| gemini["Gemini (free tier)"]
  gha -->|service key| db[("Supabase Postgres<br/>roles, notices, pdf_checks, items,<br/>profile, chat, role_marks ...")]
  db --- storage[("Storage: cvs bucket<br/>owner only")]
  storage -->|new CVs, server-side| gha
  pages["GitHub Pages: ping-dashboard<br/>(built files only)"] -->|owner login or<br/>View demo (anonymous)| db
  pages -->|Ask Ping| askfn["ask-ping function"]
  askfn -->|the caller's own rows (RLS)| db
  askfn --> gemini
```

**The hourly cycle.** pg_cron calls `kick-run`, which starts the Ping workflow (GitHub's own schedule is a backup;
both skip if a run is going or started in the last 50 minutes). The run logs in (OTP from the mailbox), reads
the companies list, new notices and their PDFs (keeping only your row), checks the mailbox, logs out, then
rebuilds the feed: rules first, Gemini only where the rules can't read a notice, "For you" marks from one
cached classifier call, deadline digests and reminders. Everything is saved to Supabase; the dashboard reads it
with your login.

**When it fails.** ERP down or flaky: retried hourly; after 3 failed runs in a row one email and one chat
message, then "back online" when it works. Credentials refused: one email and chat message at once and the
schedule pauses until you start a run yourself. See [When Ping needs you](#when-ping-needs-you).

**The demo path.** "View demo" signs in anonymously; database rules give that session only the anonymised demo
rows (a made-up student over a real snapshot), its own chat, its own preferences and a rate limit (15
questions an hour). It can't start a run, read real rows, or reach the CV bucket. See
[docs/SECURITY.md](docs/SECURITY.md).

## Status (honest)

### Today's numbers (real runs, 21 Nov 2026)

| | |
|---|---|
| login, start to finish | **19.8 s**, of which **12.6 s** waiting for the OTP mail; Get OTP pressed once |
| companies list | **201 roles**, details read for all 201, 68 applied |
| notice board | **1,624 notices** seen, **260** read in full (the first run reads only the last 14 days) |
| attachments | **64 checked, 64 read: on the list 19 / not on it 45 / unreadable 0**; none were scanned |
| mailbox | 84 mails looked at, 10 kept as placement mail |
| whole run | 12 min, 742 ERP requests, every one through the read-only gate |
| repeats merged | 177 notice messages became **162**: 15 repeats merged, 39 real changes sent as updates (29 deadline moves, 10 time changes), 0 unsure |
| rooms re-read | **8 of 15** rooms saved earlier showed the neighbouring student's room (two students per line); fixed, and every run now re-reads saved rows |
| AI fallback | the rules couldn't read 1 notice; Gemini read it right (Tata AIG, Senior Engineer Trainee - Analytics, 17 Nov 16:00) |
| evals | held-out real notices **56 of 58 checks right (97%)**; development set 143 of 143 ([report](evals/PARSER_REPORT.md)); Ask Ping evals in [evals/ask_ping](evals/ask_ping/REPORT.md) |

### Works, verified on the real ERP / real project
- Login with security question and mailbox OTP, reading everything, logging out.
- Saving to Supabase; the dashboard login reads it (check run: database ok).
- "More details" popup (CGPA cut-off, backlog rule, written test) for all 201 roles.
- Ask Ping and Check now functions deployed and answering (Ask Ping falls back
  to simple rules when Gemini is busy).
- The one-click demo's database rules, tested on a local copy of Supabase (real
  Postgres, Supabase's roles): a demo session reads only demo rows, writes only its
  own chat, sees no other session's chat, and is limited to 15 questions an hour.
- Chat tables applied to the real project from GitHub (Actions > Admin > apply-sql).

### Not working or not verified yet
- **The hourly schedule hasn't fired once.** Every run so far was started by
  hand; checked again at 13:23 IST, the 13:11 slot didn't run although GitHub
  lists the workflow as active. See [What's left](#whats-left).
- **Login refusals.** Between 05:26 and 05:37 IST the ERP refused 5 Log Ins in
  a row after a valid OTP, with no message; it worked again at 12:05. Cause
  unknown (maybe too many OTPs in a short time while testing). This counts as
  normal ERP behaviour: Ping retries Log In once, then tries again at the next
  hourly run (see [When Ping needs you](#when-ping-needs-you)).
- **Company names the rules can't place.** 2 of 15 held-out notices: "JPMC"
  (JP MorganChase) and "ACCENTURE AEH". Ping asks "which company is that?"
  instead of guessing. Deliberately not tuned to the held-out set.
- **Eligibility** says "not sure" for most roles until your profile has your
  department and degree (the Profile page).
- **One-command setup** was tested against an empty Supabase-like database
  (real Postgres with Supabase's rules), not yet a brand-new real project.

### Known ways it can break
- The ERP changes a page. The run stops ("page changed") and emails you.
- If Supabase's scheduler misses a slot, GitHub's backup schedule may start it
  late (GitHub starts scheduled runs 5-15 min late, sometimes more, and skips
  some at busy times).
- Security questions: matching ignores capitals, spaces and punctuation and
  allows a one-or-two-letter typo, nothing more. If the ERP asks a question
  that matches none of your three, Ping stops and emails you the question.
- A notice about a company that isn't in your companies list is treated as not
  yours, unless the notice or its PDF names your roll number.
- Name-only shortlists are matched on the name in your profile; a different
  spelling gives a wrong "no".
- Gemini's free tier is sometimes slow or busy; Ping gives AI at most 5 minutes
  a run and falls back to rules.
- Supabase free projects pause after a week with no activity. Hourly runs keep
  it awake; if it ever pauses, open the project and press Restore.

---

## What's left

1. **Your profile:** department, degree, CGPA, backlogs (dashboard > Profile).
2. **The deploy token** (`DASHBOARD_DEPLOY_TOKEN`, see [Live dashboard](#live-dashboard))
   expires; renew it before then and save the new value under the same name.
3. **OTP mail filter:** in your institute Gmail, From `erpkgp@adm.iitkgp.ac.in`,
   Subject `OTP` > Create filter > Skip the Inbox + Mark as read. Ping searches
   All Mail, so it still finds them.

### Admin tasks (no Supabase screens needed)
Actions > **Admin** > Run workflow, pick a task:

| task | what it does |
|---|---|
| `apply-sql` | creates or updates all tables and rules from `sql/schema.sql`, then checks them |
| `build-demo` | builds the anonymised demo from your real data, checks it for your roll number, email, name and any other roll or phone number (writes nothing if it finds one), loads it as the demo rows, reads them back and checks them again, commits `dashboard/demo-data.json` and starts the dashboard deploy |
| `gemini-check` | one test call to Gemini, then retries the notices the rules couldn't read, printing every model's answer |
| `functions-check` | the Ask Ping / Check now functions on Supabase: deployed version, which secrets they have (names only), every request and crash from the last 23 hours, and two test questions from a demo session |
| `ask-ping-page` | opens the **live** dashboard in a real browser: checks the owner sign-in screen (without signing in), clicks View demo, confirms the demo session gets 0 real rows, types "slice ctc breakdown" and "what's due tomorrow", then "any tests today?" followed by "anything else?" and "nothing else?" (follow-ups that need the conversation), and prints the replies |
| `ask-ping-evals` | runs the Ask Ping evals from demo sessions and commits `evals/ask_ping/REPORT.md` |
| `auth-config` | Supabase Auth for the live dashboard: Site URL and redirect list, anonymous sign-ins on |
| `demo-clock` | sets the one-click demo's "now" to the snapshot time in `dashboard/demo-data.json` (the demo shows, and Ask Ping answers, as of that time) without rebuilding the demo |
| `cleanup-demo` | deletes demo sessions older than 7 days and their chat (also runs daily, from Supabase's scheduler) |
| `schedule-setup` | sets up the hourly start in Supabase: a new shared secret for `kick-run` (function secret + database Vault), the two scheduled jobs from `sql/schedule.sql`, then a dry run of kick-run that starts nothing |
| `schedule-status` | lists the scheduled jobs, their last 10 runs in Supabase, and the last Ping runs on GitHub with what started each |
| `rearm-schedule` | switches the Ping workflow off and on through the API so GitHub re-registers its backup schedule |

---

## Live dashboard

**https://vin1764.github.io/ping-dashboard/**

Two repositories, so this one can stay private:

- **This repo (private)** has the code, the settings and the history. On every
  push that touches the dashboard (and after Admin > build-demo), Actions >
  Dashboard builds the static site and runs a guard over the built files
  (`setup/check_public_build.py`): it stops the deploy if they contain a Supabase
  secret or service key, a Google key, "+91", any 10-digit number outside the
  made-up 90000 range, your roll number or email, a banned word, or any file other
  than the eight expected.
- **[vin1764/ping-dashboard](https://github.com/vin1764/ping-dashboard) (public)**
  holds **only the built files**: `index.html`, `app.js`, `style.css`, `config.js`
  (the Supabase URL and publishable key, which are public by design),
  `demo-data.json` (anonymised), `.nojekyll` and a short README. Each deploy
  force-pushes one commit ("build <sha> from private repo"), so only the current
  build is ever public. GitHub Pages serves its `main` branch.
- The push uses `DASHBOARD_DEPLOY_TOKEN` (this repo's Actions secret): a
  fine-grained token for ping-dashboard only, with Contents and Pages read/write.
  Pages is switched on once by hand (doing it through the API needs Administration:
  write on the token): open **github.com/vin1764/ping-dashboard > Settings > Pages**;
  under Build and deployment, Source: **Deploy from a branch**; Branch: **main**,
  folder **/ (root)**; press **Save**. The deploy then waits until the new build
  is live.
- **The Custom domain box on that Pages screen must stay empty.** With a domain
  there, github.io redirects to it and GitHub commits a CNAME file into the public
  repo; the dashboard's sign-in redirects only allow the github.io address.
- Supabase Auth's Site URL and redirect list point at the live URL (Admin >
  auth-config); localhost stays allowed for development.

---

## How it runs

GitHub Actions (free for private repos: 2,000 minutes/month) runs
`python -m ping.run` every hour from 06:11 to 01:11 IST, 20 times a day (minute
41 UTC, away from the top of the hour when GitHub is busiest).

**What starts it:** Supabase's own scheduler (pg_cron, in the database) calls the
`kick-run` function at :41 UTC, 00:41-19:41, and kick-run presses Run workflow
on the Ping workflow (with the same token as Check now). GitHub's own schedule
(the `cron` line in `ping.yml`) stays as a backup. Both skip if a Ping run is
already going or one started in the last 50 minutes, so a slot never runs twice.
The daily demo cleanup runs on the same scheduler (21:23 UTC). Set up and checked
with Admin > `schedule-setup` and `schedule-status`. The first run
took 12 minutes; later runs only read what's new, so expect 1-3
minutes, roughly 600-1,800 minutes a month.

To run it yourself: **Actions > Ping > Run workflow**, pick a mode:

| mode | what it does |
|---|---|
| `run` | a normal run |
| `check` | only checks the secrets and the database, no ERP login |
| `probe` | logs in and prints the layout of one "more details" popup (company info only), for fixing the reader if the ERP changes it |
| `load-sample` | puts the made-up sample data into the database (for a fresh copy; the anonymised demo comes from Admin > build-demo) |
| `remove-sample` | removes exactly the demo rows again |

The dashboard's **Check now** button presses the same button.

### One run, start to finish
1. Log in: send your roll number, read the security question, pick the
   matching stored answer, press Get OTP, read the OTP from your mailbox
   (only mails that arrived after the click; press Get OTP once more if
   nothing comes in 3 minutes), log in.
2. Open CDC > Application of Placement/Internship. Read the companies list.
   For roles not seen before, read the role popup and its "more details".
3. Read the notice board. First run: only the last 14 days. After that, only
   notices not seen before. Read each new notice's full text.
4. Download attachments: yours first (companies you applied to or are
   eligible for), then other shortlists/schedules. Search each for your roll
   number, then your name. Keep only your row and the table heading.
5. Log out.
6. Look in your mailbox (read-only) for placement mail since the last run.
7. Rebuild the feed and save everything to Supabase. Stored notices and the
   saved rows from PDFs are re-read with the current rules every time, so a
   fix to the rules also corrects older messages.

## The feed

Every item has a level and a one-line title (under 160 characters):

| level | what |
|---|---|
| `always` | anything about a role you applied to (shortlist, test, extension, result), or anything that names your roll number |
| `show` | eligible, not applied, deadline ahead, not marked not-interested ("apply by X", shown on the Feed and Companies pages; in the chat these roles come as digests, below); "is this notice about X?" questions |
| `hidden` | kept but not shown: not eligible, deadline gone, not interested, not yours, tests that finished 12h+ ago, list news older than 3 days |

Which role a notice is about: the role named in the text; else, for tests and
shortlists, the roles you applied to whose selection details say there's a
written test; else all roles at that company you applied to. If Ping isn't
reasonably sure which company it is, it asks instead of guessing.

**Eligible** = CGPA at or above the cut-off (none = yes), your degree +
department in the allowed list (empty list = yes, flagged), and the backlog
rule ("Candidates should not have any active backlogs.") doesn't rule you out.
If the ERP itself says "Company requirement has CGPA cut off greater than
yours", that's a no.

If a notice gives a later deadline than the companies list, the notice wins
(the item says where the deadline came from).

**Only what's really new.** The same news often arrives two or three times.
Same company + same kind (apply / form / test / shortlist / extension / talk)
+ same deadline (or same date and venue) within 4 days is one message; later
copies are kept hidden with a note. An email that repeats a notice merges into
that notice's message (its links are kept). A real change (deadline moved,
time or venue changed, you're now on the list) becomes one **Update** message
that says what changed. Notices naming different profiles stay separate. When
unsure, Ping treats them as the same and keeps a note. On the last 14 days of
real notices this merged 15 repeats and sent 39 changes as updates; each run's
summary reports its own counts.

**Fewer, fuller messages** (`ping/digests.py`). Roles never get a card each in
the chat:

| message | when |
|---|---|
| **New roles** | once per run: "5 new roles listed at 3 companies", each with its close time (one role: a message of its own) |
| **Deadline digest** | once per batch (same kind: application / form / test, same close date and time), when it comes within 24 hours: "15 applications close tonight, Sat 21 Nov 20:00 — you've applied to none", then the list. Not sent if that run's new-roles message already listed the whole batch |
| **Reminder** | once, *N* hours before the batch closes (Profile: "Remind me before a deadline", default 2), listing only what you still haven't applied to |
| **Update** | once per change to an announced batch: a deadline extension moves roles to another time, or a role is added that no new-roles message announced. Never a second full digest |
| **Lists out** | several shortlists or test lists in one run: "3 shortlists out: ..." |

Nothing is sent on the other hourly runs: every message has a fixed id and keeps
what it said when it was first sent. Each list ends with its source: "ERP check
17:50 · companies list · notices 1791, 1795". Tested in `tests/test_digests.py`
(same-deadline grouping, reminder timing over a day of hourly runs, an extension
as one update, nothing repeated).

**For you first** (`ping/relevance.py`). On the Profile page, "What I'm looking
for" takes your own words: the kinds of roles you want and any you don't. For
every role you're not ruled
out of, once, Gemini reads its company, title and job description and answers
yes/no with a reason of at most 8 words; the answer is cached on the role and
asked again only when the role's text or your words change. Eligibility is
applied first and is never overridden. A role with no job description on the ERP
is judged on its title and tagged "(JD missing)". Every list (digests, new
roles, Ask Ping answers) then shows **For you** first, with the reason in grey,
and **Others** one line per role (collapsed). Untick "Always list other roles
separately" to see only their count. "Eligibility not verified for ..." is added
when the ERP data or your profile is incomplete. Gemini sees only the roles' own
text and your targets, never your name, roll number, CGPA or mail.

## The dashboard

`dashboard/` is a plain web page (HTML + JavaScript, no build step). It opens on
**a chat with Ping**, like WhatsApp:

- Every "for you" item is a message from Ping, newest at the bottom, in the
  order the CDC posted them. Labels: **You applied** (about a role you applied
  to), **Open for you** (you can still apply), **Question** (Ping isn't sure
  which company a notice means; tap to answer). Tap a message to see the details (deadline, venue, your row from the
  PDF, eligibility, contacts) and links to the notice, the PDF and any form.
- Type at the bottom: "what's due tomorrow", "did I apply to Accenture",
  "which room for the Eternal test", "slice ctc breakdown". Gemini answers on
  the server (the key is a Supabase function secret and never reaches the
  browser), from your feed, your roles and, for companies you name, the pay and
  bond details from the ERP's "more details". If Gemini is slow or busy, simple
  rules answer instead and the reply says so. Supabase stops a function after
  150 s; Ask Ping gives Gemini at most 100 s (45 s per model).
- The thread is saved (the `chat_messages` table), so you see the whole
  history when you come back. New messages since your last visit get an
  "unread" marker (on a first visit, only the last day counts as unread).
- When a deadline moves or a venue changes, Ping posts one **Update** message
  saying what changed; the earlier message stays, greyed and marked "Since updated".
  Things that are over stay in the history, greyed ("Deadline passed", "Over").
- **Navigation:** a bottom bar on phones, a slim left rail on desktop: Chat ·
  Companies (every role, a search box, filters For you / Applied / Closing soon /
  All, and a sheet per role with pay, eligibility, deadlines, notices and source) ·
  Profile (cards edited in place; Account has Check now, All updates, the theme
  and sign out). Look and feel: [docs/DESIGN.md](docs/DESIGN.md).
- **View demo** (sign-in screen): a one-click anonymous session on the anonymised
  snapshot, with a "Demo - sample data, read-only" chip; its chat is kept for that
  session. `?demo=1` opens the same snapshot from a file, without the database. Both
  show the snapshot as it was when it was taken (a note above the unread messages says so).

Real data needs a login. The page reads your Supabase directly with the
publishable key (that key is meant to be public), and database rules only let
emails in the `allowed_users` table see your data; a one-click demo session
(anonymous sign-in) sees only the demo rows (`is_sample = true`) and its own chat, and
can't change anything (`sql/demo.sql`). Check now and the AI answers
run as two small Supabase functions (`supabase/functions/`) that hold the
GitHub token and the Gemini key, and check that the caller is you.

PDF links open the file on the ERP itself, so they work when you're logged in
to the ERP in the same browser. Ping never stores whole PDFs.

## Your profile

One row in the `profile` table, edited from the dashboard:

| field | example |
|---|---|
| roll | leave empty to use your ERP user id |
| name | only used when a PDF has names but no roll numbers |
| department | your department exactly as the ERP writes it (the dashboard suggests the exact spellings) |
| degree | `B.TECH`, `DUAL DEGREE`, `M.SC(5YR)`, ... |
| CGPA | `8.12` |
| active backlogs | yes / no |
| CV names | your 3 CVs |
| interested / not interested | company names; not-interested companies' roles are hidden |

Whether you applied isn't in the profile. It comes from the companies list
(Application Status = Y).

## Safety

**Read-only.** On this ERP, applying is a plain page visit
(`TPJNFViewAction.jsp?mode=ApplyCV1...`), and the notice data carries
"Upload" and "Deactivate" links. So Ping doesn't rely on "only reading
pages". Every request goes through one gate (`ping/gate.py`) with an exact
list of the addresses and fields Ping may send. Anything else is refused
before it leaves, including redirects. A second list blocks words like
apply/upload/accept/save/submit in any address, and a test fails if the code
ever mentions an action page. The mailbox is opened read-only (Ping can't
even mark a mail as read). Login steps are never retried automatically; reads
are retried on network errors.

**Every ERP address Ping may contact** (everything else is refused before it leaves):

| when | address (on erp.iitkgp.ac.in) | what it is |
|---|---|---|
| logging in | `GET /IIT_ERP3/` | open the ERP (also its redirect back after login) |
| | `GET /SSOAdministration/login.htm` | the login page |
| | `POST /SSOAdministration/getSecurityQues.htm` | send your roll number, get the security question |
| | `POST /SSOAdministration/getEmilOTP.htm` | press Get OTP (sends user id, password, answer) |
| | `POST /SSOAdministration/auth.htm` | press Log In with the OTP |
| | `GET /SSOAdministration/success.htm` | the ERP's own redirect after Log In |
| | `GET /IIT_ERP3/home.htm` | ERP home page |
| opening placement | `POST /IIT_ERP3/showmenu.htm` | CDC > Application of Placement/Internship only (module 26, menu 11, that one link) |
| | `POST /TrainingPlacementSSO/TPStudent.jsp` | the companies page (module 26, menu 11 only) |
| reading | `GET /TrainingPlacementSSO/ERPMonitoring.htm` | the data behind the companies list (37) and notice board (54); only `action=fetchData` |
| | `GET /TrainingPlacementSSO/TPJNFView.jsp` | a role's details popup (`user_type=SU` only) |
| | `GET /TrainingPlacementSSO/JnfMoreDet.jsp` | a role's "more details" (`mode=jnfMoreDet` only) |
| | `GET /TrainingPlacementSSO/Notice.jsp` | the notice board page (no parameters allowed) |
| | `GET /TrainingPlacementSSO/ShowContent.jsp` | the full text of one notice |
| | `GET /TrainingPlacementSSO/AdmFilePDF.htm` | a notice's attachment (`type=NOTICE` only) |
| leaving | `GET /IIT_ERP3/logout.htm` | log out |

The only things Ping ever sends are the login steps (pressing Get OTP makes the
ERP email you an OTP) and logging out. Refused by name, among others:
`TPJNFViewAction.jsp` (applying, accepting/cancelling offers), `TPFile.jsp`
(uploads), `Notice.jsp?mode=deactive`, CV pages, NOC, feedback. Each run's log
ends with every address it actually visited and how many times.

**Secrets.** Passwords and keys live only in GitHub Secrets (encrypted, hidden
in logs, not copied when someone copies the repo), in Supabase function
secrets (GitHub token, Gemini key) and, on a laptop, in a `.env` file that git
ignores. Nothing is in the code. Each student uses their own repo, their own
secrets and their own Supabase project.

**Other students' data.** PDFs contain hundreds of other students' names.
Ping keeps only your own row and the table heading, and logs only the *shape*
of a file (pages, characters, which headings), never its contents. Captures
from the capture script are never committed.

**What goes to Gemini.** For hard notices (rules found nothing): only that
notice's text, at most 20 calls a run. For Ask Ping: your own feed titles,
your roles list and your profile, never PDFs or other students' data. Gemini's
free tier may use what it's sent to improve Google's models.

**Trade-off to know:** the OTP exists so that a password alone isn't enough.
Ping holds both your ERP password and access to your mailbox, so your GitHub
account is now the key to your ERP. Keep two-factor login on for GitHub.

## When Ping needs you

Two kinds of failed run are handled differently (`ping/run.py`):

| what happened | what Ping does |
|---|---|
| **The ERP is down or flaky:** unreachable, blank login page, Log In not accepted, no OTP mail | Nothing visible at first, and the schedule never pauses: the next hourly run tries again. After **3 failed runs in a row**: one email and one chat message, "Couldn't reach the ERP for the last 3 runs; I'll keep trying hourly." Once per streak. When a run works again: one chat message, "Back online". |
| **The ERP refused who you are:** wrong user id, password or security answer refused (no OTP sent), a security question none of your 3 answers match | **At once:** one email and one chat message saying what was refused, and the hourly runs **pause** (so the account isn't locked by repeated tries). Fix the secret, then start a run yourself (dashboard Profile > Account > Check now, or Check now on the desktop rail, or Actions > Ping > Run workflow); a run you start resumes the schedule. |

Ping sends these emails from your institute mailbox to itself. It also emails
(at most once a day) if the database isn't set up. Scheduled runs that fail
finish green on GitHub, so GitHub doesn't add its own "run failed" email every
hour; runs you start yourself still show red when they fail. The dashboard has
no "last run failed" banner; these chat messages replace it.

## AI for hard notices

Rules go first. Only when they find no deadline in a CV/extension/form notice,
or no companies in a "Multiple Companies" notice, is the notice sent to Gemini
(the `GEMINI_API_KEY` secret; model `gemini-flash-latest`, then
`gemini-flash-lite-latest`, then `gemini-2.0-flash` when one is retired, busy
or slow; at most 20 calls and 5 minutes a run). Each run's summary counts how
often that happened and the last error. Google retired `gemini-2.5-flash` for
new keys in November 2026, which is what the first run's one AI error was. To use another provider, set the variables `PING_AI_PROVIDER`,
`PING_AI_BASE_URL`, `PING_AI_MODEL` and the secret `PING_AI_KEY` (see `ping/ai.py`).

## Another student setting it up

One command, about 5 minutes, and you never open Supabase's SQL editor or login screens.

Before you start (all free, about 10 minutes): your ERP login and its 3 security questions, a
Google app password for the mailbox the ERP sends OTPs to
(`myaccount.google.com/apppasswords`, needs 2-step verification), a new
Supabase project plus a personal access token (supabase.com > avatar >
Account > Access Tokens), and your own **private** copy of this repo.

```bash
python -m pip install --user -r requirements.txt
```
```bash
python setup/new_student_setup.py
```

It asks for each value one at a time, saves them in `.env` (only you can
read it; git ignores it), creates all tables and permissions, creates your
dashboard login (confirmed) and puts it on the allowed list, signs in as that
login to prove it works, does one test ERP login, sets the GitHub secrets
(with the GitHub CLI if you have it, otherwise it prints each name and value
to paste), and ends with "Done. Open <link> and sign in with <email>".
Running it again is safe (it keeps what you typed and can reset the password).

It was tested against an empty Supabase-like database (real Postgres with
Supabase's roles and rules), not yet against a brand-new real Supabase project.

## Demo data

The demo is built from your real data by **Actions > Admin > build-demo**
(`ping/demo_from_real.py`):

- **Kept as they are:** company names, roles, pay, deadlines, notice wording,
  and your applied / not-applied list (so applied, shortlisted, test room
  still hold together).
- **Replaced:** your roll number (`22XY10042`), name (`Demo Student`) and
  CGPA (8.0); your CGPA is removed from every sentence.
- **Removed:** every other student's name, roll number and phone number (in
  notices, contact lines, lists of selected students and PDF rows), and
  everything from your mailbox.
- **Checked before anything is written:** the finished data is searched for
  your real roll number, email and name, and for anything shaped like a roll
  or phone number. If one is found, nothing is written.

It is loaded into the database as demo rows (`is_sample = true`, only demo
sessions see them; real runs never read them) and committed as
`dashboard/demo-data.json` for the no-login demo. A fresh copy of the project
that hasn't built one yet falls back to made-up sample data (`ping/sample.py`).

## Files

| path | what |
|---|---|
| `ping/gate.py` | the read-only allow list every ERP request goes through |
| `ping/erp.py` | login and the reads |
| `ping/mailbox.py` | read-only mailbox (OTP, placement mail) |
| `ping/parsers.py` | companies list, role popups, "more details", notices |
| `ping/notices.py`, `ping/dates.py`, `ping/matching.py` | what a notice means, dates, which company |
| `ping/pdfs.py` | is your roll number in the attachment |
| `ping/eligibility.py`, `ping/items.py` | eligibility and the feed |
| `ping/dedupe.py` | merging repeats, turning real changes into updates |
| `ping/store.py`, `sql/schema.sql` | Supabase tables and database rules |
| `ping/run.py` | one run, start to finish |
| `ping/ai.py` | Gemini fallback for hard notices |
| `ping/probe.py` | layout check of the "more details" popup |
| `ping/demo_from_real.py` | the anonymised demo built from your real data |
| `ping/sample.py` | made-up sample data (fallback) |
| `ping/admin.py`, `ping/supabase_admin.py` | Admin tasks: tables, Auth settings, demo, evals, checks |
| `dashboard/` | the dashboard (`build.sh` builds it into `_site/`) |
| `supabase/functions/` | Check now and Ask Ping server functions |
| `setup/capture_erp.py` | one-time page capture used to build Ping |
| `setup/new_student_setup.py` | setup for the next student |
| `evals/` | parser evals (real notices, PDF layouts) and Ask Ping evals (`ask_ping/`); `REPORT.md` is the index |
| `tests/` | offline tests, including a full run against a fake ERP and setup against a fake Supabase |

Run the tests: `python -m pip install -r requirements-dev.txt && python -m pytest -q`.
