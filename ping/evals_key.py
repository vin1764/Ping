"""Evals and Admin checks use their own Gemini key, GEMINI_API_KEY_EVALS, never the live GEMINI_API_KEY.

Requests that go through the live ask-ping function carry x-ping-evals: an HMAC-SHA256 of "ping-evals" made with
the evals key (the key itself is never sent). The function then answers with the evals key, logs key "evals", and
refuses an eval request it can't verify instead of answering it on the live key
(supabase/functions/ask-ping/evals_key.ts computes the same value).
"""

from __future__ import annotations

import hashlib
import hmac
import os


def evals_proof(key: str) -> str:
    return hmac.new(key.encode(), b"ping-evals", hashlib.sha256).hexdigest()


def eval_headers() -> dict:
    key = os.environ.get("GEMINI_API_KEY_EVALS", "").strip()
    if not key:
        raise SystemExit("GEMINI_API_KEY_EVALS is not set: evals and Admin checks never use the live Gemini key "
                         "(add it under Settings > Secrets and variables > Actions)")
    return {"x-ping-evals": evals_proof(key)}
