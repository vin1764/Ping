# Ping help

What Ping says about itself. This file is the only source: `setup/build_help.py` turns it into
`supabase/functions/_shared/help.js`, which the page and the Ask Ping function both load, and a test fails if the
two drift apart. Each `##` section is one topic; a `###` section inside "install" is one platform. Keep every line
true for any student's copy of Ping (no names, departments or preferences).

## overview

I'm Ping: I read the placement ERP for you every hour or so and tell you what matters here. I can help with:
- what's due (today, tonight, tomorrow, a date), tests and rooms, shortlists, CTC, eligibility, which CV to use
- forms: every form from the notices and your mail is in the Forms tab; tick forms as you fill them and the reminders stop. Ask "which forms haven't I filled?" or say "mark the Groww form as filled"
- installing me as an app: ask "how do I install Ping?"
- notifications: ask "how do I get notifications?"
- how often I check: ask "how often do you check?"
- your preferences: ask "how do I change my preferences?"
- what I can and can't do, and where your data lives: ask "what can you do?" or "where is my data?"
- your own copy of Ping: ask "how do I set this up?"

## install

Install me and I open like an app, straight to this chat, and still show what you've already seen when you're offline. Just trying me out? Tap View demo under the sign-in first: an anonymised snapshot, read-only.

### windows

On Windows in Chrome: open the ⋮ menu → "Install Ping…" (newer Chrome: ⋮ → "Cast, save and share" → "Install Ping…"), or click the install icon at the right end of the address bar (a screen with a down arrow). In Edge: … menu → Apps → "Install Ping". Then open Ping from the Start menu or the taskbar.

### mac

On a Mac in Chrome: open the ⋮ menu → "Install Ping…" (newer Chrome: ⋮ → "Cast, save and share" → "Install Ping…"), or click the install icon at the right end of the address bar. In Safari: File → "Add to Dock". Then open Ping from the Dock or Launchpad.

### android

On Android (Chrome): tap "Install" when I offer it, or open the ⋮ menu → "Install app" (some phones say "Add to Home screen" → Install). Then open Ping from your home screen. If you signed in in Chrome before installing, you're already signed in in the app, and you stay signed in.

### ios

On iPhone or iPad: open this page in Safari, tap Share (the square with an arrow), then "Add to Home Screen" → Add. Open Ping from the Home Screen icon: on iPhone, notifications only work from there. Sign in once inside the installed app; it doesn't share Safari's login. After that you stay signed in, and iCloud Keychain can fill the password with Face ID if you ever need it again.

### other

In Chrome or Edge, look for the install icon at the right end of the address bar, or "Install Ping" in the browser's menu. Firefox can't install sites as apps; Ping still works in a normal tab.

## notifications

I send at most one notification per ERP check: the most urgent new thing that's for you (a test or shortlist that names you, a form to fill, a deadline for a role you'd apply to), plus a reminder before a test you're on. Never twice for the same thing, and never in your quiet hours (outside the hours I check).
To turn them on: Profile → Notifications → "Turn on", then allow notifications when your browser asks. "Send a test" there checks it works. On iPhone and iPad, add Ping to your Home Screen first and open it from there.
Prefer email? Profile → Notifications → "Also email me what's for you".

## checks

I check the ERP every hour by default, between 06:00 and 01:00 IST; you can also tap "Check now" for a check right away.
To change it: Profile → Schedule & reminders (how often: every 30 minutes, every hour or every 2 hours; and between which hours), or tell me here, for example "check every 2 hours" or "only check between 8 and 23".
Reminders before a deadline: Profile → Schedule & reminders → "Remind me before a deadline (hours)", or "remind me 3 hours before".

## can

I can: read the ERP's companies list, notices and attached lists (I keep only your own row and the table heading), read placement mail in your institute mailbox, work out what's due and what you're eligible for, say which CV fits a role, answer questions here, and notify you.
Just looking? View demo, under the sign-in, opens an anonymised snapshot of a real run with its own made-up profile: read-only, and it never sees anyone's real data.
I can't: do anything on the ERP. I never apply, withdraw, submit, upload, fill forms or accept offers for you; I only read. Applying and forms are always yours to do on the ERP or the form's own page. The Forms tab is your checklist: tick forms as you fill them (your own record; I never fill or submit them), and I stop reminding you about the ticked ones.

## preferences

Your preferences change what I show you, never anything on the ERP:
- Profile → Targets: the kinds of roles you want ("product, consulting"); or tell me "only show me product and consulting roles", "also include data roles", "don't count SDE".
- Profile → Interested / Not interested companies, Feed (only what fits me first, or everything), Other roles (listed separately or not).
- Profile → About you: CGPA, department, degree, backlogs (used for eligibility). Profile → CVs: the CVs I pick from.
- Or just say it: "Groww isn't relevant", "hide the SDE role at X" (it stops showing as For you; tap Undo to take it back), "show Groww again".
Ask "what are my preferences?" to see them, or "reset my preferences" to start over.

## data

Your data lives in your own copy of Ping: a private database that only your login can read (the demo can't see it), the ERP and mail passwords only as encrypted secrets of your own GitHub repository (never in the code, never in this page), and your CVs in a private storage bucket. Ping keeps placement mail only; other mail is never read beyond its sender and subject, and login OTP mails are never stored.

## setup

Ping runs under your own accounts, nothing shared: no central server, no shared database. To run your own copy:
- Make a private copy of the source: https://github.com/vin1764/Ping (Use this template, or Import a repository). Private, so your Actions logs and data stay yours.
- Follow the setup page: https://vin1764.github.io/ping-dashboard/setup.html (a free Supabase project, your ERP login and the OTP mailbox's app password; Gemini and Groq keys are optional).
- Then install me on your phone and sign in once inside the installed app. About 45 minutes in all, most of it yours.
