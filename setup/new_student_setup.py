#!/usr/bin/env python3
"""
Ping - setup for a new student. Run it once, on your own laptop:

    python -m pip install --user -r requirements.txt
    python setup/new_student_setup.py

It will:
  1. ask for each password / key, one at a time (secret ones are not shown as you type)
  2. save them in a file called .env in this folder, readable only by you.
     .env is listed in .gitignore, so git will never upload it.
  3. check your mailbox, your database and do ONE test login to the ERP
     (it reads the OTP from your mailbox by itself, then logs out)
  4. tell you exactly what to paste where on GitHub
  5. tell you how to stop the hourly OTP mails cluttering your inbox

Nothing here is sent anywhere except to the ERP, your own mailbox and your
own Supabase project.
"""

from __future__ import annotations

import getpass
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ENV = ROOT / ".env"

FIELDS = [
    ("ERP_USER_ID", "Your ERP user id (roll number)", False),
    ("ERP_PASSWORD", "Your ERP password", True),
    ("ERP_SECQ_1", "Security question 1, written as  question::answer", True),
    ("ERP_SECQ_2", "Security question 2, written as  question::answer", True),
    ("ERP_SECQ_3", "Security question 3, written as  question::answer", True),
    ("MAIL_ADDRESS", "Your institute email address (the one the ERP OTP goes to)", False),
    ("MAIL_APP_PASSWORD", "Google app password for that mailbox (myaccount.google.com/apppasswords)", True),
    ("SUPABASE_URL", "Supabase project URL (Project Settings > API), like https://xxxx.supabase.co", False),
    ("SUPABASE_SERVICE_KEY", "Supabase SECRET key (Project Settings > API Keys, starts with sb_secret_)", True),
]


def read_env() -> dict:
    out = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"')
    return out


def write_env(values: dict) -> None:
    lines = ["# Ping secrets. NEVER commit this file (it is in .gitignore).", ""]
    lines += [f'{k}="{values[k]}"' for k, _, _ in FIELDS if values.get(k)]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(ENV, stat.S_IRUSR | stat.S_IWUSR)  # only you can read it (Mac/Linux)
    except OSError:
        pass


def ask_all(existing: dict) -> dict:
    values = dict(existing)
    print("\nStep 1 - your passwords and keys. Press Enter to keep a value already saved.\n")
    print("  Security questions: the ERP has 3 fixed questions for you and asks one at random.")
    print("  Type each exactly as the ERP shows it, then ::, then your answer.")
    print("  Example:  What is the name of your first pet?::Bruno\n")
    for key, label, secret in FIELDS:
        have = " [saved]" if values.get(key) else ""
        while True:
            prompt = f"  {label}{have}: "
            val = getpass.getpass(prompt) if secret else input(prompt)
            val = val.strip()
            if not val and values.get(key):
                break
            if not val:
                print("    (needed)")
                continue
            if key.startswith("ERP_SECQ") and "::" not in val:
                print("    Please write it as  question::answer")
                continue
            if key == "SUPABASE_SERVICE_KEY" and not val.startswith(("sb_secret_", "eyJ")):
                print("    That doesn't look like a secret key (should start with sb_secret_).")
                continue
            if key == "MAIL_APP_PASSWORD":
                val = val.replace(" ", "")
            values[key] = val
            break
    write_env(values)
    print(f"\n  Saved to {ENV} (only readable by you; git ignores it).")
    return values


def checks(values: dict) -> str | None:
    for k, v in values.items():
        os.environ[k] = v
    from ping.config import load_secrets
    from ping.erp import ErpClient, LoginError
    from ping.gate import Gate
    from ping.mailbox import Mailbox
    from ping.store import SupabaseStore

    secrets = load_secrets()
    print("\nStep 2 - checks")
    mb = Mailbox(secrets.mail_address, secrets.mail_app_password)
    try:
        mb.connect()
        print(f"  mailbox   : OK (reading '{mb.folder}', read-only)")
    except Exception as e:
        print(f"  mailbox   : FAILED - {e}\n  Check MAIL_ADDRESS and the app password, then run this again.")
        return None
    ok, msg = SupabaseStore(secrets.supabase_url, secrets.supabase_key).ready()
    if ok:
        print("  database  : OK")
    else:
        print(f"  database  : NOT READY - {msg}")
        print("    Open Supabase > SQL Editor > New query, paste the whole file sql/schema.sql, press Run.")
    print("  ERP login : trying once (an OTP mail will arrive; Ping reads it by itself)...")
    erp = ErpClient(Gate(), secrets, mb, log=lambda *_: None)
    try:
        st = erp.login()
        erp.open_placement()
        n = erp.companies_xml().count("<row")
        print(f"  ERP login : OK in {st.seconds_total:.0f}s (OTP took {st.seconds_waiting_otp:.0f}s). "
              f"Companies list has {n} rows.")
        return mb.last_otp_sender or "the ERP"
    except LoginError as e:
        print(f"  ERP login : FAILED - {e}")
        return None
    finally:
        try:
            erp.logout()
        except Exception:
            pass
        mb.close()


def github_steps(values: dict) -> None:
    print("\nStep 3 - put the same values on GitHub (so the hourly run can use them)")
    print("  1. Make your own PRIVATE copy of this project on GitHub (Use this template, or Import repository).")
    print("  2. In your copy: Settings > Secrets and variables > Actions > New repository secret.")
    print("  3. Add one secret per line below. Name = left side, Secret = the value you typed here.")
    for k, _, _ in FIELDS:
        print(f"       {k}")
    gh = shutil.which("gh")
    if gh and input("\n  The GitHub CLI (gh) is installed. Set all of them for you with it? [y/N] ").lower() == "y":
        repo = input("  Your repo, as owner/name: ").strip()
        for k, _, _ in FIELDS:
            r = subprocess.run([gh, "secret", "set", k, "--repo", repo], input=values[k], text=True,
                               capture_output=True)
            print(f"    {k}: {'set' if r.returncode == 0 else 'FAILED ' + r.stderr.strip()[:120]}")
    else:
        if input("\n  Show each value once so you can copy it? (only do this when nobody is looking) [y/N] ").lower() == "y":
            for k, _, _ in FIELDS:
                input(f"    {k} = {values[k]}    (Enter for next)")
                print("\033[F\033[K", end="")  # wipe the line again
    print("  4. Actions tab > Ping > Run workflow, mode 'run', to try it. After that it runs every hour,")
    print("     06:07 to 01:07 IST.")


def mail_filter(sender: str | None) -> None:
    print("\nStep 4 - stop the OTP mails cluttering your inbox (about 20 a day)")
    who = sender or "erpkgp@adm.iitkgp.ac.in"
    print("  In your institute Gmail: search box > Show search options:")
    print(f"     From: {who}")
    print("     Subject: OTP")
    print("  > Create filter > tick 'Skip the Inbox (Archive it)' and 'Mark as read' > Create filter.")
    print("  Ping searches All Mail, so it still finds the OTP after the filter archives it.")


def main() -> None:
    print(__doc__)
    values = ask_all(read_env())
    sender = checks(values)
    github_steps(values)
    mail_filter(sender)
    print("\nDone. Your passwords are only in .env on this laptop and in your own GitHub secrets.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Anything already typed is saved in .env.")
