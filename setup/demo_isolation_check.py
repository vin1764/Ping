"""The demo can't see or touch the owner's data (a fresh View demo session on the live project, through the same
REST API the page uses). Writes are no-ops: they set a column to the value it already has, so even a hole would change
nothing; a hole shows as a row coming back.
    python setup/demo_isolation_check.py [dashboard url]
The other direction (the owner's run never reads the demo's profile) is tests/test_firstclub_regression.py and the
owner_read policy (is_ping_owner() and not is_sample)."""
import re
import sys

import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://vin1764.github.io/ping-dashboard/").rstrip("/") + "/"
cfg = requests.get(BASE + "config.js", timeout=30).text
url = re.search(r'"?supabaseUrl"?:\s*"([^"]+)"', cfg).group(1)
key = re.search(r'"?supabaseKey"?:\s*"([^"]+)"', cfg).group(1)
r = requests.post(f"{url}/auth/v1/signup", json={}, headers={"apikey": key}, timeout=30)
r.raise_for_status()
tok = r.json()["access_token"]
H = {"apikey": key, "Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
bad = 0


def ok(cond, what, note=""):
    global bad
    bad += not cond
    print(f"{'ok  ' if cond else 'FAIL'} {what}{': ' + note if note else ''}")


prof = requests.get(f"{url}/rest/v1/profile?select=id,is_sample", headers=H, timeout=30).json()
ok(isinstance(prof, list) and prof and all(p.get("is_sample") for p in prof), "the demo reads only the demo profile", str(prof))
w = requests.patch(f"{url}/rest/v1/profile?id=eq.1", json={"id": 1}, headers={**H, "Prefer": "return=representation"}, timeout=30)
ok(w.status_code >= 400 or w.json() == [], "the demo can't write the owner's profile (a no-op write touches 0 rows)", f"HTTP {w.status_code} {w.text[:80]}")
w = requests.patch(f"{url}/rest/v1/profile?is_sample=is.true", json={"is_sample": True}, headers={**H, "Prefer": "return=representation"}, timeout=30)
ok(w.status_code >= 400 or w.json() == [], "nor the shared demo profile (its own changes go to session_prefs)", f"HTTP {w.status_code} {w.text[:80]}")
for t in ("items", "roles", "notices", "pdf_checks", "forms", "emails", "runs", "rechecks"):
    rows = requests.get(f"{url}/rest/v1/{t}?select=*&is_sample=is.false&limit=1", headers=H, timeout=30)
    n = len(rows.json()) if rows.status_code == 200 else 0
    ok(n == 0, f"real {t} rows the demo can read: {n}", "" if rows.status_code == 200 else f"HTTP {rows.status_code}")
for t in ("form_status", "chat_messages"):
    rows = requests.get(f"{url}/rest/v1/{t}?select=*&limit=50", headers=H, timeout=30)
    n = len(rows.json()) if rows.status_code == 200 else 0
    ok(n == 0, f"other people's {t} the demo can read: {n} (a fresh session has none of its own)")
print(f"\n{bad} problem(s)")
sys.exit(1 if bad else 0)
