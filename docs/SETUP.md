# Setting Ping up for yourself

Ping runs under **your own** accounts with **your own** passwords: your copy of the repo, your Supabase project,
your Gemini key. Nobody else's data is involved, and nothing of yours sits on a shared server.

## Prerequisites (all free)

- your ERP login and its 3 security questions with answers
- a Google app password for the mailbox the ERP sends your OTP to (myaccount.google.com/apppasswords; 2-step
  verification must be on)
- a Supabase project: its URL and a personal access token (supabase.com > avatar > Account > Access Tokens)
- your own **private** copy of this repository on GitHub
- optional: a Gemini API key (aistudio.google.com) for Ask Ping, "For you" marks and CV summaries
- Python 3.11+ on your computer, for the one setup script

## The one setup script

```
python -m pip install --user -r requirements.txt
python setup/new_student_setup.py
```

It asks for each secret once (hidden while you type), saves them in `.env` (git ignores it), creates all
tables, rules and the private CV bucket in your Supabase project with an **empty profile**, creates your
dashboard login, checks it, does one test login to the ERP, and puts the secrets into your GitHub repo (or
prints exactly what to paste where). Running it again is safe.

Tested: `tests/test_setup_fresh_project.py` runs the script against a local, empty Postgres with Supabase's
roles and rules (the "local replica"), not against a new real Supabase project. It checks the tables, the
login, the empty profile, that the first preferences can be saved, and that a demo session can't touch them.

## Your first chat message

Open the dashboard link the script prints, sign in, and tell Ping what you're looking for:

- "only show me <the kinds of roles you want>"
- "also include <another kind>", "don't count <a kind> as relevant"
- "remind me 3 hours before deadlines", "stop listing other roles separately"
- "what are my preferences?", "reset my preferences"

Ping replies with one line saying exactly what it saved and marks every role "For you" or not. You can also
upload up to 3 CVs on the Profile page (My CVs); Ping then says which CV to apply with for each role.

## What to expect in the first hour

- The first run (start it with Menu > Check now, or wait for minute :41) reads the companies list and the last
  14 days of notices: about 12 minutes. Later runs read only what's new: 1-3 minutes.
- The chat fills with one "new roles listed" message for that run, any deadline digests for the next 24 hours,
  and messages about lists that name you. Other students' details are never kept: from a PDF only your row and
  the table heading are saved.
- From then on, every hour from 06:11 to 01:11 IST. One reminder per deadline batch, N hours before (default 2).
- If the ERP refuses your password or security answer, you get one email and the hourly runs pause until you
  fix the secret and start a run yourself.
