#!/usr/bin/env python3
"""
Ping - one-command setup for a new student.

    python -m pip install --user -r requirements.txt
    python setup/new_student_setup.py

You never open Supabase's SQL editor or its login screens. This script:
  1. asks for each password / key one at a time (secret ones aren't shown as you type)
     and saves them in .env (git ignores it; only you can read it)
  2. creates all of Ping's tables and permissions in your Supabase project
  3. creates your dashboard login (already confirmed) and puts it on the allowed list
  4. signs in as that login to prove it works, and checks the database
  5. does one test login to the ERP (it reads the OTP from your mailbox, then logs out)
  6. puts the secrets into your GitHub repo (with the GitHub CLI if you have it),
     or prints exactly what to paste where
  7. ends with the link to open and the email to sign in with

What you need before starting (all free):
  - your ERP login, its 3 security questions + answers
  - a Google app password for the mailbox the ERP sends OTPs to
    (myaccount.google.com/apppasswords; 2-step verification must be on)
  - a Supabase project: its URL, and a personal access token
    (supabase.com > your avatar > Account > Access Tokens > Generate new token)
  - your own private copy of this repo on GitHub
Re-running is safe: it keeps what you already typed (press Enter) and fixes what's missing.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ENV = Path(os.environ.get("PING_SETUP_ENV_FILE", ROOT / ".env"))

# (name, question, secret?, required?)
FIELDS = [
    ("ERP_USER_ID", "Your ERP user id (roll number)", False, True),
    ("ERP_PASSWORD", "Your ERP password", True, True),
    ("ERP_SECQ_1", "Security question 1 and answer, as  question::answer", True, True),
    ("ERP_SECQ_2", "Security question 2 and answer, as  question::answer", True, True),
    ("ERP_SECQ_3", "Security question 3 and answer, as  question::answer", True, True),
    ("MAIL_ADDRESS", "The email address the ERP sends your OTP to", False, True),
    ("MAIL_APP_PASSWORD", "Google app password for that mailbox", True, True),
    ("SUPABASE_URL", "Supabase project URL, like https://abcd1234.supabase.co", False, True),
    ("SUPABASE_ACCESS_TOKEN", "Supabase personal access token (starts with sbp_)", True, True),
    ("GEMINI_API_KEY", "Gemini API key for AI answers (optional, Enter to skip)", True, False),
    ("PING_GITHUB_TOKEN", "GitHub token for the dashboard's Check now button (optional, Enter to skip)", True, False),
]
GITHUB_SECRETS = ["ERP_USER_ID", "ERP_PASSWORD", "ERP_SECQ_1", "ERP_SECQ_2", "ERP_SECQ_3", "MAIL_ADDRESS",
                  "MAIL_APP_PASSWORD", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SUPABASE_PUBLISHABLE_KEY",
                  "SUPABASE_ACCESS_TOKEN", "GEMINI_API_KEY", "PING_GITHUB_TOKEN"]


def say(msg: str = "") -> None:
    print(msg, flush=True)


def step(n: int, title: str) -> None:
    say(f"\n[{n}/7] {title}")


# ------------------------------------------------------------------ .env
def read_env() -> dict:
    out = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"')
    return out


def write_env(values: dict) -> None:
    names = [f[0] for f in FIELDS] + ["SUPABASE_SERVICE_KEY", "SUPABASE_PUBLISHABLE_KEY", "DASHBOARD_EMAIL", "GITHUB_REPO"]
    lines = ["# Ping secrets. NEVER commit this file (it is in .gitignore).", ""]
    lines += [f'{k}="{values[k]}"' for k in names if values.get(k)]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(ENV, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def ask(prompt: str, secret: bool, current: str | None, required: bool) -> str:
    """Environment variables win (that's how the automated test answers); else ask."""
    while True:
        have = " [saved, Enter keeps it]" if current else ""
        val = (getpass.getpass if secret else input)(f"  {prompt}{have}: ").strip()
        if not val and current:
            return current
        if val or not required:
            return val
        say("    (needed)")


def validate(key: str, val: str) -> str | None:
    if key.startswith("ERP_SECQ") and "::" not in val:
        return "write it as  question::answer"
    if key == "SUPABASE_URL" and not re.match(r"^https?://", val):
        return "should start with https://"
    if key == "SUPABASE_ACCESS_TOKEN" and not (val.startswith("sbp_") or os.environ.get("PING_SETUP_TEST")):
        return "a personal access token starts with sbp_ (not the project's secret key)"
    if key == "MAIL_ADDRESS" and "@" not in val:
        return "that doesn't look like an email address"
    return None


def collect(values: dict) -> dict:
    say("  Security questions: the ERP has 3 fixed questions for you and asks one at random.")
    say("  Type each exactly as the ERP shows it, then ::, then your answer, e.g.")
    say("  What is the name of your first pet?::Bruno\n")
    for key, prompt, secret, required in FIELDS:
        if key in os.environ:  # answered in advance (an empty value means "skip")
            values[key] = os.environ[key].strip()
        else:
            while True:
                val = ask(prompt, secret, values.get(key), required)
                problem = validate(key, val) if val else None
                if problem:
                    say(f"    {problem}")
                    continue
                values[key] = val
                break
        if key == "MAIL_APP_PASSWORD":
            values[key] = values[key].replace(" ", "")
        if key == "SUPABASE_URL":
            values[key] = values[key].rstrip("/")
    write_env(values)
    say(f"\n  Saved to {ENV} (only you can read it; git ignores it).")
    return values


# ------------------------------------------------------------------ steps
def supabase_steps(values: dict) -> None:
    from ping import supabase_admin as sa
    from ping.store import SupabaseStore

    url, token = values["SUPABASE_URL"], values["SUPABASE_ACCESS_TOKEN"]

    step(2, "Creating Ping's tables and permissions in Supabase")
    keys = sa.api_keys(url, token)
    if not keys.get("secret") or not keys.get("publishable"):
        raise sa.SetupError("couldn't read the project's publishable/secret keys with this token")
    values["SUPABASE_SERVICE_KEY"], values["SUPABASE_PUBLISHABLE_KEY"] = keys["secret"], keys["publishable"]
    sa.create_database(url, token)
    ok, msg = SupabaseStore(url, keys["secret"]).ready()
    if not ok:
        raise sa.SetupError(f"tables were created but Ping can't use them yet: {msg}")
    say("  tables, permissions and database rules: OK")

    step(3, "Creating your dashboard login")
    email = os.environ.get("DASHBOARD_EMAIL") or values.get("DASHBOARD_EMAIL") or values["MAIL_ADDRESS"]
    if not os.environ.get("DASHBOARD_EMAIL"):
        typed = input(f"  Dashboard sign-in email [{email}]: ").strip()
        email = typed or email
    values["DASHBOARD_EMAIL"] = email.lower()
    password = os.environ.get("DASHBOARD_PASSWORD")
    while not password:
        p1 = getpass.getpass("  Choose a dashboard password (8+ characters): ")
        p2 = getpass.getpass("  Type it again: ")
        if len(p1) < 8:
            say("    at least 8 characters")
        elif p1 != p2:
            say("    the two didn't match")
        else:
            password = p1
    how = sa.ensure_dashboard_user(url, keys["secret"], values["DASHBOARD_EMAIL"], password)
    sa.allow(url, keys["secret"], values["DASHBOARD_EMAIL"])
    say(f"  login {values['DASHBOARD_EMAIL']}: {how}, confirmed, on the allowed list")

    step(4, "Checking the dashboard login and the database")
    sa.sign_in_check(url, keys["publishable"], values["DASHBOARD_EMAIL"], password)
    say("  signed in like the dashboard does, and the database lets this login read Ping's data: OK")
    write_env(values)


def erp_step(values: dict) -> str | None:
    step(5, "One test login to the ERP")
    for k, v in values.items():
        os.environ.setdefault(k, v)
    from ping.config import load_secrets
    from ping.erp import ErpClient, LoginError
    from ping.gate import Gate
    from ping.mailbox import Mailbox

    secrets = load_secrets()
    mb = Mailbox(secrets.mail_address, secrets.mail_app_password)
    try:
        mb.connect()
    except Exception as e:
        say(f"  mailbox: FAILED ({e}). Check MAIL_ADDRESS and the app password, then run this again.")
        return None
    say("  mailbox: OK (read-only)")
    say("  logging in to the ERP (an OTP mail will arrive; Ping reads it itself)...")
    erp = ErpClient(Gate(), secrets, mb, log=lambda *_: None)
    try:
        st = erp.login()
        erp.open_placement()
        n = erp.companies_xml().count("<row")
        say(f"  ERP: OK in {st.seconds_total:.0f}s (OTP took {st.seconds_waiting_otp:.0f}s); companies list has {n} rows")
        return mb.last_otp_sender
    except LoginError as e:
        say(f"  ERP: FAILED - {e}")
        return None
    finally:
        try:
            erp.logout()
        except Exception:
            pass
        mb.close()


def repo_from_git() -> str | None:
    try:
        url = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"], capture_output=True,
                             text=True, timeout=10).stdout.strip()
    except Exception:
        return None
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def github_step(values: dict, use_gh: bool) -> str:
    step(6, "GitHub: secrets, hosting and the first run")
    repo = os.environ.get("GITHUB_REPO") or values.get("GITHUB_REPO") or repo_from_git() or ""
    if not os.environ.get("GITHUB_REPO"):
        typed = input(f"  Your GitHub repo, as owner/name [{repo}]: ").strip()
        repo = typed or repo
    values["GITHUB_REPO"] = repo
    write_env(values)
    owner, _, name = repo.partition("/")
    link = f"https://{owner.lower()}.github.io/{name}/"
    gh = shutil.which("gh") if use_gh else None
    secrets = [(k, values.get(k, "")) for k in GITHUB_SECRETS if values.get(k)]
    if gh:
        say(f"  Using the GitHub CLI to set {len(secrets)} secrets on {repo}...")
        failed = []
        for k, v in secrets:
            r = subprocess.run([gh, "secret", "set", k, "--repo", repo], input=v, text=True, capture_output=True)
            if r.returncode:
                failed.append(f"{k}: {r.stderr.strip()[:100]}")
        say("  secrets: " + ("all set" if not failed else "some failed:\n    " + "\n    ".join(failed)))
        r = subprocess.run([gh, "api", "-X", "POST", f"repos/{repo}/pages", "-f", "build_type=workflow"],
                           capture_output=True, text=True)
        pages = "on" if r.returncode == 0 or "already" in (r.stdout + r.stderr).lower() else "NOT on"
        say(f"  GitHub Pages (hosts the dashboard): {pages}")
        if pages != "on":
            say("    Private repos need GitHub Pro (free with the GitHub Student Developer Pack).")
        for wf, inputs in (("dashboard.yml", []), ("ping.yml", ["-f", "mode=run"])):
            subprocess.run([gh, "workflow", "run", wf, "--repo", repo, *inputs], capture_output=True)
        say("  started: the dashboard deploy and Ping's first run (the first run takes ~12 minutes)")
    else:
        say(f"  On GitHub, open {repo} > Settings > Secrets and variables > Actions > New repository secret,")
        say("  and add each line below (Name on the left, Secret on the right).")
        say("  These are your real passwords: clear the screen afterwards.\n")
        width = max(len(k) for k, _ in secrets)
        for k, v in secrets:
            say(f"    {k.ljust(width)}  {v}")
        say("\n  Then: Settings > Pages > Source: GitHub Actions (hosts the dashboard),")
        say("  and Actions > Dashboard > Run workflow, then Actions > Ping > Run workflow (mode: run).")
    return link


def main() -> int:
    ap = argparse.ArgumentParser(description="Ping one-command setup")
    ap.add_argument("--skip-erp-test", action="store_true", help="don't do the test ERP login")
    ap.add_argument("--no-gh", action="store_true", help="don't use the GitHub CLI even if installed")
    args = ap.parse_args()
    from ping.supabase_admin import SetupError
    t0 = time.monotonic()
    say(__doc__.split("You never")[0].strip())
    step(1, "Your passwords and keys")
    values = collect(read_env())
    try:
        supabase_steps(values)
    except SetupError as e:
        say(f"\n  STOPPED: {e}\n  Fix that and run this again; it keeps what you've typed.")
        return 1
    sender = None if args.skip_erp_test else erp_step(values)
    link = github_step(values, use_gh=not args.no_gh)
    step(7, "Your OTP mails")
    say("  In the mailbox the OTPs go to: search bar > Show search options >")
    say(f"    From: {sender or 'erpkgp@adm.iitkgp.ac.in'}   Subject: OTP")
    say("  > Create filter > Skip the Inbox (Archive it) + Mark as read. Ping still finds them in All Mail.")
    say(f"\nDone in {time.monotonic() - t0:.0f}s. Open {link} and sign in with {values['DASHBOARD_EMAIL']}.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\nStopped. What you typed so far is saved in .env; run this again to continue.")
        sys.exit(1)
