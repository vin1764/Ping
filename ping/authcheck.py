"""Diagnostics for the dashboard login (runs in `check` mode, no ERP login).

Answers: does the Supabase URL + publishable key in the secrets point at one
and the same project, is email/password sign-in on there, and does your user
exist in THAT project with a password it can sign in with. Emails are printed
partly hidden; no passwords or keys are printed.
"""

from __future__ import annotations

import requests


def _mask(email: str) -> str:
    name, _, domain = (email or "").partition("@")
    return (name[:2] + "***@" + domain) if domain else "***"


def check_dashboard_auth(url: str, secret_key: str, publishable_key: str, mail_address: str) -> list[str]:
    out: list[str] = []
    base = url.rstrip("/")
    ref = base.split("//", 1)[-1].split(".", 1)[0]
    out.append(f"project in SUPABASE_URL      : {ref}")
    if not publishable_key:
        out.append("SUPABASE_PUBLISHABLE_KEY     : NOT SET in this workflow - the dashboard build would have no key")
    else:
        out.append(f"publishable key              : starts {publishable_key[:16]}..., {len(publishable_key)} characters")
        r = requests.get(f"{base}/auth/v1/settings", headers={"apikey": publishable_key}, timeout=30)
        if r.status_code == 200:
            s = r.json()
            out.append("publishable key + URL        : SAME project (key accepted)")
            out.append(f"email sign-in enabled        : {s.get('external', {}).get('email')}")
            out.append(f"new sign-ups disabled        : {s.get('disable_signup')}")
            out.append(f"auto-confirm emails          : {s.get('mailer_autoconfirm')}")
        else:
            out.append(f"publishable key + URL        : REJECTED (HTTP {r.status_code}: {r.text[:120]}) - "
                       "the key is from a different project or mistyped")

    hdrs = {"apikey": secret_key}
    r = requests.get(f"{base}/auth/v1/admin/users", params={"per_page": 50}, headers=hdrs, timeout=30)
    if r.status_code in (401, 403):
        r = requests.get(f"{base}/auth/v1/admin/users", params={"per_page": 50},
                         headers={**hdrs, "Authorization": f"Bearer {secret_key}"}, timeout=30)
    if r.status_code != 200:
        out.append(f"dashboard users              : could not list (HTTP {r.status_code}: {r.text[:120]})")
        return out
    users = r.json().get("users", [])
    out.append(f"dashboard users in project   : {len(users)}")
    me = (mail_address or "").strip().lower()
    for u in users:
        providers = sorted({i.get("provider") for i in u.get("identities") or []} |
                           set((u.get("app_metadata") or {}).get("providers") or []))
        flags = [
            "confirmed" if u.get("email_confirmed_at") or u.get("confirmed_at") else "NOT confirmed",
            f"sign-in methods: {', '.join(p for p in providers if p) or 'none'}",
            "invited (no password until the invite is accepted)" if u.get("invited_at") and not u.get("last_sign_in_at") else "",
            f"BANNED until {u['banned_until']}" if u.get("banned_until") else "",
            f"last sign-in {u['last_sign_in_at'][:16]}" if u.get("last_sign_in_at") else "never signed in",
            "<- same as MAIL_ADDRESS" if (u.get("email") or "").lower() == me else "",
        ]
        raw = u.get("email") or ""
        if raw != raw.strip() or raw != raw.lower():
            flags.append("NOTE: stored email has capitals or spaces")
        out.append(f"  - {_mask(raw)}: " + "; ".join(f for f in flags if f))
    if me and not any((u.get("email") or "").lower() == me for u in users):
        out.append(f"  your MAIL_ADDRESS ({_mask(me)}) is NOT a user in this project")
    return out
