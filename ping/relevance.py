"""Which roles are what you're looking for ("For you") and which are the others.

You say what you're looking for in your own words (in the chat, or on the Profile page): the kinds of roles you want
and any you don't. For every role, once, Gemini reads the company, the title and the job description from the ERP and answers {relevant: yes/no, reason: <= 8 words}. The answer is cached on the role
(roles.relevance) with a key made from your text and the role's text, so a role is asked about again only when one
of them changes.

Eligibility stays a hard filter applied first: a role the ERP or your profile rules out is never classified and
never listed. A role whose ERP entry has no job description is classified on its title alone and tagged
"(JD missing)".

Only the role's own public text goes to Gemini (company, title, job description, a few role fields), never your
name, roll number, CGPA or anything from your mailbox.
"""

from __future__ import annotations

import hashlib
import json
import re
import time

import requests

from .ai import _msg

PROMPT = """A student at IIT Kharagpur describes the jobs they want:
<<<
{targets}
>>>

For each role below, decide whether it is one of the jobs they want. Judge the work the role actually does (from
the job description when there is one), not just the company. Reply with JSON only, one entry per role, in order:
[{{"id": "<role id>", "relevant": true or false, "reason": "at most 8 words"}}]

Roles:
{roles}"""

BATCH = 20               # roles per call (the free tier allows few calls a minute)
JD_CHARS = 900           # enough to tell product from engineering; keeps a batch small
BUDGET_SECONDS = 240     # all classification calls in one run together
FIELDS = ("Job Profile", "Job Designation", "Profile", "Role", "Domain", "Job Type")
LETTERS = str.maketrans("0123456789", "ghijklmnop")
stats = {"calls": 0, "classified": 0, "errors": 0, "last_error": None, "seconds": 0.0}


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


# What the ERP has instead of a job description: "Attached", "Find Attached", "NA", "-", a bare link, "As mentioned in
# Registration Email", "Will be shared at the time of opening applications", "PFA the JD".
PLACEHOLDER = re.compile(r"^(?:none|null|n/?a|-+|\.+|tbd|attached|find attached|pfa(?: the)? jd|as mentioned in .{0,40}|"
                         r"attached for your reference|sharing as attachment.{0,30}|will be shared.{0,60}|"
                         r"(?:please )?(?:see|refer)(?: to)? .{0,40}|https?://\S+)\.?$", re.I)


def no_jd(jd: str) -> bool:
    jd = _clean(jd)
    return not jd or bool(PLACEHOLDER.match(jd)) or len(re.sub(r"https?://\S+", "", jd).strip()) < 25


def role_text(r: dict) -> tuple[str, bool]:
    """What Gemini reads about a role, and whether the ERP gave no job description."""
    jd = _clean(r.get("job_description"))
    if no_jd(jd):
        jd = ""
    extra = []
    fields = ((r.get("more_details") or {}).get("fields") or {}) if isinstance(r.get("more_details"), dict) else {}
    for k in FIELDS:
        if fields.get(k):
            extra.append(f"{k}: {_clean(fields[k])[:120]}")
    text = f"Company: {_clean(r.get('company'))}\nTitle: {_clean(r.get('designation'))}"
    if extra:
        text += "\n" + "\n".join(extra)
    text += f"\nJob description: {jd[:JD_CHARS] if jd else '(none given; judge on the title)'}"
    return text, not jd


def cache_key(targets: str, r: dict) -> str:
    text, _ = role_text(r)
    # letters only: a run of digits in a stored key would look like a phone number to the demo's privacy check
    return hashlib.sha1((_clean(targets).lower() + "\n" + text).encode()).hexdigest()[:16].translate(LETTERS)


def needs(r: dict, targets: str) -> bool:
    rel = r.get("relevance") or {}
    return bool(_clean(targets)) and rel.get("key") != cache_key(targets, r)


def classify(roles: list[dict], targets: str, cfg: dict) -> dict[str, dict]:
    """{role id: {relevant, reason, jd_missing, key, model}} for the roles that need it. Roles Gemini didn't
    answer for (busy, out of time) are left out and tried again next run."""
    if not _clean(targets) or cfg.get("provider") != "openai_compatible" or not cfg.get("key"):
        return {}
    todo = [r for r in roles if needs(r, targets)]
    out: dict[str, dict] = {}
    started = time.monotonic()
    for i in range(0, len(todo), BATCH):
        if time.monotonic() - started > BUDGET_SECONDS:
            break
        chunk = todo[i:i + BATCH]
        texts = {r["id"]: role_text(r) for r in chunk}
        listing = "\n\n".join(f"[id: {rid}]\n{t}" for rid, (t, _) in texts.items())
        answer, model = _ask(PROMPT.format(targets=_clean(targets)[:600], roles=listing), cfg, started)
        if not isinstance(answer, list):
            continue
        for a in answer:
            if not isinstance(a, dict) or a.get("id") not in texts or not isinstance(a.get("relevant"), bool):
                continue
            words = _clean(a.get("reason")).split()
            missing = texts[a["id"]][1]
            out[a["id"]] = {"relevant": a["relevant"], "reason": " ".join(words[:8]).rstrip(".,;"),
                            "jd_missing": missing, "key": cache_key(targets, next(r for r in chunk if r["id"] == a["id"])),
                            "targets": _clean(targets).lower(), "model": model}
    stats["classified"] += len(out)
    stats["seconds"] += time.monotonic() - started
    return out


def _ask(prompt: str, cfg: dict, started: float):
    for model in [cfg.get("model") or ""] + list(cfg.get("fallback_models", [])):
        if time.monotonic() - started > BUDGET_SECONDS:
            break
        stats["calls"] += 1
        try:
            r = requests.post(cfg["base_url"].rstrip("/") + "/chat/completions", timeout=90,
                              headers={"Authorization": f"Bearer {cfg['key']}"},
                              json={"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]})
            if r.status_code >= 400:
                stats["last_error"] = f"{model}: HTTP {r.status_code} {_msg(r)}"
                continue
            content = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\[.*\]", content, re.S)
            if m:
                return json.loads(m.group(0)), model
            stats["last_error"] = f"{model}: no JSON list in the reply"
        except Exception as e:
            stats["last_error"] = f"{model}: {type(e).__name__}: {str(e)[:120]}"
    stats["errors"] += 1
    return None, None


def tag(r: dict, targets: str) -> tuple[str | None, str]:
    """('for_you' | 'other' | None, reason) for a role, from its cached answer (None: not classified yet, or no
    targets set)."""
    rel = r.get("relevance") or {}
    if not _clean(targets) or rel.get("key") != cache_key(targets, r) or not isinstance(rel.get("relevant"), bool):
        return None, ""
    reason = rel.get("reason") or ""
    if rel.get("jd_missing"):
        reason = (reason + " (JD missing)").strip()
    return ("for_you" if rel["relevant"] else "other"), reason
