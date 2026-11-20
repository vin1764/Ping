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
stats = {"calls": 0, "answers": 0, "errors": 0}


def refine_notice(text: str, ref: datetime, companies: list[str], cfg: dict) -> dict | None:
    if cfg.get("provider") != "openai_compatible" or not cfg.get("base_url") or not cfg.get("key"):
        return None
    if stats["calls"] >= MAX_CALLS:
        return None
    stats["calls"] += 1
    prompt = PROMPT.format(ref=ref.isoformat(), companies=", ".join(companies[:300]), text=text[:6000])
    data = None
    for model in [cfg.get("model") or ""] + list(cfg.get("fallback_models", [])):
        body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]}
        try:
            r = requests.post(cfg["base_url"].rstrip("/") + "/chat/completions", json=body, timeout=40,
                              headers={"Authorization": f"Bearer {cfg['key']}"})
            if r.status_code in (400, 404) and cfg.get("fallback_models"):
                continue  # model name retired: try the next one
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", content, re.S)
            data = json.loads(m.group(0)) if m else None
            break
        except Exception:
            data = None
            break
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
