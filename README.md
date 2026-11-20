# Ping

Ping logs into the IIT Kharagpur ERP for you every hour, reads the placement
companies list, the CDC notice board, the PDFs attached to notices and your
institute mailbox, and keeps only what is about **you**:

- "Accordion opened, eligible for Data & AI Analyst (CG 7+, all depts). Apply by Fri 16:00."
- "You're on the Pine Labs shortlist (SDE). Test Sat 10:00, Nalanda, room V2."
- "Pine Labs shortlist is out (SDE). You're not on it."
- "ICICI Lombard (Actuarial Analyst): fill the form by Sat 16:00."

Everything goes into your own Supabase database, and a small dashboard shows it.

**Try the demo (made-up data, no login):** https://claude.ai/artifact/TWGCZxEawg7zZrrjSDnur7
(the owner has to share it from its Share menu before other people can open it).
Once GitHub Pages is on, the same demo is also at `https://vin1764.github.io/Ping_ERPbot/?demo=1`.

It **only reads**. It cannot apply, submit, upload or accept anything (see [Safety](#safety)).

---

## Status (honest)

### Verified on the real ERP (first real run, 21 Nov 2026, 05:01 IST)

| | |
|---|---|
| login, start to finish | **16.9 s**, of which **11.9 s** waiting for the OTP mail; Get OTP pressed once |
| OTP mail | from `erpkgp@adm.iitkgp.ac.in`, code in the subject line |
| companies list | **201 roles** seen, 201 new (first run), 65 applied; 0 popup failures |
| notice board | **1,624 notices** seen, **262 new** (first run reads only the last 14 days); rules unsure on 1 |
| attachments | **64 checked, 61 read: yes 17 / no 44 / unknown 0**; all were real text PDFs (none scanned); 3 failed to download (brief network errors, now retried) |
| mailbox | 60 mails looked at, 8 kept as placement mail |
| whole run | 11 min, 744 ERP requests, all through the read-only gate |

Also verified for real:
- The "more details" popup's layout (read on 2 roles in a probe run). Its
  first reader was wrong and came back empty for all 201 roles; the reader is
  now rewritten for the real layout and tested, but **not yet re-run on the ERP**.
- The Gemini key works (it turned "five in the evening on the twenty-second of
  November, 2026" into 22 Nov 17:00).
- The "database not set up" email reached the mailbox.

### Verified on copies of real pages (your capture) and in tests
- Reading the companies list, role popups (designation, pay, CGPA cut-off,
  allowed departments, the ERP's own "cut-off greater than yours" warning),
  the notice board and a notice's full text.
- Dates from real notice wording ("till 4:00 PM, 21st November, 2026",
  "Deadline: 21st November 2026, 4:00 PM", "by 5:00 PM today", "scheduled from
  7:15 PM onwards on 19th November, 2026", schedule lists like
  "(12:30 AM  1:30 AM, 10th November)").
- "Multiple Companies" notices split into one item per company.
- Company names: exact name first, then the same name ignoring capitals, then
  loose matching. In the capture, of 385 notices about a company in your list,
  138 used the exact name, 139 differed only in capitals and 102 were
  shortened ("NAVI" for "Navi Limited"). Real ambiguity ("Accenture" when
  there are three Accenture entities) becomes an "is it about X?" question.
- The read-only gate refuses every action address found in the real pages.
- The dashboard, in demo mode, clicked through in a real browser.

### Not verified yet
- **Saving to Supabase**: the tables don't exist yet, so nothing real has been saved.
- **The dashboard with real data, its login, Check now and Ask Ping**: they
  need the tables, a login and the two functions deployed (see
  [What's left for you](#whats-left-for-you)).
- **Room / slot / time from your rows in real PDFs**: 17 real "yes" results,
  but the first run didn't log which table headings were found. The next run
  logs the headings (never anyone's names).
- **Eligibility on real roles**: needs your profile (department, degree, CGPA).

### Known ways it can break
- The ERP changes a page. The run stops ("page changed") and emails you.
- GitHub starts scheduled runs late (5-15 min, sometimes more) and now and
  then skips one at busy times.
- Security questions: matching ignores capitals, spaces and punctuation and
  allows a one-or-two-letter typo, nothing more. If the ERP asks a question
  that matches none of your three, Ping stops and emails you the question.
- A notice about a company that isn't in your companies list is treated as not
  yours, unless the notice or its PDF names your roll number.
- Name-only shortlists are matched on the name in your profile; a different
  spelling gives a wrong "no".
- Supabase free projects pause after a week with no activity. Hourly runs keep
  it awake; if it ever pauses, open the project and press Restore.

---

## What's left for you

1. **Create the tables:** Supabase > SQL Editor > New query > paste all of
   [`sql/schema.sql`](sql/schema.sql) > Run. Until then the hourly runs skip
   themselves (to save free minutes) and email you once a day.
2. **Your profile:** department, degree, CGPA, backlogs (in the dashboard's
   Profile page, or Supabase > Table Editor > profile).
3. **Dashboard login:** Supabase > Authentication > Users > Add user > your
   institute email (the `MAIL_ADDRESS` secret) + a password, tick Auto Confirm.
   Then in Authentication > Sign In / Providers, turn **off** "Allow new users to sign up".
4. **Host the dashboard:** Settings > Pages > Source: **GitHub Actions**, then
   Actions > Dashboard > Run workflow. Private repos need GitHub Pro, which is
   free with the GitHub Student Developer Pack. If that's not available, any
   free static host works: connect the repo to Cloudflare Pages or Netlify,
   build command `bash dashboard/build.sh`, output folder `_site`, environment
   variables `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`.
5. **Check now + Ask Ping** (optional): add two repo secrets, then run
   Actions > Dashboard:
   - `SUPABASE_ACCESS_TOKEN`: Supabase > Account > Access Tokens > Generate.
   - `PING_GITHUB_TOKEN`: GitHub > Settings > Developer settings > Fine-grained
     tokens > only this repository > Repository permissions > **Actions: Read and write**.
6. **OTP mail filter:** in your institute Gmail, From `erpkgp@adm.iitkgp.ac.in`,
   Subject `OTP` > Create filter > Skip the Inbox + Mark as read. Ping searches
   All Mail, so it still finds them.

---

## How it runs

GitHub Actions (free for private repos: 2,000 minutes/month) runs
`python -m ping.run` every hour from 06:07 to 01:07 IST, 20 times a day. The
first run took 11 minutes; later runs only read what's new, so expect 1-3
minutes, roughly 600-1,800 minutes a month.

To run it yourself: **Actions > Ping > Run workflow**, pick a mode:

| mode | what it does |
|---|---|
| `run` | a normal run |
| `check` | only checks the secrets and the database, no ERP login |
| `probe` | logs in and prints the layout of one "more details" popup (company info only), for fixing the reader if the ERP changes it |
| `load-sample` | puts the made-up demo data into the database |
| `remove-sample` | removes exactly the demo data again |

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
7. Rebuild the feed and save everything to Supabase.

## The feed

Every item has a level and a one-line title (under 160 characters):

| level | what |
|---|---|
| `always` | anything about a role you applied to (shortlist, test, extension, result), or anything that names your roll number |
| `show` | eligible, not applied, deadline ahead, not marked not-interested ("apply by X"); the 24h reminder (it replaces the "apply by" item); "is this notice about X?" questions |
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

## The dashboard

`dashboard/` is a plain web page (HTML + JavaScript, no build step):

- **For you:** your items, newest first, with the one-line summary, the
  deadline, links to the notice and the PDF, and a filter for the three levels.
  "Is it about X?" questions get one-click answers that the next run uses.
- **Companies:** a page per company with its roles, whether you applied, the
  deadline, the pay and your eligibility (with the reasons).
- **Profile:** roll, department, degree, CGPA, backlogs, CV names,
  interested / not-interested companies.
- **Check now:** starts a run.
- **Ask Ping:** "what's due tomorrow?", "did I apply to Accenture?". Answered
  by Gemini on the server (the key never reaches the browser). In demo mode,
  or if the server function isn't set up, it answers with simple rules.
- **Demo mode** (`?demo=1`): made-up data, no login, nothing saved.

Real data needs a login. The page reads your Supabase directly with the
publishable key (that key is meant to be public), and database rules only let
emails in the `allowed_users` table see anything. Ping adds your
`MAIL_ADDRESS` there on every run. "Check now" and "Ask Ping" run as two small
Supabase functions (`supabase/functions/`) that hold the GitHub token and the
Gemini key, and check that the caller is you.

PDF links open the file on the ERP itself, so they work when you're logged in
to the ERP in the same browser. Ping never stores whole PDFs.

## Your profile

One row in the `profile` table, edited from the dashboard:

| field | example |
|---|---|
| roll | leave empty to use your ERP user id |
| name | only used when a PDF has names but no roll numbers |
| department | `COMPUTER SCIENCE AND ENGINEERING` (as the ERP writes it; the dashboard suggests the exact spellings) |
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

It emails you (from your institute mailbox to itself) at most once a day per
problem: database not set up, a security question it doesn't recognise, login
failing twice in a row, the ERP refusing the OTP.

## AI for hard notices

Rules go first. Only when they find no deadline in a CV/extension/form notice,
or no companies in a "Multiple Companies" notice, is the notice sent to Gemini
(the `GEMINI_API_KEY` secret; model `gemini-2.5-flash`, falling back to newer
names if Google retires it). Each run's summary counts how often that
happened. To use another provider, set the variables `PING_AI_PROVIDER`,
`PING_AI_BASE_URL`, `PING_AI_MODEL` and the secret `PING_AI_KEY` (see `ping/ai.py`).

## Another student setting it up

1. Make your own **private** copy of this repo.
2. Create a free Supabase project and run `sql/schema.sql` in its SQL Editor.
3. Get a Google app password for your institute mailbox
   (`myaccount.google.com/apppasswords`; 2-step verification has to be on).
4. On your laptop: `python -m pip install --user -r requirements.txt`, then
   `python setup/new_student_setup.py`. It asks for everything one by one,
   saves it to `.env` (readable only by you), does one test login, and tells
   you what to paste where on GitHub and how to set up the mail filter.
5. Follow steps 2-6 of [What's left for you](#whats-left-for-you).
6. Actions > Ping > Run workflow.

## Demo data

`load-sample` (Run workflow button, or `python -m ping.run --mode load-sample`)
loads made-up companies, notices, shortlist results and a full feed into the
database. Every demo row has `is_sample = true`; `remove-sample` deletes
exactly those, and a real profile is never overwritten. The dashboard's demo
mode doesn't need this: it reads `demo-data.json`, built by
`python -m ping.sample dashboard/demo-data.json`.

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
| `ping/store.py`, `sql/schema.sql` | Supabase tables and database rules |
| `ping/run.py` | one run, start to finish |
| `ping/ai.py` | Gemini fallback for hard notices |
| `ping/probe.py` | layout check of the "more details" popup |
| `ping/sample.py` | demo data |
| `dashboard/` | the dashboard (`build.sh` builds it into `_site/`) |
| `supabase/functions/` | Check now and Ask Ping server functions |
| `setup/capture_erp.py` | one-time page capture used to build Ping |
| `setup/new_student_setup.py` | setup for the next student |
| `tests/` | offline tests, including a full run against a fake ERP |

Run the tests: `python -m pip install -r requirements-dev.txt && python -m pytest -q`.
