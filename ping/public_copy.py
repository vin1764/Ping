"""A public copy of this repository's history, with every real value replaced (Actions > Admin > public-copy).

Runs on GitHub's runner, where the real values are (secrets and the profile row): this file holds none of them.

1. A fresh mirror of this repository (all branches).
2. git filter-repo:
   - every earlier version of dashboard/demo-data.json becomes today's anonymised snapshot (early versions were
     written before the anonymiser existed);
   - text replacements in every file of every commit: the ERP user id (roll number) -> the demo's fake roll, the
     mailbox address -> student@example.com, the profile's real name -> Demo Student, the Supabase project's
     address -> https://YOUR-PROJECT.supabase.co, and the banned word -> Ping.
3. Checks on the rewritten history, before anything leaves the runner: every version of demo-data.json passes the
   anonymiser's final check; no secret value this job holds appears in any blob; the banned word appears nowhere;
   key-shaped text (Supabase secret keys, access tokens, Google keys, GitHub tokens) appears nowhere.
4. If every check passes: pushed to PUBLIC_REPO_URL with PUBLIC_REPO_TOKEN when both are set (a new, empty public
   repository the owner made), otherwise written as a git bundle for the workflow to upload as a private artifact.
This repository and its history are never changed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANNED = "ins" + "tinct"
KEY_SHAPES = {
    "supabase secret key": r"sb_secret_[A-Za-z0-9_\-]{20,}",
    "supabase access token": r"sbp_[A-Za-z0-9]{30,}",
    "google key": r"AIza[0-9A-Za-z_\-]{30,}",
    "github token": r"(?:ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{30,}",
}
SECRET_ENVS = ["ERP_USER_ID", "ERP_PASSWORD", "ERP_SECQ_1", "ERP_SECQ_2", "ERP_SECQ_3", "MAIL_ADDRESS", "MAIL_APP_PASSWORD",
               "SUPABASE_SERVICE_KEY", "SUPABASE_ACCESS_TOKEN", "GEMINI_API_KEY_EVALS", "GEMINI_API_KEY_LIVE",
               "PING_GITHUB_TOKEN", "DASHBOARD_DEPLOY_TOKEN"]


def run(*a, cwd=None, check=True) -> str:
    return subprocess.run(list(a), cwd=cwd, check=check, capture_output=True, text=True).stdout


def say(m=""):
    print(m, flush=True)


def secret_values() -> dict[str, str]:
    out = {}
    for n in SECRET_ENVS:
        v = os.environ.get(n, "").strip()
        if n.startswith("ERP_SECQ") and "::" in v:
            v = v.split("::", 1)[1].strip()
        if len(v) >= 6:
            out[n] = v
    return out


def roll_pattern(roll: str) -> str:
    """The roll number in any case, with or without a space, dash or underscore between its parts (22XY10042,
    22xy10042, 22 XY 10042, 22-XY-10042)."""
    parts = re.findall(r"[0-9]+|[A-Za-z]+", roll)
    return r"[\s\-_]?".join(re.escape(x) for x in parts) if parts else re.escape(roll)


def replacements(real_name: str | None) -> list[tuple[str, str, str]]:
    """(what, pattern, replacement): regular expressions, matched without regard to case. The mailbox goes first
    (it can contain the roll)."""
    from .demo_from_real import FAKE_NAME, FAKE_ROLL
    pairs = []
    roll = os.environ.get("ERP_USER_ID", "").strip()
    mail = os.environ.get("MAIL_ADDRESS", "").strip()
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    if mail:
        pairs.append(("mailbox", re.escape(mail), "student@example.com"))
    if roll:
        pairs.append(("roll", roll_pattern(roll), FAKE_ROLL))
    if real_name and len(real_name) > 3:
        pairs.append(("name", r"\s+".join(re.escape(w) for w in real_name.split()), FAKE_NAME))
    if url:
        pairs.append(("project address", re.escape(url), "https://YOUR-PROJECT.supabase.co"))
    return pairs


def make(target: Path, clean_demo: bytes, pairs: list[tuple[str, str]]) -> None:
    run("git", "clone", "--quiet", "--mirror", str(ROOT), str(target))
    # every historical blob of the demo snapshot -> today's clean one
    old = set()
    for c in run("git", "rev-list", "--all", "--", "dashboard/demo-data.json", cwd=target).split():
        b = run("git", "rev-parse", f"{c}:dashboard/demo-data.json", cwd=target, check=False).strip()
        if b:
            old.add(b)
    clean_file = target.parent / "clean-demo.json"
    clean_file.write_bytes(clean_demo)
    ids_file = target.parent / "demo-blobs.txt"
    ids_file.write_text("\n".join(sorted(old)))
    rules = target.parent / "replacements.txt"
    lines = [f"regex:(?i){pat}==>{rep}" for _, pat, rep in pairs]
    lines.append(f"regex:(?i){BANNED}==>Ping")
    rules.write_text("\n".join(lines) + "\n", encoding="utf-8")
    callback = (f"ids = set(open({str(ids_file)!r}).read().split())\n"
                f"if blob.original_id.decode() in ids:\n"
                f"    blob.data = open({str(clean_file)!r}, 'rb').read()\n")
    subprocess.run(["git", "filter-repo", "--force", "--quiet", "--replace-text", str(rules), "--blob-callback", callback],
                   cwd=target, check=True)
    for f in (rules, clean_file, ids_file):
        f.unlink()


def check(target: Path, secrets: dict[str, str]) -> list[str]:
    from .demo_from_real import final_check
    problems = []
    blobs = set()
    for line in run("git", "rev-list", "--all", "--objects", cwd=target).splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            blobs.add((parts[0], parts[1]))
    counts = {k: 0 for k in ["demo-data versions", "blobs read"]}
    leaks: dict[str, int] = {}
    for oid, path in blobs:
        if run("git", "cat-file", "-t", oid, cwd=target).strip() != "blob":
            continue
        data = subprocess.run(["git", "cat-file", "-p", oid], cwd=target, capture_output=True).stdout
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        counts["blobs read"] += 1
        if path.endswith("dashboard/demo-data.json") or path == "dashboard/demo-data.json":
            counts["demo-data versions"] += 1
            if final_check(text):
                problems.append(f"a demo-data.json version fails the anonymiser check: {final_check(text)}")
        low = text.lower()
        if BANNED in low:
            leaks["the banned word"] = leaks.get("the banned word", 0) + 1
        for name, v in secrets.items():
            if v.lower() in low or (name == "ERP_USER_ID" and re.search(roll_pattern(v), text, re.I)):
                leaks[name] = leaks.get(name, 0) + 1
        for name, rx in KEY_SHAPES.items():
            if re.search(rx, text):
                leaks[name] = leaks.get(name, 0) + 1
    for k, n in leaks.items():
        problems.append(f"{k}: in {n} blob(s)")
    say(f"checked {counts['blobs read']} text blobs, {counts['demo-data versions']} versions of demo-data.json")
    return problems


def main() -> int:
    from .store import SupabaseStore
    from .config import load_secrets
    secrets = load_secrets(require_erp=False, require_store=True)
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    real_name = (store.select("profile", {"id": "eq.1"}) or [{}])[0].get("name")
    pairs = replacements(real_name)
    say(f"replacing, in every commit: {', '.join(w for w, _, _ in pairs) or 'nothing found'} (of mailbox, roll, name, "
        f"project address), and the banned word")
    clean = (ROOT / "dashboard" / "demo-data.json").read_bytes()
    from .demo_from_real import final_check
    if final_check(clean.decode("utf-8")):
        say("today's demo-data.json fails the anonymiser check: stopping")
        return 1
    work = Path(tempfile.mkdtemp())
    target = work / "ping.git"
    make(target, clean, pairs)
    branches = run("git", "for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=target).split()
    commits = run("git", "rev-list", "--all", "--count", cwd=target).strip()
    say(f"rewritten: {commits} commits, branches {branches}")
    problems = check(target, secret_values())
    if problems:
        say("NOT published, the checks found:")
        for p in problems:
            say(f"  - {p}")
        return 1
    say("checks passed: every demo-data.json version clean; no secret value, key-shaped text or banned word in any blob")
    url, token = os.environ.get("PUBLIC_REPO_URL", "").strip(), os.environ.get("PUBLIC_REPO_TOKEN", "").strip()
    if url and token:
        push = url.replace("https://", f"https://x-access-token:{token}@")
        main_branch = run("git", "symbolic-ref", "--short", "HEAD", cwd=target).strip()
        subprocess.run(["git", "push", "--quiet", push, f"{main_branch}:main"], cwd=target, check=True,
                       capture_output=True)
        say(f"pushed {main_branch} to {url} as main")
    else:
        out = ROOT / "ping-public.bundle"
        run("git", "bundle", "create", str(out), "--all", cwd=target)
        say(f"no PUBLIC_REPO_URL / PUBLIC_REPO_TOKEN: wrote {out.name} ({out.stat().st_size // 1024} KB) for the "
            f"workflow to upload as a private artifact (1 day)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
