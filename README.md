# Ping

Ping logs into the IIT Kharagpur ERP for you every hour, reads the placement
companies list, the CDC notice board, the PDFs attached to notices and your
institute mailbox, and keeps only what is about **you**:

- "Accordion opened, eligible for Data & AI Analyst (CG 7+, all depts). Apply by Fri 16:00."
- "You're on the Pine Labs shortlist (SDE). Test Sat 10:00, Nalanda, room V2."
- "Pine Labs shortlist is out (SDE). You're not on it."
- "ICICI Lombard (Actuarial Analyst): fill the form by Sat 16:00."

Everything goes into your own Supabase database, for a dashboard to show
(the dashboard is a separate project).

It **only reads**. It cannot apply, submit, upload or accept anything (see
[Safety](#safety)).

---

## Status (honest)

_Last updated after the first real runs; see "Real run results" below._

**Works and verified on the real ERP**
- see "Real run results" below

**Works, verified only against copies of real pages (your capture) and tests**
- Reading the companies list (all ~200 rows come in one response), role
  popups (designation, pay, CGPA cut-off, allowed departments, the ERP's own
  "cut-off greater than yours" warning), the notice board (all ~1,600 notices
  in one response) and the full text of a notice.
- Deadline and event times from real notice wording (tested on the phrasings
  that actually occur: "till 4:00 PM, 21st November, 2026", "Deadline: 21st
  November 2026, 4:00 PM", "by 5:00 PM today", "scheduled from 7:15 PM onwards
  on 19th November, 2026", schedule lists like "(12:30 AM  1:30 AM, 10th November)").
- Splitting "Multiple Companies" notices into one item per company.
- Matching notice names to companies-list names: on the 760 placement
  notices in the capture, 390 matched with confidence, 117 were generic
  (read from the text), 15 were genuinely ambiguous (e.g. "Accenture" when
  there are three Accenture entities) and become "is it about X?"
  questions, and the rest name companies that aren't in your companies list.
- The read-only gate refuses every action address found in the real pages.

**Assumed (not seen yet, built from your description)**
- The "Click Here for more details" popup (`JnfMoreDet.jsp`) was not in the
  capture. It is read generically as `label: value` lines and its raw text is
  stored, so the backlog rule / CGPA criteria / selection details can be
  re-read later without fetching again.
- PDFs: the capture contained no real PDF bytes (Chrome's PDF viewer swallowed
  them; the capture script is fixed now). Shortlist/room-list reading is
  tested on generated PDFs and Excel files that look like typical CDC lists.
  Each real run logs the *shape* of every attachment (pages, text length,
  scanned or not) so this can be checked without printing anyone's name.
- The OTP email's exact wording: Ping accepts any mail after the Get OTP click
  that mentions "OTP" and contains a 4-8 digit code.

**Known ways it can break**
- The ERP changes a page. The run stops with "page changed" and emails you.
- GitHub runs scheduled jobs late (5-15 min, sometimes more) and occasionally
  skips one at busy times.
- Security questions: matching ignores capitals, spaces and punctuation and
  allows a one-or-two-letter typo, nothing more. If the ERP shows a question
  that matches none of your three, Ping stops and emails you the question.
- A notice about a company that isn't in your companies list is ignored
  (it isn't yours), unless the notice or its PDF names your roll number.
- Shortlists that list names only (no roll numbers) are matched on your name
  from the profile; spelling differences will cause a "no".
- Room/slot/time extraction from a PDF depends on the table having headings
  like Room/Venue/Slot/Time. Otherwise you get "you're on it" without a room.
- Supabase free projects pause after a week with no activity; hourly runs
  keep it awake. If it does pause, open the project and press Restore.

---

## How it runs

GitHub Actions (free for private repos: 2,000 minutes/month) runs
`python -m ping.run` every hour from 06:07 to 01:07 IST, 20 times a day.
A run takes about 1-2 minutes after the first one, so a month uses roughly
600-1,200 minutes.

To run it yourself: **GitHub > your repo > Actions > Ping > Run workflow**,
pick a mode, press the green button:

| mode | what it does |
|---|---|
| `run` | a normal run |
| `check` | only checks the secrets and the database, no ERP login |
| `load-sample` | puts demo data (made-up companies) into the database |
| `remove-sample` | removes exactly the demo data again |

The dashboard can press the same button later through GitHub's API
(`workflow_dispatch` on `ping.yml`).

### One run, start to finish
1. Log in: send your roll number, read the security question, pick the
   matching stored answer, press Get OTP, read the OTP from your mailbox
   (only mails that arrived after the click; press Get OTP once more if
   nothing comes in 3 minutes), log in.
2. Open CDC > Application of Placement/Internship. Read the companies list.
   For roles not seen before, read the role popup and its "more details".
3. Read the notice board. First run: only the last 14 days. After that:
   only notices not seen before. Read each new notice's full text.
4. Download attachments: yours first (companies you applied to or are
   eligible for), then other shortlists/schedules. Search each for your roll
   number, then your name. Keep only your row and the table heading.
5. Log out.
6. Look in your mailbox (read-only) for placement mails since the last run.
7. Rebuild the feed and save everything to Supabase.

## The feed

Every item has a level and a one-line title (under 160 characters):

| level | what |
|---|---|
| `always` | anything about a role you applied to (shortlist, test, extension, result), or anything that names your roll number |
| `show` | you're eligible, haven't applied, deadline ahead, not marked not-interested ("apply by X"); a reminder 24h before the deadline; "is this notice about X?" questions |
| `hidden` | kept but not shown: not eligible, deadline gone, not interested, not yours |

Rules for which role a notice is about: the role named in the text; else for
tests/shortlists, the roles you applied to whose selection details mention a
written test; else all roles at that company you applied to. If Ping isn't
reasonably sure which company it is, it doesn't guess.

**Eligible** = CGPA at or above the cut-off (none = yes), your degree +
department in the allowed list (empty list = yes, flagged), and the backlog
rule doesn't rule you out. If the ERP itself says "Company requirement has
CGPA cut off greater than yours", that's a no.

If a notice gives a later deadline than the companies list, the notice wins
(the item says where the deadline came from).

## Your profile

One row in the `profile` table. Until the dashboard exists, edit it in
Supabase > Table Editor > profile:

| column | example |
|---|---|
| `roll` | leave empty to use your ERP user id |
| `name` | only used when a PDF has names but no roll numbers |
| `department` | `COMPUTER SCIENCE AND ENGINEERING` (as the ERP writes it) |
| `degree` | `B.TECH`, `DUAL DEGREE`, `M.SC(5YR)`, ... |
| `cgpa` | `8.12` |
| `active_backlogs` | `false` |
| `cv_names` | `{Software CV,Data CV,Product CV}` |
| `interested_companies` / `not_interested_companies` | `{Accordion}` |
| `notice_types` | `{PLACEMENT}` (internship notices are ignored) |

Applied status is not in the profile. It comes from the companies list
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
even mark a mail as read).

**Secrets.** Passwords and keys live only in GitHub Secrets (encrypted,
hidden in logs, not copied when someone copies the repo) and, on a laptop,
in a `.env` file that git ignores. Nothing is in the code. Each student uses
their own repo, their own secrets and their own Supabase project.

**Other students' data.** PDFs contain hundreds of other students' names.
Ping keeps only your own row and the table heading, and logs only the
*shape* of a file (pages, characters), never its contents. Captures from the
capture script are never committed.

The database has Row Level Security on with no policies, so only the
secret key can read it. The dashboard will add a policy for you when it's built.

**Trade-off to know:** the OTP exists so that a password alone isn't enough.
Ping holds both your ERP password and access to your mailbox, so your GitHub
account is now the key to your ERP. Keep two-factor login on for GitHub.

## When Ping needs you

It emails you (from your institute mailbox to itself) at most once a day per
problem: database not set up, a security question it doesn't recognise,
login failing twice in a row, the ERP refusing the OTP.

## Optional AI for hard notices

Deadlines and company lists are read by rules. Each run counts notices where
the rules found nothing ("rules unsure"). If that number stays high, switch
on an AI model for just those notices: set repository **variables**
`PING_AI_PROVIDER=openai_compatible`, `PING_AI_BASE_URL`, `PING_AI_MODEL` and
the **secret** `PING_AI_KEY` (any provider with an OpenAI-style API, many
have free tiers). Only the notice text is sent, never PDFs or your data. See
`ping/ai.py`.

## Setting it up

**You (already done):** secrets are in GitHub. Remaining:
1. Supabase > SQL Editor > New query > paste [`sql/schema.sql`](sql/schema.sql) > Run.
2. Fill your profile row (see above).
3. Gmail filter for OTP mails: From = the ERP's OTP sender, Subject = OTP >
   Skip the Inbox + Mark as read. Ping searches All Mail, so it still finds them.

**Another student:**
1. Make your own **private** copy of this repo.
2. Create a free Supabase project and run `sql/schema.sql` in its SQL Editor.
3. Get a Google app password for your institute mailbox
   (`myaccount.google.com/apppasswords`; needs 2-step verification on).
4. On your laptop: `python -m pip install --user -r requirements.txt`, then
   `python setup/new_student_setup.py`. It asks for everything one by one,
   saves it to `.env`, does one test login, and tells you what to paste where
   on GitHub and how to set up the mail filter.
5. Actions > Ping > Run workflow.

## Demo data

`load-sample` (Run workflow button, or `python -m ping.run --mode load-sample`)
loads made-up companies, notices, shortlist results and a full feed, so the
dashboard works for someone without ERP access. Every demo row has
`is_sample = true`; `remove-sample` deletes exactly those. A real profile is
never overwritten by the demo one.

## Files

| path | what |
|---|---|
| `ping/gate.py` | the read-only allow list every ERP request goes through |
| `ping/erp.py` | login and the reads |
| `ping/mailbox.py` | read-only mailbox (OTP, placement mails) |
| `ping/parsers.py` | companies list, role popups, notices |
| `ping/notices.py`, `ping/dates.py`, `ping/matching.py` | what a notice means, dates, which company |
| `ping/pdfs.py` | is your roll number in the attachment |
| `ping/eligibility.py`, `ping/items.py` | eligibility and the feed |
| `ping/store.py`, `sql/schema.sql` | Supabase |
| `ping/run.py` | one run, start to finish |
| `ping/sample.py` | demo data |
| `ping/ai.py` | optional AI hook (off) |
| `setup/capture_erp.py` | one-time page capture used to build Ping |
| `setup/new_student_setup.py` | setup for the next student |
| `tests/` | offline tests, including a full run against a fake ERP |

Run the tests: `python -m pip install -r requirements-dev.txt && python -m pytest -q`.
