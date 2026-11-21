# Build prompts

Every prompt the owner gave the coding agent in the session that built Ping, verbatim and in order,
with the time each was sent. Only the owner's messages: no replies, tool output, automatic notices or hook
messages. Messages marked *sent while the agent was working* were typed while a task was running and reached it
mid-task.

One change from verbatim: a word that must not appear in this repository is written as `[banned word]`
(5 places, all of them instructions not to use it). Everything else is exactly as sent.

32 prompts, 20 Nov 2026 22:06 UTC to 21 Nov 2026 17:38 UTC.

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
