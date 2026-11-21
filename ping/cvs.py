"""Your CVs (up to 3 PDFs with labels, Profile > My CVs), for "Apply with: <label>".

The PDFs live in a private Supabase Storage bucket ("cvs"): only the owner's login can upload, list or download
them (database rules, sql/schema.sql), demo sessions can't, and they are never in git. The hourly run (on GitHub
Actions, server-side) reads each new or replaced PDF once, extracts its text, and has Gemini write a short
structured summary (at most 300 tokens) that is stored in the profile (profile.cvs). The raw text is never logged
or stored; only the summary is kept, and contact details are removed from it. The classifier
(ping/relevance.py) gets the summaries next to your targets text and names the best CV per role.
"""

from __future__ import annotations

import io
import json
import re

import requests

from .ai import _msg

BUCKET = "cvs"
MAX_CVS = 3
TEXT_CHARS = 12_000          # what Gemini reads of one CV
SUMMARY_PROMPT = """Summarise this CV so it can be matched to job roles. Reply with JSON only, at most 300 tokens:
{{"focus": "the kind of roles this CV is written for, in a few words",
  "skills": ["at most 8 skills or tools"],
  "experience": ["at most 4 internships, projects or positions, a few words each"],
  "education": "degree and field, in a few words"}}
Never include the person's name, email, phone number, address, roll number or any other ID.

CV text:
<<<
{text}
>>>"""
CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|\+?\d[\d \-]{8,}\d")
stats = {"read": 0, "summarised": 0, "errors": 0, "last_error": None}


def summary_line(s: dict) -> str:
    """{"focus":..,"skills":[..],..} -> one line for the classifier and the Profile page."""
    bits = []
    if s.get("focus"):
        bits.append(f"for {s['focus']}")
    if s.get("skills"):
        bits.append("skills: " + ", ".join(map(str, s["skills"][:8])))
    if s.get("experience"):
        bits.append("experience: " + "; ".join(map(str, s["experience"][:4])))
    if s.get("education"):
        bits.append(f"education: {s['education']}")
    return CONTACT.sub("[removed]", "; ".join(bits))[:900]


def cvs_text(cvs: list[dict] | None) -> str:
    """The CV block the classifier reads (also part of its cache key): one line per summarised CV."""
    return "\n".join(f"- {c['label']}: {c['summary']}" for c in (cvs or []) if c.get("label") and c.get("summary"))


def _pdf_text(data: bytes) -> str:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)[:TEXT_CHARS]


def _summarise(text: str, cfg: dict) -> dict | None:
    prompt = SUMMARY_PROMPT.format(text=text)
    for model in [cfg.get("model") or ""] + list(cfg.get("fallback_models", [])):
        try:
            r = requests.post(cfg["base_url"].rstrip("/") + "/chat/completions", timeout=60,
                              headers={"Authorization": f"Bearer {cfg['key']}"},
                              json={"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]})
            if r.status_code >= 400:
                stats["last_error"] = f"{model}: HTTP {r.status_code} {_msg(r)}"
                continue
            m = re.search(r"\{.*\}", r.json()["choices"][0]["message"]["content"], re.S)
            if m:
                return json.loads(m.group(0))
        except Exception as e:  # never log the CV text itself
            stats["last_error"] = f"{model}: {type(e).__name__}"
    return None


def summarise_new(store, url: str, service_key: str, profile: dict, cfg: dict) -> dict:
    """Summarise CVs uploaded or replaced since their last summary; save them in the profile. Returns counts."""
    cvs = [dict(c) for c in (profile.get("cvs") or [])][:MAX_CVS]
    todo = [c for c in cvs if c.get("path") and c.get("summarised_for") != c.get("uploaded_at")]
    if not todo or cfg.get("provider") != "openai_compatible":
        return {"cvs": len(cvs), "summarised": 0}
    for c in todo:
        try:
            r = requests.get(f"{url.rstrip('/')}/storage/v1/object/{BUCKET}/{c['path']}", timeout=60,
                             headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"})
            r.raise_for_status()
            stats["read"] += 1
            s = _summarise(_pdf_text(r.content), cfg)
            if s:
                c["summary"], c["summarised_for"] = summary_line(s), c.get("uploaded_at")
                stats["summarised"] += 1
            else:
                stats["errors"] += 1
        except Exception as e:
            stats["errors"] += 1
            stats["last_error"] = f"{c.get('label')}: {type(e).__name__}"
    store.upsert("profile", [{"id": profile.get("id", 1), "cvs": cvs}])
    profile["cvs"] = cvs
    return {"cvs": len(cvs), "summarised": stats["summarised"], "errors": stats["errors"], "last_error": stats["last_error"]}
