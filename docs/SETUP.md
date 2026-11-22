# Set up Ping for yourself

Your own copy of Ping runs under your own accounts. This page is also published as `setup.html` next to the
dashboard (built from this file at every deploy, so the two always say the same thing).

## Reviewing Ping?

Sign in on the [dashboard](https://vin1764.github.io/ping-dashboard/) with the credentials in the submission note. The rest of this page is for setting up a copy of your own.

## What you get

- Every hour, Ping reads your placement ERP (companies, notices and the PDFs that name you) and posts only what's about you in one chat thread.
- Deadlines come as one digest per closing time with a reminder before it, and lists that name you (shortlists, test rooms) come with your row.
- Ask Ping in plain words: "what's due tonight?", "which CV for Groww?", "am I eligible for X?".

## What it never does

- It only reads. It never applies, never submits a form, never uploads a CV and never changes anything on the ERP.
- Your passwords and keys stay in your own GitHub repository and your own Supabase project. There is nothing central: no shared server, no shared database, nobody else's copy.

## What you need

- A GitHub account.
- A free Supabase project (supabase.com).
- A free Gemini API key (aistudio.google.com). Optional, but Ask Ping and the "For you" marks need it.
- Your ERP login: user id, password, the 3 security questions with their answers, and the mailbox the ERP sends your OTP to (with a Google app password for it).
- Python 3.11 or newer on your computer, for the one setup script.

Everything above is on a free tier. Ping fits in it: about 20 short runs a day on GitHub Actions, a small database, and a few hundred Gemini calls a day. When Gemini's free quota runs out, Ping answers from your data without it.

## Steps

Source repo: SOURCE_REPO_URL

1. **Copy the source repo** as a **private** repository under your account (GitHub > New repository > Import a repository), then clone it:

   ```
   git clone https://github.com/<you>/<your-copy>.git ping
   cd ping
   ```

2. **Create a Supabase project** (free plan). Note its URL (`https://<id>.supabase.co`) and create a personal access token: avatar > Account > Access Tokens.

3. **Have your secrets ready.** The setup script asks for each one and stores it; only the last one you add by hand.

   | name | what it is | where it goes |
   |---|---|---|
   | `ERP_USER_ID`, `ERP_PASSWORD` | your ERP login | GitHub repo secrets (the script) |
   | `ERP_SECQ_1`, `ERP_SECQ_2`, `ERP_SECQ_3` | each security question and answer, as `question::answer` | GitHub repo secrets (the script) |
   | `MAIL_ADDRESS`, `MAIL_APP_PASSWORD` | the OTP mailbox and its Google app password | GitHub repo secrets (the script) |
   | `SUPABASE_URL`, `SUPABASE_ACCESS_TOKEN` | from step 2 | GitHub repo secrets (the script) |
   | `SUPABASE_SERVICE_KEY`, `SUPABASE_PUBLISHABLE_KEY` | read from your project by the script | GitHub repo secrets (the script) |
   | `GEMINI_API_KEY` | your Gemini key (optional) | GitHub repo secrets (the script), then Supabase function secrets (the deploy) |
   | `PING_GITHUB_TOKEN` | a fine-grained token for your copy, Actions: read and write (optional: Check now and the hourly start) | GitHub repo secrets (the script), then Supabase function secrets (the deploy) |
   | `DASHBOARD_DEPLOY_TOKEN` | a fine-grained token for a new, empty public repo `<you>/ping-dashboard`, Contents and Pages: read and write | add it yourself: your copy > Settings > Secrets and variables > Actions |

4. **Run the setup script once.** It saves your answers in `.env` on your computer (git ignores it), creates the tables, rules and the private CV bucket in your Supabase project with an empty profile, creates your dashboard login, does one test login to the ERP and puts the secrets into your repo. Running it again is safe.

   ```
   python -m pip install --user -r requirements.txt
   python setup/new_student_setup.py
   ```

5. **Turn on the schedule:** your copy > Actions > Admin > Run workflow > `schedule-setup`. Supabase then starts a check every hour, 06:11 to 01:11 IST; `schedule-status` shows the last starts.

   ```
   gh workflow run admin.yml -f task=schedule-setup
   ```

   For notifications on your phone, also make the push keys (one command; the private key goes straight into your Supabase secrets, see `docs/PUSH.md`):

   ```
   gh workflow run admin.yml -f task=push-setup
   ```

6. **Open your dashboard.** On `<you>/ping-dashboard` > Settings > Pages, choose Deploy from a branch, `main`, `/ (root)`, and leave Custom domain empty. Then Actions > Dashboard > Run workflow, and open `https://<you>.github.io/ping-dashboard/`.

7. **Answer Ping's first questions in the chat:** your feed, degree and department, what you're looking for, a CV, how often to check, when to remind you. Every answer can be changed later by just telling Ping ("check every 30 minutes").

8. **Done.** Ping runs your first check while you answer, then posts as things happen.

## How long it takes

**Time to first feed: about 45 minutes**, most of it yours:

| step | time | how it was measured |
|---|---|---|
| accounts, the Supabase project, keys and GitHub secrets (steps 1-4) | about 30 min | by hand, the first time |
| the setup script on an empty project | 0.2 s | `setup/replica_walkthrough.py` on the local replica (22 Nov) |
| first open, sign-in, onboarding in the chat (10 answers) | 9 s of page time, plus your reading | same |
| the first real check: two weeks of notices, roles and PDFs | 12.1 min | Ping's first real run (`evals/real_run.json`) |
| every check after that | under 1 min | runs #13 and #15 |
| first digest on the page, and a question answered | 0.2 s, 4 ms | the replica walkthrough |

So the first messages land within the hour, and every check after that takes under a minute.

## If something goes wrong

- **The ERP shows a blank login page or won't accept Log In:** that's the ERP, not your setup. Ping tries again next hour and only writes to you after 3 failed runs in a row.
- **GitHub's own scheduled runs never fire:** that's why the hourly start comes from Supabase (step 5). Run `schedule-setup` again and check `schedule-status`.
- **The dashboard redirects to another address and sign-in fails:** the Custom domain box on `ping-dashboard` > Settings > Pages must be empty.

## Privacy

- Your feed, roles, notices, chat and preferences live in your own Supabase project, readable only with your login. From a PDF only your own row and the table heading are kept, never other students' rows.
- Your CVs sit in a private storage bucket in that project; Ping keeps a short summary of each to suggest which one to apply with.
- Your passwords and keys live only in your repo's secrets, your Supabase function secrets and the `.env` file on your computer.
- Gemini sees only your own feed, roles and profile when you ask something, never a PDF.
- The public `ping-dashboard` repo holds only the built page. Its demo is an anonymised snapshot: real companies, a made-up student, no other students, and four made-up mails instead of real ones.
