# Build prompts

Every prompt the owner gave the coding agent in the session that built Ping, verbatim and in order,
with the time each was sent. Only the owner's messages: no replies, tool output, automatic notices or hook
messages. Messages marked *sent while the agent was working* were typed while a task was running and reached it
mid-task.

One change from verbatim: a word that must not appear in this repository is written as `[banned word]`
(6 places, all of them instructions not to use it). Everything else is exactly as sent.

64 prompts, 20 Nov 2026 22:06 UTC to 22 Nov 2026 17:22 UTC.

## 1. Sat 21 Nov 2026, 03:36 IST (22:06 UTC)

`````text
check repo
`````

## 2. Sat 21 Nov 2026, 03:41 IST (22:11 UTC)

`````text
ok so I want to build a small tool for myself for placement season. calling it Ping. I'm a product person not a dev, so you're going to have to make the technical calls and explain them to me in plain words.
The problem. At IIT KGP all placement stuff sits in the campus ERP. There's a companies list (one row per role, with the pay, the apply window etc) and a CDC notice board (shortlists, test schedules, forms to fill, deadline extensions). None of it gets emailed to us. The notices get forwarded to the batch whatsapp groups but that's 10-20 messages a day covering every company, whether I'm eligible for it or not, and the actual shortlist or the test room allocation is always inside a pdf attached to the notice, never in the message. So everyone keeps opening the ERP 10 times a day to see if anything is for them.
What I want Ping to do: log into the ERP for me every hour, read the companies list and the notice board, open the attached pdfs, check my institute mailbox, and tell me only what's actually mine. Things like "you're eligible for X, apply by Y", "you're on the Z shortlist, test sat 10am room V2", "you applied to A, the shortlist is out and you're not on it". Save all of it somewhere a dashboard can read later. The dashboard is a separate thing, don't build it now.
How login works, I've checked all of this myself:

* it's one page. user id, password, an answer to a security question, and an OTP box with a Get OTP button next to it, then Log In
* the security question only shows up after you type your user id. every student has 3 fixed questions and one gets asked at random each time
* the OTP comes to the institute mailbox linked to the ERP
* no captcha
* the ERP logs you out after 10 minutes of doing nothing, so don't try to stay logged in between runs, just log in fresh every time
* there's no limit on how many times a day you can log in, I asked

Things I care about:

* it has to cost me nothing to run. free tiers only. you pick what
* it runs every hour from 6am to 1am IST, and I also want a way to trigger a run myself from the dashboard later
* it's just for me, running under my own accounts with my own passwords. if another student wants it they should be able to copy the project and run it under their own accounts. nobody's passwords should ever sit on a shared server or in a shared database
* it must never DO anything on the ERP. no applying, no submitting, no uploading. only reading. this is non negotiable
* my passwords and keys must not end up in the code or on github in the open. tell me how you'll handle that
* the whatsapp groups are not a source. ignore them

Don't write any code yet. First give me the plan in plain language: what tools you'll use, why they're free, and what one run does from start to finish. Then give me a one-time setup script I run by hand that logs me in (I'll type the OTP myself) and saves copies of the real ERP pages so you build from what the pages actually look like instead of guessing. Also suggest a name for the project folder. Then stop and wait for me.
`````

## 3. Sat 21 Nov 2026, 04:05 IST (22:35 UTC)

`````text
ran the capture script on my laptop. my laptop has a Device Guard policy from the organisation that blocks things. pip.exe was blocked so I installed playwright with "python -m pip install --user playwright" and that worked. but the browser launch fails. it downloaded chromium fine, then the moment it launches, the process gets killed. error is TargetClosedError, "Target page, context or browser has been closed", exit code 3236495362.

I have normal Chrome and Edge installed and they open fine. can you change the capture script to use one of those instead of playwright's own chromium? and give me the updated file.
`````

## 4. Sat 21 Nov 2026, 04:39 IST (23:09 UTC)

`````text
@"/root/.claude/uploads/55eb6ef9-bf2a-53cd-a660-deaf3a02e27f/5868871b-erp-20261121-041159.zip" done. repo is private. zip from the capture script is attached. mailbox app password worked, I've got it.
I need to step away for a few hours, so I'm giving you everything for the backend in one go. build the whole thing, test it against the captures, and if you can trigger a real run yourself and read the logs, do that too and fix whatever breaks. if you hit something that genuinely needs me, stop and leave me a clear list of what you need. don't wait on me for small decisions, make the sensible call and note it.
secrets are already in github with these exact names: ERP_USER_ID, ERP_PASSWORD, ERP_SECQ_1, ERP_SECQ_2, ERP_SECQ_3 (each one is "question::answer"), MAIL_ADDRESS, MAIL_APP_PASSWORD, SUPABASE_URL, SUPABASE_SERVICE_KEY. use those. the supabase key is one of the new "secret" keys (starts with sb_secret_), not the old service_role one. the supabase project is empty, create whatever tables you need (give me the SQL as a file too in case it has to be run by hand).
notifications: skip telegram. the dashboard is the main thing. email me at my institute address if you need anything.
on "no AI": searching pdfs for my roll number without AI makes sense, keep that. but deadlines in notices are written as sentences in all sorts of ways, and some notices list several companies in the text. try rules first, but leave a place to plug in a free AI model for those bits if the rules keep getting them wrong. I'll decide after seeing real notices.
here's everything about the ERP pages, use the captures for the real details.
LOGIN order should be: type my roll number, wait for the security question to appear, pick the matching answer from my 3 stored ones (match the question loosely, ignore capitals, spaces and punctuation, and if none match, stop and tell me which question it showed), type it, type the password, click Get OTP, watch my mailbox for an OTP mail that arrived after that click (wait up to 3 min, if nothing comes press Get OTP once more), type the code, log in, do the work, log out. every run is a fresh login, the ERP drops you after 10 min idle anyway.
COMPANIES LIST each row is one role, not one company. Accordion has 3 rows, AiPrise has 4. around 200 rows, 20 per page. columns left to right exactly as written:
| Company | Additional | PPT | Apply/Acceptance | CTC | Currency | Additional Details | Application Status | Resume Upload Start | Resume Upload End | Interview/Selection | Contract

* Application Status shows Y when I've applied. that's how you know. I won't track it by hand
* Resume Upload End is the apply deadline
* dates in the cells look like 2026-10-21 15:30 even though the caption at the top says DD-MM-YYYY. go by the cells
* currency isn't always INR, there's a JPY row

the role name in Apply/Acceptance is a link. it opens a popup that only shows details. company name, a small table (form type, designation, pay, bond, additional criteria, CGPA cut-off where 0.0 means none), job description, a "Click Here for more details" link, and then "Allowed Departments and degrees" which looks like B.TECH --- AEROSPACE ENGINEERING(B.TECH 4Y) DUAL DEGREE --- AEROSPACE ENGINEERING/ARTIFICIAL INTELLIGENCE ... that list is the eligibility. store it so you can check whether my degree + department is in it.
"more details" opens a second popup with lots of label: value lines. pay breakup, take home, bonuses, bond, 1st year ctc, "Is there a CGPA criteria", "Backlog Eligibility", and a Selection Details section (shortlist from resumes, written test, mode etc). save all of it. three matter for logic: the backlog rule, the CGPA cutoff, the selection details.
only open popups for rows you haven't seen before. and that role link is where applying starts, so read the popup, close it, click nothing else. if there's an apply button at the bottom, don't go near it.
NOTICE BOARD columns exactly as on the page:
| Type | Subject | Company | Notice | Notice Time | Download

* Notice Time is written like 21-11-2026 00:07, day first, different from the companies list
* Subject is a category. seen: Date extension, CV Submission, Urgent, Schedule, PPO. get the full list from the captures
* Company is a real name, or "Multiple Companies", or something generic like "CDC Placement Schedule"
* the Notice column is cut off. the full text is in the popup when you click the row (title "Placement/Internship Form Description File"). read it from there
* Download is a pdf link when there's an attachment

two real notices so you see what they're like:
Subject: Date extension, Company: ICICI LOMBARD "The CV Submission for ICICI Lombard for the role of Actuarial Analyst has been opened till 4:00 PM, 21st November, 2026. All candidates who are applying for the role, are required to kindly fill the Additional Details Form given below. Link: https://forms.gle/Di2j1Sw7VyCurUud7 Deadline: 21st November 2026, 4:00 PM. Interested and eligible students are advised to apply on the portal and fill the form within the given deadline. No further extensions will be given." this is two things to do. apply on the portal AND fill the form, both by 21 nov 4pm. one notice can mean more than one to-do.
Subject: Urgent, Company: ETERNAL "PFA the test room allocation of shortlisted candidates for the Assessment of Eternal, scheduled from 7:15 PM onwards on 19th November, 2026. Venue: Nalanda Classroom Complex. Students are required to carry their original Institute ID card... The test link has been shared on their Institute Email ID. ... POCs: [name] (+91 ...), [name] (+91 ...)" plus a pdf so: test 19 nov 7:15pm, venue Nalanda, my room is in the pdf, save the POCs as contacts, and since it says the link was emailed, look in my mailbox for anything from Eternal after the notice time and attach the link.
rules

* use Subject to decide the kind. CV Submission = apply, Date extension = deadline moved, Schedule = test or PPT depending on the text, PPO = just info, Urgent = could be anything, read the text
* which company: use the Company column. only read the text when it says Multiple Companies or something generic. Multiple Companies notices list them in the text, so one item per company
* deadlines are in sentences in all formats. pull them out as proper IST dates and times, keep the original wording too. if a notice gives a newer deadline than the companies list, the notice wins
* 1600+ notices. first run only goes back 14 days, after that only what's new

PDFS, the important part shortlists aren't in the notice text, they're in the pdf as a table of roll numbers and names. same for room allocations, who sits where and when. for every new notice with a pdf:

* read the text and tables. if a pdf is a scanned image handle that, but check the captures first, I think they're all proper text
* look for MY roll number first, it's unique. name only as fallback, and note which one matched
* if I'm in it, take only my row and the table heading and work out room, venue, date, time, slot. don't feed the whole pdf anywhere, it's 300 other people's names
* store yes / no / unknown. unknown only if the pdf couldn't be read at all both answers matter. "you're on the Pine Labs shortlist, round 2 sat 10am room V2" obviously, but "Pine Labs shortlist is out and you're not on it" for something I applied to is also something I want to be told. if the company isn't one I applied to or am eligible for but it looks like a shortlist or schedule, still check the pdf, just do those last.

WHAT GETS SHOWN which role a notice is about: if the text names the role use that. else for test/shortlist notices prefer roles whose selection details say there's a written test. else attach to all of that company's roles I've applied to. if you're not reasonably sure which company, don't guess, show it as "couldn't match this, is it about X?" and I'll fix it.
eligible = my CGPA at or above the cutoff (none = yes), my degree + department in the allowed list (empty list = yes but flag it), backlog rule doesn't rule me out.
three levels

* always show: anything about a role I've applied to. shortlist, test, extension, result
* show with "apply by X": eligible, not applied, deadline ahead, company not marked not-interested. also remind me 24h before the deadline
* keep but don't show: not eligible, deadline gone, or marked not-interested

every item gets one line under 160 characters saying what to do and by when. like "Accordion opened, eligible for Data & AI Analyst (CG 7+, all depts). Apply by Fri 16:00."
my profile (I'll edit it from the dashboard): roll, department, degree, CGPA, active backlogs yes/no, names of my 3 CVs, companies I'm interested in, companies I'm not. applied status is NOT here, it comes from the companies list.
also a way to load sample data so the dashboard works for someone with no ERP access. I need that for the demo.
WRAP UP, after it's built and tested

* run it for real if you can and give me the numbers: roles seen/new, notices seen/new, pdfs read, yes/no/unknown counts, anything that couldn't be parsed, how long login + OTP took. if you can't trigger it yourself, tell me exactly what to click
* README in plain language with an honest status section: what works, what I verified vs what's assumed, known ways it breaks
* a setup script for the next student: asks for each password/key one by one, stores them safely, does one test login, tells them exactly what to paste where on github, and tells them to add a mail filter so the hourly OTP mails don't clutter their inbox
* then put it on github properly. small commits, sensible order. double check no passwords or keys are in there before you push
* finish with a short summary for me: what's done, what you decided on your own, what's left, and anything you need from me
`````

## 5. Sat 21 Nov 2026, 05:12 IST (23:42 UTC)

`````text
one more thing before I go. I've added two more secrets: GEMINI_API_KEY (free gemini key, use it for the messy bits like deadlines written in sentences and notices listing several companies, rules first then this as fallback) and SUPABASE_PUBLISHABLE_KEY.

once the backend is done and tested, build the dashboard too. keep it simple and free to host, a plain web app is fine, I don't need anything fancy. it should:
- show my "for you" items as a list, newest first, with the one line summary, the deadline, and a way to open the original notice or pdf
- a filter for the three levels (always show / apply by / hidden)
- a page per company showing its roles, whether I applied, the deadline, the pay, and the eligibility
- a page where I edit my profile (roll, department, degree, cgpa, backlogs, cv names, interested / not interested companies)
- a "check now" button that triggers a run
- a "demo mode" that works with the sample data and no login, so someone reviewing this can click around without my ERP access. the real data should be behind a login
- if it's not too much extra, a small "ask Ping" chat box that answers questions like "what's due tomorrow" or "did I apply to accenture" using the gemini key, but keep the key on the server side, never in the browser. if that's a lot of work skip it and tell me

host it somewhere free, give me the link, and put the demo mode link in the README.
`````

## 6. Sat 21 Nov 2026, 05:15 IST (23:45 UTC) — sent while the agent was working

`````text
small correction: notices always use the exact company name as it appears in the companies list (eg "Accenture Solutions Private Limited", not just "Accenture"). so match on the exact name first and only fall back to loose matching if there's no exact hit. the "shared first word" rule shouldn't be needed much.
`````

## 7. Sat 21 Nov 2026, 11:30 IST (06:00 UTC)

`````text
dashboard login keeps saying "Invalid login credentials". I've created the user in supabase (auto confirmed, email provider is on) and I'm sure of the password. check that the dashboard is using my actual supabase project url and the publishable key from the secrets, and that nothing in the sign-in code is restricting which email can log in. tell me what you find.
`````

## 8. Sat 21 Nov 2026, 11:44 IST (06:14 UTC)

`````text
still "Invalid login credentials". user is confirmed, never signed in, zero logs on the user. I'm signing in on the claude.ai page you published, and that page DOES have a sign-in form (email, password, sign in button, "try the demo" link under it), so your assumption that it has no sign-in form is wrong. I think that page was built with the wrong config. open whatever you published to claude.ai, check its config, confirm the supabase url in it contains sdcorifzwpizfpggoady and the key is my publishable key, and republish it if not. also tell me whether the project-wide auth logs on supabase should show my failed attempts, so I can confirm which project the page is hitting.
`````

## 9. Sat 21 Nov 2026, 12:13 IST (06:43 UTC)

`````text
check passed, database ok. I've started a real run (mode run). while that goes:
1. once it saves, build the demo mode from the real data, anonymised as I said earlier, and replace the made-up demo
2. add the read-only reviewer login
3. send me the plain-words list of allowed ERP addresses and the read-only confirmation I asked for
4. hourly runs should be on from now, 6am to 1am IST
`````

## 10. Sat 21 Nov 2026, 12:14 IST (06:44 UTC) — sent while the agent was working

`````text
one more change to the dashboard, and it's a big one. make the main screen a chat, like whatsapp. that's how the product is meant to feel.

- it opens on a chat with Ping. every new "for you" item shows up as a message from Ping, with the time, newest at the bottom, exactly like a chat thread. the one line summary is the message, and tapping it expands to show the details and a link to the notice or pdf
- I type at the bottom. anything I ask ("what's due tomorrow", "did I apply to accenture", "which room for the eternal test", "what's the ctc at airbus") gets answered by Ping in the same thread, using the ask Ping logic you built
- the thread is saved, so when I come back I see the whole history and can scroll up. the last message at the bottom is always the latest thing that happened
- unread messages get a marker, like whatsapp, so I can see what's new since I last opened it
- the three level filter, the company pages and the profile page can live behind a menu button at the top. the chat is the home screen
- demo mode and the reviewer login should show the same chat, with the anonymised real data as the messages
- keep it clean and fast. no fancy animations, just a chat that works on a phone screen too

don't lose anything that already works. this is a change to how it looks and feels, not to what it knows.
`````

## 11. Sat 21 Nov 2026, 12:16 IST (06:46 UTC) — sent while the agent was working

`````text
the first time setup was painful. I had to run two sql files by hand in the right order, create the dashboard user in supabase's screens, fix a password mess, and I still got "not allowed" after signing in because the allow list was empty until a run saves. another student will hit every one of those. I don't want that.

make the setup script do all of it so a new student never opens supabase's sql editor or auth screens:
- creates all the tables and permissions in their supabase project (it has the secret key, use it)
- asks them for a dashboard password and creates the dashboard user, confirmed, and adds them to the allowed list
- checks that the user can sign in, and that the database is ok, before it finishes
- prints the exact things to paste into github secrets, with the names
- ends with "done, open <dashboard link> and sign in with <email>"

then test it as if you're a brand new student with an empty supabase project, and fix whatever breaks. the whole thing should be one command and under 10 minutes.
`````

## 12. Sat 21 Nov 2026, 12:21 IST (06:51 UTC) — sent while the agent was working

`````text
one more thing. the same message often reaches me more than once: on the notice board and again by email, or a notice gets re-posted with a tiny edit, or a deadline extension repeats everything from the original notice. right now that would turn into two or three messages from Ping, which is the exact clutter I'm trying to get rid of.

so before Ping sends anything, check whether it's really new:
- same company, same kind of thing (apply / test / shortlist / form), same deadline or same date and venue, within a few days of each other = the same item. don't send it again
- an email that says what a notice already said = not new
- a re-posted notice with small wording changes = not new
- but a real change IS new and should be sent as an update, not a fresh item: "deadline moved from thu 4pm to fri 4pm", "venue changed to ...", "you've now been shortlisted". say what changed, in the same message thread
- if you're genuinely unsure whether two things are the same, treat them as the same and keep a note, I'd rather miss a duplicate than get spammed

test it against the real notices from today's run, there should be plenty of repeats in there, and tell me how many it merged.
`````

## 13. Sat 21 Nov 2026, 12:23 IST (06:53 UTC) — sent while the agent was working

`````text
the chat works and answered "whiteoak ctc?" correctly from rules, nice. but it says "AI helper not reachable: Failed to fetch". so the gemini part of ask Ping isn't reachable from the page. find out why: is the server function for it deployed (SUPABASE_ACCESS_TOKEN is in the secrets), and can the page actually reach it from where it's hosted? fix it so questions like "what's due tomorrow" and "which room for the eternal test" get proper answers. and keep the rules fallback, it's good that it still answered.
`````

## 14. Sat 21 Nov 2026, 12:32 IST (07:02 UTC)

`````text
I'm stepping away for a few hours. do all of this, make sensible calls, and leave me a summary at the end.

decisions:
- demo from real data: your proposal is fine. keep company names, roles, pay, deadlines and notice wording. fake roll number, name and cgpa. strip all other students' names, rolls and phones. nothing from my mailbox. keep my applied / not-applied list as it is, don't shuffle it, the demo only makes sense if applied → shortlisted → test room holds together.
- reviewer login: (a), a login that only sees the anonymised demo. create it, pick a password, and put both in the summary for me.

try to do these yourself, since you have the tokens:
- run sql/chat.sql on my supabase project the same way the setup script creates tables. if you can't, tell me.
- the hourly schedule hasn't fired. try disabling and re-enabling the workflow yourself through github. then check at 13:23 whether the 13:11 run happened. if it still didn't, tell me exactly what to click.

then:
- look at the gemini error from today's run and tell me if it matters.
- build an evals file for the submission: a set of real notices and pdfs from today's run with the expected answer for each (company, kind, deadline, am I in the pdf, room), and a script that runs Ping's logic over them and prints accuracy. include the duplicate merging numbers and the pdf numbers from the real run. this is a deliverable I have to submit, so make the output readable by a non technical reviewer.
- go through the dashboard once as a reviewer would, using the demo, and fix anything that looks broken or confusing.
- update the README: one-command setup, the chat, the demo link, the reviewer login (without the password), the ERP address list, the honest status section, and the numbers from today's run.
- commit everything in small commits and push.
- finish with a summary: what's done, what you decided, what's left, what I need to do, in that order.
`````

## 15. Sat 21 Nov 2026, 14:36 IST (09:06 UTC)

`````text
ask Ping now says "AI not reachable: HTTP 546" when I ask "slice ctc breakdown". the rules answered with the basic ctc, but the breakdown (take home, bonus, bond) is in the data and the AI should have given it. 546 means the function itself is crashing. read the function's logs on supabase, find out why, fix it, and test it from the page with that exact question and "what's due tomorrow". also make sure the function has the gemini key on its side, not just in github.
`````

## 16. Sat 21 Nov 2026, 16:12 IST (10:42 UTC)

`````text
Two things, in this order.

1. Rotate the reviewer login. Run Admin > create-reviewer with a new random password (don't print it; store it the same way the current one is stored, and tell me only where it is stored). Confirm the earlier Admin run logs that showed the old password are deleted or that the old password no longer works.

2. Then give me a status audit of Ping, no code changes. For each item below say DONE / PARTIAL / NOT STARTED with one line of evidence (file or workflow name):
- Hourly ERP auto-login 06:00–01:00 IST via GitHub Actions, read-only on the ERP
- Failed login = retry next run; alert (dashboard item + one email) only after 3 consecutive failures
- Sources covered: ERP company list (CG criteria, departments, roles, stipends), ERP notices (shortlists, test deadlines, forms, extensions), institute email
- Dashboard home = WhatsApp-style chat: new "for you" items arrive as messages from Ping, I ask questions in the same thread, history saved, unread markers; filters / company list / profile pages behind a menu
- Ask Ping function: timeouts, model fallback, pay-breakdown data, per-request log line
- One-script first-time setup for a new student (creates tables, dashboard user, allow-list, verifies sign-in) with no manual Supabase SQL/auth steps
- Reviewer read-only login on the anonymised data
- Evals for Ask Ping (a repeatable question set with expected answers)
- A document listing the exact prompts the agent uses
- README: setup, Admin workflows, architecture

Finish with: the repo's folder tree (2 levels), the list of GitHub Actions workflows and what each does, and the list of Supabase functions and tables. Keep it to facts, no suggestions.
`````

## 17. Sat 21 Nov 2026, 17:08 IST (11:38 UTC)

`````text
Four fixes, then a report. Commit after each one.

1. Schedule never fires. ping.yml has run 0 times on cron. Find out why (workflow not on the default branch, repo flagged inactive, cron disabled after 60 days without a push, workflow permissions, or anything else) and fix it. Then confirm it is armed: show me the next scheduled time GitHub reports, and after the next :41 tick confirm a scheduled run actually happened (start that check in the background and tell me the result when it lands; don't block on it).

2. Failed-login policy must match the decision. Treat these two cases differently:
   a) ERP unreachable / blank login page / login form not accepting: this is normal ERP behaviour. Retry at the next hourly run, never pause the schedule. After 3 consecutive failed runs: one email AND one Ping message in the chat thread ("Couldn't reach the ERP for the last 3 runs; I'll keep trying hourly"). Send it once per streak, and one "back online" Ping message when a run succeeds again. Remove the generic dashboard banner.
   b) Credentials refused / bad user ID / OTP refused: this is a real problem. Alert immediately (email + Ping message) and pause the schedule until I run it by hand. Keep whatever already does this.
   Update tests for both cases.

3. Stipend. Check what the ERP company list actually shows for internship roles. If there is a stipend column or a stipend inside the CTC text, parse it into its own field, show it in the company page and pass it to ask-ping like CTC. If the ERP has no stipend anywhere, say so and change nothing.

4. Dashboard deploy readiness. Do NOT make the repo public. Report: (a) whether Pages can be enabled on this repo as it stands (private, current plan); (b) a full scan of the git history, all branches, for anything that must not be public: real student data, real names/roll numbers, ERP credentials, Supabase service keys, Gemini keys, the reviewer password, .env files, raw ERP captures. List every hit with file and commit. (c) Whether demo-data.json and evals/real_run.json are fully anonymised. (d) If I decide to go public, the exact steps you would take, including history rewrite if needed.

Finish with a short report in the same table format as before, plus the diff summary of what changed.
`````

## 18. Sat 21 Nov 2026, 17:26 IST (11:56 UTC)

`````text
Remove every real person's data from the demo, everywhere it lives. No decision needed from me; go.

1. Anonymiser (ping/demo_from_real.py): match any 10-digit Indian mobile with any spacing, with or without +91 / 0 prefix; drop every personal name on POC / coordinator / contact lines (keep the role word, e.g. "Placement coordinator"); strip Teams/Zoom/Meet IDs, passcodes and join links; replace company recruiting email addresses with careers@example.com. Add a final assertion pass that fails the build if any 10-digit number, +91, or a name from a denylist ([name], [name], [name], [name], [name], [name]) survives anywhere in the output.

2. Rebuild and republish all three copies: run Admin build-demo, replace the reviewer's database rows with the new demo, and republish the claude.ai demo page. Confirm each by grepping the live output for the denylist and for any 10-digit number.

3. Tests and comments: replace the real names, roll numbers and phone numbers in tests/test_demo_from_real.py, the comment in ping/demo_from_real.py, and the names in tests/fake_erp.py and tests/test_rules.py with clearly made-up values (rolls like 22XY10042, numbers in the 90000 xxxxx range). All tests must still pass.

4. Repo-wide check: grep HEAD for every value in your table from the last report, plus any 10-digit number not in the fake list. Report zero hits or list them. Don't rewrite git history yet; the repo stays private for now.

5. Schedule: when the 12:58 UTC check lands, tell me whether the 12:41 UTC run happened on cron, and what it did (logged in, items found, duration).

Finish with the same status table and diff summary.
`````

## 19. Sat 21 Nov 2026, 17:45 IST (12:15 UTC)

`````text
Build the Ask Ping evals and the prompts document. Commit after each part.

PART A — Ask Ping evals (evals/ask_ping/)
1. Write cases.json: 30–40 questions against the anonymised demo data, each with question, category, and checks. Categories and roughly how many:
   - company facts (8): CTC and breakdown, eligibility/CG cut-off, departments allowed, role, location — e.g. "slice ctc breakdown", "am I eligible for Harness"
   - deadlines (8): "what's due tomorrow", "what closes this week", "when does X's form close", "anything due today" — fixed by passing a snapshot time so answers are deterministic
   - notices/shortlists/tests (6): "am I shortlisted anywhere", "when is X's test and where", "latest notice for Y"
   - negative / no-hallucination (6): a company not in the data, a date with nothing due, a field the data doesn't have — the expected answer says so plainly and invents nothing
   - read-only / scope (4): "apply to X for me", "withdraw my application", "change my CV on the ERP" — must refuse and say Ping is read-only
   - robustness (4): typos, lowercase company names, two questions in one message
   Checks are deterministic: must_contain (list, case-insensitive), must_not_contain, numbers_present, max_words. Put expected values by reading the demo data, not by running the model.
2. run_ask_ping_evals.py: calls the deployed ask-ping function with the reviewer login and the fixed snapshot time, runs every case, writes evals/ask_ping/REPORT.md with per-category scores, the failures with question / answer / failed check, and the model used and latency per case. Must be runnable from Admin (new task ask-ping-evals) and locally.
3. Run it. Report the score. If anything fails because the prompt or the data passed to Gemini is wrong (not because the check is wrong), fix the function and re-run once. Don't loosen checks to make them pass; if a check is genuinely wrong, say which and why.
4. Update evals/REPORT.md to be the index: the parser evals (held-out 56/58, dev 143/143) and the Ask Ping evals, each with what it measures, how to re-run, and the current score.

PART B — Prompts document (docs/PROMPTS.md)
1. Generate it from source so it can't drift: a small script (setup/export_prompts.py) that extracts every prompt string from ping/ai.py and supabase/functions/ask-ping/index.ts and writes them verbatim into docs/PROMPTS.md, each with: where it runs, what input it gets, what output format is expected, and which model(s) it's sent to with the fallback order and timeouts.
2. Add a tests check that fails if docs/PROMPTS.md is out of date with the source.
3. The word "[banned word]" must not appear anywhere in the repo, docs, prompts, demo, or claude.ai page. Grep and confirm zero hits.

Then: the schedule result from the 12:58 UTC check, the status table, and the diff summary.
`````

## 20. Sat 21 Nov 2026, 18:01 IST (12:31 UTC)

`````text
Deploy the dashboard to GitHub Pages from a separate public repo. This repo stays private. Commit after each part.

1. Public repo. Create a public repository named ping-dashboard under my account (use gh if you're authenticated; if not, stop and give me the exact steps). It will hold ONLY built static files: index.html, app.js, style.css, config.js, demo-data.json, .nojekyll, and a short README (what Ping is, that this repo is the built dashboard only, link to nothing private). Its README and files must not contain the word "[banned word]".

2. Token. I need to create a fine-grained personal access token for the push. Stop and tell me exactly: the GitHub URL to open, repository access = only ping-dashboard, the exact permissions needed (Contents read/write; Pages read/write if you'll enable Pages via API; nothing else), an expiry, and the secret name to save it under in THIS repo's Actions secrets (DASHBOARD_DEPLOY_TOKEN). Wait until I say it's saved.

3. Workflow. Split dashboard.yml into two jobs: (a) deploy-functions: the existing Supabase function + secrets deploy, unchanged; (b) deploy-pages: run build.sh, then a guard step that fails if the built output contains any of: sb_secret_, service_role, AIza, a 10-digit number outside the fake 90000 range, +91, my roll number, my email, "[banned word]". Then push the built output to ping-dashboard main with a commit message like "build <short-sha> from private repo". Enable Pages on ping-dashboard (source: main, root) via API with the token. Remove the "skipped while Pages is off" condition.

4. Supabase. Add the Pages URL (https://<my-user>.github.io/ping-dashboard/) to Auth URL configuration: Site URL and the redirect allow-list, keeping localhost entries for development. If ask-ping or check-now restrict CORS by origin, add the new origin. Report what you changed.

5. Paths. The site is served from a sub-path (/ping-dashboard/). Make sure every asset path, the Supabase redirect URL and any fetch of demo-data.json work under that sub-path, not just at root.

6. Verify live, not locally. Run the Dashboard workflow, wait for Pages to publish, then re-point setup/ask_ping_page_test.py (and the Admin ask-ping-page task) at the live URL by default: real browser, reviewer sign-in, both questions, HTTP 200. Also confirm the owner login flow works on the live URL as far as the password screen (don't sign in as me).

7. README (private repo): add a "Live dashboard" line with the URL, how the two-repo deploy works, and that the public repo has built files only.

Finish with: the live URL, the status table, and the diff summary.
`````

## 21. Sat 21 Nov 2026, 18:10 IST (12:40 UTC)

`````text
done step 1 & 2
`````

## 22. Sat 21 Nov 2026, 18:14 IST (12:44 UTC) — sent while the agent was working

`````text
Replace the reviewer login with a one-click demo. Commit after each part.

1. Supabase: enable Anonymous sign-ins. Write RLS so a session with is_anonymous = true can SELECT only rows where is_sample = true in every table, can INSERT/SELECT its own chat_messages (tagged with its own auth.uid()), and nothing else — no UPDATE/DELETE anywhere, no access to real rows, runs, state, contacts, emails or allowed_users. Keep the owner's policies unchanged. Add tests that an anonymous session cannot read a non-sample row or write anything except its own chat.

2. ask-ping and check-now: for an anonymous session, ask-ping answers from the demo rows only; check-now refuses. Rate-limit anonymous sessions: 15 questions per session per hour and a global anonymous cap of 100 per hour, returning a friendly message when hit, so the demo can't burn the Gemini quota while judges are using it. Log counts only, no question text.

3. Dashboard: on the sign-in screen add a prominent "View demo" button under the normal sign-in. It calls signInAnonymously(), lands on the chat home with the demo "for you" messages already there, and shows a small persistent "Demo — sample data, read-only" chip. The owner sign-in stays as it is. Verify under the /ping-dashboard/ sub-path.

4. Cleanup: a scheduled step (daily, inside an existing workflow) that deletes anonymous users and their chat_messages older than 7 days.

5. Remove the reviewer account: drop the reviewer_users table and sql/reviewer.sql, remove Admin create-reviewer, and switch ask-ping-page, the Ask Ping evals and any other reviewer-login use to the demo button / an anonymous session. Grep for "reviewer" and clean up docs and README.

6. Verify live: real browser on the Pages URL, click View demo, ask "slice ctc breakdown" and "what's due tomorrow", HTTP 200 and sensible answers; confirm the demo session gets 0 real rows. Then the status table and diff summary.
`````

## 23. Sat 21 Nov 2026, 18:15 IST (12:45 UTC) — sent while the agent was working

`````text
Ask Ping has no conversation memory. Example from the live chat: "any test today?" → correct answer, then "nothing else?" → "The data does not contain any information about 'nothing else'". Fix it properly. Commit after each part.

1. Context: ask-ping must receive the last 10 messages of the same thread (both sides, oldest first) along with the new question. Pull them from chat_messages for that user/session inside the function (don't trust the client to send history). Cap at ~2,000 tokens; drop oldest first.

2. Prompt: add rules for follow-ups —
   - A short or elliptical message ("nothing else?", "and tomorrow?", "what about slice?", "same for analyst role?", "when?") continues the previous turn: resolve it against the last question and answer, then answer the resolved question. Never answer about the literal words of the follow-up and never quote the user's words back in a "the data does not contain…" line.
   - If a follow-up is genuinely ambiguous between two readings, answer the most likely one in one line and offer the other in a second line. Do not ask a clarifying question back unless neither reading can be answered.
   - Time awareness: the function already gets the snapshot time. For anything today, say whether it's already over ("Groww test was at 15:00 today, so it's over"), coming up ("in 2 hours"), or now. For "nothing else?"-type questions, answer with the count: "No, that was the only test today" / "Two more: …".
   - "No" answers must be short and specific: "No other tests today. Next one is X on Mon 24 Nov, 10:00." — never a sentence about what the data does or doesn't contain.

3. Evals: add a multi-turn section to evals/ask_ping/cases.json — a case is a list of turns, each turn with its own checks, run in order in one thread. At least 8 conversations, including: ["any test today?", "nothing else?"], ["meesho ctc", "and slice?"], ["what's due tomorrow", "and the day after?"], ["am I eligible for groww", "why not?" or "which cv?"], ["latest notice for harness", "when is it?"], and one where the follow-up changes topic entirely ("ok. what's due this week?") to make sure history doesn't drag the old topic in. Update run_ask_ping_evals.py to run turn sequences and REPORT.md to score them separately.

4. Run the full evals (single-turn and multi-turn) against the deployed function. Report scores before and after. Fix the prompt if needed and re-run once; don't loosen checks.

5. Verify live from the dashboard page: type "any test today?" then "nothing else?" and paste both answers in your report.
`````

## 24. Sat 21 Nov 2026, 18:31 IST (13:01 UTC)

`````text
<!-- attach -->
> Your click: https://github.com/vin1764/ping-dashboard/settings/pages → Source: Deploy from a branch → Branch: main, folder / (root) → Save. Then tell me

http://ping.erp/ done
`````

## 25. Sat 21 Nov 2026, 18:34 IST (13:04 UTC)

`````text
Custom domain removed. Go ahead:

1. Schedule via Supabase. Use pg_cron + pg_net in the project to call a new function `kick-run` every hour at :41 IST-equivalent (06:11–01:11 IST window, i.e. 00:41–19:41 UTC), which triggers the Ping workflow by workflow_dispatch using the same GitHub token check-now uses. Guard it: skip if a Ping run started in the last 50 minutes or one is in progress. Keep GitHub's cron line in ping.yml as a backup; the same guard prevents double runs if GitHub ever starts firing. Move the daily demo cleanup onto the same mechanism (one call a day). Verify by watching for the next :41 tick and reporting the run that it started.

2. Run the Dashboard deploy, confirm https://vin1764.github.io/ping-dashboard/ loads with no redirect and the CNAME file is gone, then do the live checks: View demo → "slice ctc breakdown" and "what's due tomorrow" (HTTP 200), demo session sees 0 real rows, owner sign-in reaches the password screen.

3. Deploy conversation memory once the baseline eval score is recorded; run the evals again with memory; report both scores and the live "any test today?" → "nothing else?" exchange from the page.

4. README: replace the "Pages was switched on by hand" line with the exact steps, and add a line that a custom domain must stay empty. Status table and diff summary at the end.
`````

## 26. Sat 21 Nov 2026, 18:38 IST (13:08 UTC) — sent while the agent was working

`````text
Add to the conversation-memory change before deploying it. Live demo just now: "any tests today?" → correct. "anything else?" → the full read-only disclaimer followed by a dump of every deadline today. Two more fixes:

1. The read-only refusal must only appear when the message actually asks Ping to do something (apply, withdraw, submit, upload, change, accept, decline, fill…). Find what triggered it here (a keyword rule, a prompt instruction that says to prepend it when "unsure", or the model) and fix it. A question never gets the disclaimer. Add eval cases: "anything else?", "what else?", "and?", "ok" must contain no refusal text; "apply to groww for me" must.

2. Time-aware wording: for events earlier today say "was at 15:00 today, so it's over"; for later today, "at 20:00 today (in 1h 25m)"; never say "is today at 15:00" after 15:00. Add eval cases with a fixed snapshot time of 18:35 IST.

3. Expected answer for this exact exchange, which should be a multi-turn eval case: "any tests today?" → "Yes — Groww (Associate Product Manager) was at 15:00 today, so it's over." then "anything else?" → "No other tests today. 15 application deadlines close at 20:00 tonight, none applied — say 'what's due today' for the list." (wording can differ; the checks are: no refusal text, says no other tests, mentions the 20:00 deadlines count, under 60 words).

Then continue: deploy memory, run both eval sets, report before/after scores and paste the live exchange.
`````

## 27. Sat 21 Nov 2026, 18:50 IST (13:20 UTC)

`````text
how long
`````

## 28. Sat 21 Nov 2026, 18:58 IST (13:28 UTC)

`````text
are you idle? i have more tasks
`````

## 29. Sat 21 Nov 2026, 18:58 IST (13:28 UTC)

`````text
Two feed features. Commit after each part. The chat home must get quieter, not busier.

PART A — Deadline digests
1. Replace per-role "Reminder: X closes …" cards with one message per batch: items that share the same close date+time (and same kind: application / form / test) become one message, e.g. heading "15 applications close tonight, Sat 21 Nov 20:00 — you've applied to none", then the list grouped per Part B. One digest per batch when it first appears; one reminder N hours before close (profile setting, default 2 h) listing only what is still unapplied; nothing on the other hourly runs. If the batch changes (new role added, extension), send one "updated" message, not a new full digest.
2. New companies, shortlists and test notices keep their own messages but also collapse when several arrive in the same run ("3 new companies listed: …").
3. Each digest ends with a one-line source: notice numbers + the check time ("ERP check 17:50, notices 1791, 1795, 1796").

PART B — Target-role relevance
1. Profile page: a free-text "What I'm looking for" box (e.g. "product, consulting, business/data analyst and finance roles; not core software engineering") and a checkbox "Always list other roles separately so I don't miss anything" (default on).
2. Classifier: for every role, once, Gemini reads company + title + JD/description + role text from the ERP and returns {relevant: yes/no, reason: ≤8 words}. Cache in the roles table; reclassify only if the role text or my targets change. Eligibility (CG cut-off, department) stays a hard filter applied before this. If the ERP has no JD for a role, classify on title alone and tag it "(JD missing)".
3. Every list in the feed and in Ask Ping answers is split: "For you" first (with the reason in grey), then "Others" (collapsed to one line per role). Add "Eligibility not verified for X" when the ERP data is incomplete. Ask Ping must use the same classification for "which of these are relevant to me", "anything for product roles tonight", etc.
4. Evals: build evals/relevance/cases.json from the demo roles with my targets set to the example above. Propose labels for all 201 roles in a table (company, role, your label, reason) for me to correct in one pass before you score anything; then report precision/recall for "For you". Add digest tests (same-deadline grouping, reminder timing, update-not-duplicate).
5. Demo: set the demo profile's targets to the example above so the View demo feed shows the grouping. Make sure the demo "for you" thread has no more than ~6 messages for today instead of 15+ cards.

Verify live on the Pages URL (View demo): screenshot-level description of today's thread, and the Ask Ping answer to "what's due tonight that's relevant to me". Status table, diff summary.
`````

## 30. Sat 21 Nov 2026, 19:27 IST (13:57 UTC)

`````text
Ping must be generic: no student-specific rule, name, department or preference anywhere in code, prompts, evals or docs. Everything personal lives in that student's profile row and is set through the chat. Commit after each part.

1. Preferences by chat. Ask Ping recognises preference statements and saves them to the profile, e.g. "only show me product, consulting and analyst roles", "also include data scientist roles", "don't count SDE as relevant", "remind me 3 hours before deadlines", "stop listing other roles separately", "which cv for … " later. Flow: detect → update the profile fields (targets text, reminder hours, list-others flag) → reply with one line confirming exactly what was saved ("Saved: targets = …; reminders 3 h before") → reclassify affected roles → answer any question in the same message. Also support "what are my preferences?" and "reset my preferences". Additive edits must merge, not overwrite ("also include X" appends; "not X" adds an exclusion). The Profile page stays as the editable view of the same fields. Add multi-turn eval cases for all of these, including a wrong detection check (a question that mentions "product roles" must not change preferences).

2. Classification is per profile. Classify with ONE batched Gemini call per (targets text, roles list) instead of one call per role; cache by hash of targets + role text so identical targets reuse results. Demo sessions may change preferences too: the change applies to their own session, uses the same cache, and counts against their rate limit; it resets when the session ends. Make sure a demo user changing targets never touches the owner's profile.

3. Evals must be persona-based, not me-based. evals/relevance keeps a fixture persona with its targets text written in the file (the current demo persona), and the labels are "correct for that persona". Apply that persona's text consistently to the 31 "?" rows and re-check the other 170; list changes; set labels_confirmed true; report precision/recall. Add a second persona (e.g. core-software targets) with ~40 labelled roles so the evals prove the classifier follows the stated targets rather than a fixed rule. I'll set my own targets through the chat afterwards — don't hardcode them anywhere.

4. Ask Ping list format: "✓ applied" marker with unapplied first; deadline stated once in the heading ("Close tonight 20:00 (in 1h 56m) — 14 for you, 3 applied:"); Others = one "Company — Role" line each, no per-company grouping; reasons shown in the feed only, not in chat answers. Add as eval checks and re-run the Ask Ping evals.

5. "Eligibility not verified for 39": verify against the ERP's CG cut-off and department where the data exists; keep the note only for roles with missing criteria, with the count.

6. Setup: confirm setup/new_student_setup.py creates an empty profile and that a brand-new student's first chat message can be their preferences; README gets a "First 5 minutes" section: run setup, open dashboard, tell Ping what you're looking for, done.

Status table, scores, diff summary.
`````

## 31. Sat 21 Nov 2026, 19:28 IST (13:58 UTC) — sent while the agent was working

`````text
I'm away until 22:00 IST. Work through everything below in order without stopping for questions: take the most reasonable reading, write each judgement call to docs/DECISIONS.md (one line each, dated), and if a step truly needs me, skip it and add it to the "Needs Vinayak" list at the end. Commit after each part, push, keep the live site working at all times (deploy only after tests pass). At 21:45 IST stop whatever is in progress at a clean commit and write the handoff report.

PART 1 — CV upload (my earlier spec): Profile "My CVs" (up to 3 PDFs with labels) in a private Supabase Storage bucket, owner-only RLS, never in git, never visible to demo sessions. Parse once (pdftotext or equivalent, server-side), Gemini makes a ≤300-token structured summary per CV stored in the profile; re-summarise only on replace; raw text never logged. Classifier gets CV summaries + targets text (targets text wins on conflict) and returns {relevant, best_cv, reason}. "Apply with: <label>" on role cards, in digests, and in Ask Ping ("which cv for groww", "what should I apply to tonight with my finance cv"). Demo gets one fabricated CV per label (made-up person, passes the anonymiser check). Tests: demo session cannot list/download from the bucket. Extend evals/relevance with best_cv labels for the fixture persona.

PART 2 — Hardening pass. (a) Review every RLS policy and list them in docs/SECURITY.md: who can read/write each table and bucket; prove with tests that an anonymous session sees 0 real rows in every table and the bucket. (b) Secrets inventory: where each secret lives (GitHub, Supabase), what uses it, confirm none in git, none printed in any workflow log in the last 20 runs. (c) Rate limits and the Gemini timeouts documented. (d) Grep repo, docs, demo and the public dashboard repo for "[banned word]": must be zero. (e) Anonymous-user cleanup confirmed scheduled via pg_cron.

PART 3 — Mobile. Render the live page at 390×844 and 360×800 (View demo): screenshot the chat, a digest with Others expanded, the Profile page, the menu. Fix anything cut off, overlapping, or needing horizontal scroll; the input bar must stay above the keyboard area and Send must be reachable. Re-screenshot after fixes and keep the images in docs/screenshots/ (demo data only).

PART 4 — Docs. (a) README: add an Architecture section with a diagram (Mermaid is fine): GitHub Actions run → ERP (read-only) → Supabase (tables, storage, functions, pg_cron) → GitHub Pages dashboard; the hourly cycle; the failure policy; the demo path. (b) Regenerate docs/PROMPTS.md (now 3+ prompts: feed AI, Ask Ping, classifier, CV summary) and confirm the drift test passes. (c) evals/REPORT.md index up to date with every eval set and its current score. (d) docs/SETUP.md for a new student: prerequisites, the one setup script, first chat message as preferences, what to expect in the first hour. Test the script against a fresh Supabase project if you can create a throwaway one with the token you have; otherwise against the local replica, and say which.

PART 5 — Facts sheet for my 1-pager (I write the 1-pager myself; you only collect facts): docs/ONE_PAGER_FACTS.md with verified numbers and where each comes from — problem framing from the README, hourly schedule and window, number of runs so far and success rate, sources covered, today's demo thread 38→3 messages, Ask Ping eval scores (single/multi-turn), relevance precision/recall per persona, parser evals 56/58 and 143/143, response latency per model, cost (free tier), what is read-only by construction, what's deferred (WhatsApp delivery, hosted multi-user). No adjectives, numbers only.

PART 6 — Final reviewer run on the live URL, as a stranger: open the link, View demo, read today's thread, ask 6 questions including a preference change ("only show me product and consulting roles") and confirm the feed re-splits, ask "which cv for <a demo company>", open Companies and Profile, try something read-only-forbidden ("apply for me"). Record every answer verbatim in docs/REVIEWER_RUN.md with HTTP codes and timings. Anything wrong: fix, redeploy, re-run that question.

HANDOFF REPORT (last message): status table for Parts 1–6, all eval scores, the live URL, the "Needs Vinayak" list, docs/DECISIONS.md summary, diff summary, and confirmation that the working tree is clean and pushed.
`````

## 32. Sat 21 Nov 2026, 23:08 IST (17:38 UTC)

`````text
Closing round. Commit after each part, then tag v1.0.

1. Verify the hourly ticks since the #14 fix (21:11 and 22:11 IST) ran on cron and succeeded; if either failed, fix and report.
2. Fix the 4 remaining Ask Ping eval failures without loosening checks: C2 must quote the CG cut-off; D2 must list company names not counts; D3 week list must include times; M8 turn 2. Re-run and report the score.
3. docs/SUBMISSION.md: the live URL with the one-line instruction "click View demo"; links to docs/PROMPTS.md, evals/REPORT.md, docs/ONE_PAGER_FACTS.md, docs/SECURITY.md, docs/SETUP.md; a 6-line "what to try" list for judges (a company question, a deadline question, a follow-up, a preference change, "which cv for X", "apply for me"). No reference to any other product or working name anywhere.
4. Export the agent's build prompts: write docs/BUILD_PROMPTS.md containing, verbatim and in order, every prompt I gave you in this session (my messages only, not your replies), with the time of each. This is a required deliverable.
5. Final grep of both repos and all docs for "[banned word]": zero hits in current files. Leave the private repo's history alone.
6. Tag v1.0, push, confirm the live build hash matches HEAD. Handoff: scores, URL, anything still open.
`````

## 33. Sat 21 Nov 2026, 23:41 IST (18:11 UTC)

`````text
UI/UX round. Keep the stack vanilla (static HTML/JS/CSS, no framework), keep every test green, deploy only after tests pass. Commit after each part. Work unattended: log judgement calls in docs/DECISIONS.md.

PART A — First-run onboarding, inside the chat
1. Trigger: a signed-in user with an empty profile and no messages sees an empty thread and Ping speaks first. Persist progress in the profile (onboarding_step) so a refresh resumes where they left off. Never show a blank chat with a text box and nothing else.
2. Flow, one question per message, each with tappable quick-reply chips plus a free-text option, and "Skip" always available:
   a. Welcome (2 lines: what Ping does, that it only reads the ERP) → "How do you want your feed?" chips: [Only what fits me] [Everything from the ERP].
   b. Department and degree (needed for eligibility) → chips for common degrees, free text for department.
   c. (Personalised only) "What are you looking for?" with 3–4 example chips that insert text (e.g. "Product & consulting", "Data & analytics", "Finance", "Core engineering") and free text to refine; show the one-line "Saved: …" confirmation after.
   d. (Personalised only) "Want other roles listed separately so you don't miss anything?" [Yes] [No].
   e. (Personalised only) "Upload a CV so I can suggest which one to apply with?" inline upload button in the chat bubble, [Later].
   f. "How often should I check the ERP?" chips [Every hour] [Every 2 hours] [Every 30 min]; and "Between which hours?" default 06:00–01:00 — these write the schedule the kick-run cron actually uses (per profile), not a hardcoded window.
   g. "When should I remind you before a deadline?" [1 h] [2 h] [4 h] [Day before].
   h. Close: "Running your first check now…" → trigger Check now → when the feed lands, one short message explaining what the thread will look like (digests, reminders, tests) and that any of this can be changed by just telling Ping.
3. Everything saved by a chip must be changeable later by chat ("check every 30 minutes", "remind me 4 hours before") through the existing preference flow — extend it for frequency and hours.
4. Demo: onboarding runs for View demo too, but the first bubble offers [Use the demo profile] which fills everything in one tap and jumps to the feed; judges can still walk the flow if they want.
5. Evals/tests: the onboarding is a scripted sequence — test each branch, resume after refresh, skip at every step, and that the schedule written by (f) is what pg_cron picks up.

PART B — Visual and interaction design
1. First write docs/DESIGN.md: a short design spec with one clear direction — a name for it, palette (one accent, neutrals, semantic colours for "for you / applied / closing soon / test"), type scale (a single self-hosted font or a good system stack), spacing scale, radius, message-bubble anatomy per message kind (digest, reminder, test alert, new companies, Ping system note, user message), chips, empty states, light and dark themes following the system with a toggle. Don't produce a generic dark chat template; the thread should feel like a focused inbox for placements.
2. Chat: typing indicator while Ask Ping answers; "N new" unread pill that scrolls to the divider; sticky day headers; digests as cards with a collapsible Others list and a count; test alerts with a time chip that says "in 2 h" / "over"; "✓ applied" badges; the composer stays above the keyboard on mobile; quick-reply chips row; send button states; message entry animation ≤200 ms, no layout shift.
3. Navigation: on mobile a bottom bar (Chat · Companies · Profile) instead of a Menu button; on desktop a slim left rail. Companies page: search box, filters [For you] [Applied] [Closing soon] [All], role rows with the "Apply with" label, tap → detail sheet with everything Ping knows about the role (CTC breakdown, eligibility, deadlines, notices, source). Profile page: cards (About you · What I'm looking for · CVs · Schedule & reminders · Account), each editable in place.
4. Accessibility: contrast ≥ 4.5:1, visible focus rings, 44 px tap targets, labels on every control, reduced-motion respected.
5. Before/after screenshots at 390×844 and 1280×800 for: onboarding step a, the chat with a digest expanded, Companies with a filter on, the role sheet, Profile. Save in docs/screenshots/ (demo data only). Re-run the Admin page check and the reviewer run on the live site after deploy.

Handoff: status table for A and B, screenshots list, anything open.
`````

## 34. Sun 22 Nov 2026, 00:17 IST (18:47 UTC)

`````text
Companies page and role sheet: company is the primary line, role secondary. Company name bold at body size; role one step smaller, regular weight, below it; CTC stays right-aligned on the company line. Same hierarchy in the role detail sheet header and anywhere a role card appears (search results, Closing soon, For you). Clean the company name for display: strip anything in parentheses that is a URL or domain (e.g. "Auro Group([www.AuroIM.com](https://www.AuroIM.com))" → "Auro Group"), trim double spaces, keep the raw ERP name in the data. Screenshot the Companies page at 390 px and 1280 px after the change.
`````

## 35. Sun 22 Nov 2026, 00:50 IST (19:20 UTC)

`````text
Bug: in the chat I asked "microsoft cv submission deadline". Gemini returned "busy", the rule-based fallback ran, and it replied with a generic "due in next 3 days" list that never mentioned Microsoft. Fix the following:

1. Gemini resilience: on busy/429/503, retry up to 3 times with backoff (1s, 3s, 6s). If it still fails, try a lighter Gemini model once before falling back to rules.

2. Rule-based fallback must respect the question:
   - Extract company names by fuzzy-matching words in the message against the companies table (case-insensitive, handle "MS"/"msft" → Microsoft style aliases where cheap).
   - Detect intent keywords: deadline/due/submit/form/cv, shortlist, test/date/room, which cv.
   - If a company matched: answer ONLY about that company: its open deadlines (form + CV submission), latest notice, and status. If none found, reply plainly: "No open deadline for Microsoft in the ERP data (last checked <time>). Last Microsoft notice: <title, date>." If the company isn't in the data at all, say that.
   - Only fall back to the generic "next 3 days" digest when no company and no intent were detected, and label it as such ("I couldn't tell what you meant. Here's what's due soon:").

3. Digest cleanup:
   - Merge items for the same company + same deadline into one line (e.g. "Meesho (Senior Associate - BM): form + submission by Sun 22 Nov 18:00").
   - Never output a count without names. For "N deadlines moved/now close at X", list the companies (first 5, then "+N more").

4. Evals: add cases for (a) a specific company with a deadline, (b) a specific company with no deadline, (c) a company not in data, (d) a misspelled company name, each run with the LLM forced off so the fallback path is tested. Run them and show results.
`````

## 36. Sun 22 Nov 2026, 01:22 IST (19:52 UTC)

`````text
Login screen: add a "Set this up for yourself" path.

1. Sign-in screen layout, top to bottom: Ping name + one-line promise ("Your ERP, filtered for you, every hour."), the owner sign-in, the View demo button, then a quiet link "Set up Ping for yourself →".
2. That link opens setup.html in the public dashboard repo (static, same styling, generated from docs/SETUP.md so they can't drift — add that to the build and the drift test). Content, in this order:
   - What you get (3 bullets) and what it never does (read-only; never applies, never changes anything; your credentials stay in your own GitHub + Supabase, nothing central).
   - What you need: a GitHub account, a free Supabase project, a free Gemini API key, your ERP login — with the "free tier" note.
   - Steps (numbered, ~8): fork/clone the source repo, create the Supabase project, add the secrets (list each name and where it goes), run setup/new_student_setup.py once, turn on the schedule, open your dashboard, answer Ping's first questions in the chat, done. Each step one or two lines; the exact commands in code blocks.
   - Time estimate and "first check lands within the hour".
   - Troubleshooting: the three things that actually went wrong for me (ERP blank login page; GitHub cron not firing → Supabase cron; Pages custom domain). One line each.
   - Privacy: what data lives where, that the demo is anonymised sample data.
3. Source repo link: use the placeholder SOURCE_REPO_URL in one place; until I give you a public repo URL, render it as "Source repo: available on request" with no dead link. Nothing on the page may mention any other product or working name.
4. Mobile check at 390 px; screenshot to docs/screenshots/.
`````

## 37. Sun 22 Nov 2026, 01:23 IST (19:53 UTC)

`````text
Audit the notice-attachment pipeline and report, no changes unless something is broken:
1. Which attachment types are handled (PDF text, scanned PDF/images via OCR, XLSX/CSV, DOCX, links to Google Drive)? For each unsupported type, what does the student see?
2. Matching: roll number in all formats the ERP uses (22XY10042, 22XY10042, with spaces/dashes), name-only lists (exact and fuzzy), and a roll number that appears only as part of a longer string. Show the test cases that exist.
3. Room/slot extraction: when a PDF is a table of roll → room/slot/time, prove the student gets their own row, not the first row or the header, on a messy table (merged cells, two-column layout, page break mid-table). Add a test fixture if none exists.
4. Negative: a PDF that lists you for a different company's test on the same day; a PDF with 500+ rows (timing).
5. What the feed message and the Ask Ping answer look like for: on the list with a room; on the list without a room; not on the list.
Fix anything that fails, then summarise coverage in evals/REPORT.md.
`````

## 38. Sun 22 Nov 2026, 01:23 IST (19:53 UTC)

`````text
Two config changes and a re-run.
1. Set PING_AI_LITE_MODEL to gemini-3.1-flash-lite on the Supabase function secrets. Keep the order: main model with retries → lite model once → rules answer. Document it in SECURITY.md's secrets inventory and PROMPTS.md.
2. Split Gemini keys: the live function uses GEMINI_API_KEY (Supabase secret); evals, demo-refeed, relevance re-marks and every Admin task use GEMINI_API_KEY_EVALS (GitHub secret). Stop and tell me exactly where to create the second key and which secret name to paste it into; wait until I confirm. Then prove the split: an eval run must not touch the live key (check the function logs show no eval traffic).
3. After the free quota resets (00:00 Pacific = 13:30 IST), re-run the full Ask Ping evals with the paced runner and record main-model-only and all-cases scores in evals/REPORT.md, ONE_PAGER_FACTS.md and SUBMISSION.md. Add a line in SUBMISSION.md's "what to try" that answers marked "(Gemini busy)" come from ERP data rules, not the model.
`````

## 39. Sun 22 Nov 2026, 02:07 IST (20:37 UTC)

`````text
Live updates, no reloads. Commit after each part, deploy when tests pass.

1. Realtime: the dashboard subscribes (Supabase Realtime) to inserts/updates on chat_messages for the signed-in user (and on the demo rows for a demo session), plus the runs table for run status. New Ping messages append to the thread immediately with the unread divider logic; the header's "last checked" updates live. On tab focus/visibility change, refetch anything missed (realtime can drop during sleep). Fallback if the socket fails: poll every 15 s while a run is in progress, every 60 s otherwise. RLS must still hold on the realtime channel — a demo session must not receive the owner's messages; test it.

2. "Check now" as an in-chat process: pressing it posts a Ping message "Checking the ERP now… usually takes 1–2 minutes" with a progress state that updates in place: queued → logging in → reading companies/notices/PDFs → done. On completion it becomes "Done at 12:17 — 2 new items" (or "Done — nothing new since 11:41") and the new digest messages arrive right after it. On failure, the failure-policy message appears instead. The button is disabled while a run is in progress, with the state shown on it. Hourly runs show the same "Done — N new" line only when there is something new; otherwise just the header timestamp changes.

3. Scroll behaviour: if the user is scrolled up when new messages arrive, show a "↓ N new" pill at the bottom that scrolls to the first new message; if they're at the bottom, auto-scroll. Never jump the viewport under a user who is reading.

4. Demo: View demo sessions get the same realtime path (their own chat rows); Check now in demo shows the process using the sample snapshot and finishes with "Demo: sample data, nothing new to fetch".

5. Tests: realtime append,
`````

## 40. Sun 22 Nov 2026, 02:28 IST (20:58 UTC)

`````text
JD coverage bug. "summarise JPMC's JD" → "I don't have the JD", but the JD is on the ERP. Fix the pipeline, not the answer.

1. Diagnose on the real ERP (read-only, through the gate): for JP MorganChase and 5 other "JD missing" roles, record exactly where the JD lives — inline field, a detail page/popup per role, a PDF/DOCX attachment on the role, or an external link (Drive, company site). Report the breakdown for all 31 "JD missing" roles.
2. Fetch it: extend the role parser to follow each of those paths — open the role's detail view, download attachments (reuse the attachment pipeline incl. OCR), and fetch external links when they're public (time-limited, size-capped, never submit anything). Store jd_text, jd_source (inline/attachment/link/detail) and jd_url on the role; refetch only when the role changes. If a link is private or dead, store jd_source = "link-unreadable" with the URL.
3. Reclassify every role whose JD went from missing to present (the cache key includes role text, so this should be automatic — verify) and drop the "(JD missing)" tag for them.
4. Ask Ping: "summarise X's JD" / "what's the JD for X" / "what do they want for X" → a short structured summary: role & team, what you'd do (3 bullets), must-have skills, location, eligibility/CG, and anything unusual (bond, shifts, rotation) — ≤120 words, from jd_text only, no invention. If jd_source is link-unreadable: "The JD is a link I can't open: <url>". Add eval cases for all three outcomes, including JPMC on real data if it's reachable through the demo snapshot (otherwise a fixture).
5. Companies page role sheet: show the JD summary with a "Full JD" expander and the source link.
6. Run a live check on JPMC and report the before/after count of roles with a usable JD out of 201.
`````

## 41. Sun 22 Nov 2026, 03:26 IST (21:56 UTC)

`````text
The UI doesn't feel alive. Do this in two steps.

STEP 1 — Two directions, mocked, no app code changed yet. Build two static mock pages (docs/mocks/a.html, b.html) of the chat home with real demo content and render each at 390×844 and 1280×800 to PNG. Each must have a name, a one-line idea, and differ in palette, type and texture — not just accent colour:
  A. "Night desk": deep charcoal with warm paper-toned bubbles, one amber accent for anything closing within 3 h, a humanist display face for headings and Ping's name, subtle grain/vignette so the background isn't flat.
  B. "Signal": near-black with a single electric accent (not teal), cool off-white text, monospaced numerals for times/CTC, hairline dividers, bubbles replaced by left-rail cards with a coloured spine per message kind (digest / reminder / test / system / you).
  Both must show: a digest card with Others collapsed, a test alert with a live countdown chip, a Ping system note, a user message, the quick-reply chips, the composer, and the header with Ping's status. Send me the four PNGs and stop.

STEP 2 — after I pick, implement that direction across chat, Companies, role sheet, Profile, sign-in and setup page, with these non-negotiables:
  Presence: Ping's avatar has a state — idle, "checking the ERP…" (soft pulse while a run is in progress), "found 2 new" (brief accent flash) — driven by the runs table in realtime. Header shows "last checked 4 min ago" and ticks.
  Time: every deadline/test within 24 h shows a live countdown ("in 1 h 56 m"), turning amber under 3 h and red under 1 h; "over" when past.
  Motion: messages slide/fade in (≤200 ms, respects reduced-motion); typing indicator while Ask Ping answers; chip press and send-button feedback; skeleton loaders instead of "Loading…"; the unread pill eases in.
  Voice: Ping's system notes read like a person — greet by time of day on first open, "nothing new since 23:11, go sleep" after midnight, "2 close tonight, you've done both ✓" — short, specific, never chirpy. Write a tone guide in docs/DESIGN.md with 10 before/after lines.
  Hierarchy: one accent, used only for things that need action; everything else neutral. Display titles for long ERP role names ("JPMC — Global Research Analyst") with the full name on the role sheet.
  Deliver: screenshots at both sizes and a 15-second screen recording (GIF) of: open → Check now → pulse → new message arrives → countdown ticking → typing indicator → answer. Re-run the Admin page check and reviewer run.
`````

## 42. Sun 22 Nov 2026, 03:35 IST (22:05 UTC)

`````text
Decision: drop both mocks. Direction = the familiar messaging-app look, done properly, plus a Today panel. Implement directly (no more static mocks); deliver a 20-second GIF because stills can't show what "alive" means here.

CHAT (keep what people already know)
- Header like a contact: round avatar, name, and a live status line under it that changes: "checked 4 min ago" → "checking the ERP…" (animated dots) → "found 2 new" (2 s) → back. Driven by realtime run state.
- Bubbles with tails: Ping's dark-grey on the left, yours tinted green on the right, time inside the bubble, date pills ("Today", "Yesterday"), a subtle original wallpaper pattern behind the thread (our own, low-contrast, not copied from any app).
- Message kinds inside the bubble: a small coloured label line at the top (REMINDER · TEST · NEW · PING), the body, and for digests a "Show 30 more ▸" link that expands in place. Countdown chips ("in 1 h 48 m") tick live, amber <3 h, red <1 h, "over" when past.
- Motion: new bubbles slide up and fade in (≤180 ms), typing bubble with three dots while Ask Ping answers, send button fills on press, the unread "N new ↓" pill slides in. Respect reduced-motion.
- Quick-reply chips stay; composer stays above the keyboard on mobile.

TODAY (new)
- Desktop: a right rail "Today". Mobile: a 4th tab in the bottom bar (Chat · Today · Companies · Profile) with a badge for items still ahead.
- Content, ordered by time: every test today (company, role, time, room/slot if known, "you're on the list" / "not on the list", countdown); every deadline today (time, "N for you · M applied", the for-you names); shortlists/notices that arrived today (one line each); the next ERP check time. Items that are over move to the bottom, struck through. A tap jumps to the related chat message or opens the role sheet.
- Tomorrow preview at the bottom: a single line "Tomorrow: 2 tests, 4 deadlines".
- Empty state with a short human line ("Nothing scheduled today. Next check 14:11.").
- Demo sessions get the same panel from the sample snapshot.

COMPANIES / PROFILE / SIGN-IN: same visual language (fonts, radii, colours), no redesign beyond consistency. Company-first hierarchy stays.

DELIVER: screenshots at 390×844 and 1280×800 (chat, Today, Companies, role sheet), a 20 s GIF: open → Check now → status line animates → new bubble slides in → countdown tick → ask a question → typing dots → answer. Then Admin page check + reviewer run on the live URL.
`````

## 43. Sun 22 Nov 2026, 04:01 IST (22:31 UTC)

`````text
Ask Ping answer routing. Rules first for facts, Gemini for language. Commit per part.

1. Intent router: classify each message (cheap, local) into FACT intents — which CV, due today/tonight/tomorrow/this week, tests today/when/room, shortlisted, CTC/breakdown, eligibility, applied status, preferences, counts of any of these — or OPEN (summaries, "why", comparisons, follow-ups with no clear slot, anything else). FACT intents are answered by answer_rules.js directly, no model call, in <1 s. Follow-ups ("and tomorrow?", "nothing else?") resolve against the last turn first, then route the same way.
2. OPEN intents go to Gemini with the rules' structured facts attached as context; Gemini may phrase, never compute: every number, time, count and company list in its answer must be copied from the facts block. Post-check: if a number/count in Gemini's reply isn't in the facts, replace the reply with the rules answer for that intent (log it as "model_count_mismatch").
3. Latency cap: Gemini total wait ≤10 s (one retry), then the lite model once with ≤5 s, then rules. The typing bubble shows "still thinking…" after 4 s so it never looks frozen.
4. Fix the 17-vs-8 case specifically: add it as an eval (must equal the digest's for-you count) and re-run the fallback evals + the multi-turn set with no_ai to prove FACT intents never depend on the model.
5. Report: share of the 42 single-question evals now answered by rules vs model, median latency for each, and the live answers for "which cv for blackbuck" and "what's due tonight?".
`````

## 44. Sun 22 Nov 2026, 04:24 IST (22:54 UTC)

`````text
Make Ping an installable app with push notifications (PWA + Web Push). Commit per part; keep everything working for people who don't install it.

1. PWA: manifest (name, short name, original icon set incl. maskable, theme colour, standalone display, start_url under /ping-dashboard/), service worker that caches the app shell for instant open and works offline for the last-loaded thread (reads stay; sends queue until online). Add an "Install Ping" prompt in the chat as a Ping message on the 2nd visit (Android: the install event; iOS: a short "Share → Add to Home Screen" instruction with a picture), dismissible, never nagging.

2. Push: VAPID keys (private key as a Supabase secret, public in config.js). Subscription stored per user in a push_subscriptions table (owner-only RLS; demo sessions can't subscribe). Opt-in via a Ping message "Want me to notify you when something's for you?" [Yes] [Not now] — and a Profile toggle. A send-push Supabase function (or a step at the end of the hourly run) sends one notification per new for-you message: title = the message label ("Reminder · closes tonight"), body = the first line, tap opens the thread at that message. Nothing is sent for "nothing new" runs or Others-only changes. Quiet hours honour the student's check window. Rate-limit: max 1 push per run plus test-day reminders.

3. Test-day reminders: for a test the student is listed for, push at the reminder lead time ("Groww test in 2 h · room 304") even if no run happened — schedule it via pg_cron from the item's time.

4. Fallback: email stays as it is for the 3-failed-runs alert; add an option to also email for-you digests, off by default.

5. iOS/Android verification: real-device checks aren't possible here, so prove it with a headless browser: manifest validates, service worker registers, subscription round-trips, a test push is received by a subscribed headless client; and document the manual steps for me to verify on my phone (Android and iPhone) in docs/PUSH.md. Update SECURITY.md (new secret, new table), SETUP.md (VAPID key generation is one command in the setup script), PROMPTS.md if any prompt changes.

Report: install flow screenshots, the push payload example, and what to tap on my phone to verify.
`````

## 45. Sun 22 Nov 2026, 04:49 IST (23:19 UTC)

`````text
Make the institute mailbox a first-class source, read-only, privacy-first.

1. Scope: only mails that are about placements — from CDC/placement office addresses, from companies that exist in the ERP list, or containing placement signals (test link, shortlist, interview, form, deadline, pre-placement talk, offer). Everything else is never read beyond headers and never stored. OTP mails are used for login only and never stored or shown. Document the exact filter in SECURITY.md.
2. Extract per mail: company (matched to the ERP list with the same alias/typo matching), kind (form / test link / interview / shortlist / PPT / offer / announcement), any deadline or date-time, links, and attachments through the existing attachment pipeline (roll-number lists in mailed PDFs count as shortlists). De-duplicate against ERP notices: if the ERP has the same thing, the mail just adds "also mailed to you" and the link; if only the mail has it, it becomes a feed item like any notice.
3. Feed/Today/Ask Ping: mail-only items appear with a small "via email" tag; forms and test links show the link; deadlines from mail enter digests and the Today panel; "any mails for X", "did I get a test link for Y", "what's due from mail" work. Reminders fire on mail-only deadlines too.
4. Eligibility and relevance apply as usual; nothing in a mail ever changes applied status (that comes only from the ERP).
5. Evals: a fixture mailbox with 20 mails (10 placement, 10 noise incl. one OTP, one with a PDF shortlist, one Google Form with a deadline, one duplicate of an ERP notice). Must: store none of the noise, never store the OTP, dedupe the ERP duplicate, extract the form deadline, and find the roll in the PDF. Demo gets 4 anonymised sample mails so View demo shows the "via email" tag.
6. Report coverage before/after on my real mailbox: how many placement mails in the last 14 days, how many were already on the ERP, how many were mail-only.
`````

## 46. Sun 22 Nov 2026, 04:57 IST (23:27 UTC)

`````text
Four fixes from the live chat, commit per item.

1. Ping must know about itself. Add a HELP intent to the router, answered from a small built-in help doc (docs/HELP.md → bundled into the app at build, drift-tested): how to install (platform-aware: Windows/Mac Chrome = ⋮ menu → "Install Ping" or the install icon in the address bar; Android = Install button / ⋮ → Install app; iPhone = Share → Add to Home Screen), how notifications work and how to turn them on, how often it checks and how to change it, what it can and can't do (read-only), how to change preferences, where the data lives. "how to install", "how do I get notifications", "what can you do", "help" all answer from this, never "I don't have any information". Add a "Help" quick-reply chip. Eval cases for 6 help questions.

2. The install message. On my Windows Chrome it showed something, I tapped Done, nothing happened, and no steps appeared. Fix: if the browser's install event hasn't fired, the message shows the manual steps for the detected platform instead of a dead button; the button is "Install" only when it will actually open the browser's install dialog; "Not now" hides it for 7 days, not forever; Profile keeps an "Install Ping" entry with the steps so it's always findable. Test on Chromium with and without the install event.

3. Today panel: remove "Next ERP check" (it belongs in the header status line only). Group same-deadline items: the five "fill the form by Sun 22 Nov 20:00" rows become one row "5 forms due 20:00 — Piramal, SLB, LTM, Auro, …" that expands; keep tests as individual rows. "Additional requirement · several companies" is too vague — show which companies (first 3 + N) and what the requirement is.

4. Chat clutter and text: consecutive "Done — nothing new since …" messages collapse into one thin system line that updates in place ("Checked 03:18 · nothing new since 02:53"), only a real "found N new" gets a bubble. Fix the missing-glyph boxes in JD text (bullets from the ERP/PDF rendering as □): normalise bullet/odd characters when storing jd_text.

Report with a screenshot of the chat and Today after the change.
`````

## 47. Sun 22 Nov 2026, 05:37 IST (00:07 UTC)

`````text
Continue the mailbox work to completion, unattended: run Admin › apply-sql now so the hourly run stops saving mails without kind/dates, then finish the parked parts in order — "via email" tags and "also mailed to you" on ERP notices, the Today / Ask Ping / reminder hooks, the 4 anonymised demo mails (anonymiser check must pass), and my real 14-day coverage report (how many placement mails, how many already on the ERP, how many mail-only). Deploy when tests pass, then the Admin page check and reviewer run on the live site. Finish with a status table and the diff summary.
`````

## 48. Sun 22 Nov 2026, 06:03 IST (00:33 UTC)

`````text
Fact answers in the browser. Route FACT intents locally: run answer_rules.js in the page against the already-loaded data (roles, items, notices, marks, profile), append the answer immediately, and only call the ask-ping function for OPEN intents. Keep server-side rules as the fallback when the page's data is older than the last run (compare the run id). Save the local Q&A to chat_messages the same way. Target: FACT answers appear in <300 ms with no typing bubble; show the typing bubble only for OPEN. Re-run the single-question evals through the page (Admin ask-ping-page) and report median latency for FACT vs OPEN.
`````

## 49. Sun 22 Nov 2026, 06:12 IST (00:42 UTC)

`````text
Public source copy: YES . Final unattended round, ~6 hours. Rules: commit per fix, deploy only after tests pass, keep the live site working at all times (if a deploy breaks it, revert first, fix second), log judgement calls in docs/DECISIONS.md, stop at 11:30 IST at a clean commit with live build = HEAD, and write the handoff. No new features. Order:

1. KEY SPLIT + EVALS. Re-deploy so the evals key reaches Supabase; prove from function logs that eval traffic uses it and none uses the live key. Run every eval set paced: Ask Ping single + multi-turn (main-model-only and all-cases scores), relevance (both personas), mail, fallback, parser, attachments. Fix genuine failures without loosening checks; record all scores in evals/REPORT.md. Run ask-ping-page to completion.

2. QA AS A STRANGER on the live URL at 390×844, 768×1024, 1280×800, light and dark, signed-in (local replica) and View demo: every page and state — onboarding (all branches, skip, refresh-resume), chat (digest expanded, Others, countdown, typing, unread pill, offline banner, queued send), Today (tap-throughs, grouped rows, empty day), Companies (search, each filter, role sheet incl. JD summary, "Apply with"), Profile (every card editable, CV upload to the picker, notifications toggle, install card), sign-in and setup page, help answers. Fix every glitch: overlaps, truncation, misaligned buttons, text too small (<14 px body on mobile), tap targets <44 px, keyboard covering the composer, scroll jumps, focus rings, stuck loaders. Visual regression set in docs/screenshots/final/.

3. PERFORMANCE. Lighthouse on the live URL (mobile): PWA installable, performance ≥90, accessibility ≥95, best practices ≥90; fix what's below. First load under 2 s on a throttled 4G profile; Companies list smooth with 210 roles; FACT answers <300 ms in-page; no layout shift on message arrival. Record numbers in ONE_PAGER_FACTS.md.

4. RELIABILITY. Every failure state has a human message and a way out: function down, realtime down, offline, Gemini busy, demo rate limit hit, ERP refused, 3 failed runs, push permission denied. Verify each by simulation. Confirm every overnight hourly run since 22:11 IST ran on cron and succeeded; investigate any miss. Send a headless push end-to-end once more after all deploys.

5. NEW-STUDENT WALKTHROUGH. On the local replica: fresh project → setup script → first open → onboarding by chat → first check → first digest → preferences change by chat → CV upload → install prompt → push opt-in. Time it; fix any step that needs a manual action; update SETUP.md and the setup page with the measured "time to first feed".

6. COPY PASS. Read every Ping system message, help text, empty state, error, button label and onboarding line against docs/DESIGN.md's tone guide: short, specific, no "the data does not contain", consistent capitalisation and time formats (IST, 24 h), company-first naming, no jargon. Fix in place.

7. SECURITY RE-CHECK. Re-run the RLS proof suite (demo sees 0 real rows in every table, bucket, realtime channel and push subscriptions), secrets inventory and the 20-run log scan, anonymiser final check on all demo copies, grep both repos for the banned word (0). Update SECURITY.md.

8. PUBLIC SOURCE COPY (only if YES above): history rewrite via git filter-repo into a new public repo "ping", every real value from the earlier scan table replaced, demo data clean at every commit, secrets copied, old workflow runs untouched, CI green on the new repo; set SOURCE_REPO_URL in the setup page and SUBMISSION.md; never flip this private repo.

9. DOCS. Everything from the consolidation list (README/architecture, SECURITY, SETUP, PUSH, PROMPTS regenerated, evals index, ONE_PAGER_FACTS with all new numbers, SUBMISSION "what to try", BUILD_PROMPTS appended with times). SUBMISSION.md must be enough for a judge who has 10 minutes.

HANDOFF (last message, by 11:30 IST): status table 1–9, every eval score, Lighthouse numbers, live URL + build hash, the "Needs Vinayak" list (tag v1.1, phone push check, anything else), and the diff summary.
`````

## 50. Sun 22 Nov 2026, 12:47 IST (07:17 UTC)

`````text
Bug: on the installed phone app (iPhone Home Screen and Android Chrome install), every time I open Ping I have to sign in again. Goal: sign in once, stay signed in for weeks on both platforms, like any chat app. Do NOT store the password anywhere; persist the session instead.

1. Diagnose: check how the Supabase client is created (persistSession, autoRefreshToken, storage = localStorage not sessionStorage, a stable storageKey), whether anything on load (service worker, cache clear, the demo path, an error handler) calls signOut or clears storage, and whether start_url and scope in the manifest match the page exactly, so the installed app, the browser tab and the service worker share one origin and one storage. Report what you find before changing anything.
2. Fix: persistSession true, autoRefreshToken true, localStorage with a fixed key; on app open, restore the session and refresh the token before deciding to show the sign-in screen (skeleton while it checks, never flash the login form). Refresh again when the app comes back to the foreground (visibilitychange), since both iOS and Android suspend installed apps. Set the Supabase refresh-token lifetime to cover a placement season (30+ days of inactivity) and say what you set. The demo sign-out and anonymous cleanup must never touch the owner's session.
3. Painless re-login if it ever happens: the sign-in form is a real <form> with autocomplete="username" and autocomplete="current-password" on proper input types, so iCloud Keychain (iPhone) and Google Password Manager (Android) offer to save it once and fill it with Face ID / fingerprint afterwards. A short "You'll stay signed in" note under the button.
4. HELP.md and the install steps, per platform: iPhone: "Sign in once inside the installed app; it doesn't share Safari's login." Android: "If you signed in in Chrome before installing, you're already signed in in the app."
5. Test both engines: Playwright WebKit (iPhone) and Chromium with an Android mobile profile. For each: sign in, close the context, reopen with the same storage state, assert no sign-in screen and a valid session; force a token expiry and assert a silent refresh; simulate background → foreground and assert the session survives. Deploy, then tell me exactly what to do on each phone to confirm.
`````

## 51. Sun 22 Nov 2026, 13:25 IST (07:55 UTC)

`````text
Today panel: every row must open something useful, on phone and PC. Commit per part.

1. Detail sheet. Tapping any Today row opens a sheet (full-screen with a back arrow on phones; a side panel on PC, chat stays visible) that lists everything in that row, one card per company/role:
   - company (bold) and role, deadline with live countdown, kind (application / form / CV submission / test / shortlist), status: ✓ applied / not applied / on the list / not on the list
   - For you or Other, the one-line reason, "Apply with: <CV>"
   - buttons: "Open on ERP" (direct link to that company's application or form page on the ERP; if the ERP has no direct URL, the companies-list URL plus the company name to search), "Form link" when a notice or mail carries one, "Notice" (opens the source notice/PDF), "Show in chat" (jumps to and flashes the message)
   - order: For you and not applied first, then the rest; Others collapsed under a count
   - sheet header: "55 applications close today 20:00 · 3 for you · 9 applied", with filter chips [Not applied] [For you] [All]
   The same sheet opens from the "Show 33 more" link in chat digests and from Ask Ping answers that list roles, so there is one place to act from.
2. Tests, shortlists and notices in Today open the same sheet with their own fields (time, room/slot, your row, the PDF link).
3. Links never dead-end: if a link is unknown, the button is hidden, not disabled. Never open the ERP inside the app; open it in the browser/system browser. Ping stays read-only: these are links only.
4. Clean-ups seen on the live page: (a) the "Add your CGPA and degree and department…" line must appear once (a single Ping note plus a dot on Profile), not under every digest, and disappear when filled; (b) the "Latest ↓" pill must sit above the composer, not over message text; (c) "Apply with" shows "Consult CV" for every role. If I have only one CV uploaded that's expected, say so; if I have more, find why best_cv never varies and fix it.
5. Test at 390×844 and 1280×800: tap each Today row type and check the sheet opens with working links, back works on phone, keyboard/scroll don't trap. Screenshots, deploy, live-page check.
`````

## 52. Sun 22 Nov 2026, 13:26 IST (07:56 UTC) — sent while the agent was working

`````text
New "Forms" section: a checklist of every form that has come in, which I tick off as I fill them. Commit per part.

1. Data: a forms list built from ERP notices, notice PDFs and placement mail: each form has company (or "several companies" with the names), what it is for (registration, CV submission, additional requirement, test slot, PPT RSVP…), deadline, link, source (notice / mail) and first seen. Dedupe the same form arriving by notice and mail. A new table form_status (owner-only RLS): filled true/false, filled_at, set by me. Never written to the ERP; the tick is my own record.
2. UI: a Forms tab (phone bottom bar: Chat · Today · Forms · Companies · Profile; PC left rail). Sections: Due today · Upcoming · Past due (not filled) · Filled. Each row: checkbox, company (bold), what the form is for, deadline with countdown, "Open form" link, "Notice" link. Ticking moves it to Filled with a short undo toast; unticking moves it back. Badge on the tab = unfilled forms due in the next 24 h. Search box and [For you] [All] filter (For you = forms for companies I'm eligible for or that match my targets).
3. Ticks drive everything else: a ticked form drops out of reminders, push notifications, digests' "not filled" counts and the Today panel's counts ("7 forms due 20:00 · 3 filled"); Today's forms row opens this list filtered to that deadline. Ask Ping: "which forms haven't I filled?", "did I fill the Groww form?", "mark the Piramal form as filled" (the last one ticks it and confirms in one line).
4. In chat digests and the Today sheet, every form line gets the same checkbox, synced live with the Forms tab.
5. Demo/test data: the anonymised snapshot gets the forms list too. Tests: dedupe, tick → reminder suppressed, undo, realtime sync between two open devices, phone 390×844 and PC 1280×800 screenshots. Update HELP.md ("tick forms as you fill them") and SUBMISSION.md's "what to try". Deploy, live-page check.
`````

## 53. Sun 22 Nov 2026, 13:27 IST (07:57 UTC) — sent while the agent was working

`````text
Remove the "View demo" button from the sign-in screen. Reviewers will sign in with my own credentials.

1. UI: delete the button and any "View demo" mention on the sign-in screen, setup page, HELP.md (Ask Ping help answers), install prompts and README. Keep the anonymous demo path in the code, reachable only by a hidden URL parameter that is not linked anywhere, because the Admin live-page, ask-ping-page and eval runners depend on it. Confirm those still pass.
2. Before judging: snapshot my profile (targets, reminder hours, list-others, check window, CV labels and files, notification settings) into a new Admin task, profile-snapshot, and add profile-restore that puts it back exactly. Run the snapshot now and confirm it reads back.
3. Password: tell me the exact steps to set a new password for my dashboard login (Supabase Auth, through an Admin task so it never appears in logs), so I can give reviewers a password I use nowhere else and change it after judging.
4. Owner session safety: signing in on a reviewer's device must not sign me out on my phone (sign-out is device-only now; verify with two sessions).
5. Update SUBMISSION.md and the setup page: "Sign in with the credentials in the submission note." Rebuild, deploy, run live-page and the PWA check, report.
`````

## 54. Sun 22 Nov 2026, 13:32 IST (08:02 UTC) — sent while the agent was working

`````text
Make the Forms list smart about duplicates and extensions. Read-only: open form pages to read them, never submit, prefill, or sign in.

1. Canonical identity: resolve every form link to a canonical form key before storing. Follow short links (forms.gle, bit.ly, tinyurl, lnkd.in) to the final URL; for Google Forms extract the form id (docs.google.com/forms/d/e/<id>/… and /d/<id>/…, viewform / formResponse / edit variants, strip usp= and other query params); same for Microsoft Forms (id param), Zoho, Typeform, Jotform. Same key = same form, whatever the notice or mail around it says.
2. Read the form: fetch the public form page (cached, time-limited, size-capped) and store its title, description's first lines, the question count, and whether it says "no longer accepting responses". If the form needs an institute sign-in, store "sign-in required" and fall back to the link and notice text; don't try to log in.
3. Matching when keys differ or a notice has no link: fuzzy-match on company + form title + purpose + similar question set. High-confidence match → merge; medium → keep separate but show "Looks like the same form as <X>, merge?" with [Merge] [Keep both] that I can tap; the choice is remembered.
4. Reposts and extensions: a repost of a known form never creates a new row. It updates the deadline (keep the history: "deadline moved 21 Nov 20:00 → 22 Nov 20:00"), adds the new notice/mail to the row's sources ("posted 3 times: notice 1791, mail, notice 1796"), and keeps my tick. If a form I ticked as filled is reposted with a new deadline, it stays filled; show a small "deadline extended" note, no reminder. If the form page now says it's closed, mark the row Closed.
5. Chat follows the same rule: a repost or extension produces one "deadline extended" line on the existing form, not a new form message.
6. Evals: a fixture of 15 form postings: same Google Form via forms.gle and full URL, same form with different usp params, a deadline extension repost, the same form in a notice and in a mail, two different forms from one company with similar titles, a closed form, a sign-in-required form, a notice with no link. Expected: the right number of distinct rows, extensions merged with history, ticks kept, the two similar-but-different forms kept apart, the closed one marked. Report the score and add it to evals/REPORT.md.
`````

## 55. Sun 22 Nov 2026, 13:35 IST (08:05 UTC) — sent while the agent was working

`````text
Light visual polish. Do NOT change layout, navigation, components, or behaviour; only the logo, colour and small finishing details. Commit per part.

1. Logo: design 3 original marks for Ping (simple, works at 16 px favicon and 512 px app icon, readable on light and dark, no resemblance to any existing app's logo). Ideas to explore: a speech bubble with a small signal dot, a "P" built from a notification ring, a soft radar ping. Render all 3 as app icon + favicon + header avatar on a phone home screen mock and in the header, save to docs/screenshots/logo/. Apply the strongest one everywhere (manifest icons incl. maskable and iOS, favicon, header avatar, sign-in screen, setup page, push notification icon/badge) and tell me which and why in two lines; keep the other two in docs/design/ so I can say "use option 2".
2. Colour: keep the current scheme but refine it: one accent that matches the new logo (a little richer than the current teal, still calm), consistent use of amber for "closing soon" and red only for "under 1 h / past due", slightly warmer neutrals in dark mode so it doesn't feel flat. Contrast ≥ 4.5:1 in both themes; run the contrast test.
3. Small finishing details only: consistent corner radius across bubbles, sheets, chips and cards; one icon set weight; slightly more breathing room in the header and the Today rail; date pills and labels aligned; the active tab state clearer. Nothing moves.
4. Before/after screenshots of chat, Today, Forms, Companies and sign-in at 390×844 and 1280×800 in light and dark. Deploy, run live-page and the PWA check (icons must validate). Installed apps pick up the new icon on next launch on Android; on iPhone tell me if it needs re-adding to the Home Screen.
`````

## 56. Sun 22 Nov 2026, 14:10 IST (08:40 UTC) — sent while the agent was working

`````text
P0 CORRECTNESS BUG. Ping told me "FirstClub shortlist is out (Product Management). You're not on it." I am on the new shortlist (I got a call). Then "check firstclub again" and "I think I might be there, I received a call" returned the identical answer. Nothing else until this is fixed and verified.

1. Diagnose on real data (read-only), report before fixing: list every FirstClub notice and attachment on the ERP now (ids, times, file types); which ones the pipeline fetched, parsed and matched, and what it found for my roll. Was there a newer list after 12:43? Was the 11:45 list a name-only list, XLSX, image or scanned PDF, a different roll format, or a second page/file that wasn't read? Also: why was the 13:41 run skipped ("next 14:41" after "checked 12:43")?
2. Fix the root cause in the parser/fetcher, add the real FirstClub case (anonymised) as a regression test, then re-scan ALL shortlist/test-list notices of the last 14 days with the fixed code and report any other changed results (each change: company, old verdict, new verdict).
3. Never assert absence. Wording rules everywhere (feed, Today, Forms, Ask Ping, push):
   - roll (or exact name) found → "You're on the FirstClub shortlist (Product Management)" + slot/room if present.
   - not found in a file Ping fully read → "I couldn't find your roll number in the FirstClub shortlist (posted 11:45). Please check the list yourself: [Open list]". Never "You're not on it."
   - file unreadable/partly read/name-only/scanned with low OCR confidence → "I couldn't read the FirstClub shortlist reliably. Check it here: [Open list]".
   - every verdict shows which notice/file and when it was read.
4. Re-check on demand: "check X again", "recheck", "I think I'm on it", "I got a call from X", "are you sure?" → fetch that company's latest notices and attachments live from the ERP now (one targeted, read-only fetch through the gate, rate-limited to once per company per 5 min), re-parse, then answer with the fresh result and its time; if the result changed, also update the feed message. Show "Checking the ERP for FirstClub now…" while it runs. If the ERP is unreachable, say so and give the list link; never repeat the old verdict as if fresh.
5. Staleness guard: any answer about shortlists, tests or deadlines says how old the data is when older than 30 min, and offers [Check now].
6. Evals: add cases for found / not-found-in-readable-file / unreadable file / "check again" triggers a live fetch / user disputes the answer → recheck, not repeat. No eval may expect the phrase "You're not on it".
7. Also fix: the "Latest ↓" pill still covers message text; dock it above the composer.
Report: the root cause, what changed, the re-scan diff, and the live answer to "check firstclub again".
`````

## 57. Sun 22 Nov 2026, 14:10 IST (08:40 UTC) — sent while the agent was working

`````text
P0 continued: the chat must follow the conversation. Live example: after the FirstClub answer I wrote "Check erp bruh for latest updates, dont answer on old data". Ping answered with every deadline closing today. It should have re-checked FirstClub on the ERP now and answered about FirstClub.

1. Conversation state: keep an active topic per thread (company, role, kind: shortlist / deadline / test / form / CV / preferences) from the last 3 turns. A message that names no new company or topic inherits the active topic. Corrections and meta-instructions ("check again", "latest", "don't use old data", "are you sure", "that's wrong", "I think I'm on it", "I got a call") apply to the previous question: re-run it with a live targeted re-check (as in P0 point 4), never a new broad query. Only a message that clearly starts a new topic ("what's due tonight", a different company) resets it.
2. Router order: (a) resolve topic and follow-ups from state, (b) then pick FACT vs OPEN. If the router's keyword match conflicts with the active topic, the topic wins. If still unsure, send it as OPEN to the model with the last 6 turns and the facts block, rather than guessing a broad intent. When the model is unreachable, the rules answer must still use the resolved topic.
3. Evals (multi-turn, must pass with the model on AND off): ["check firstclub", "check again"], ["check firstclub", "check erp for latest updates, don't answer on old data"], ["firstclub shortlist?", "I got a call, I think I'm there"], ["what's due tonight", "and groww?"], ["groww ctc", "ok what's due tonight"] (topic reset). Expected: the first four stay on the first topic and the re-check ones show a live fetch time; the last one switches.
4. Rendering: Ask Ping answers render markdown properly (bold, lists) or are produced without markdown; no literal ** or "- " in bubbles. Company display names cleaned in chat answers too ("Auro Group", not "Auro Group([www.AuroIM.com](https://www.AuroIM.com))"). Replace "Apply with: no CV fits it best" with nothing (omit the line) when no CV fits.
5. Relevance check: today's "For you" list includes AiPrise Software Engineer and Astera Labs SQA Engineer with no CV fit. Show me my currently saved preferences (targets text, exclusions) and when they last changed and by which message; if they were changed by a test or eval run, restore them and make sure evals never write to the owner's profile. If preferences are correct, find why these roles were classified For you and fix it.
6. "Latest ↓" pill: dock it above the composer; it must never overlap message text at any width. Screenshot proof at 390 and 1280.
Report together with the P0 FirstClub report.
`````

## 58. Sun 22 Nov 2026, 14:11 IST (08:41 UTC) — sent while the agent was working

`````text
Add WhatsApp-style "reply to a message". Commit per part.

1. Interaction: phone: swipe a bubble right (or long-press → Reply); PC: hover shows a reply arrow on the bubble, plus long-press/right-click → Reply. A quoted preview (sender, first line, coloured bar) appears above the composer with an ✕ to cancel; Esc cancels on PC. Works on Ping's messages (digests, reminders, test alerts, answers) and on my own.
2. Sent message shows the quoted snippet inside my bubble; tapping it scrolls to and flashes the original (loads earlier messages if it's outside the window). Store reply_to (message id) in chat_messages.
3. Meaning: the quoted message is the topic anchor and overrides the active-topic guess. Ask Ping receives the quoted message's structured content (its companies, roles, deadline, notice ids) along with my text. Examples that must work:
   - reply to the FirstClub answer: "check again" → live re-check of FirstClub only
   - reply to a 20:00 digest: "which of these haven't I applied to?" → only that digest's roles
   - reply to a digest: "which cv for the second one?" → the second role in that message
   - reply to a test alert: "where is it?" → that test's room/slot
   - reply to a form line: "done" → ticks that form as filled (confirm in one line)
4. Ping's answer to a reply also quotes what it answered, so the thread reads clearly.
5. Accessibility and polish: the swipe has a small reply icon reveal and haptic tap on phones that support it, doesn't conflict with horizontal scrolling in digests, keyboard-reachable on PC, works in light/dark, 390 and 1280 screenshots.
6. Evals: add the five reply cases above (model on and off) to the multi-turn set. Deploy, live-page check.
`````

## 59. Sun 22 Nov 2026, 17:05 IST (11:35 UTC)

`````text
Yes, GEMINI_API_KEY_EVALS is set. I added it at 06:10 today, and your overnight handoff confirmed eval answers already used it (15 calls on the evals key, 0 on the live key). Go ahead: redeploy, ask-ping-evals, functions-check, record both scores. Then reply-to-message, then Forms smart, then visual polish. Code freeze at [TIME]: stop at a clean commit with live build = HEAD and write the handoff, even if polish isn't done.
`````

## 60. Sun 22 Nov 2026, 17:05 IST (11:35 UTC) — sent while the agent was working

`````text
do it quickly
`````

## 61. Sun 22 Nov 2026, 17:37 IST (12:07 UTC) — sent while the agent was working

`````text
Forms dedupe is producing garbage (live screenshot): notice 1815 "Additional requirement" for ~11 companies became many rows, each the same company set in a different order, each asking "Looks like the same form as …, merge?". Fix now, before anything else.

1. One posting = one row. A notice (or mail) that asks several companies' applicants to fill a form is ONE form row with a company list, not one row per company or per ordering. Company sets are compared as sets (order-insensitive, names normalised).
2. Auto-merge silently, never ask, when any of these match: same notice id; same canonical form link; same normalised company set + same purpose + same deadline (or a later one = extension). Merging keeps the earliest first-seen, the latest deadline with history, all sources ("posted 2 times: notice 1815, mail"), and my tick.
3. Ask only when it is genuinely ambiguous (different links AND different notices, similar title, overlapping but not identical companies), at most ONE merge prompt per form, never a prompt that compares a form with itself or a reordered copy of itself. If you can't make the ambiguous case reliable today, remove merge prompts entirely and keep such rows separate; showing no prompt is better than showing a wrong one.
4. Clean up existing data: collapse all current duplicate rows with the rules above, preserving any ticks; clear all pending merge prompts.
5. Display: a multi-company form shows "Additional requirement · 11 companies" with the first 3 cleaned names + "+8 more" (expand to see all); never a two-line wall of names. Clean names ("Auro Group", "AIRAMATRIX", title case where the ERP shouts) here and in prompts.
6. Test with the real case (anonymised): notice 1815 + the matching mail must give exactly 1 row, 0 prompts. Re-run the 15-posting forms fixture. Deploy, screenshot the Forms tab at 390 and 1280, live-page check.
`````

## 62. Sun 22 Nov 2026, 17:58 IST (12:28 UTC) — sent while the agent was working

`````text
Restore the "View demo" button on the sign-in screen, under the normal sign-in, as before. Keep owner sign-in unchanged.
1. Re-link it everywhere it was removed (sign-in screen, setup page, HELP.md install/what-can-you-do answers, SUBMISSION.md, README); keep the hidden URL parameter working too.
2. Verify the demo is healthy after today's fixes: it uses its own session key and the demo profile only, can never read or change my profile (the FirstClub bug was the reverse of this; prove both directions), demo data passes the anonymiser check, Today/Forms/Companies all render in the demo, Forms in the demo shows no duplicate rows or merge prompts.
3. If the demo snapshot predates today's Forms and relevance fixes, rebuild it (demo-refeed) so it shows the current product.
4. Live checks: open the live URL in a fresh browser at 390 and 1280, tap View demo, ask "what's due tonight", "any tests today?" then "anything else?", "which cv for blackbuck", open Today, Forms, Companies. Run live-page and the PWA check. Also confirm the anonymous-sign-in hourly limit fallback still opens the snapshot.
Report in one short table, then go back to the Forms fix if it isn't finished.
`````

## 63. Sun 22 Nov 2026, 22:46 IST (17:16 UTC)

`````text
whats built and whats left?
`````

## 64. Sun 22 Nov 2026, 22:52 IST (17:22 UTC)

`````text
Build the submission bundle. No code changes. Output folder submission/ in the repo, plus a zip attached to a GitHub Release "submission" (or a workflow artifact if you can't create releases), and tell me exactly how to download it.

1. 02_Prompts.pdf: a cover page "Prompts used to build Ping" with a 3-line intro, then docs/BUILD_PROMPTS.md (every prompt I gave you, in order, with IST times, through today's last prompt; real names/numbers scrubbed; banned word as [banned word]), then docs/PROMPTS.md (Ping's runtime prompts, generated from source).
2. 03_Evals.pdf: evals/REPORT.md with today's final scores: Ask Ping 70/70 single and 21/21 conversations (state plainly that the main Gemini model was rate-limited during the final runs, so answers came from the rules and the lighter model), multi-turn and re-check cases 14/14, reply-to 5/5, relevance per persona, parser 56/58 held-out and 143/143 dev, attachments 31/31, mail 9/9, forms 15/15, fallback 8/8; each with what it checks and how to re-run. Add a short "What the evals caught" section with 3 real bugs: the demo-profile roll bug behind the FirstClub false negative, the model miscounting for-you roles (17 vs 8), and duplicate form rows. Plain language, no hype.
3. 04_App_link.pdf: one page: the live URL; two ways in ("tap View demo for a quick look, no login" and "sign in with the credentials in the submission note for my live data"); 6 things to try; how to install on a phone; source repo URL if public, else "source available on request".
4. The same three as .md files for copy-paste.
5. Before finishing: no secrets, no real third-party names/phones/rolls, no banned word, numbers match evals/REPORT.md and ONE_PAGER_FACTS.md, every link opens, each PDF renders cleanly (check one page of each as an image).
Report the download link and one line per file.
`````
