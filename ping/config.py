"""Settings and secrets. Secrets only ever come from environment variables
(GitHub Secrets on the server, a git-ignored .env file on a laptop)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
ERP_BASE = "https://erp.iitkgp.ac.in"

FIRST_RUN_LOOKBACK_DAYS = 14
OTP_WAIT_SECONDS = 180
REQUEST_PAUSE_SECONDS = 0.15  # be gentle with the ERP between popup fetches


class ConfigError(Exception):
    pass


def load_dotenv(path: str | os.PathLike = ".env") -> None:
    """Minimal .env reader for laptop use. Never overrides real env vars."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


@dataclass
class SecurityAnswer:
    question: str
    answer: str


@dataclass
class Secrets:
    erp_user_id: str
    erp_password: str
    security_answers: list[SecurityAnswer]
    mail_address: str
    mail_app_password: str
    supabase_url: str = ""
    supabase_key: str = ""
    ai: dict = field(default_factory=dict)

    @property
    def roll(self) -> str:
        return self.erp_user_id.strip().upper()


def parse_secq(raw: str, name: str) -> SecurityAnswer:
    if "::" not in raw:
        raise ConfigError(f"{name} must look like 'question::answer'")
    q, a = raw.split("::", 1)
    if not q.strip() or not a.strip():
        raise ConfigError(f"{name} has an empty question or answer")
    return SecurityAnswer(q.strip(), a.strip())


def load_secrets(require_erp: bool = True, require_store: bool = True) -> Secrets:
    env = os.environ
    missing = []

    def need(key: str, required: bool = True) -> str:
        val = env.get(key, "").strip()
        if required and not val:
            missing.append(key)
        return val

    user = need("ERP_USER_ID", require_erp)
    pw = need("ERP_PASSWORD", require_erp)
    secq_raw = [need(f"ERP_SECQ_{i}", require_erp) for i in (1, 2, 3)]
    mail = need("MAIL_ADDRESS", require_erp)
    mail_pw = need("MAIL_APP_PASSWORD", require_erp)
    sb_url = need("SUPABASE_URL", require_store)
    sb_key = need("SUPABASE_SERVICE_KEY", require_store)
    if missing:
        raise ConfigError("Missing secrets: " + ", ".join(missing))
    answers = [parse_secq(r, f"ERP_SECQ_{i}") for i, r in enumerate(secq_raw, 1) if r]
    ai = {
        "provider": env.get("PING_AI_PROVIDER", "").strip().lower(),
        "base_url": env.get("PING_AI_BASE_URL", "").strip(),
        "model": env.get("PING_AI_MODEL", "").strip(),
        "key": env.get("PING_AI_KEY", "").strip(),
    }
    gemini = env.get("GEMINI_API_KEY", "").strip()
    if gemini and not ai["provider"]:
        # Gemini's free tier, through its OpenAI-compatible endpoint
        ai = {"provider": "openai_compatible",
              "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
              "model": ai["model"] or "gemini-flash-latest", "key": gemini,
              # gemini-2.5-flash was retired for new keys (Nov 2026); the free tier is sometimes busy (503)
              # 404 in Nov 2026: gemini-2.0-flash, gemini-2.5-flash-lite, gemma-3-27b-it (see Admin > gemini-check)
              "fallback_models": ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
                                  "gemma-4-31b-it"]}
    return Secrets(user, pw, answers, mail, mail_pw.replace(" ", ""), sb_url, sb_key, ai)


def norm_text(s: str) -> str:
    """Lowercase and keep only letters/digits: 'What is your pet's name?' -> 'whatisyourpetsname'."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())
