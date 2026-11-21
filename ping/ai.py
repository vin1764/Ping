"""AI fallback for the two things rules find hardest: deadlines written as free
sentences, and company lists inside "Multiple Companies" notices.

Rules always go first. This is only called when the rules come back empty
for a notice, at most MAX_CALLS times per run, and it only ever sees that
notice's text (never PDFs, never your data).

With the GEMINI_API_KEY secret set, Gemini's free tier is used automatically.
To use another provider instead, set these (as GitHub Secrets/variables):

  PING_AI_PROVIDER = openai_compatible
  PING_AI_BASE_URL = e.g. https://generativelanguage.googleapis.com/v1beta/openai
                     or https://api.groq.com/openai/v1
  PING_AI_MODEL    = the model name your provider gives you
  PING_AI_KEY      = your API key (secret)

Any provider with an OpenAI-style /chat/completions endpoint works.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime

import requests

PROMPT = """You read placement notices from IIT Kharagpur's career centre.
Notice time (IST): {ref}
Known company names: {companies}

Notice text:
<<<
{text}
>>>

Reply with JSON only:
{{"deadlines": [{{"at": "YYYY-MM-DDTHH:MM:00+05:30", "text": "exact words from the notice"}}],
  "companies": [{{"name": "company as written", "profiles": ["role", "..."]}}]}}
Use [] when there is nothing. Do not invent dates."""


MAX_CALLS = 20
BUDGET_SECONDS = 300  # all AI calls in one run together
stats = {"calls": 0, "answers": 0, "errors": 0, "last_error": None, "attempts": []}


def _msg(r) -> str:
    """Gemini's own error message ("This model ... is no longer available", "high demand"), not the JSON."""
    try:
        body = r.json()
        body = body[0] if isinstance(body, list) and body else body
        return str(body["error"]["message"])[:200]
    except Exception:
        return r.text[:200]


def refine_notice(text: str, ref: datetime, companies: list[str], cfg: dict) -> dict | None:
    if cfg.get("provider") != "openai_compatible" or not cfg.get("base_url") or not cfg.get("key"):
        return None
    if stats["calls"] >= MAX_CALLS or stats.setdefault("seconds", 0.0) > BUDGET_SECONDS:
        return None  # the free tier can be slow; never let it hold up a run
    stats["calls"] += 1
    prompt = PROMPT.format(ref=ref.isoformat(), companies=", ".join(companies[:300]), text=text[:6000])
    data = None
    started = time.monotonic()
    for model in [cfg.get("model") or ""] + list(cfg.get("fallback_models", [])):
        body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]}
        try:
            r = requests.post(cfg["base_url"].rstrip("/") + "/chat/completions", json=body, timeout=60,
                              headers={"Authorization": f"Bearer {cfg['key']}"})
            if r.status_code >= 400:
                stats["last_error"] = f"{model}: HTTP {r.status_code} {_msg(r)}"
                stats["attempts"] = (stats["attempts"] + [stats["last_error"]])[-10:]
                if r.status_code in (400, 404, 429, 500, 503):
                    continue  # model name retired, or busy right now: try the next one
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", content, re.S)
            if not m:
                raise ValueError(f"no JSON in the reply: {content[:80]!r}")
            data = json.loads(m.group(0))
            break
        except Exception as e:  # timeout or a reply that isn't JSON: try the next model
            stats["last_error"] = f"{model}: {type(e).__name__}: {str(e)[:160]}"
            stats["attempts"] = (stats["attempts"] + [stats["last_error"]])[-10:]
            data = None
            if time.monotonic() - started > BUDGET_SECONDS:
                break
    stats["seconds"] = stats.get("seconds", 0.0) + time.monotonic() - started
    if data is None:
        stats["errors"] += 1
        return None
    stats["answers"] += 1
    if not isinstance(data, dict):
        return None
    good = []
    for d in data.get("deadlines", []) or []:
        try:
            datetime.fromisoformat(d["at"])
            good.append(d)
        except Exception:
            continue
    data["deadlines"] = good
    data["companies"] = [c for c in data.get("companies", []) or [] if isinstance(c, dict) and c.get("name")]
    return data
