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
{cvs}
For each role below, decide whether it is one of the jobs they want. Judge the work the role actually does (from
the job description when there is one), not just the company. If what they want and their CVs disagree, what they
want wins. Reply with JSON only, one entry per role, in order:
[{{"id": "<role id>", "relevant": true or false, "best_cv": "<label of the CV to apply with, or empty>", "reason": "at most 8 words"}}]

Roles:
{roles}"""
CV_BLOCK = "Their CVs (label: summary):\n{lines}\n"

BATCH = 250              # roles per call: normally all of them in one call
JD_CHARS = 400           # enough to tell product from engineering; keeps one call for every role small
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


def _h(s: str) -> str:
    # letters only: a run of digits in a stored key would look like a phone number to the demo's privacy check
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16].translate(LETTERS)


def targets_hash(targets: str, cvs: str = "") -> str:
    """Same in supabase/functions/ask-ping/marks.ts: lower-case, spaces squeezed, sha1, first 16, digits as letters.
    The CV summaries are part of it (they decide best_cv): new CVs, new marks."""
    return _h(_clean(targets).lower() + (("\n" + _clean(cvs)) if _clean(cvs) else ""))


def role_hash(r: dict) -> str:
    """Same in marks.ts: company | title | job description, spaces squeezed (the ERP's own text)."""
    return _h("|".join(_clean(r.get(k)) for k in ("company", "designation", "job_description")))


def cache_key(targets: str, r: dict, cvs: str = "") -> str:
    return targets_hash(targets, cvs) + ":" + role_hash(r)


def needs(r: dict, targets: str, cvs: str = "") -> bool:
    rel = r.get("relevance") or {}
    return bool(_clean(targets)) and rel.get("key") != cache_key(targets, r, cvs)


def classify(roles: list[dict], targets: str, cfg: dict, cvs: str = "") -> dict[str, dict]:
    """{role id: {relevant, reason, jd_missing, key, model}} for the roles that need it. Roles Gemini didn't
    answer for (busy, out of time) are left out and tried again next run."""
    if not _clean(targets) or cfg.get("provider") != "openai_compatible" or not cfg.get("key"):
        return {}
    todo = [r for r in roles if needs(r, targets, cvs)]
    labels = [line[2:].split(":", 1)[0] for line in cvs.splitlines() if line.startswith("- ")]
    out: dict[str, dict] = {}
    started = time.monotonic()
    for i in range(0, len(todo), BATCH):
        if time.monotonic() - started > BUDGET_SECONDS:
            break
        chunk = todo[i:i + BATCH]
        texts = {r["id"]: role_text(r) for r in chunk}
        listing = "\n\n".join(f"[id: {rid}]\n{t}" for rid, (t, _) in texts.items())
        answer, model = _ask(PROMPT.format(targets=_clean(targets)[:600], roles=listing,
                                           cvs=CV_BLOCK.format(lines=cvs) if cvs else ""), cfg, started)
        if not isinstance(answer, list):
            continue
        for a in answer:
            if not isinstance(a, dict) or a.get("id") not in texts or not isinstance(a.get("relevant"), bool):
                continue
            words = _clean(a.get("reason")).split()
            missing = texts[a["id"]][1]
            cv = _clean(a.get("best_cv"))
            out[a["id"]] = {"relevant": a["relevant"], "reason": " ".join(words[:8]).rstrip(".,;"),
                            "best_cv": cv if cv in labels else "", "jd_missing": missing,
                            "key": cache_key(targets, next(r for r in chunk if r["id"] == a["id"]), cvs), "model": model}
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


def tag(r: dict, targets: str, cvs: str = "") -> tuple[str | None, str]:
    """('for_you' | 'other' | None, reason) for a role, from its cached answer (None: not classified yet, or no
    targets set)."""
    rel = r.get("relevance") or {}
    if not _clean(targets) or rel.get("key") != cache_key(targets, r, cvs) or not isinstance(rel.get("relevant"), bool):
        return None, ""
    reason = rel.get("reason") or ""
    if rel.get("jd_missing"):
        reason = (reason + " (JD missing)").strip()
    return ("for_you" if rel["relevant"] else "other"), reason


def mark_roles(store, roles: list[dict], targets: str, cfg: dict, cvs: str = "") -> dict:
    """Attach r["relevance"] to every role from the role_marks cache, classifying the missing ones in one call and
    saving them. Returns counts for the run summary."""
    if not _clean(targets):
        return {"targets_set": False}
    th = targets_hash(targets, cvs)
    try:
        cached = {c["role_hash"]: c for c in store.select("role_marks", {"targets_hash": f"eq.{th}"})}
    except Exception:
        cached = {}
    for r in roles:
        c = cached.get(role_hash(r))
        if c:
            r["relevance"] = {"relevant": c["relevant"], "reason": c.get("reason") or "", "jd_missing": c.get("jd_missing"),
                              "best_cv": c.get("best_cv") or "", "key": cache_key(targets, r, cvs), "model": c.get("model")}
    todo = [r for r in roles if needs(r, targets, cvs)]
    found = classify(todo, targets, cfg, cvs) if todo else {}
    rows = []
    for r in roles:
        if r["id"] in found:
            r["relevance"] = found[r["id"]]
            rows.append({"targets_hash": th, "role_hash": role_hash(r), "relevant": found[r["id"]]["relevant"],
                         "reason": found[r["id"]]["reason"], "jd_missing": found[r["id"]]["jd_missing"],
                         "best_cv": found[r["id"]]["best_cv"],
                         "model": found[r["id"]]["model"]})
    if rows:
        store.upsert("role_marks", list({(x["targets_hash"], x["role_hash"]): x for x in rows}.values()),
                     key="targets_hash,role_hash")
    return {"targets_set": True, "from_cache": len(roles) - len(todo), "classified": len(found),
            "unanswered": len(todo) - len(found), "calls": stats["calls"], "last_error": stats["last_error"]}
