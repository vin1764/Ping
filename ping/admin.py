"""One-off maintenance tasks, run on GitHub (Actions > Admin) where the secrets live.

  apply-sql        create/update all tables, permissions and rules (sql/schema.sql) with the access token
  build-demo       build the anonymised demo from your real data, check it, save it for the static demo
                   (dashboard/demo-data.json) and load it as the rows a demo session sees
  gemini-check     call Gemini once and show exactly what comes back, plus retry the notices the rules missed
  functions-check  the Ask Ping / Check now functions on Supabase: deployed versions, which secrets they have
                   (names only), their logs from the last 24 hours, and two test questions from a demo session
  auth-config      Supabase Auth settings for the live dashboard: Site URL and redirect allow-list point at
                   https://<owner>.github.io/ping-dashboard/ (localhost kept for development), anonymous
                   sign-ins on (the one-click demo), and the old reviewer login deleted
  log-scan         search the logs of the last 20 workflow runs for any secret value (prints counts only)
  live-page        live updates on the published dashboard: messages without a reload, scroll rules, the demo's
                   Check now, catching up without the socket, and the row rules on the Realtime channel
  relevance-evals  score "For you" per fixture persona (evals/relevance) and commit its report
  demo-refeed      rebuild the demo's feed with the current code (digests, "For you"), from the same snapshot:
                   example targets on the demo profile, Gemini marks the demo roles, loads and commits it
  jd-report        job descriptions on your real roles: how many have a usable JD before (the ERP's own text
                   field) and now (inline, JD file, public link, details), by source; the roles that had none; JPMC
  demo-jd          copy the JD fields (text, source, link, summary) of your real roles onto the demo's roles,
                   scrubbed and checked like the rest of the demo; saves dashboard/demo-data.json and loads it
  push-setup       push notifications: a VAPID key pair made here, the private key straight into the Supabase function
                   secrets (never printed, never in git), the public key into dashboard/push-public-key.txt (committed,
                   public by design); does nothing if push is already set up (push-rotate makes a new pair and clears
                   the subscriptions, which the old key no longer reaches)
  push-check       push end to end without a phone: the send-push function's public key, a test subscription's
                   encrypted request decrypted here, quiet hours, and the row rules (a demo session can't subscribe)
  demo-clock       set the demo's "now" (the demo profile's updated_at) to the snapshot time in
                   dashboard/demo-data.json, without rebuilding the demo
  cleanup-demo     delete one-click demo sessions (anonymous users) older than 7 days and their chat messages
                   (also runs daily inside Supabase, see schedule-setup)
  schedule-setup   schedule the hourly Ping run and the daily demo cleanup inside Supabase (pg_cron + the kick-run
                   function), with a new shared secret; then a dry-run call to prove it's wired up
  schedule-status  the Supabase jobs, their last runs and calls, and the latest Ping runs on GitHub
  notice-forms     reads only: every form link of a notice (NOTICE_IDS, default 1815), the companies named next to
                   it, its form page title, mails with the link, and the stored row holding it
  feedback-evals   run evals/feedback ("X not relevant", "show X again", "undo") against the deployed function
  ask-ping-evals   run evals/ask_ping (questions against the deployed function from demo sessions) and save the report
  rearm-schedule   switch the Ping workflow off and on through GitHub's API, which makes GitHub register its
                   hourly schedule again, then show what GitHub reports about it
  ask-ping-page    open the live dashboard in a real browser, click "View demo", type the test
                   questions (two single ones, then "any tests today?" with two follow-ups) into the
                   chat and print the replies shown on screen
"""

from __future__ import annotations

import json
import re
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from . import ai, supabase_admin as sa
from .config import IST, load_secrets
from .demo_from_real import REAL, build_from_store, final_check, load_to_db, verify
from .store import SupabaseStore

ROOT = Path(__file__).resolve().parent.parent


def say(msg=""):
    print(msg, flush=True)


def apply_sql(secrets) -> int:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        say("SUPABASE_ACCESS_TOKEN is not set in the repo secrets")
        return 2
    sa.create_database(secrets.supabase_url, token)
    # The data API caches the list of tables; ask it to reload, then confirm from the database itself.
    sa.run_sql(secrets.supabase_url, token, "notify pgrst, 'reload schema';")
    rows = sa.run_sql(secrets.supabase_url, token,
                      "select t, to_regclass('public.' || t) is not null as present from unnest(array["
                      "'chat_messages','demo_questions','allowed_users','items','profile']) t")
    say("  in the database: " + ", ".join(f"{r['t']}={'yes' if r['present'] else 'NO'}" for r in rows))
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    for t in ("chat_messages", "items", "profile"):
        for attempt in range(10):
            try:
                store.select(t, {"limit": "1"})
                say(f"  {t}: reachable through the data API")
                break
            except Exception as e:
                if attempt == 9:
                    raise
                time.sleep(3)
    say("schema.sql applied (tables, permissions, owner and demo rules, chat). Your data was not touched.")
    return 0


def build_demo(secrets) -> int:
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    data = build_from_store(store, secrets.erp_user_id, secrets.mail_address)
    real_name = (store.select("profile", {"id": "eq.1"}) or [{}])[0].get("name")
    problems = verify(data, secrets.erp_user_id, secrets.mail_address, real_name)
    if problems:
        say("NOT written, anonymising left something behind:")
        for p in problems:
            say(f"  - {p}")
        return 1
    out = ROOT / "dashboard" / "demo-data.json"
    out.write_text(json.dumps(data, default=str, ensure_ascii=False), encoding="utf-8")
    counts = load_to_db(store, data)
    visible = sum(1 for i in data["items"] if i["level"] != "hidden")
    say(f"demo built from the real data: {counts}; {visible} items shown in the chat")
    say(f"anonymising check: passed (no real roll, email or name; no other rolls, phones, ten-digit numbers, "
        f"'+91', meeting links or real names from the denylist). Wrote {out.name}, {out.stat().st_size // 1024} KB")
    # read back exactly what a demo session now sees and check it again
    live = {t: store.select(t, {"is_sample": "is.true"}) for t in
            ("profile", "roles", "notices", "pdf_checks", "items", "runs", "contacts", "emails")}
    left = final_check(live)
    say(f"demo rows in the database, read back ({', '.join(f'{t} {len(r)}' for t, r in live.items())}): "
        + ("clean" if not left else "NOT CLEAN: " + "; ".join(left)))
    file_left = final_check(out.read_text(encoding="utf-8"))
    say(f"{out.name} as written: " + ("clean" if not file_left else "NOT CLEAN: " + "; ".join(file_left)))
    return 0 if not left and not file_left else 1


def demo_persona() -> dict:
    """The demo's made-up student (evals/relevance/personas.json): the only place its targets are written."""
    data = json.loads((ROOT / "evals" / "relevance" / "personas.json").read_text(encoding="utf-8"))
    return next(p for p in data["personas"] if p["id"] == "demo")


def demo_refeed(secrets) -> int:
    """The demo as the feed now shows it, from the same anonymised snapshot (companies, roles, pay, deadlines and
    notices unchanged): the demo profile gets example targets, Gemini marks each demo role 'For you' or not (only
    the roles' own text is sent), and the feed is rebuilt with digests at the snapshot time."""
    from .eligibility import evaluate
    from .items import build_items
    from . import relevance
    from .demo_from_real import final_check, load_to_db
    out = ROOT / "dashboard" / "demo-data.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    now = datetime.fromisoformat(data["generated_at"])
    persona = demo_persona()
    DEMO_TARGETS = persona["targets"]
    profile = {**data["profile"], "targets": DEMO_TARGETS, "list_other_roles": persona["list_other_roles"],
               "reminder_hours": persona["reminder_hours"], "updated_at": data["generated_at"],
               # made-up CVs (summaries only; the demo has no files and can't reach the CV bucket)
               "cvs": persona.get("cvs", []), "cv_names": [c["label"] for c in persona.get("cvs", [])]}
    from .cvs import cvs_text
    roles = data["roles"]
    open_ = [r for r in roles if evaluate(r, profile)["eligible"] is not False]
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    for attempt in range(3):            # the free tier is sometimes busy; whatever is left goes next round
        counts = relevance.mark_roles(store, open_, DEMO_TARGETS, secrets.ai, cvs_text(profile["cvs"]))
        say(f"round {attempt + 1}: {counts}")
        if not counts.get("unanswered"):
            break
        time.sleep(30)
    left = [r for r in open_ if relevance.needs(r, DEMO_TARGETS, cvs_text(profile["cvs"]))]
    if left:
        say(f"{len(left)} roles still unclassified; not written (run demo-refeed again)")
        return 1
    # demo ids carry "sample:" (the anonymised copy keeps them apart from your real rows)
    plain = lambda i: str(i).replace("sample:", "")
    old = {plain(i["id"]): i for i in data["items"]}
    checks = {c["notice_id"]: c for c in data["pdf_checks"]}
    notices = [n for n in data["notices"] if n.get("analysis")]
    # twice: the second time with the snapshot's own items as "the last run", so every message keeps the time
    # Ping first saw it (a backlog read on the first run stays in its place instead of collapsing)
    first = build_items(roles, notices, checks, profile, now, [], {}, previous={})
    # only ordinary items carry their time over; Ping's own list messages are rebuilt from the snapshot
    seen = {it["id"]: {"id": it["id"], "first_seen": old[plain(it["id"])]["first_seen"]} for it in first
            if it.get("category") not in ("digest", "listing", "collapse")
            and plain(it["id"]) in old and old[plain(it["id"])].get("first_seen")}
    items = build_items(roles, notices, checks, profile, now, [], {}, previous=seen)
    for it in items:
        it["first_seen"] = (old.get(plain(it["id"])) or {}).get("first_seen") or it.get("first_seen") or now.isoformat()
        it["id"] = "sample:" + plain(it["id"])
        it.update({"is_sample": True, "dismissed": False, "done": False})
    data["profile"], data["items"] = profile, items
    # the four sample mails and the forms list, with today's code, on the rebuilt feed (as demo-mails does)
    from .demo_from_real import add_forms, add_sample_mails
    data = add_forms(add_sample_mails(data))
    problems = final_check(data)
    if problems:
        say("NOT written, the check found: " + "; ".join(problems))
        return 1
    out.write_text(json.dumps(data, default=str, ensure_ascii=False), encoding="utf-8")
    counts = load_to_db(store, data)
    marked = [r for r in roles if (r.get("relevance") or {}).get("relevant") is not None]
    say(f"demo feed rebuilt at {now:%d %b %H:%M} IST: {len(items)} items; roles marked {len(marked)} "
        f"({sum(r['relevance']['relevant'] for r in marked)} for you, "
        f"{sum(bool(r['relevance'].get('jd_missing')) for r in marked)} with no JD); loaded {counts}")
    live = {t: store.select(t, {"is_sample": "is.true"}) for t in
            ("profile", "roles", "notices", "pdf_checks", "items", "runs", "contacts", "emails")}
    left_db = final_check(live)
    say("demo rows read back: " + ("clean" if not left_db else "NOT CLEAN: " + "; ".join(left_db)))
    return 0 if not left_db else 1


JD_FIELDS = ("jd_text", "jd_source", "jd_url", "jd_note", "jd_key", "jd_summary")


def jd_report(secrets) -> int:
    from .jd import usable
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    roles = store.select("roles", REAL)
    before = [r for r in roles if usable(r.get("job_description") or "")]
    now = [r for r in roles if usable(r.get("jd_text") or "")]
    src = {}
    for r in roles:
        src[r.get("jd_source") or "not looked up yet"] = src.get(r.get("jd_source") or "not looked up yet", 0) + 1
    say(f"roles: {len(roles)}")
    say(f"usable JD before (the ERP's own JD field, >= 200 characters of real text): {len(before)} of {len(roles)}")
    say(f"usable JD now (inline, JD file, public link or details): {len(now)} of {len(roles)}")
    say("by source: " + ", ".join(f"{k} {v}" for k, v in sorted(src.items(), key=lambda kv: -kv[1])))
    summ = [r for r in roles if r.get("jd_summary")]
    say(f"summaries: {len(summ)} ({sum((r['jd_summary'] or {}).get('model') == 'rules' for r in summ)} by rules)")
    # the "(JD missing)" marks as the feed shows them: role_marks for the owner's targets and CVs
    from . import relevance
    from .cvs import cvs_text
    prof = (store.select("profile", {"id": "eq.1"}) or [{}])[0]
    targets = "" if prof.get("feed_mode") == "all" else (prof.get("targets") or "")
    marks = {}
    if targets:
        th = relevance.targets_hash(targets, cvs_text(prof.get("cvs")))
        marks = {m["role_hash"]: m for m in store.select("role_marks", {"targets_hash": f"eq.{th}"})}
    marked = [r for r in roles if relevance.role_hash(r) in marks]
    flagged = [r for r in marked if marks[relevance.role_hash(r)].get("jd_missing")]
    say(f"'For you' marks for the current JDs: {len(marked)} roles marked, {len(flagged)} shown '(JD missing)'"
        + ("" if len(marked) else " (the next hourly run marks roles whose JD changed)"))
    missing = [r for r in roles if not usable(r.get("job_description") or "")]
    say(f"\nroles without a usable JD in the ERP's own field ({len(missing)}), and what was found:")
    for r in sorted(missing, key=lambda r: (r.get("jd_source") or "", r["company"])):
        how = r.get("jd_source") or "not looked up yet"
        extra = (f"{len(r.get('jd_text') or '')} chars" + (f" from {r['jd_url']}" if r.get("jd_url") else "")
                 if r.get("jd_text") else (r.get("jd_url") or r.get("jd_note") or ""))
        say(f"  {r['company'][:28]:28} | {(r.get('designation') or '')[:34]:34} | {how}: {str(extra)[:110]}")
    say("\nJPMC:")
    for r in roles:
        if re.search(r"(?i)\bj\.?\s*p\.?\s*morgan|jpmc", r["company"]):
            s = r.get("jd_summary") or {}
            say(f"  {r['company']} | {r.get('designation')} | source {r.get('jd_source')} | "
                f"{len(r.get('jd_text') or '')} chars | own field {len(r.get('job_description') or '')} chars | "
                f"'(JD missing)' now: {bool((marks.get(relevance.role_hash(r)) or {}).get('jd_missing'))}")
            say("  summary: " + json.dumps({k: v for k, v in s.items() if k != "key"}, ensure_ascii=False))
    return 0


def demo_jd(secrets) -> int:
    from .demo_from_real import Scrubber
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    real = {r["id"]: r for r in store.select("roles", REAL)}
    real_name = (store.select("profile", {"id": "eq.1"}) or [{}])[0].get("name")
    scrub = Scrubber(secrets.erp_user_id, real_name, secrets.mail_address)
    out = ROOT / "dashboard" / "demo-data.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    copied, dropped = {}, 0
    for r in data["roles"]:
        src = real.get(str(r["id"]).replace("sample:", ""))
        if not src or not src.get("jd_source"):
            continue
        fields = scrub.walk({k: src.get(k) for k in JD_FIELDS})
        if final_check(fields):
            # something in this JD fails the demo's check (a phone number, an email): the demo gets no text for it
            fields = {**{k: None for k in JD_FIELDS}, "jd_source": "none", "jd_note": "not in the demo"}
            dropped += 1
        r.update(fields)
        copied[fields["jd_source"]] = copied.get(fields["jd_source"], 0) + 1
    problems = final_check(data)
    if problems:
        say("NOT written, the check found: " + "; ".join(problems))
        return 1
    out.write_text(json.dumps(data, default=str, ensure_ascii=False), encoding="utf-8")
    counts = load_to_db(store, data)
    say(f"JD fields copied onto {sum(copied.values())} demo roles: {copied}; {dropped} left out by the check; "
        f"loaded {counts}")
    live = {t: store.select(t, {"is_sample": "is.true"}) for t in ("roles", "items")}
    left = final_check(live)
    say("demo rows read back: " + ("clean" if not left else "NOT CLEAN: " + "; ".join(left)))
    return 0 if not left else 1


PUSH_KEY_FILE = ROOT / "dashboard" / "push-public-key.txt"


def _secret_names(secrets, token: str) -> set:
    ref = sa.project_ref(secrets.supabase_url)
    r = requests.get(f"{API}/v1/projects/{ref}/secrets", timeout=30, headers={"Authorization": f"Bearer {token}"})
    return {x.get("name") for x in (r.json() if r.ok else [])}


def push_setup(secrets, rotate: bool = False) -> int:
    from .push import vapid_keys
    from .run import DASHBOARD_URL
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        say("SUPABASE_ACCESS_TOKEN is not set in the repo secrets")
        return 1
    have = _secret_names(secrets, token)
    if not rotate and "VAPID_PRIVATE_KEY" in have and PUSH_KEY_FILE.exists():
        say(f"push is already set up (public key {PUSH_KEY_FILE.read_text().strip()[:12]}...); run push-rotate for a new pair")
        return 0
    pub, priv = vapid_keys()
    ref = sa.project_ref(secrets.supabase_url)
    r = requests.post(f"{API}/v1/projects/{ref}/secrets", timeout=30, headers={"Authorization": f"Bearer {token}"},
                      json=[{"name": "VAPID_PUBLIC_KEY", "value": pub}, {"name": "VAPID_PRIVATE_KEY", "value": priv},
                            {"name": "VAPID_SUBJECT", "value": DASHBOARD_URL}])
    say(f"VAPID keys set as Supabase function secrets (VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT): HTTP {r.status_code}")
    if r.status_code >= 300:
        return 1
    PUSH_KEY_FILE.write_text(pub + "\n", encoding="utf-8")
    say(f"public key written to dashboard/{PUSH_KEY_FILE.name} ({pub[:12]}...); the dashboard deploy puts it in config.js")
    if rotate:
        store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
        store.delete("push_subscriptions", {"endpoint": "not.is.null"})
        say("old subscriptions removed: each device turns notifications on again (Profile > Notifications)")
    return 0


def _b64u(s: str) -> bytes:
    import base64
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def decrypt_push(body: bytes, ua_private, auth_secret: bytes) -> bytes:
    """Decrypt a Web Push message body (RFC 8291, aes128gcm), as a browser does with its subscription keys."""
    import hashlib
    import hmac
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, rs, idlen = body[:16], int.from_bytes(body[16:20], "big"), body[20]
    as_public = body[21:21 + idlen]
    cipher = body[21 + idlen:]
    assert len(cipher) <= rs, "one record"
    ext = lambda key, data: hmac.new(key, data, hashlib.sha256).digest()  # noqa: E731
    expand = lambda prk, info, n: hmac.new(prk, info + b"\x01", hashlib.sha256).digest()[:n]  # noqa: E731
    secret = ua_private.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public))
    ua_public = ua_private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    ikm = expand(ext(auth_secret, secret), b"WebPush: info\x00" + ua_public + as_public, 32)
    prk = ext(salt, ikm)
    plain = AESGCM(expand(prk, b"Content-Encoding: aes128gcm\x00", 16)).decrypt(expand(prk, b"Content-Encoding: nonce\x00", 12), cipher, None)
    return plain[:plain.rindex(b"\x02")]          # the padding delimiter of the last record


def push_check(secrets) -> int:
    """Push end to end, without a phone (docs/PUSH.md): the function's key, a real encrypted request for a test
    subscription decrypted here, the VAPID token, and the row rules."""
    import json as _json
    import os as _os
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    from .supabase_admin import demo_session
    ok_all = True
    def check(ok, what):
        nonlocal ok_all
        ok_all &= bool(ok)
        say(f"{'ok  ' if ok else 'FAIL'} {what}")
    url = _function_url(secrets, "send-push")
    g = requests.get(url, timeout=30, headers={"apikey": secrets.supabase_key})
    pub = (g.json() if g.ok else {}).get("publicKey") or ""
    file_pub = PUSH_KEY_FILE.read_text().strip() if PUSH_KEY_FILE.exists() else ""
    check(pub and pub == file_pub, f"send-push serves the public key that config.js carries ({pub[:12]}...)")
    # a subscription as a browser makes one: its own P-256 key and a 16-byte auth secret
    ua = ec.generate_private_key(ec.SECP256R1())
    auth = _os.urandom(16)
    b64u = lambda b: __import__("base64").urlsafe_b64encode(b).rstrip(b"=").decode()  # noqa: E731
    p256dh = ua.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/ping-push-check", "keys": {"p256dh": b64u(p256dh), "auth": b64u(auth)}}
    payload = {"title": "Test · today 15:00", "body": "Groww test at 15:00 · room 304 (in 2 h)", "url": "./#m-t1", "tag": "t1"}
    r = requests.post(url, timeout=30, json={"mode": "dry", "subscription": sub, "payload": payload},
                      headers={"Authorization": f"Bearer {secrets.supabase_key}", "apikey": secrets.supabase_key})
    check(r.status_code == 200, f"the function encrypts a notification for a subscription (HTTP {r.status_code})")
    if r.status_code == 200:
        d = r.json()
        h = {k.lower(): v for k, v in d["headers"].items()}
        check(h.get("content-encoding") == "aes128gcm" and int(h.get("ttl", 0)) > 0, f"headers: {sorted(h)}")
        plain = decrypt_push(__import__("base64").b64decode(d["body"]), ua, auth)
        check(_json.loads(plain) == payload, f"decrypted with the subscription's own keys: {plain.decode()[:90]}")
        # the VAPID token: signed by the private key whose public half is in config.js, for this push service
        m = __import__("re").match(r"vapid t=([^,]+), k=(.+)", h.get("authorization", ""))
        check(bool(m) and m.group(2) == pub, "Authorization: vapid t=<JWT>, k=<the public key>")
        if m:
            head, body, sig = m.group(1).split(".")
            claims = _json.loads(_b64u(body))
            key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), _b64u(pub))
            raw = _b64u(sig)
            try:
                key.verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")),
                           f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256()))
                sig_ok = True
            except InvalidSignature:
                sig_ok = False
            check(sig_ok and claims.get("aud") == "https://fcm.googleapis.com" and claims.get("exp", 0) > time.time() and
                  str(claims.get("sub", "")).startswith(("https://", "mailto:")),
                  f"VAPID JWT signature valid; aud {claims.get('aud')}, sub {claims.get('sub')}, expires in "
                  f"{(claims.get('exp', 0) - time.time()) / 3600:.1f} h")
    # the row rules: the service writes and reads a subscription back; a demo session can neither add nor see one
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    row = {"endpoint": sub["endpoint"], "p256dh": sub["keys"]["p256dh"], "auth": sub["keys"]["auth"], "user_agent": "push-check"}
    store.upsert("push_subscriptions", [row], key="endpoint")
    back = store.select("push_subscriptions", {"endpoint": f"eq.{sub['endpoint']}"})
    check(len(back) == 1 and back[0]["p256dh"] == row["p256dh"], "a subscription round-trips through push_subscriptions")
    hdr, _uid = demo_session(secrets.supabase_url, os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""))
    base = {**hdr, "apikey": os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""), "Content-Type": "application/json"}
    ins = requests.post(f"{secrets.supabase_url}/rest/v1/push_subscriptions", timeout=30, headers=base,
                        json={**row, "endpoint": row["endpoint"] + "-demo"})
    see = requests.get(f"{secrets.supabase_url}/rest/v1/push_subscriptions?select=endpoint", timeout=30, headers=base)
    check(ins.status_code >= 400 and see.ok and see.json() == [],
          f"a demo session can't subscribe (HTTP {ins.status_code}) and sees no subscriptions ({len(see.json()) if see.ok else '?'} rows)")
    store.delete("push_subscriptions", {"endpoint": f"eq.{sub['endpoint']}"})
    say("" if ok_all else "some checks failed")
    return 0 if ok_all else 1


def gemini_check(secrets) -> int:
    cfg = secrets.ai
    if not cfg.get("provider"):
        say("no GEMINI_API_KEY in the secrets")
        return 2
    # which models this key can call right now (Google retires and renames them; a retired name answers 404)
    import requests
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", timeout=30,
                     headers={"x-goog-api-key": cfg.get("key", "")}, params={"pageSize": 1000})
    if r.status_code == 200:
        names = sorted(m["name"].split("/", 1)[1] for m in r.json().get("models", [])
                       if "generateContent" in m.get("supportedGenerationMethods", []))
        say(f"models this key can call ({len(names)}): {', '.join(names)}")
        configured = [cfg.get("model")] + list(cfg.get("fallback_models", []))
        gone = [m for m in configured if m and m not in names]
        say("configured models missing from that list: " + (", ".join(gone) if gone else "none"))
    else:
        say(f"listing models: HTTP {r.status_code}")
    test = "The CV submission of Northwind (made-up) closes at five in the evening on the twenty-second of November, 2026."
    res = ai.refine_notice(test, datetime(2026, 11, 20, tzinfo=IST), ["Northwind"], cfg)
    say(f"models tried in order: {[cfg.get('model')] + list(cfg.get('fallback_models', []))}")
    say(f"test call: {'answered' if res else 'FAILED'}; {res}")
    for a in ai.stats["attempts"]:
        say(f"  model said: {a}")
    # Ask Ping's main model has 10 s in all: how long it takes on a prompt the size of Ask Ping's, with its default
    # thinking and with less (an option the model refuses answers 400, which is reported, not retried)
    main = os.environ.get("PING_AI_MODEL") or "gemini-flash-latest"
    big = ("FACTS start here.\n" + "\n".join(f"- Company {i} (made-up): role Analyst {i}, CTC {10 + i % 20} LPA, closes "
           f"2{i % 9} Nov 20:00, CG cut-off 7.{i % 10}" for i in range(220)) + "\nFACTS end here.\n\n"
           "Question: which three of these pay the most and close soonest? Answer in under 80 words.")
    for label, extra in (("default thinking", {}), ("thinkingBudget 0", {"thinkingConfig": {"thinkingBudget": 0}}),
                         ("thinkingLevel low", {"thinkingConfig": {"thinkingLevel": "low"}})):
        for attempt in (1, 2):
            t = time.monotonic()
            try:
                rr = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{main}:generateContent",
                                   headers={"x-goog-api-key": cfg.get("key", "")}, timeout=60,
                                   json={"contents": [{"role": "user", "parts": [{"text": big}]}],
                                         "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096, **extra}})
                um = rr.json().get("usageMetadata", {}) if rr.headers.get("content-type", "").startswith("application/json") else {}
                say(f"  {main}, {label}, try {attempt}: HTTP {rr.status_code} in {time.monotonic() - t:.1f} s; "
                    f"prompt {len(big)} chars; thinking tokens {um.get('thoughtsTokenCount', 0)}"
                    + ("" if rr.ok else f"; {rr.text[:160]}"))
            except Exception as e:
                say(f"  {main}, {label}, try {attempt}: {type(e).__name__} after {time.monotonic() - t:.1f} s")
            time.sleep(2)
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    missed = [n for n in store.select("notices", REAL) if (n.get("analysis") or {}).get("rule_misses")]
    say(f"notices the rules couldn't read: {len(missed)}")
    for n in missed[:5]:
        ai.stats["last_error"] = None
        res = ai.refine_notice(n.get("text") or n.get("preview") or "", datetime.fromisoformat(n["notice_time"]),
                               [r["company"] for r in store.select("roles", REAL)], cfg)
        say(f"  notice {n['notice_id']} ({n['subject']} / {n['company']}): misses {n['analysis']['rule_misses']} -> "
            f"{'Gemini answered: ' + json.dumps(res)[:300] if res else 'no answer; ' + str(ai.stats['last_error'])}")
    return 0 if res is not None or not missed else 1


API = "https://api.supabase.com"


def _z(t) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")  # the logs API accepts only this shape


def _logs(ref: str, token: str, sql: str, hours: int = 23) -> list:
    from datetime import timedelta, timezone
    end = datetime.now(timezone.utc)
    r = requests.get(f"{API}/v1/projects/{ref}/analytics/endpoints/logs", timeout=60,
                     headers={"Authorization": f"Bearer {token}"},
                     params={"sql": sql, "iso_timestamp_start": _z(end - timedelta(hours=hours)),
                             "iso_timestamp_end": _z(end)})
    _logs.last_error = None
    if r.status_code >= 400:
        _logs.last_error = f"HTTP {r.status_code} {r.text[:300]}"
        say(f"  (logs query failed: {_logs.last_error})")
        return []
    body = r.json()
    if body.get("error"):
        _logs.last_error = str(body["error"])[:300]
        say(f"  (logs query error: {_logs.last_error})")
    return body.get("result") or []


def _when(ts) -> str:
    try:
        v = float(ts)
        v = v / 1e6 if v > 1e14 else v / 1e3 if v > 1e11 else v
        return f"{datetime.fromtimestamp(v, IST):%d %b %H:%M:%S}"
    except (TypeError, ValueError):
        try:
            return f"{datetime.fromisoformat(str(ts).replace('Z', '+00:00').replace(' ', 'T')).astimezone(IST):%d %b %H:%M:%S}"
        except ValueError:
            return str(ts)


def _source_logs(ref: str, token: str, source: str, function_id, fields: str, limit: int) -> list:
    """Supabase's logs API (ClickHouse SQL): one `logs` table, filtered by source; its docs name the
    column both source_name and source, so try both."""
    for col in ("source", "source_name"):
        rows = _logs(ref, token, f"""
            SELECT timestamp, {fields}
            FROM logs
            WHERE {col} = '{source}' AND log_attributes['function_id'] = '{function_id}'
            ORDER BY timestamp DESC
            LIMIT {limit}""")
        if rows or not _logs.last_error:
            return rows
    return []


def ask_as_demo(url: str, questions: list[str]) -> list[tuple[str, int, float, str]]:
    """Ask Ping exactly like the dashboard's demo does: a one-click (anonymous) session, POST {question}."""
    hdr, _ = sa.demo_session(url, os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""))
    out = []
    for q in questions:
        t = time.monotonic()
        from .evals_key import eval_headers   # Admin checks run on the evals Gemini key, not the live one
        a = requests.post(f"{url.rstrip('/')}/functions/v1/ask-ping", timeout=180, json={"question": q},
                          headers={**hdr, **eval_headers()})
        out.append((q, a.status_code, time.monotonic() - t, a.text[:1500]))
    return out

LATENCY_QUESTIONS = ["slice ctc breakdown", "what's due tomorrow", "navi roles", "elig?", "jd of ather energy",
                     "which cv for aiprise", "process till now?", "any interviews for groww?", "ctc?",
                     "is phyagents test today"]


def ask_latency(secrets) -> int:
    """Read-only: 10 questions from a fresh one-click demo session (demo data, evals keys), timed per stage by the
    function itself (timing: stages, reads, cold), then the same 10 with the model steps off (no_ai) for the rules'
    answers' fingerprints, to compare across versions. Prints a table and the medians."""
    import statistics
    from .evals_key import eval_headers
    url = secrets.supabase_url.rstrip("/")
    rows = []
    for label, extra in (("timed", {}), ("rules only", {"no_ai": True})):
        hdr, _ = sa.demo_session(url, os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""))
        for q in LATENCY_QUESTIONS:
            t = time.monotonic()
            r = requests.post(f"{url}/functions/v1/ask-ping", timeout=180, json={"question": q, **extra},
                              headers={**hdr, **eval_headers()})
            ms = int((time.monotonic() - t) * 1000)
            try:
                b = r.json()
            except ValueError:
                b = {"error": r.text[:200]}
            rows.append({"set": label, "q": q, "status": r.status_code, "client": ms, **b})
            time.sleep(1.5)
    med = lambda xs: int(statistics.median(xs)) if xs else 0
    timed = [x for x in rows if x["set"] == "timed"]
    say("per request (timed set): client ms | function ms | cold | route | model | slowest stages")
    for x in timed:
        tm = x.get("timing") or {}
        st = sorted((tm.get("stages") or {}).items(), key=lambda kv: -kv[1])[:4]
        say(f"  {x['q'][:28]:28} | {x['client']:5} | {tm.get('total', '-'):>5} | {'cold' if tm.get('cold') else 'warm':4} | "
            f"{x.get('route', x.get('error', '?'))!s:5} | {x.get('model', '-')!s:28} | " + ", ".join(f"{k} {v}" for k, v in st))
    cl = [x["client"] for x in timed]
    fn = [(x.get("timing") or {}).get("total") for x in timed if x.get("timing")]
    say(f"\nclient: median {med(cl)} ms, worst {max(cl) if cl else 0} ms; inside the function: median {med(fn)} ms, "
        f"worst {max(fn) if fn else 0} ms; outside it (network, gateway, boot): median "
        f"{med([x['client'] - x['timing']['total'] for x in timed if x.get('timing')])} ms; cold starts "
        f"{sum(1 for x in timed if (x.get('timing') or {}).get('cold'))}/{len(timed)}")
    for key in ("stages", "reads"):
        names = sorted({k for x in timed for k in ((x.get("timing") or {}).get(key) or {})})
        say(f"{key} (median / worst ms over the requests that had it):")
        for n in names:
            v = [(x["timing"][key] or {}).get(n) for x in timed if x.get("timing") and n in (x["timing"].get(key) or {})]
            say(f"  {n:22} {med(v):6} / {max(v):6}  ({len(v)} requests)")
    say("\nrules' answers (model steps off), fingerprints to compare across versions:")
    for x in rows:
        if x["set"] == "rules only":
            say(f"  {x['q'][:28]:28} -> {x.get('rules_hash') or x.get('route') or x.get('error')}  ({x['client']} ms)")
    return 0


def functions_check(secrets) -> int:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        say("SUPABASE_ACCESS_TOKEN is not set in the repo secrets")
        return 2
    ref = sa.project_ref(secrets.supabase_url)
    hdr = {"Authorization": f"Bearer {token}"}
    fns = requests.get(f"{API}/v1/projects/{ref}/functions", headers=hdr, timeout=30).json()
    ids = {}
    say("deployed functions:")
    for f in fns if isinstance(fns, list) else []:
        ids[f.get("id")] = f.get("slug")
        say(f"  {f.get('slug')}: status {f.get('status')}, version {f.get('version')}, "
            f"updated {datetime.fromtimestamp((f.get('updated_at') or 0) / 1000, IST):%d %b %H:%M IST}, "
            f"verify_jwt {f.get('verify_jwt')}")
    names = sorted(x.get("name", "") for x in requests.get(f"{API}/v1/projects/{ref}/secrets", headers=hdr,
                                                            timeout=30).json())
    say(f"secrets the functions can read on Supabase (names only): {', '.join(names)}")
    for n in ("GEMINI_API_KEY", "GEMINI_API_KEY_EVALS", "GROQ_API_KEY", "GROQ_API_KEY_EVALS"):
        say(f"  {n} on the Supabase side: {'yes' if n in names else 'NO'}")
    ask_id = next((i for i, slug in ids.items() if slug == "ask-ping"), None)

    say("\nask-ping requests, last 23 h (newest first):")
    rows = _source_logs(ref, token, "function_edge_logs", ask_id, """
        log_attributes['response.status_code'] AS status, log_attributes['request.method'] AS method,
        log_attributes['execution_time_ms'] AS ms, log_attributes['version'] AS version""", 40)
    for x in rows:
        say(f"  {_when(x.get('timestamp'))} {x.get('method')} -> HTTP {x.get('status')} in {x.get('ms')} ms "
            f"(version {x.get('version')})")
    say("\nask-ping messages (errors, crashes, shutdown reasons), last 23 h:")
    rows = _source_logs(ref, token, "function_logs", ask_id, """
        event_message, severity_text AS severity, log_attributes['level'] AS level,
        log_attributes['event_type'] AS event_type""", 60)
    for x in rows:
        msg = " ".join(str(x.get("event_message") or "").split())[:400]
        say(f"  {_when(x.get('timestamp'))} [{x.get('level') or x.get('severity')}/{x.get('event_type')}] {msg}")

    # which Gemini key each answer used: evals and Admin checks must show "evals", never "live"
    rows = _source_logs(ref, token, "function_logs", ask_id, "event_message", 1000)
    tally: dict = {}
    for x in rows:
        try:
            ev = json.loads(str(x.get("event_message") or "").strip())
        except ValueError:
            continue
        if ev.get("event") in ("answered", "no_answer"):
            # a model was called only when something was tried (rules, JD and help answers call none)
            called = bool(ev.get("tried")) and not ev.get("no_ai")
            k = (ev.get("key") or "(before the split)", ev.get("role") or "?", "model called" if called else "no model call")
            tally[k] = tally.get(k, 0) + 1
    say("\nask-ping answers by Gemini key, last 23 h (key, caller, model called or not: answers):")
    for (k, who, called), n in sorted(tally.items()):
        say(f"  {k}, {who}, {called}: {n}")

    if os.environ.get("SUPABASE_PUBLISHABLE_KEY"):
        say("\ntest questions from a one-click demo session on the evals key (demo data, same function):")
        try:
            for q, code, secs, body in ask_as_demo(secrets.supabase_url, ["slice ctc breakdown", "what's due tomorrow"]):
                say(f"  Q: {q}\n  -> HTTP {code} in {secs:.1f}s: {body}")
        except sa.SetupError as e:
            say(f"  {e}")
    return 0


def _model_tally(events: list[dict]) -> dict:
    """Per model: calls, answers, and why the rest failed, from the 'tried' lists ("model:429:300ms",
    "model:TimeoutError:10000ms", "model:empty(MAX_TOKENS)") of the answered / no_answer events."""
    out: dict = {}
    for ev in events:
        tried = ev.get("tried") or []
        seen = []
        for t in tried:
            parts = str(t).split(":")
            model, what = parts[0], parts[1] if len(parts) > 1 else "?"
            m = out.setdefault(model, {"calls": 0, "answered": 0, "why": {}, "ms": []})
            if what.startswith("empty("):          # a 200 with no text: that call didn't answer
                m["answered"] -= 1
                m["why"]["empty"] = m["why"].get("empty", 0) + 1
                continue
            m["calls"] += 1
            seen.append(model)
            if what == "200":
                m["answered"] += 1
                if len(parts) > 2 and parts[2].endswith("ms") and parts[2][:-2].isdigit():
                    m["ms"].append(int(parts[2][:-2]))
            else:
                key = "timeout" if "Timeout" in what or "Abort" in what else what
                m["why"][key] = m["why"].get(key, 0) + 1
        # a 200 whose answer was then thrown away (a made-up number) still counts as the model answering
    return out


def chat_diagnose(secrets) -> int:
    """Reads only. (1) the latest chat message with 'relevant' in it (24 h): its time, the message it replied to, Ping's
    answer, and the ask-ping requests and log lines around it; (2) per model, on the live key and on the evals key:
    calls, answers and failures in the last 24 h."""
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        say("SUPABASE_ACCESS_TOKEN is not set in the repo secrets")
        return 2
    ref = sa.project_ref(secrets.supabase_url)
    hdr = {"Authorization": f"Bearer {token}"}
    fns = requests.get(f"{API}/v1/projects/{ref}/functions", headers=hdr, timeout=30).json()
    ask_id = next((f.get("id") for f in fns if f.get("slug") == "ask-ping"), None) if isinstance(fns, list) else None
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    from datetime import timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    msgs = store.select("chat_messages", {"created_at": f"gte.{since}", "order": "created_at.asc"},
                        columns="role,text,created_at,reply_quote,owner_id")
    me = [m for m in msgs if m.get("role") == "me" and re.search(r"relevan", m.get("text") or "", re.I)]
    at = None
    if me:
        m = me[-1]
        at = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00"))
        nxt = next((x for x in msgs if x.get("role") == "ping" and x.get("owner_id") == m.get("owner_id")
                    and x["created_at"] > m["created_at"]), None)
        say(f"the message: {_when(m['created_at'])} {m['text']!r}")
        say(f"  replying to: {str(m.get('reply_quote') or '(not a reply)')[:200]}")
        if nxt:
            say(f"  Ping's answer ({_when(nxt['created_at'])}), first 600 chars:\n    " + nxt["text"][:600].replace("\n", "\n    "))
    else:
        say("no chat message with 'relevant' in the last 24 h")
    edge = _logs(ref, token, f"""
        SELECT timestamp, log_attributes['response.status_code'] AS status, log_attributes['execution_time_ms'] AS ms,
               log_attributes['version'] AS version
        FROM logs WHERE source = 'function_edge_logs' AND log_attributes['function_id'] = '{ask_id}'
        ORDER BY timestamp DESC LIMIT 1000""", hours=24)
    lines = _logs(ref, token, f"""
        SELECT timestamp, event_message FROM logs
        WHERE source = 'function_logs' AND log_attributes['function_id'] = '{ask_id}'
        ORDER BY timestamp DESC LIMIT 5000""", hours=24)

    def ts(x):
        raw = x.get("timestamp") or 0
        try:
            v = float(raw)
            return datetime.fromtimestamp(v / 1e6 if v > 1e14 else v / 1e3, timezone.utc)
        except (TypeError, ValueError):
            t = datetime.fromisoformat(str(raw).replace("Z", "+00:00").replace(" ", "T"))
            return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    if at:
        say("\nask-ping requests within 3 min of it (HTTP status, time):")
        for x in sorted(edge, key=ts):
            if abs((ts(x) - at).total_seconds()) <= 180:
                say(f"  {_when(x['timestamp'])} HTTP {x.get('status')} in {x.get('ms')} ms (version {x.get('version')})")
        say("ask-ping log lines within 3 min of it:")
        for x in sorted(lines, key=ts):
            if abs((ts(x) - at).total_seconds()) <= 180:
                say(f"  {_when(x['timestamp'])} {' '.join(str(x.get('event_message') or '').split())[:500]}")
    codes: dict = {}
    for x in edge:
        codes[str(x.get("status"))] = codes.get(str(x.get("status")), 0) + 1
    say(f"\nask-ping HTTP statuses, last 24 h: {dict(sorted(codes.items()))}")
    evs = []
    for x in lines:
        try:
            ev = json.loads(str(x.get("event_message") or "").strip())
        except ValueError:
            continue
        if isinstance(ev, dict):
            evs.append(ev)
    for key in ("live", "evals"):
        mine = [e for e in evs if e.get("event") in ("answered", "no_answer") and e.get("key") == key]
        by = {}
        for e in mine:
            k = e.get("model") if e.get("event") == "answered" else "no answer"
            by[k] = by.get(k, 0) + 1
        say(f"\n{key} key: {len(mine)} answers in 24 h, answered by: {by}")
        for model, t in sorted(_model_tally(mine).items()):
            rate = f"{100 * t['answered'] / t['calls']:.0f}%" if t["calls"] else "n/a"
            ms = sorted(t["ms"])
            med = f", median {ms[len(ms) // 2] / 1000:.1f} s" if ms else ""
            say(f"  {model}: {t['calls']} calls, {t['answered']} answered ({rate}{med}); failures: {t['why']}")
        sizes = sorted(e.get("prompt_chars") for e in mine if e.get("prompt_chars"))
        if sizes:
            say(f"  prompt size: median {sizes[len(sizes) // 2]:,} characters, largest {sizes[-1]:,}")
    errs: dict = {}
    for e in evs:
        if e.get("event") == "gemini_error":
            k = (e.get("model"), e.get("status"))
            errs[k] = errs.get(k, 0) + 1
    say(f"\nGemini error responses, both keys, 24 h (model, HTTP status: count): {errs}")
    for e in evs:
        if e.get("event") == "gemini_error":
            say(f"  e.g. {e.get('model')} {e.get('status')}: {str(e.get('body'))[:300]}")
            break
    return 0


def ask_ping_page(secrets) -> int:
    """The live page's checks (setup/ask_ping_page_test.py), then every single-question eval typed into the page
    (setup/ask_ping_page_evals.py: who answered, time to the reply on screen, the checks), written to
    evals/ask_ping/PAGE_RUN.md."""
    import subprocess
    checks = subprocess.run([sys.executable, str(ROOT / "setup" / "ask_ping_page_test.py"),
                           "slice ctc breakdown", "what's due tomorrow",
                           # follow-ups in the same demo session: the answers must use the conversation
                           "any tests today?", "anything else?", "nothing else?",
                           # the demo profile says what it's looking for: the answer splits For you / Others
                           "what's due tonight that's relevant to me", "which cv for groww"]).returncode
    say("\n---- single-question evals through the page ----")
    evals = subprocess.run([sys.executable, str(ROOT / "setup" / "ask_ping_page_evals.py")]).returncode
    return checks or evals


def prefs_report(secrets) -> int:
    """Your saved preferences (profile id 1), when they last changed and by which chat message, which roles the
    feed now marks For you, and a check that no demo or eval row is read as yours. Reads only."""
    from .relevance import tag
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    rows = store.select("profile", {}, columns="id,is_sample,updated_at,targets,interested_companies,not_interested_companies,list_other_roles,feed_mode,notice_types,reminder_hours,roll,name,cgpa,cvs,department,degree,active_backlogs")
    me = next((r for r in rows if r.get("id") == 1), {})
    say("profile rows: " + ", ".join(f"id {r['id']} (sample={r.get('is_sample')}, updated {r.get('updated_at')})" for r in rows))
    say(f"yours (id 1): updated_at {me.get('updated_at')} (also moves when the chat marks messages read)")
    say(f"  targets: {me.get('targets')!r}")
    say(f"  interested companies: {me.get('interested_companies')}; not interested: {me.get('not_interested_companies')}")
    say(f"  list other roles: {me.get('list_other_roles')}; feed mode: {me.get('feed_mode')}; notice types: {me.get('notice_types')}; reminder {me.get('reminder_hours')} h")
    say(f"  roll set in profile: {bool(me.get('roll'))} (same as ERP login: {str(me.get('roll') or secrets.erp_user_id).upper() == secrets.erp_user_id.upper()}); CGPA set: {me.get('cgpa') is not None}")
    # the chat messages that changed preferences: yours, then Ping's "Saved: …" reply
    chat = store.select("chat_messages", {"is_sample": "is.false", "order": "created_at.desc"}, columns="role,text,created_at")[:400]
    saved = [m for m in chat if m["role"] == "ping" and re.match(r"^(Saved|Done|Updated|Noted)[:,]", m["text"] or "")]
    for m in saved[:5]:
        before = next((x for x in chat if x["role"] == "me" and x["created_at"] <= m["created_at"]), None)
        say(f"  change {m['created_at']}: you wrote {(before or {}).get('text', '?')[:120]!r} -> Ping: {m['text'][:140]!r}")
    if not saved:
        say("  no preference change in your chat (the targets were set on the Profile page or during onboarding)")
    # what the feed marks For you now, with the targets above
    roles = store.select("roles", {"is_sample": "is.false"})
    from .cvs import cvs_text
    from .eligibility import evaluate
    from .relevance import mark_roles
    cvt = cvs_text(me.get("cvs"))
    marks = mark_roles(store, roles, me.get("targets") or "", {}, cvt)     # from the cache only: no model call here
    say(f"marks: {marks}")
    for_you = [r for r in roles if tag(r, me.get("targets") or "", cvt)[0] == "for_you" and evaluate(r, me)["eligible"] is not False]
    say(f"For you now: {len(for_you)} roles")
    for name in ("aiprise", "astera"):
        for r in roles:
            if name in (r.get("company") or "").lower():
                t, why = tag(r, me.get("targets") or "", cvt)
                say(f"  {r['company']} — {r.get('designation')}: {t} ({why}); best CV {((r.get('relevance') or {}).get('best_cv') or '-')}")
    return 0


def forms_report(secrets) -> int:
    """The forms list as stored (read-only): rows, rows for several companies, merge prompts left (should be 0),
    pending merge choices, ticks and whether each tick's row exists, and the row(s) of notice 1815."""
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    rows = store.select("forms", {"is_sample": "is.false"})
    keys = {r["key"] for r in rows}
    ticks = [t for t in store.select("form_status", {"is_demo": "is.false"}) if t.get("filled")]
    say(f"forms rows: {len(rows)}; for several companies: {sum(1 for r in rows if len(r.get('companies') or []) > 1)}; "
        f"rows with a merge prompt: {sum(1 for r in rows if r.get('looks_like'))}; pending merge choices: {len(store.select('form_merges', {'is_demo': 'is.false'}))}")
    say(f"ticks: {len(ticks)}, on rows that exist: {sum(1 for t in ticks if t['form_key'] in keys)}")
    every = store.select("form_status", {})
    say(f"form_status rows in all: {len(every)} (yours: {sum(1 for t in every if not t.get('is_demo'))}, ticked "
        f"{sum(1 for t in every if not t.get('is_demo') and t.get('filled'))}; demo sessions': {sum(1 for t in every if t.get('is_demo'))})")
    for t in every:
        if not t.get("is_demo"):
            say(f"  yours: {t['form_key'][:48]} filled={t.get('filled')} at {t.get('filled_at') or t.get('updated_at')}")
    for r in rows:
        if any(s.get("id") == "1815" for s in r.get("sources") or []):
            say(f"notice 1815 -> row {r['key']}: {len(r.get('companies') or [])} companies, due {r.get('due_at')}, "
                f"{len(r.get('sources') or [])} sources, {len(r.get('deadline_history') or [])} deadline moves")
    # a notice with a form per company: its rows, each with its own companies, form and tick
    filled = {t["form_key"] for t in ticks}
    by_notice: dict = {}
    for r in rows:
        for src in r.get("sources") or []:
            if src.get("type") == "notice":
                by_notice.setdefault(str(src.get("id")), []).append(r)
    for nid, rs in sorted(by_notice.items(), key=lambda kv: -len(kv[1])):
        if len(rs) < 2:
            continue
        say(f"notice {nid}: {len(rs)} rows, one per form")
        for r in sorted(rs, key=lambda r: ", ".join(r.get("companies") or [])):
            link = r.get("final_url") or r.get("link") or ""
            say(f"  - {', '.join(r.get('companies') or [])[:80]} | {(r.get('title') or '(no page title)')[:50]} | "
                f"{'own form link' if link else 'no link'} {r['key'][:40]} | {'ticked' if r['key'] in filled else 'not ticked'}")
    for r in rows:
        if any("risa" in (c or "").lower() for c in r.get("companies") or []):
            say(f"RISA Labs: row {r['key']} with {len(r.get('companies') or [])} companies, Open form -> "
                f"{'yes' if (r.get('final_url') or r.get('link')) else 'NO LINK'}, {'ticked' if r['key'] in filled else 'not ticked'}")
    for t in ticks:
        r = next((x for x in rows if x["key"] == t["form_key"]), None)
        say(f"tick on {t['form_key'][:40]}: {', '.join((r or {}).get('companies') or ['(no such row)'])[:80]}")
    sig = {}
    for r in rows:
        sig.setdefault((frozenset(c.lower() for c in r.get("companies") or []), r.get("purpose"), r.get("due_at")), []).append(r["key"])
    dup = {k: v for k, v in sig.items() if len(v) > 1}
    say(f"rows with the same companies, purpose and deadline: {sum(len(v) for v in dup.values())} in {len(dup)} groups")
    return 0


def push_examples(secrets) -> int:
    """Reads only: notifications as they would read now, rendered from your live items and roles (one per type, and
    the grouped ones). A type with nothing open right now is shown on its most recent example, as it read 3 h before."""
    from datetime import timedelta, timezone
    from . import push
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    items = store.select("items", REAL)
    roles = {r["id"]: r for r in store.select("roles", REAL)}
    now = datetime.now(timezone.utc).astimezone(IST)
    shown = 0

    def show(label, note, at_now):
        nonlocal shown
        shown += 1
        say(f"{shown}. {label}{f' ({at_now})' if at_now else ''}")
        say(f"   title: {note['title']}")
        for line in (note.get("body") or "").split("\n"):
            say(f"   body:  {line}")
        say(f"   tap:   {note['url']}")
    every = push.acts(items, roles, now)
    for typ, label in (("apply", "Application"), ("form", "Form"), ("extended", "Deadline extension"), ("test", "Test"),
                       ("shortlist", "Shortlist"), ("new", "New role for you")):
        a = next((x for x in sorted(every, key=lambda x: x["at"] or now) if x["type"] == typ), None)
        if a:
            show(label, push.render([a], now), "")
            continue
        # nothing open of this type now: its latest example, as it read 3 h before its time (an extension: 30 min
        # after it was seen)
        for it in sorted(items, key=lambda i: str(i.get("due_at") or i.get("event_at") or i.get("first_seen") or ""), reverse=True):
            at = push._at(it.get("due_at") or it.get("event_at")) or push._at(it.get("first_seen"))
            if not at:
                continue
            then = at - timedelta(hours=3)
            ext = (it.get("details") or {}).get("extended")
            if typ == "extended" and isinstance(ext, list) and ext:
                seen = push._at(ext[-1].get("at") or ext[-1].get("seen_at"))
                if not seen:
                    continue
                then = seen + timedelta(minutes=30)
            got = [x for x in push.acts([it], roles, then) if x["type"] == typ]
            if got:
                show(label, push.render(got[:1], then), f"as on {then:%a %d %b %H:%M}")
                break
        else:
            say(f"-. {label}: nothing of this type in your data")
    # grouped: the deadline with the most to do
    for typ, label in (("apply", "Grouped applications"), ("new", "Grouped new roles"), ("form", "Grouped forms")):
        by: dict = {}
        for x in every:
            if x["type"] == typ:
                by.setdefault(x["at"], []).append(x)
        best = max(by.values(), key=len, default=[])
        if len(best) > 1:
            show(label, push.render(best, now), "")
            continue
        # none now: the latest deadline that had several, as it read 3 h before
        dues = sorted({str(i.get("due_at")) for i in items if i.get("due_at")}, reverse=True)
        for due in dues:
            at = push._at(due)
            then = at - timedelta(hours=3)
            got = [x for x in push.acts(items, roles, then) if x["type"] == typ and x["at"] == at]
            if len(got) > 1:
                show(label, push.render(got, then), f"as on {then:%a %d %b %H:%M}")
                break
        else:
            say(f"-. {label}: no deadline with more than one in your data")
    return 0


def _real_facts(secrets) -> Path:
    """The real data in the shape Ask Ping's rules read (as the function builds it), written to the runner's temp
    folder only (never committed, never printed): roles, items, notices with their text, the files' checks (a JD's
    text; a student list's never), placement mail, form pages."""
    import json as _json
    import tempfile
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    runs = sorted(store.select("runs", REAL), key=lambda r: str(r.get("started_at") or ""), reverse=True)
    roles = []
    for r in store.select("roles", REAL):
        rel = r.get("relevance") or {}
        roles.append({**{k: r.get(k) for k in ("id", "company", "designation", "job_description", "jd_text", "jd_source", "jd_url",
                                               "jd_note", "jd_summary", "applied", "eligible", "ctc", "currency", "cgpa_cutoff", "bond", "allowed")},
                      "deadline": r.get("effective_deadline") or r.get("apply_end"), "pay": (r.get("more_details") or {}).get("fields") or {},
                      "cv": rel.get("best_cv") if rel.get("relevant") else None, "for_you": rel.get("relevant"),
                      "jd_location": (r.get("jd_summary") or {}).get("location")})
    items = []
    for i in store.select("items", REAL):
        if i.get("dismissed"):
            continue
        d = i.get("details") or {}
        items.append({**{k: i.get(k) for k in ("id", "company", "category", "title", "due_at", "event_at", "level", "pdf_status", "role_ids",
                                               "notice_id", "first_seen", "sort_at", "done")},
                      "hidden_because": d.get("hidden_because"), "subject": d.get("subject"), "venue": d.get("venue"), "kind": d.get("kind"),
                      "notice_time": d.get("notice_time"), "pdf": d.get("pdf"), "via": d.get("via"), "mail": d.get("mail"), "todo": d.get("todo")})
    notices = [{k: n.get(k) for k in ("id", "notice_id", "year", "company", "subject", "text", "notice_time", "has_attachment")}
               for n in store.select("notices", REAL)]
    checks = [{"notice_id": c["notice_id"], "status": c.get("status"), "context": c.get("context") if c.get("status") == "jd" else None}
              for c in store.select("pdf_checks", REAL)]
    mails = []
    for m in store.select("emails", REAL):
        p = m.get("pdf") or {}
        mails.append({**{k: m.get(k) for k in ("id", "received_at", "sender", "subject", "snippet", "company", "main_link", "due_at")},
                      "pdf": {"status": p.get("status"), "file": p.get("file"), "context": p.get("context") if p.get("status") == "jd" else None} if p else None})
    forms = [{k: f.get(k) for k in ("key", "company", "companies", "title", "description", "link", "final_url", "due_at", "purpose", "closed")}
             for f in store.select("forms", REAL)]
    prof = (store.select("profile", {"id": "eq.1"}) or [{}])[0]
    now = datetime.now(timezone.utc).isoformat()
    last = runs[0].get("finished_at") or runs[0].get("started_at") if runs else None
    facts = {"now": now, "lastChecked": last, "profile": {k: prof.get(k) for k in ("cgpa", "department", "degree", "active_backlogs")},
             "prefs": {"listOthers": prof.get("list_other_roles") is not False}, "roles": roles, "items": items, "notices": notices,
             "pdf_checks": checks, "emails": mails, "forms": forms}
    out = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "ping_real_facts.json"
    out.write_text(_json.dumps(facts, default=str))
    return out


def _old_rules(rev: str = "b1f809e") -> str | None:
    """The rules as they were at rev (for the before numbers), in a temp folder."""
    import subprocess
    import tempfile
    d = Path(tempfile.mkdtemp())
    for f in ("answer_rules.js", "help.js"):
        r = subprocess.run(["git", "show", f"{rev}:supabase/functions/_shared/{f}"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            return None
        (d / f).write_text(r.stdout)
    return str(d / "answer_rules.js")


def ask_evals_real(secrets) -> int:
    """Reads only: the self-generated Ask Ping evals (evals/generated/generate.js) on the real data, with today's rules
    and with the rules before this round (b1f809e): questions, % correct, false absences, repeats, the failures."""
    import subprocess
    facts = _real_facts(secrets)
    gen = str(ROOT / "evals" / "generated" / "generate.js")
    old = _old_rules()
    if old:
        say("==== before (rules at b1f809e)")
        subprocess.run(["node", gen, str(facts), "--show=0"], cwd=ROOT, env={**os.environ, "PING_RULES": old})
    say("==== now")
    return subprocess.run(["node", gen, str(facts), "--show=40"], cwd=ROOT).returncode


def chat_audit(secrets) -> int:
    """Reads only: every absence-style answer the live bot gave in the owner's chat history, asked again now with the
    same earlier questions against today's data and rules, and checked against the data itself; lists the wrong ones."""
    import json as _json
    import subprocess
    facts = _real_facts(secrets)
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    chat = sorted(store.select("chat_messages", REAL), key=lambda m: str(m.get("created_at")))
    path = facts.parent / "ping_real_chat.json"
    path.write_text(_json.dumps([{k: m.get(k) for k in ("role", "text", "created_at")} for m in chat], default=str))
    return subprocess.run(["node", str(ROOT / "evals" / "generated" / "audit_chat.js"), str(facts), str(path)], cwd=ROOT).returncode


def posted_report(secrets, hours: float = 6) -> int:
    """Reads only: every message that became visible in the chat in the last `hours` (first_seen), with its key
    (company, task, deadline, form link), why it may be a repeat, and the push notifications queued or sent."""
    from collections import Counter
    from . import posting
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    since = (datetime.now(timezone.utc) - timedelta(hours=float(os.environ.get("PING_HOURS") or hours))).isoformat()
    items = store.select("items", REAL)
    now = datetime.now(timezone.utc)
    shown = sorted([i for i in items if i.get("level") != "hidden" and not i.get("dismissed") and str(i.get("first_seen") or "") >= since],
                   key=lambda i: str(i.get("first_seen")))
    keys = Counter(posting.post_key(i) for i in items if i.get("level") != "hidden" and not i.get("dismissed"))
    say(f"visible messages first seen since {since[:16]} UTC: {len(shown)}")
    for i in shown:
        k = posting.post_key(i)
        flags = [f"same key x{keys[k]}" if keys[k] > 1 else "", "past due when posted" if posting.is_past(i, datetime.fromisoformat(str(i["first_seen"]).replace("Z", "+00:00"))) else ""]
        say(f"  {str(i['first_seen'])[:19]} | {i['id'][:60]:60} | {str(i.get('company'))[:22]:22} | {i.get('category')} | due {str(i.get('due_at') or i.get('event_at') or '')[:16]} | {str(i.get('title'))[:70]!r} {' '.join(f for f in flags if f)}")
    try:
        q = [x for x in store.select("push_queue", {}) if str(x.get("created_at") or x.get("send_at") or "") >= since]
    except Exception as e:
        q = []
        say(f"push queue not readable: {type(e).__name__}")
    say(f"push queue rows since then: {len(q)} (pushes a run sends directly are in its log as 'push: ...')")
    for x in q[:20]:
        say(f"  {str(x.get('send_at') or x.get('created_at'))[:16]} | {str(x.get('title'))[:60]!r} | sent={x.get('sent_at') or x.get('sent')}")
    # what the chat draws (dashboard/app.js inChat): visible items, and past ones Ping posted while they still mattered,
    # at the notice's / mail's own time. Groups of 2+ with the same key are repeats in the thread.
    groups: dict = {}
    for i in items:
        if in_chat(i):
            groups.setdefault(posting.post_key(i), []).append(i)
    reps = {k: v for k, v in groups.items() if len(v) > 1}
    say(f"messages in the chat: {sum(len(v) for v in groups.values())}; keys shown more than once: {len(reps)}")
    for k, v in sorted(reps.items(), key=lambda kv: -len(kv[1])):
        say(f"  x{len(v)} {k[:110]}")
        for i in sorted(v, key=lambda i: str(_chat_time(i))):
            d = i.get("details") or {}
            say(f"     shown at {str(_chat_time(i))[:16]} | first seen {str(i.get('first_seen'))[:16]} | {i['id'][:70]} | {i.get('level')} {str(d.get('hidden_because') or '')[:40]!r} | {str(i.get('title'))[:60]!r}")
    co = os.environ.get("PING_COMPANY")
    if co:
        say(f"every item for {co!r}:")
        for i in sorted([i for i in items if co.lower() in str(i.get("company") or "").lower() or co.lower() in str(i.get("title") or "").lower()], key=lambda i: str(_chat_time(i))):
            d = i.get("details") or {}
            say(f"  in chat={in_chat(i)!s:5} | shown at {str(_chat_time(i))[:16]} | first seen {str(i.get('first_seen'))[:16]} | {i['id'][:70]} | {i.get('category')} | {i.get('level')} {str(d.get('hidden_because') or '')[:40]!r} | due {str(i.get('due_at'))[:16]} | dismissed={i.get('dismissed')} | {str(i.get('title'))[:70]!r}")
    return 0


def _chat_time(i):
    from .posting import chat_time
    return chat_time(i)


def in_chat(i) -> bool:
    from .posting import in_chat as f
    return f(i)
    d = i.get("details") or {}
    why = str(d.get("hidden_because") or "")
    if not PAST_WHY.search(why):
        return False
    def t(v):
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00")) if v else None
        except ValueError:
            return None
    seen = t(_chat_time(i))
    if not seen:
        return True
    if "deadline gone" in why and t(i.get("due_at")):
        return seen < t(i.get("due_at"))
    if "already happened" in why and t(i.get("event_at")):
        return seen < t(i.get("event_at")) + timedelta(hours=12)
    if "older than 3 days" in why and t(i.get("sort_at")):
        return seen < t(i.get("sort_at")) + timedelta(days=3)
    if "reminder" in why and t(i.get("due_at")):
        return seen < t(i.get("due_at")) - timedelta(days=1)
    return True


def restore_items(secrets) -> int:
    """Writes to Ping's own feed only: brings the given messages back into the chat (dismissed = false). The ids come
    in the company input, comma-separated, and must exist (owner or demo)."""
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    ids = [x.strip() for x in (os.environ.get("PING_COMPANY") or "").split(",") if x.strip()]
    found = [i["id"] for i in store.select("items", {"id": "in.(" + ",".join(f'"{x}"' for x in ids) + ")"}, columns="id")] if ids else []
    say(f"restoring {len(found)} of {len(ids)} message(s): {', '.join(found)}")
    if found:
        store._req("PATCH", "items", params={"id": "in.(" + ",".join(f'"{x}"' for x in found) + ")"}, json={"dismissed": False},
                   headers={"Prefer": "return=minimal"})
    return 0


def posting_cleanup(secrets, hours: float = 4) -> int:
    """Writes to Ping's own feed only (never the ERP). Takes out of the chat (dismissed: kept in the data, gone from
    the thread), owner and demo: repeats of a message (same company, task, deadline, link and words: the first kept;
    none when a copy was folded into a digest or judged a duplicate / another company's form), and what a re-scan or
    re-read in the last `hours` put into the history (a message about something more than a day old, or one already
    past when Ping found it)."""
    from . import posting
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    since = datetime.now(timezone.utc) - timedelta(hours=float(os.environ.get("PING_HOURS") or hours))
    dt = posting._dt
    for label, query in (("owner", REAL), ("demo", {"is_sample": "is.true"})):
        items = store.select("items", query)
        before = {i["id"] for i in items if posting.in_chat(i)}
        copies = [dict(i, details=dict(i.get("details") or {})) for i in items]
        posting.collapse_repeats(copies)
        drop = {i["id"]: (i["details"].get("hidden_because") or "") for i in copies if i["id"] in before and not posting.in_chat(i)}
        for i in items:
            fs, at = dt(i.get("first_seen")), dt(posting.chat_time(i))
            if i["id"] in before and i["id"] not in drop and fs and fs >= since and i.get("category") not in ("digest", "listing"):
                if at and at < fs - posting.BACKFILL:
                    drop[i["id"]] = "an older message a re-scan or re-read found again"
                elif i.get("level") == "hidden" or posting.is_past(i, fs):
                    drop[i["id"]] = "already past when Ping found it"
        say(f"{label}: {len(before)} messages in the chat; {len(drop)} to take out")
        byid = {i["id"]: i for i in items}
        for k, why in sorted(drop.items(), key=lambda kv: str(posting.chat_time(byid[kv[0]]))):
            i = byid[k]
            say(f"  shown at {str(posting.chat_time(i))[:16]} | {k[:60]} | {str(i.get('title'))[:60]!r} | {why[:60]}")
        ids = sorted(drop)
        for n in range(0, len(ids), 40):
            chunk = ids[n:n + 40]
            store._req("PATCH", "items", params={"id": "in.(" + ",".join(f'"{x}"' for x in chunk) + ")"}, json={"dismissed": True},
                       headers={"Prefer": "return=minimal"})
        if ids:
            left = [i for i in store.select("items", query) if posting.in_chat(i)]
            say(f"{label}: {len(left)} messages in the chat now")
    return 0


def jd_sources(secrets, company: str | None = None) -> int:
    """Reads only: everything Ping has stored about one company that could hold a JD (default RISA Labs): the role
    page's JD, the company's notices (does the text mention a JD or a file?), each notice file's check (a JD kept
    whole, a list, unreadable), placement mail (subject, sender's name, the attachment's kind), linked form pages.
    Prints where each came from; never the text of a student list."""
    import re as _re
    want = (company or os.environ.get("PING_COMPANY") or "risa").strip().lower()
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    hit = lambda s: want in str(s or "").lower()  # noqa: E731
    JDW = _re.compile(r"job description|\bjds?\b|role description|attached|attachment|pdf", _re.I)
    roles = [r for r in store.select("roles", REAL) if hit(r.get("company"))]
    say(f"roles ({len(roles)}):")
    for r in roles:
        say(f"  {r.get('designation')!s:50} jd_source={r.get('jd_source')} jd_text={len(r.get('jd_text') or '')} chars "
            f"note={r.get('jd_note')!r} ERP field={str(r.get('job_description') or '')[:50]!r} form_doc={r.get('has_form_doc')} "
            f"company_doc={r.get('has_company_doc')}")
    notices = sorted([n for n in store.select("notices", REAL) if hit(n.get("company")) or hit(n.get("subject")) or hit(n.get("text"))],
                     key=lambda n: str(n.get("notice_time")))
    checks = {c["notice_id"]: c for c in store.select("pdf_checks", REAL)}
    say(f"notices ({len(notices)}):")
    for n in notices:
        c = checks.get(n["id"]) or {}
        jdw = sorted({m.group(0).lower() for m in JDW.finditer(n.get("text") or "")})
        say(f"  {n['notice_id']} {str(n.get('notice_time'))[:16]} {n.get('company')!s:28} {str(n.get('subject'))[:50]!r} "
            f"kind={(n.get('analysis') or {}).get('kind')} file={n.get('has_attachment')} text mentions={jdw} "
            f"| file check: {c.get('status') or 'not checked'} {c.get('format') or ''} {c.get('pages') or ''}p "
            f"roll-like={c.get('roll_like_count')} {c.get('error') or ''}")
    mails = sorted([m for m in store.select("emails", REAL) if hit(m.get("company")) or hit(m.get("subject")) or hit(m.get("snippet"))],
                   key=lambda m: str(m.get("received_at")))
    say(f"placement mail ({len(mails)}):")
    for m in mails:
        p = m.get("pdf") or {}
        who = _re.sub(r"\s*<[^>]*>", "", m.get("sender") or "")
        say(f"  {str(m.get('received_at'))[:16]} from {who[:30]!r} {str(m.get('subject'))[:60]!r} kind={m.get('kind')} "
            f"attachment={p.get('file')!r} {p.get('status') or ''} rules_version={m.get('rules_version')} "
            f"mentions JD={bool(JDW.search((m.get('subject') or '') + ' ' + (m.get('snippet') or '')))}")
    forms = [f for f in store.select("forms", REAL) if any(hit(x) for x in [f.get("company"), *(f.get("companies") or [])])]
    say(f"form pages ({len(forms)}):")
    for f in forms:
        say(f"  {f.get('key')} {str(f.get('title'))[:60]!r} purpose={f.get('purpose')} due={f.get('due_at')} "
            f"sources={[s.get('type') + ':' + str(s.get('id')) for s in (f.get('sources') or [])]}")
    return 0


def public_ci(secrets) -> int:
    """Reads only: the public copy's latest workflow runs (Tests, Dashboard, Ping) and whether it's non-empty, with
    PUBLIC_REPO_TOKEN. Prints the repository as 'owner / name' (the URL itself is a masked secret)."""
    url, token = os.environ.get("PUBLIC_REPO_URL", "").strip(), os.environ.get("PUBLIC_REPO_TOKEN", "").strip()
    m = re.match(r"https://github\.com/([^/]+)/([^/.]+)", url)
    if not (m and token):
        say("needs PUBLIC_REPO_URL and PUBLIC_REPO_TOKEN")
        return 2
    api = f"https://api.github.com/repos/{m.group(1)}/{m.group(2)}"
    hdr = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    repo = requests.get(api, headers=hdr, timeout=30).json()
    say(f"{m.group(1)} / {m.group(2)}: private={repo.get('private')}, template={repo.get('is_template')}, size={repo.get('size')} KB, "
        f"default branch {repo.get('default_branch')}")
    head = requests.get(f"{api}/commits?per_page=1", headers=hdr, timeout=30).json()
    sha = head[0]["sha"] if isinstance(head, list) and head else ""
    say(f"head {sha[:7]}: {head[0]['commit']['message'].splitlines()[0][:80] if sha else '(empty)'}")
    runs = requests.get(f"{api}/actions/runs?per_page=20", headers=hdr, timeout=30).json().get("workflow_runs") or []
    for r in runs:
        say(f"  {r['name']:10} {r['event']:9} {r['status']:10} {r.get('conclusion')!s:9} {r['head_sha'][:7]} {r['created_at']}")
    bad = [r for r in runs if r["head_sha"] == sha and r["status"] == "completed" and r.get("conclusion") not in ("success", "skipped")]
    return 1 if bad else 0


def notice_forms(secrets) -> int:
    """Reads only. For notice(s) NOTICE_IDS (default 1815): every form link in the text (in order), the companies
    named next to it (the text between the previous link and this one, and on the link's own line), the form page's
    title, mails that carry the same link (subject's companies), the attachment, and the stored Forms row(s) that
    hold the link now. Prints company names and link ids only, never the notice text."""
    from .forms import key_of
    from .notices import URL_RE, FORM_RE
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    ids = [x.strip() for x in os.environ.get("NOTICE_IDS", "1815").split(",") if x.strip()]
    pages = {p["key"]: p for p in store.select("form_pages")}
    rows = store.select("forms", {"is_sample": "is.false"})
    mails = store.select("emails", REAL) if True else []
    for nid in ids:
        ns = [n for n in store.select("notices", {"notice_id": f"eq.{nid}"}) if not n.get("is_sample")]
        if not ns:
            say(f"notice {nid}: not stored")
            continue
        n = ns[0]
        text = re.sub(r"[\u2060\u200b\ufeff]", "", n.get("text") or n.get("preview") or "")
        a = n.get("analysis") or {}
        targets = [t.get("company") or t.get("name") for t in a.get("targets") or []]
        say(f"\nnotice {nid} ({n.get('notice_time')}), subject {n.get('subject')!r}, attachment: {'yes' if n.get('has_attachment') else 'no'}")
        say(f"  companies the notice lists ({len(targets)}): {', '.join(targets)}")
        links = list(dict.fromkeys(u.rstrip(".,;") for u in URL_RE.findall(text)))
        forms = [l for l in links if FORM_RE.search(l)]
        say(f"  links in the text: {len(links)}, of them form links: {len(forms)}")
        low, prev = text.lower(), 0
        named_anywhere = set()
        for i, f in enumerate(forms):
            pos = low.find(f.lower())
            line_start = low.rfind("\n", 0, pos) + 1
            seg = text[prev:pos]
            line = text[line_start:pos]
            near = [t for t in targets if t and (t.lower() in seg.lower() or t.split()[0].lower() in seg.lower().split())]
            on_line = [t for t in targets if t and (t.lower() in line.lower() or t.split()[0].lower() in line.lower().split())]
            k = key_of(f) or ""
            final = (pages.get(k) or {}).get("final_url")
            fk = key_of(final) if final else k
            title = (pages.get(fk) or pages.get(k) or {}).get("title")
            in_mails = [m for m in mails if f in json.dumps(m.get("links") or [])]
            held = [r for r in rows if fk in (r.get("merged_keys") or []) or r.get("key") == fk or k in (r.get("merged_keys") or [])]
            named_anywhere |= set(on_line or near)
            say(f"  link {i + 1}: {k[:48]}" + (f" -> {fk[:48]}" if fk != k else ""))
            say(f"     on its line: {', '.join(on_line) or '-'} | since the previous link: {', '.join(near) or '-'}")
            say(f"     form page title: {title or '(not read)'}")
            say(f"     mails with this link: {len(in_mails)}" + (f" ({'; '.join((m.get('company') or '?') for m in in_mails[:4])})" if in_mails else ""))
            say(f"     stored row now: " + ("; ".join(f"{r['key'][:30]} with {len(r.get('companies') or [])} companies" for r in held) or "none"))
            prev = pos + len(f)
        missing = [t for t in targets if t and t not in named_anywhere]
        say(f"  companies named next to no link: {', '.join(missing) or 'none'}")
        # the feed items this notice made, per company: what the Forms list is built from
        its = [i for i in store.select("items", {"notice_id": f"eq.{nid}"}) if not i.get("is_sample")]
        say(f"  items from this notice: {len(its)}")
        for i in sorted(its, key=lambda i: (i.get("company") or "", i["id"])):
            d = i.get("details") or {}
            td = d.get("todo") or {}
            say(f"     {i['id'][-22:]} {i.get('company')!s:28.28} {i.get('category'):8} {i.get('level'):7} "
                f"link={key_of(td['link'])[:24] if td.get('link') else '-':24} form={((d.get('form') or {}).get('key') or '-')[:24]:24} "
                f"hidden: {d.get('hidden_because') or '-'}")
    # every notice of the last 14 days that names several companies and has a form link: what the Forms list holds now
    from datetime import timedelta, timezone
    from .forms import NO_LINK
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    say("\nmulti-company notices with forms, last 14 days (links found -> rows -> companies with no link):")
    for n in sorted(store.select("notices", {**REAL, "notice_time": f"gte.{since}"}), key=lambda n: n.get("notice_time") or ""):
        a = n.get("analysis") or {}
        listed = [t.get("company") for t in a.get("targets") or [] if t.get("company")]
        flinks = [t for t in a.get("todos") or [] if t.get("action") == "fill_form"]
        if len(listed) < 2 or not flinks:
            continue
        mine = [r for r in rows if any(str(x.get("id")) == str(n["notice_id"]) for x in r.get("sources") or [] if x.get("type") == "notice")]
        nolink = [", ".join(r.get("companies") or []) for r in mine if r.get("title") == NO_LINK]
        multi = [r for r in mine if len(r.get("companies") or []) > 1]
        say(f"  notice {n['notice_id']} ({(n.get('notice_time') or '')[:10]}): {len(flinks)} form link(s), {len(listed)} listed companies "
            f"-> {len(mine)} row(s){f', {len(multi)} with several companies' if multi else ''}; no link: {', '.join(nolink) or 'none'}")
        for r in multi:
            say(f"     several companies on one row: {', '.join(r.get('companies') or [])[:120]} | {(r.get('title') or '')[:40]}")
    every = store.select("forms", {})
    for r in every:
        if r["key"] == "notice:1602":
            say(f"row notice:1602: companies {r.get('companies')}, title {r.get('title')!r}, due {r.get('due_at')}, "
                f"link {key_of(r.get('final_url') or r.get('link') or '') or '-'}, merged_keys {[k[:30] for k in r.get('merged_keys') or []]}, "
                f"sources {[(x.get('type'), x.get('id')) for x in r.get('sources') or []]}")
    for name in ("Auro", "Ather", "TATA AIG"):
        hits = [r for r in every if any(name.lower() in (c or "").lower() for c in r.get("companies") or [])]
        say(f"all stored rows naming {name}: " + ("; ".join(f"{r['key'][:34]} sample={r.get('is_sample')} companies={len(r.get('companies') or [])}"
                                                          for r in hits) or "none"))
    for name in ("RISA", "Diageo", "Piramal", "Nomura"):
        hits = [r for r in rows if any(name.lower() in (c or "").lower() for c in r.get("companies") or [])]
        say(f"{name}: " + ("; ".join(f"{', '.join(r.get('companies') or [])[:60]} | {(r.get('title') or '')[:50]} | "
                                    f"{'own link' if (r.get('final_url') or r.get('link')) else 'no link'}" for r in hits) or "no row"))
    return 0


def live_page(secrets) -> int:
    """Live updates on the published dashboard (setup/live_page_test.py): a new message appears without a reload,
    the scroll rules, the demo's Check now, catching up without the socket, and the row rules on the Realtime
    channel, including an owner message (posted with the service key, deleted right after) never reaching a demo
    session."""
    import subprocess
    return subprocess.run([sys.executable, str(ROOT / "setup" / "live_page_test.py")]).returncode


def auth_config(secrets) -> int:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    if not token or not owner:
        say("needs SUPABASE_ACCESS_TOKEN and GITHUB_REPOSITORY_OWNER (run it on GitHub: Actions > Admin)")
        return 2
    live = f"https://{owner.lower()}.github.io/ping-dashboard/"
    url = f"{API}/v1/projects/{sa.project_ref(secrets.supabase_url)}/config/auth"
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    cur = requests.get(url, headers=hdr, timeout=30)
    if cur.status_code >= 300:
        say(f"reading the Auth settings failed: HTTP {cur.status_code} {cur.text[:200]}")
        return 1
    cur = cur.json()
    before_site, before_list = cur.get("site_url") or "", [u for u in (cur.get("uri_allow_list") or "").split(",") if u]
    keep = list(before_list)  # nothing already there is removed
    if ("localhost" in before_site or "127.0.0.1" in before_site) and before_site != live:
        keep.append(before_site)  # the old local Site URL stays allowed for development
    if not any("localhost" in u or "127.0.0.1" in u for u in keep):
        keep += ["http://localhost:8000/**", "http://127.0.0.1:8000/**"]  # python -m http.server, for development
    wanted = [live, live + "**"] + keep
    new_list = list(dict.fromkeys(wanted))
    say(f"before: site_url = {before_site or '(empty)'}; redirect allow-list = {before_list or '(empty)'}")
    say(f"before: anonymous sign-ins {'on' if cur.get('external_anonymous_users_enabled') else 'off'}, "
        f"new sign-ups {'off' if cur.get('disable_signup') else 'on'}, "
        f"email confirmation {'off' if cur.get('mailer_autoconfirm') else 'required'}")
    # An anonymous sign-in is a sign-up to Supabase, so sign-ups must be allowed for the demo. That's safe for the
    # data: the owner rules only let emails in allowed_users read anything, the demo rules only anonymous
    # sessions, and email sign-ups must confirm their address first (no automatic confirmation).
    say("before: sessions: " + ", ".join(f"{k} = {cur.get(k)!r}" for k in SESSION_FIELDS))
    r = requests.patch(url, headers=hdr, timeout=30, json={"site_url": live, "uri_allow_list": ",".join(new_list),
                                                           "external_anonymous_users_enabled": True,
                                                           "disable_signup": False, "mailer_autoconfirm": False})
    if r.status_code >= 300:
        say(f"updating the Auth settings failed: HTTP {r.status_code} {r.text[:200]}")
        return 1
    # Staying signed in for a whole placement season: a session never ends by time or by inactivity (0 = no limit),
    # only by signing out on that device; access tokens last 1 h and are refreshed by the page; refresh tokens are
    # single-use and rotate, a used one accepted again only within 10 s (a retry), so a stolen old one is useless.
    s = requests.patch(url, headers=hdr, timeout=30, json=SESSION_SETTINGS)
    if s.status_code >= 300:
        # time-box and inactivity limits are a paid-plan setting; on the free plan they're always "no limit"
        say(f"session settings: HTTP {s.status_code} {s.text[:160]}; trying without the paid-plan fields")
        s = requests.patch(url, headers=hdr, timeout=30, json={k: v for k, v in SESSION_SETTINGS.items()
                                                                if not k.startswith("sessions_")})
        if s.status_code >= 300:
            say(f"session settings not changed: HTTP {s.status_code} {s.text[:160]}")
    after = requests.get(url, headers=hdr, timeout=30).json()
    say(f"after:  site_url = {after.get('site_url')}; redirect allow-list = {(after.get('uri_allow_list') or '').split(',')}")
    say("after:  sessions: " + ", ".join(f"{k} = {after.get(k)!r}" for k in SESSION_FIELDS))
    say(f"after:  anonymous sign-ins {'on' if after.get('external_anonymous_users_enabled') else 'OFF'}, "
        f"new sign-ups {'off' if after.get('disable_signup') else 'on'}, "
        f"email confirmation {'off' if after.get('mailer_autoconfirm') else 'required'}")
    # the reviewer login the one-click demo replaces
    base = secrets.supabase_url.rstrip("/") + "/auth/v1/admin/users"
    admin_hdr = {"apikey": secrets.supabase_key, "Authorization": f"Bearer {secrets.supabase_key}"}
    users = requests.get(base, headers=admin_hdr, params={"per_page": 1000}, timeout=30).json().get("users", [])
    old = [u for u in users if (u.get("email") or "").lower() == "reviewer@ping-demo.example"]
    for u in old:
        d = requests.delete(f"{base}/{u['id']}", headers=admin_hdr, timeout=30)
        say(f"old reviewer login deleted: HTTP {d.status_code}")
    if not old:
        say("old reviewer login: not there")
    ok = after.get("site_url") == live and after.get("external_anonymous_users_enabled") and not after.get("disable_signup")
    return 0 if ok and not after.get("mailer_autoconfirm") else 1


SESSION_SETTINGS = {"jwt_exp": 3600, "refresh_token_rotation_enabled": True, "security_refresh_token_reuse_interval": 10,
                    "sessions_timebox": 0, "sessions_inactivity_timeout": 0, "sessions_single_per_user": False}
SESSION_FIELDS = ("jwt_exp", "sessions_timebox", "sessions_inactivity_timeout", "sessions_single_per_user",
                  "refresh_token_rotation_enabled", "security_refresh_token_reuse_interval")


def auth_sessions(secrets) -> int:
    """Read-only: how long a sign-in lasts (the Auth session settings) and what happened to the owner's sessions in
    the last 7 days (Supabase's auth log: sign-ins, token refreshes, refused or reused refresh tokens, sign-outs).
    Counts and times only; no token, and the owner's email shown as "owner"."""
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        say("needs SUPABASE_ACCESS_TOKEN")
        return 2
    ref = sa.project_ref(secrets.supabase_url)
    cur = requests.get(f"{API}/v1/projects/{ref}/config/auth", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if cur.status_code < 300:
        c = cur.json()
        say("Auth session settings: " + ", ".join(f"{k} = {c.get(k)!r}" for k in SESSION_FIELDS))
    else:
        say(f"reading the Auth settings failed: HTTP {cur.status_code}")
    owner = (os.environ.get("MAIL_ADDRESS") or "").strip().lower()
    rows = []
    for col in ("source", "source_name"):
        rows = _logs(ref, token, f"""
            SELECT timestamp, event_message FROM logs
            WHERE {col} = 'auth_logs'
              AND (event_message LIKE '%/token%' OR event_message LIKE '%logout%' OR event_message LIKE '%refresh%'
                   OR event_message LIKE '%revoked%' OR event_message LIKE '%login%' OR event_message LIKE '%session%')
            ORDER BY timestamp DESC LIMIT 500""", hours=24 * 7)
        if rows or not _logs.last_error:
            break
    if not rows:
        # nothing matched: look at what the auth log holds at all (the last 24 h; the logs API keeps a short window
        # on the free plan), under either source name
        for src in ("auth_logs", "auth"):
            for col in ("source", "source_name"):
                rows = _logs(ref, token, f"SELECT timestamp, event_message FROM logs WHERE {col} = '{src}' "
                                         "ORDER BY timestamp DESC LIMIT 300", hours=24)
                if rows:
                    say(f"(auth events found under {col} = '{src}', last 24 h)")
                    break
            if rows:
                break
    counts: dict[str, int] = {}
    lines = []
    for r in rows:
        try:
            m = json.loads(r.get("event_message") or "{}")
        except ValueError:
            m = {"msg": str(r.get("event_message"))[:120]}
        who_raw = str(m.get("actor_username") or m.get("email") or m.get("auth_event", {}).get("actor_username") or "").lower()
        who = "owner" if owner and who_raw == owner else ("anonymous/other" if who_raw or m.get("actor_id") else "?")
        what = " ".join(str(x) for x in (m.get("action") or m.get("auth_event", {}).get("action") or "", m.get("path") or "",
                                         m.get("grant_type") or "", m.get("status") or "",
                                         (m.get("error") or m.get("msg") or "")[:90]) if x)
        for secret_like in ("refresh_token=", "access_token"):
            what = what.split(secret_like)[0]
        key = f"{who}: {what}"
        counts[key] = counts.get(key, 0) + 1
        if who == "owner" or any(w in what.lower() for w in ("already used", "revoked", "logout", "invalid refresh")):
            lines.append(f"  {_when(r.get('timestamp'))}  {key}")
    say(f"auth log, last 7 days: {len(rows)} matching events")
    for k, n in sorted(counts.items(), key=lambda x: -x[1])[:40]:
        say(f"  {n:5}  {k}")
    say("owner events and every refused / revoked / sign-out event, newest first:")
    for l in lines[:80]:
        say(l)
    return 0


# ------------------------------------------------------------------ profile snapshot / restore (judging)
SNAPSHOT_SQL = """create table if not exists public.profile_snapshots (
  id bigserial primary key, taken_at timestamptz default now(), profile jsonb not null,
  push_subscriptions jsonb not null default '[]', files jsonb not null default '[]');
alter table public.profile_snapshots enable row level security;
revoke all on public.profile_snapshots from anon, authenticated;
grant all on public.profile_snapshots to service_role;
grant usage, select on sequence public.profile_snapshots_id_seq to service_role;"""
SNAP_DIR = "snapshots"


def _rest(secrets, method: str, path: str, **kw):
    h = {"apikey": secrets.supabase_key, "Authorization": f"Bearer {secrets.supabase_key}", **kw.pop("headers", {})}
    return requests.request(method, secrets.supabase_url.rstrip("/") + path, headers=h, timeout=60, **kw)


def _cv_files(secrets, prefix: str = "") -> dict[str, int]:
    """{path: size} of the files directly in the cvs bucket (or under prefix); snapshot copies are left out."""
    r = _rest(secrets, "POST", "/storage/v1/object/list/cvs", json={"prefix": prefix, "limit": 1000})
    out = {}
    for o in r.json() if r.ok else []:
        if o.get("id") is None:                      # a folder (e.g. snapshots/)
            continue
        out[(prefix + "/" if prefix else "") + o["name"]] = int((o.get("metadata") or {}).get("size") or 0)
    return out


def _copy(secrets, src: str, dst: str) -> bool:
    _rest(secrets, "DELETE", "/storage/v1/object/cvs", json={"prefixes": [dst]})
    return _rest(secrets, "POST", "/storage/v1/object/copy", json={"bucketId": "cvs", "sourceKey": src, "destinationKey": dst}).ok


def _profile_digest(p: dict) -> str:
    """What the snapshot holds, without the text itself: the fields a reviewer could change."""
    cvs = p.get("cvs") or []
    return (f"targets {'set' if p.get('targets') else 'empty'} ({len(p.get('targets') or '')} chars), reminder_hours "
            f"{p.get('reminder_hours')}, list_other_roles {p.get('list_other_roles')}, feed_mode {p.get('feed_mode')}, "
            f"check every {p.get('check_every_minutes')} min {p.get('check_from')}-{p.get('check_to')}, email_digests "
            f"{p.get('email_digests')}, CVs {[c.get('label') for c in cvs]} "
            f"({sum(1 for c in cvs if c.get('summary'))} summarised), cv_names {p.get('cv_names')}")


def profile_snapshot(secrets) -> int:
    """The owner's profile row, push subscriptions and CV files, kept server-side (a table only the service key
    can read; the files copied inside the private cvs bucket), then read back and compared."""
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    sa.run_sql(secrets.supabase_url, token, SNAPSHOT_SQL)
    prof = (_rest(secrets, "GET", "/rest/v1/profile", params={"id": "eq.1", "select": "*"}).json() or [None])[0]
    if not prof:
        say("no owner profile row (id 1)")
        return 1
    push = _rest(secrets, "GET", "/rest/v1/push_subscriptions", params={"select": "*"}).json()
    ins = _rest(secrets, "POST", "/rest/v1/profile_snapshots", headers={"Prefer": "return=minimal"},
                json={"profile": prof, "push_subscriptions": push if isinstance(push, list) else []})
    if ins.status_code >= 300:
        say(f"saving the snapshot failed: HTTP {ins.status_code} {ins.text[:200]}")
        return 1
    sid = _rest(secrets, "GET", "/rest/v1/profile_snapshots", params={"select": "id", "order": "id.desc", "limit": "1"}).json()[0]["id"]
    files = _cv_files(secrets)
    copied = []
    for path, size in files.items():
        ok = _copy(secrets, path, f"{SNAP_DIR}/{sid}/{path}")
        copied.append({"path": path, "size": size, "ok": ok})
    _rest(secrets, "PATCH", "/rest/v1/profile_snapshots", params={"id": f"eq.{sid}"}, json={"files": copied})
    # read it back
    back = _rest(secrets, "GET", "/rest/v1/profile_snapshots", params={"id": f"eq.{sid}", "select": "*"}).json()[0]
    same = json.dumps(back["profile"], sort_keys=True, default=str) == json.dumps(prof, sort_keys=True, default=str)
    in_snap = _cv_files(secrets, f"{SNAP_DIR}/{sid}")
    files_ok = all(in_snap.get(f"{SNAP_DIR}/{sid}/{c['path']}") == c["size"] for c in copied)
    say(f"snapshot {sid} taken {back['taken_at']}")
    say(f"profile: {_profile_digest(back['profile'])}")
    say(f"push subscriptions: {len(back['push_subscriptions'])} device(s)")
    listed = ", ".join(f"{c['path']} {c['size']} B" for c in copied) or "none"
    say(f"CV files: {len(copied)} copied ({listed})")
    say(f"read back: profile identical {same}; files present with the same sizes {files_ok}")
    return 0 if same and files_ok else 1


def profile_restore(secrets) -> int:
    """Back to the latest snapshot, exactly: the profile row, the push subscriptions (devices added since are
    removed, so a reviewer's phone stops getting the owner's notifications) and the CV files (copied back; files
    uploaded since are removed)."""
    snaps = _rest(secrets, "GET", "/rest/v1/profile_snapshots", params={"select": "*", "order": "id.desc", "limit": "1"}).json()
    if not isinstance(snaps, list) or not snaps:
        say("no snapshot to restore (run Admin > profile-snapshot first)")
        return 1
    snap = snaps[0]
    sid = snap["id"]
    prof = dict(snap["profile"])
    r = _rest(secrets, "POST", "/rest/v1/profile", params={"on_conflict": "id"},
              headers={"Prefer": "resolution=merge-duplicates,return=minimal"}, json=[prof])
    say(f"profile row: HTTP {r.status_code}")
    keep = {p["endpoint"] for p in snap["push_subscriptions"]}
    now_push = _rest(secrets, "GET", "/rest/v1/push_subscriptions", params={"select": "endpoint"}).json() or []
    gone = [p["endpoint"] for p in now_push if p["endpoint"] not in keep]
    for ep in gone:
        _rest(secrets, "DELETE", "/rest/v1/push_subscriptions", params={"endpoint": f"eq.{ep}"})
    if snap["push_subscriptions"]:
        _rest(secrets, "POST", "/rest/v1/push_subscriptions", params={"on_conflict": "endpoint"},
              headers={"Prefer": "resolution=merge-duplicates,return=minimal"}, json=snap["push_subscriptions"])
    say(f"push subscriptions: {len(keep)} kept, {len(gone)} added since removed")
    want = {c["path"] for c in snap["files"]}
    restored = sum(_copy(secrets, f"{SNAP_DIR}/{sid}/{c['path']}", c["path"]) for c in snap["files"])
    extra = [p for p in _cv_files(secrets) if p not in want]
    if extra:
        _rest(secrets, "DELETE", "/storage/v1/object/cvs", json={"prefixes": extra})
    say(f"CV files: {restored} of {len(want)} copied back; {len(extra)} uploaded since removed")
    now = (_rest(secrets, "GET", "/rest/v1/profile", params={"id": "eq.1", "select": "*"}).json() or [{}])[0]
    diff = [k for k in prof if k != "updated_at" and json.dumps(prof.get(k), sort_keys=True, default=str)
            != json.dumps(now.get(k), sort_keys=True, default=str)]
    sizes = _cv_files(secrets)
    files_ok = all(sizes.get(c["path"]) == c["size"] for c in snap["files"])
    since = _rest(secrets, "GET", "/rest/v1/chat_messages", params={"select": "id", "created_at": f"gt.{snap['taken_at']}"},
                  headers={"Prefer": "count=exact", "Range": "0-0"})
    say(f"profile now: {_profile_digest(now)}")
    say(f"read back: profile matches the snapshot {not diff}{'' if not diff else ' (differs: ' + ', '.join(diff) + ')'}; "
        f"CV files match {files_ok}")
    say(f"chat messages since the snapshot: {since.headers.get('content-range', '?').split('/')[-1]} (kept; not part of the profile)")
    return 0 if not diff and files_ok else 1


def set_dashboard_password(secrets) -> int:
    """The dashboard login's password, from the GitHub secret DASHBOARD_PASSWORD (masked in logs; never printed
    here). Then one sign-in with it to prove it works, and that check's session signed out again (this device only).
    Other sessions are left alone: Admin > end-reviewer-sessions ends the ones started after the latest snapshot."""
    pw = os.environ.get("DASHBOARD_PASSWORD", "")
    email = (os.environ.get("DASHBOARD_EMAIL") or os.environ.get("MAIL_ADDRESS") or "").strip().lower()
    if len(pw) < 12:
        say("set the GitHub secret DASHBOARD_PASSWORD first (at least 12 characters; see docs/SECURITY.md, Judging)")
        return 2
    if not email:
        say("no login email (DASHBOARD_EMAIL or MAIL_ADDRESS)")
        return 2
    users = _rest(secrets, "GET", "/auth/v1/admin/users", params={"per_page": 1000}).json().get("users", [])
    user = next((u for u in users if (u.get("email") or "").lower() == email), None)
    if not user:
        say("the dashboard login isn't in Supabase Auth (run the setup script first)")
        return 1
    r = _rest(secrets, "PUT", f"/auth/v1/admin/users/{user['id']}", json={"password": pw})
    say(f"password updated: HTTP {r.status_code}")
    if r.status_code >= 300:
        return 1
    pub = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    t = requests.post(secrets.supabase_url.rstrip("/") + "/auth/v1/token", params={"grant_type": "password"}, timeout=30,
                      headers={"apikey": pub}, json={"email": email, "password": pw})
    ok = t.status_code == 200
    say(f"a sign-in with the new password: {'works' if ok else f'FAILED (HTTP {t.status_code})'}")
    if ok:
        lo = requests.post(secrets.supabase_url.rstrip("/") + "/auth/v1/logout", params={"scope": "local"}, timeout=30,
                           headers={"apikey": pub, "Authorization": f"Bearer {t.json()['access_token']}"})
        say(f"that check's session signed out again (this session only): HTTP {lo.status_code}")
    return 0 if ok else 1


def end_reviewer_sessions(secrets) -> int:
    """After judging: ends the dashboard login's sessions that started after the latest profile snapshot (the
    reviewers' devices). Sessions from before it (your own phone and laptop) stay signed in."""
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    email = (os.environ.get("MAIL_ADDRESS") or "").strip().lower()
    snaps = _rest(secrets, "GET", "/rest/v1/profile_snapshots", params={"select": "taken_at", "order": "id.desc", "limit": "1"}).json()
    if not isinstance(snaps, list) or not snaps:
        say("no snapshot: run Admin > profile-snapshot before judging (its time decides which sessions are the reviewers')")
        return 1
    since = snaps[0]["taken_at"]
    q = lambda sql: sa.run_sql(secrets.supabase_url, token, sql)  # noqa: E731
    who = "(select id from auth.users where lower(email) = " + "'" + email.replace("'", "''") + "')"
    before = q(f"select count(*) filter (where created_at <= '{since}') as kept, count(*) filter (where created_at > '{since}') as later "
               f"from auth.sessions where user_id = {who}")
    say(f"sessions of the dashboard login: {before[0]['kept'] if before else '?'} from before the snapshot ({since}), "
        f"{before[0]['later'] if before else '?'} started after it")
    q(f"delete from auth.sessions where user_id = {who} and created_at > '{since}'")
    after = q(f"select count(*) as n from auth.sessions where user_id = {who} and created_at > '{since}'")
    say(f"ended the sessions started after the snapshot; left: {after[0]['n'] if after else '?'}")
    return 0


def cleanup_demo(secrets) -> int:
    r = requests.post(secrets.supabase_url.rstrip("/") + "/rest/v1/rpc/cleanup_demo_sessions", timeout=60,
                      headers={"apikey": secrets.supabase_key, "Authorization": f"Bearer {secrets.supabase_key}",
                               "Content-Type": "application/json"}, json={"days": 7})
    if r.status_code >= 300:
        say(f"cleanup failed: HTTP {r.status_code} {r.text[:200]}")
        return 1
    say(f"demo cleanup (older than 7 days): {r.json()}")
    return 0


def demo_clock(secrets) -> int:
    """The one-click demo shows, and asks Ping, as of the snapshot time. It reads that time from the demo profile's
    updated_at; demo builds made before that field was written left an older time there."""
    data = json.loads((ROOT / "dashboard" / "demo-data.json").read_text(encoding="utf-8"))
    when = data["generated_at"]
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    before = (store.select("profile", {"is_sample": "is.true"}, columns="id,updated_at") or [{}])[0]
    if not before.get("id"):
        say("no demo profile in the database (run build-demo)")
        return 1
    r = requests.patch(secrets.supabase_url.rstrip("/") + "/rest/v1/profile", timeout=30,
                       params={"id": f"eq.{before['id']}", "is_sample": "is.true"},
                       headers={"apikey": secrets.supabase_key, "Authorization": f"Bearer {secrets.supabase_key}",
                                "Content-Type": "application/json", "Prefer": "return=representation"},
                       json={"updated_at": when})
    after = r.json()[0]["updated_at"] if r.status_code < 300 and r.json() else f"HTTP {r.status_code} {r.text[:200]}"
    say(f"demo snapshot time: {before.get('updated_at')} -> {after} (demo-data.json generated_at {when})")
    return 0 if r.status_code < 300 else 1


def _function_url(secrets, name: str) -> str:
    return f"{secrets.supabase_url.rstrip('/')}/functions/v1/{name}"


def schedule_setup(secrets) -> int:
    import secrets as pysecrets
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        say("SUPABASE_ACCESS_TOKEN is not set in the repo secrets")
        return 2
    ref = sa.project_ref(secrets.supabase_url)
    shared = pysecrets.token_urlsafe(32)
    r = requests.post(f"{API}/v1/projects/{ref}/secrets", timeout=30, json=[{"name": "PING_CRON_SECRET", "value": shared}],
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    say(f"kick-run's shared secret set as a function secret: HTTP {r.status_code}")
    if r.status_code >= 300:
        return 1
    lit = shared.replace("'", "''")
    sa.run_sql(secrets.supabase_url, token, f"""
        do $$ begin
          if exists (select 1 from vault.secrets where name = 'ping_cron_secret') then
            perform vault.update_secret((select id from vault.secrets where name = 'ping_cron_secret'), '{lit}');
          else
            perform vault.create_secret('{lit}', 'ping_cron_secret', 'shared secret for the kick-run function');
          end if;
        end $$;""")
    say("the same secret stored in the database's Vault as ping_cron_secret")
    sql = (ROOT / "sql" / "schedule.sql").read_text(encoding="utf-8").replace("{{FUNCTION_URL}}", _function_url(secrets, "kick-run")) \
        .replace("{{PUSH_URL}}", _function_url(secrets, "send-push"))
    sa.run_sql(secrets.supabase_url, token, sql)
    jobs = sa.run_sql(secrets.supabase_url, token, "select jobname, schedule, active from cron.job order by jobname")
    for j in jobs:
        say(f"  job {j['jobname']}: '{j['schedule']}' (UTC), active {j['active']}")
    time.sleep(5)  # a new function secret takes a moment to reach the function
    for attempt in range(6):
        c = requests.post(_function_url(secrets, "kick-run"), json={"task": "check"}, timeout=60,
                          headers={"x-ping-cron": shared, "Content-Type": "application/json"})
        if c.status_code == 200:
            break
        time.sleep(10)
    say(f"dry run of kick-run (doesn't start anything): HTTP {c.status_code} {c.text[:300]}")
    return 0 if c.status_code == 200 and len(jobs) >= 3 else 1


def schedule_status(secrets) -> int:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    q = lambda sql: sa.run_sql(secrets.supabase_url, token, sql)  # noqa: E731
    for j in q("select jobid, jobname, schedule, active from cron.job order by jobname"):
        say(f"job {j['jobname']}: '{j['schedule']}' UTC, active {j['active']}")
        n = 24 if j["jobname"] == "ping-hourly" else 3    # the hourly job: the last 12 hours of ticks
        for d in q(f"select status, start_time, return_message from cron.job_run_details where jobid = {int(j['jobid'])} "
                   f"order by start_time desc limit {n}"):
            say(f"   ran {d['start_time']}: {d['status']} {str(d['return_message'])[:80]}")
    # kick-run's replies to the hourly ticks (started a run, or why not); the 5-minute push ticks ({"sent": ...}) left
    # out. pg_net keeps replies for about 6 hours.
    for h in q("select created, status_code, left(content::text, 160) as body from net._http_response "
               "where coalesce(content::text, '') not like '%\"sent\"%' order by created desc limit 16"):
        say(f"kick-run reply {h['created']}: HTTP {h['status_code']} {h['body']}")
    gh = os.environ.get("GITHUB_TOKEN", "")
    r = requests.get(f"https://api.github.com/repos/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/workflows/ping.yml/runs",
                     params={"per_page": 20}, headers={"Authorization": f"Bearer {gh}"}, timeout=30)
    for run in r.json().get("workflow_runs", []) if r.ok else []:
        say(f"Ping run {run['id']}: {run['event']}, started {run['run_started_at']}, {run['status']} {run.get('conclusion') or ''}")
    return 0


def live_providers(secrets) -> int:
    """evals/ask_ping/live_providers.py: 20 open questions as a demo visitor on the live keys, per provider."""
    import subprocess
    return subprocess.run([sys.executable, str(ROOT / "evals" / "ask_ping" / "live_providers.py")]).returncode


def feedback_evals(secrets) -> int:
    """evals/feedback: 12 feedback messages against the deployed function, model on and off (evals keys)."""
    import subprocess
    return subprocess.run([sys.executable, str(ROOT / "evals" / "feedback" / "run_feedback_evals.py")]).returncode


def ask_ping_evals(secrets) -> int:
    import subprocess
    return subprocess.run([sys.executable, str(ROOT / "evals" / "ask_ping" / "run_ask_ping_evals.py")]).returncode


def relevance_evals(secrets) -> int:
    import subprocess
    return subprocess.run([sys.executable, str(ROOT / "evals" / "relevance" / "run_relevance_evals.py")]).returncode


def log_scan(secrets) -> int:
    """Download the logs of the last 20 workflow runs and search them for every secret value this job has, and for
    key-shaped text. Prints counts and run numbers only, never a value."""
    import io as _io
    import zipfile
    token, repo = os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", "")
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    names = ["ERP_USER_ID", "ERP_PASSWORD", "ERP_SECQ_1", "ERP_SECQ_2", "ERP_SECQ_3", "MAIL_ADDRESS", "MAIL_APP_PASSWORD",
             "SUPABASE_SERVICE_KEY", "SUPABASE_ACCESS_TOKEN", "GEMINI_API_KEY_EVALS", "GEMINI_API_KEY_LIVE", "PING_GITHUB_TOKEN",
             "DASHBOARD_DEPLOY_TOKEN", "DASHBOARD_PASSWORD"]
    values = {}
    for n in names:
        v = os.environ.get(n, "").strip()
        if n.startswith("ERP_SECQ") and "::" in v:
            v = v.split("::", 1)[1].strip()          # the answer is the secret part
        if len(v) >= 6:
            values[n] = v
    patterns = {"Supabase secret key": re.compile(r"sb_secret_[A-Za-z0-9_-]{10,}"), "Supabase access token": re.compile(r"sbp_[a-f0-9]{20,}"),
                "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"), "GitHub token": re.compile(r"(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{20,}")}
    runs = requests.get(f"https://api.github.com/repos/{repo}/actions/runs", headers=h, params={"per_page": 20}, timeout=30).json()
    found, scanned = [], 0
    for run in runs.get("workflow_runs", [])[:20]:
        r = requests.get(run["logs_url"], headers=h, timeout=60)
        if r.status_code != 200:
            say(f"  run {run['run_number']} ({run['name']}): logs HTTP {r.status_code}")
            continue
        scanned += 1
        with zipfile.ZipFile(_io.BytesIO(r.content)) as z:
            text = "\n".join(z.read(n).decode("utf-8", "replace") for n in z.namelist())
        for n, v in values.items():
            if v in text:
                found.append(f"run {run['name']} #{run['run_number']}: the value of {n}")
        for what, rx in patterns.items():
            if rx.search(text):
                found.append(f"run {run['name']} #{run['run_number']}: something shaped like a {what}")
    say(f"scanned the logs of {scanned} runs for the values of {len(values)} secrets ({', '.join(sorted(values))}) "
        f"and for key-shaped text")
    say("found: " + ("nothing" if not found else "; ".join(found)))
    return 0 if not found else 1


def rearm_schedule(secrets) -> int:
    """GitHub registers a workflow's cron when it sees the file on the default branch. ping.yml has been there
    since the repo was created and never fired, so the registration was lost; disable + enable re-registers it."""
    token, repo = os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        say("needs GITHUB_TOKEN and GITHUB_REPOSITORY (run this on GitHub: Actions > Admin)")
        return 2
    gh = requests.Session()
    gh.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                       "X-GitHub-Api-Version": "2022-11-28"})
    base = f"https://api.github.com/repos/{repo}"
    info = gh.get(f"{base}", timeout=30).json()
    wf = gh.get(f"{base}/actions/workflows/ping.yml", timeout=30).json()
    say(f"repo: default branch {info.get('default_branch')}, private {info.get('private')}, "
        f"archived {info.get('archived')}, pushed {info.get('pushed_at')}")
    say(f"Ping workflow before: state {wf.get('state')}, updated {wf.get('updated_at')}")
    runs = gh.get(f"{base}/actions/workflows/ping.yml/runs", params={"event": "schedule", "per_page": 1}, timeout=30).json()
    say(f"scheduled runs so far: {runs.get('total_count')}")
    for action in ("disable", "enable"):
        r = gh.put(f"{base}/actions/workflows/ping.yml/{action}", timeout=30)
        say(f"{action}: HTTP {r.status_code}{'' if r.status_code < 300 else ' ' + r.text[:200]}")
        if r.status_code >= 300:
            return 1
        time.sleep(3)
    wf = gh.get(f"{base}/actions/workflows/ping.yml", timeout=30).json()
    say(f"Ping workflow after: state {wf.get('state')}, updated {wf.get('updated_at')}")
    from datetime import timedelta, timezone
    now = datetime.now(timezone.utc)
    nxt = now.replace(minute=41, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(hours=1)
    while not 0 <= nxt.hour <= 19:
        nxt += timedelta(hours=1)
    say("GitHub's API does not report a 'next run' time for schedules; from the cron '41 0-19 * * *' the next "
        f"tick is {nxt:%H:%M} UTC ({nxt.astimezone(IST):%H:%M} IST). GitHub may start it a few minutes late.")
    return 0 if wf.get("state") == "active" else 1


def demo_mails(secrets) -> int:
    """The four made-up sample mails in the demo snapshot (dashboard/demo-data.json) and in the demo rows a one-click
    demo session reads, so View demo shows "via email". Nothing from the real mailbox is used."""
    from .demo_from_real import add_forms, add_sample_mails
    out = ROOT / "dashboard" / "demo-data.json"
    data = add_forms(add_sample_mails(json.loads(out.read_text(encoding="utf-8"))))
    problems = final_check(data)
    if problems:
        say("NOT written, the check found: " + "; ".join(problems))
        return 1
    out.write_text(json.dumps(data, default=str, ensure_ascii=False), encoding="utf-8")
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    counts = load_to_db(store, data)
    live = {t: store.select(t, {"is_sample": "is.true"}) for t in ("items", "emails")}
    mail_items = [i for i in live["items"] if (i.get("details") or {}).get("via") == "email"]
    left = final_check(live)
    say(f"demo rows written: {counts}; sample mails in the database: {len(live['emails'])}, their messages: "
        f"{len(mail_items)} ({sum(1 for i in mail_items if i['level'] != 'hidden')} shown); anonymising check of what a "
        f"demo session reads: " + ("clean" if not left else "NOT CLEAN: " + "; ".join(left)))
    return 0 if not left and len(mail_items) == 4 else 1


def followup_evals(secrets) -> int:
    """The follow-up evals with the model's own reading, EVAL KEYS ONLY (GROQ_API_KEY_EVALS, GEMINI_API_KEY_EVALS):
    your real chat history's follow-ups (evals/followups/real_cases.js), with the turn-on verdict; the 30
    hurried-student conversations on the demo data too when the company input is "hurried". Your data goes to a temp file on the runner (deleted at the end, never committed);
    the log has scores, latency, the fallback rate and short masked questions only."""
    import json as _json
    import subprocess
    import tempfile
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    roles = store.select("roles", REAL)
    for r in roles:
        r["deadline"] = r.get("effective_deadline") or r.get("apply_end")
        r["pay"] = ((r.get("more_details") or {}).get("fields")) or {}
    items = [i for i in store.select("items", REAL) if not i.get("dismissed")]
    for i in items:
        d = i.get("details") or {}
        i.update({"hidden_because": d.get("hidden_because"), "subject": d.get("subject"), "kind": d.get("kind"),
                  "notice_time": d.get("notice_time"), "pdf": d.get("pdf"), "via": d.get("via"), "mail": d.get("mail"), "todo": d.get("todo")})
    checks = [{"notice_id": c["notice_id"], "status": c.get("status"), "context": c.get("context") if c.get("status") == "jd" else None}
              for c in store.select("pdf_checks", {}) if not c.get("is_sample")]
    data = {"now": datetime.now(IST).isoformat(), "lastChecked": datetime.now(IST).isoformat(),
            "profile": (store.select("profile", {"id": "eq.1"}) or [{}])[0], "prefs": {"listOthers": True},
            "roles": roles, "items": items, "notices": store.select("notices", REAL), "pdf_checks": checks,
            "emails": [{k: m.get(k) for k in ("id", "received_at", "sender", "subject", "snippet", "company", "main_link", "due_at", "pdf")}
                       for m in store.select("emails", REAL)],
            "forms": [f for f in store.select("forms", {}) if not f.get("is_sample")]}
    chat = sorted([{"role": m["role"], "text": m["text"], "created_at": m["created_at"], "reply_to": m.get("reply_to"),
                    "reply_quote": m.get("reply_quote")}
                   for m in store.select("chat_messages", {"is_sample": "is.false"}, columns="role,text,created_at,reply_to,reply_quote")],
                  key=lambda m: m["created_at"])
    env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY_LIVE")}
    root = Path(__file__).resolve().parents[1]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        _json.dump({"data": data, "chat": chat}, fh, default=str)
        path = fh.name
    try:
        say(f"== your chat history ({len(chat)} messages) ==")
        subprocess.run(["node", str(root / "evals" / "followups" / "run.js"), "--real", path], env=env, check=False)
    finally:
        os.unlink(path)
    # the 30 made-up conversations: on request only (company input "hurried"); the Groq eval key's free tier allows a
    # few calls a minute, and the real replay above is the one the turn-on rule is decided on
    if (os.environ.get("PING_COMPANY") or "").strip().lower() == "hurried":
        say("== the 30 hurried-student conversations (demo data) ==")
        subprocess.run(["node", str(root / "evals" / "followups" / "run.js")], env=env, check=False)
    return 0


def repost_item(secrets) -> int:
    """Writes to Ping's own feed only: posts one message again for you (the company input: its item id), at the bottom
    of the chat (details.reposted_at, kept across rebuilds) and with a push. For a message you never saw."""
    from . import push
    iid = (os.environ.get("PING_COMPANY") or "").strip()
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    rows = store.select("items", {"id": f"eq.{iid}"})
    if not rows:
        say(f"no message {iid!r}")
        return 1
    it = rows[0]
    now = datetime.now(timezone.utc)
    details = {**(it.get("details") or {}), "reposted_at": now.isoformat()}
    store._req("PATCH", "items", params={"id": f"eq.{iid}"}, json={"details": details, "dismissed": False},
               headers={"Prefer": "return=minimal"})
    roles = {r["id"]: r for r in store.select("roles", REAL)}
    note = push.compose([{**it, "details": details}], roles, now.astimezone(IST))
    say(f"posted again: {it.get('title')!r}")
    if note:
        res = push.send(secrets.supabase_url, secrets.supabase_key, note)
        say(f"push: {note.get('title')!r} -> {({k: res.get(k) for k in ('status', 'sent', 'devices', 'ok', 'why', 'error')})}")
        if res.get("why") == "quiet hours":       # held back, not dropped: sent when your check window opens
            prof = (store.select("profile", {"id": "eq.1", "select": "check_from"}) or [{}])[0]
            at = push.window_start(now, prof.get("check_from"))
            store.upsert("push_queue", [{"id": f"repost:{iid}", "kind": "run", "title": note["title"], "body": note.get("body") or "",
                                         "url": note.get("url"), "tag": note.get("tag") or iid, "send_at": at.isoformat(),
                                         "sent_at": None, "result": None}])
            say(f"push: quiet hours now; queued for {at.strftime('%a %d %b %H:%M')} IST, when your check window opens")
    else:
        say("push: nothing to send (compose returned nothing)")
    return 0


def company_report(secrets) -> int:
    """Reads only: everything Ping holds about one company (the company input): its roles (applied, eligible, for you
    or not and why), its items (level, why hidden, category, task, due, link, when first seen, in the chat or not),
    its mails and its notices. To answer "where did X go?"."""
    from . import posting
    want = (os.environ.get("PING_COMPANY") or "").strip().lower()
    if not want:
        say("give a company in the company input")
        return 1
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    hit = lambda v: want in str(v or "").lower()
    for r in store.select("roles", REAL):
        if hit(r.get("company")):
            rel = r.get("relevance") or {}
            say(f"role {r['id']} | {r.get('designation')} | applied={r.get('applied')} eligible={r.get('eligible')} | "
                f"deadline {str(r.get('effective_deadline'))[:16]} | for you={rel.get('relevant')} ({str(rel.get('why') or rel.get('reason') or '')[:80]})")
    for i in sorted([i for i in store.select("items", REAL) if hit(i.get("company")) or hit(i.get("title"))], key=lambda i: str(i.get("first_seen"))):
        d = i.get("details") or {}
        say(f"item {i['id'][:60]} | {i.get('category')} | level {i.get('level')} {str(d.get('hidden_because') or '')[:50]!r} | dismissed={i.get('dismissed')} | "
            f"in chat={posting.in_chat(i)} | due {str(i.get('due_at'))[:16]} | todo {(d.get('todo') or {}).get('action')} link={'yes' if (d.get('todo') or {}).get('link') else 'no'} | "
            f"via {d.get('via')} | mail note {str((d.get('mail') or {}).get('note') or '')[:40]!r} | first seen {str(i.get('first_seen'))[:16]} | notice_time {str(d.get('notice_time'))[:16]} | {str(i.get('title'))[:90]!r}")
    for m in store.select("emails", REAL):
        if hit(m.get("company")) or hit(m.get("subject")):
            say(f"mail {m['id']} | received {str(m.get('received_at'))[:16]} | kind {m.get('kind')} | due {str(m.get('due_at'))[:16]} | link {'yes' if m.get('main_link') else 'no'} | kept because {m.get('kept_because')} | {str(m.get('subject'))[:80]!r}")
    for n in store.select("notices", REAL):
        if hit(n.get("company")) or hit(n.get("subject")):
            a = n.get("analysis") or {}
            say(f"notice {n.get('notice_id')} | {str(n.get('notice_time'))[:16]} | {str(n.get('subject'))[:60]!r} | kind {a.get('kind')} | todos {[(t.get('action'), str(t.get('due'))[:16], bool(t.get('link'))) for t in a.get('todos') or []]} | attachment={n.get('has_attachment')}")
    runs = sorted(store.select("runs", {"started_at": f"gte.{(datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()}"}), key=lambda r: str(r.get("started_at")))
    say("runs, last 12 h (started, trigger, status, mails read/kept):")
    for r in runs:
        c = r.get("counts") or {}
        say(f"  {str(r.get('started_at'))[:16]} {r.get('trigger')} {r.get('status')} {c.get('mails_scanned', '-')}/{c.get('mails_kept', '-')}")
    return 0


def mail_peek(secrets) -> int:
    """Reads only: the subjects of the ERP mailer's mails that today's filter skipped as not placement (last 10 days,
    subject only), and what the EY recruiter's mails ask (kind, date, link host, subject), to decide whether they're
    still actionable. Nothing stored."""
    from . import mail_source
    from .mailbox import Mailbox
    from .matching import CompanyIndex
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    roles = store.select("roles", REAL)
    index = CompanyIndex(roles)
    prof = (store.select("profile", {"id": "eq.1"}) or [{}])[0]
    now = datetime.now(IST)
    mb = Mailbox(secrets.mail_address, secrets.mail_app_password)
    heads = mb.heads_after(now - timedelta(days=10), limit=5000)
    say("ERP mailer mails skipped as not placement (subject only):")
    for h in heads:
        name, local, domain = mail_source._address(h.sender)
        if domain == "adm.iitkgp.ac.in" and not mail_source.scope(h, index).keep and not mail_source.OTP_RE.search(h.subject or ""):
            say(f"  {h.received:%d %b %H:%M} | subject: {h.subject[:120]!r} | bulk={h.bulk} | placement word in subject: {mail_source.signal(h.subject)!r}")
    say("EY recruiter mails:")
    for h in heads:
        if mail_source._address(h.sender)[2].endswith("ey.com"):
            full = mb.fetch_full(h.uid)
            if not full:
                continue
            row = mail_source.read(full[0], full[1], mail_source.Verdict(True, "company_sender", None), index, prof.get("roll") or "", prof.get("name") or "")
            if not row:
                continue
            host = re.sub(r"^https?://([^/]+).*", r"\1", row.get("main_link") or "") or "-"
            say(f"  {h.received:%d %b %H:%M} | bulk={h.bulk} | kind {row['kind']} | due {row.get('due_at')} | event {row.get('event_at')} | when words {row.get('when_text')!r} | link {host} | links {len(row.get('links') or [])} | subject: {h.subject[:120]!r}")
    mb.close()
    return 0


def mail_audit(secrets) -> int:
    """Reads only (the mailbox opened read-only, nothing stored). A: how mail reading works today, on the last 7 days:
    the mailbox, the filters, mails read and kept, the latest 3 kept, CDC mail skipped and why, and whether every run
    reads mail. Prints dates, senders' domains, kinds and reasons; a subject only for the latest 3, masked where it could name
    other students."""
    import imaplib
    from collections import Counter
    from . import mail_source
    from .mailbox import HEADER_FIELDS, Mailbox, _internal, parse_head
    from .matching import CompanyIndex
    if not (secrets.mail_address and secrets.mail_app_password):
        say("no MAIL_ADDRESS / MAIL_APP_PASSWORD")
        return 1
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    roles = store.select("roles", REAL)
    notices = [n for n in store.select("notices", REAL) if n.get("analysis")]
    prof = (store.select("profile", {"id": "eq.1"}) or [{}])[0]
    stored = store.select("emails", REAL)
    index = CompanyIndex(roles)
    now = datetime.now(IST)
    extra = tuple(x.strip() for x in os.environ.get("PING_PLACEMENT_SENDERS", "").split(",") if x.strip())
    me = secrets.mail_address.lower()
    local, _, dom = me.partition("@")
    mb = Mailbox(secrets.mail_address, secrets.mail_app_password)
    mb.connect()

    def heads_since(days):
        """Headers (and Gmail's thread id) of every mail in the window, in batches; no cap."""
        uids = mb._search_uids(now - timedelta(days=days))
        out = []
        for k in range(0, len(uids), 150):
            part = ",".join(uids[k:k + 150])
            items = "(INTERNALDATE " + ("X-GM-THRID " if mb.gmail else "") + f"BODY.PEEK[HEADER.FIELDS ({HEADER_FIELDS} MESSAGE-ID)])"
            typ, data = mb.imap.uid("FETCH", part, items)
            for d in data or []:
                if not isinstance(d, tuple):
                    continue
                meta = d[0] or b""
                uid = (re.search(rb"UID (\d+)", meta) or [b"", b""])[1]
                h = parse_head(uid.decode() if uid else "", d[1], _internal(meta))
                t = re.search(rb"X-GM-THRID (\d+)", meta)
                h.thread = t.group(1).decode() if t else None
                if h.received >= now - timedelta(days=days):
                    out.append(h)
        return sorted(out, key=lambda h: h.received)

    def mask_subject(sub):
        sub = re.sub(r"\b\d{2}[A-Z]{2}\d{5}\b", "▒", sub or "")
        caps = re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", sub)
        people = [c for c in caps if not index.scan_text(c) and not re.search(
            r"Placement|Career|Development|Centre|Center|Online|Test|Interview|Form|Round|Pre|Talk|Offer|Shortlist|Registration|Process|Campus|Drive|Update|Final|Result", c)]
        return "(subject masked: it may name students)" if len(people) >= 2 or re.search(r"\bstudents?:|\bcandidates?:", sub, re.I) else sub[:90]

    def who(sender):
        name, _, domain = mail_source._address(sender)
        return f"{name[:40] or '(no name)'} <…@{domain}>"

    # ---------------------------------------------------------------- A: today, last 7 days
    say("A. MAIL READING TODAY (read-only)")
    say(f"  mailbox: {local[:2]}…@{dom} (IMAP {mb.host}, opened read-only, folder {mb.folder!r}, Gmail={mb.gmail})")
    say("  placement mail = from the placement office (a cdc / placement / career-development / training-and-placement"
        f" address{', or one of ' + str(len(extra)) + ' addresses in PING_PLACEMENT_SENDERS' if extra else ''}), or naming a"
        " listed company (subject, sender name or domain), or from a test platform, or a placement word in the subject;"
        " never OTP / account / shopping mail, job-board alerts, or bulk mail not from those senders")
    h7 = heads_since(7)
    verdicts = [(h, mail_source.scope(h, index, extra)) for h in h7]
    kept7 = [(h, v) for h, v in verdicts if v.keep]
    say(f"  last 7 days: {len(h7)} mails read (headers only); kept as placement mail: {len(kept7)} "
        f"({dict(Counter(v.because for _, v in kept7))}); not kept: {dict(Counter(v.because for _, v in verdicts if not v.keep))}")
    since7 = (now - timedelta(days=7)).isoformat()
    in_data = [r for r in stored if str(r.get("received_at") or "") >= since7]
    say(f"  in Ping's data from those 7 days: {len(in_data)} mails")
    say("  the latest 3 kept (from Ping's data):")
    for r in sorted(in_data, key=lambda r: str(r["received_at"]))[-3:]:
        say(f"    {str(r['received_at'])[:16]} | {who(r.get('sender') or '')} | {r.get('kind')} | {mask_subject(r.get('subject') or '')}")
    office = lambda h: bool(mail_source.PLACEMENT_SENDER.search(f"{mail_source._address(h.sender)[0]} {mail_source._address(h.sender)[1]} "
                                                               + " ".join(mail_source._domain_words(mail_source._address(h.sender)[2]))))
    cdc = [(h, v) for h, v in verdicts if office(h) or re.search(r"\bcdc\b|placement|erp", h.sender, re.I)]
    skipped = [(h, v) for h, v in cdc if not v.keep]
    ids = {r["id"] for r in stored}
    unsaved = [(h, v) for h, v in cdc if v.keep and mail_source.mail_id(h.received, h.sender, h.subject) not in ids]
    say(f"  CDC / placement-office mail in those 7 days: {len(cdc)}; skipped: {len(skipped)}; kept but not in Ping's data: {len(unsaved)}")
    for h, v in skipped:
        say(f"    skipped {h.received:%d %b %H:%M} | {who(h.sender)} | because: {v.because}")
    for h, v in unsaved[:10]:
        say(f"    not saved {h.received:%d %b %H:%M} | {who(h.sender)} | kept because {v.because} (an OTP in the body, or read before this rule version)")
    runs = sorted(store.select("runs", {"started_at": f"gte.{(now - timedelta(days=1)).isoformat()}"}), key=lambda r: str(r.get("started_at")))
    say(f"  runs in the last 24 h: {len(runs)}; each run's mail step (mails read / kept):")
    for r in runs[-12:]:
        c = r.get("counts") or {}
        say(f"    {str(r.get('started_at'))[:16]} {r.get('trigger') or ''} {r.get('status') or ''}: "
            f"{c.get('mails_scanned', '-')} / {c.get('mails_kept', '-')}" + (" (mail step failed)" if c.get("mail_scan_failed") else ""))
    say(f"  last mail scan saved: {store.get_state('last_mail_scan')}. The mail step runs in every run whose ERP login "
        "worked, before the posting guard, and doesn't look at PING_POSTING: a paused run still reads and saves mail")

    mb.close()
    return 0


def mail_coverage(secrets) -> int:
    """Placement mail of the last 14 days on the real mailbox, read-only, nothing stored: how many placement mails,
    how many the ERP already had (a notice says the same), how many are mail-only; and what the old filter kept.
    Prints counts, dates, kinds and company names only (never a subject, a sender or any text)."""
    from datetime import timedelta
    from collections import Counter
    from . import mail_source
    from .mailbox import Mailbox
    from .matching import CompanyIndex
    if not (secrets.mail_address and secrets.mail_app_password):
        say("no MAIL_ADDRESS / MAIL_APP_PASSWORD")
        return 1
    store = SupabaseStore(secrets.supabase_url, secrets.supabase_key)
    roles = store.select("roles", REAL)
    notices = [n for n in store.select("notices", REAL) if n.get("analysis")]
    prof = (store.select("profile", {"id": "eq.1"}) or [{}])[0]
    index = CompanyIndex(roles)
    now = datetime.now(IST)
    since = now - timedelta(days=14)
    mb = Mailbox(secrets.mail_address, secrets.mail_app_password)
    heads = mb.heads_after(since)
    # the old scan, on the same headers: a listed company's full name in subject/sender, or cdc/placement/erp in the sender
    old_kept = sum(1 for h in heads if "otp" not in h.subject.lower() and (index.scan_text(f"{h.subject} {h.sender}")
                   or any(w in h.sender.lower() for w in ("cdc", "placement", "erp"))))
    extra = tuple(x.strip() for x in os.environ.get("PING_PLACEMENT_SENDERS", "").split(",") if x.strip())
    rows, st = mail_source.scan(mb, since, index, prof.get("roll") or secrets.erp_user_id or "", prof.get("name") or "", extra)
    mb.close()
    twins = {r["id"]: mail_source.erp_twin(r, notices) for r in rows}
    on_erp = [r for r in rows if twins[r["id"]]]
    only = [r for r in rows if not twins[r["id"]]]
    s = st.as_dict()
    say(f"last 14 days ({since:%d %b} to {now:%d %b %H:%M} IST): {s['headers_seen']} mails (headers only)")
    say(f"  placement mails: {len(rows)} (kept because: {dict(s['kept_because'])}); OTP mails skipped: {s['otp_skipped']}")
    say(f"  not placement, never read beyond headers: {s['headers_seen'] - s['bodies_read']} ({dict(s['dropped'])})")
    say(f"  already on the ERP (a notice says the same): {len(on_erp)}")
    say(f"  mail-only: {len(only)}  by kind {dict(Counter(r['kind'] for r in only))}; with a deadline or time "
        f"{sum(1 for r in only if r['due_at'] or r['event_at'])}; with a form/test link {sum(1 for r in only if r['main_link'])}; "
        f"attachments read {s['attachments_read']}, your roll found in {sum(1 for r in rows if (r.get('pdf') or {}).get('status') == 'yes')}")
    say(f"  before (the old scan, same 14 days): {old_kept} mails kept, shown only when about a company you applied to")
    say("  per mail (date · kind · company · on the ERP):")
    for r in sorted(rows, key=lambda r: r["received_at"]):
        say(f"    {r['received_at'][:16].replace('T', ' ')} · {r['kind']} · {r['company'] or '(placement office / no listed company)'}"
            f" · {'yes' if twins[r['id']] else 'mail-only'}")
    return 0


def public_copy(secrets) -> int:
    """The history with every real value replaced, checked, then pushed to the public repository (ping/public_copy.py)."""
    import subprocess
    return subprocess.run([sys.executable, "-m", "ping.public_copy"], cwd=ROOT).returncode


def main() -> int:
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    secrets = load_secrets(require_erp=False, require_store=True)
    tasks = {"apply-sql": apply_sql, "build-demo": build_demo,
             "gemini-check": gemini_check, "chat-diagnose": chat_diagnose, "functions-check": functions_check, "ask-latency": ask_latency, "ask-ping-page": ask_ping_page, "rearm-schedule": rearm_schedule, "ask-ping-evals": ask_ping_evals, "feedback-evals": feedback_evals, "relevance-evals": relevance_evals, "auth-config": auth_config, "auth-sessions": auth_sessions, "profile-snapshot": profile_snapshot, "profile-restore": profile_restore, "set-dashboard-password": set_dashboard_password, "end-reviewer-sessions": end_reviewer_sessions, "cleanup-demo": cleanup_demo, "demo-clock": demo_clock, "demo-refeed": demo_refeed, "jd-report": jd_report, "demo-jd": demo_jd, "push-setup": push_setup,
             "push-rotate": lambda sec: push_setup(sec, rotate=True), "push-check": push_check, "demo-mails": demo_mails, "mail-coverage": mail_coverage, "public-copy": public_copy, "schedule-setup": schedule_setup, "schedule-status": schedule_status, "log-scan": log_scan, "live-page": live_page, "prefs-report": prefs_report, "forms-report": forms_report, "notice-forms": notice_forms, "public-ci": public_ci, "live-providers": live_providers, "push-examples": push_examples, "jd-sources": jd_sources, "posted-report": posted_report, "mail-audit": mail_audit, "mail-peek": mail_peek, "company-report": company_report, "repost-item": repost_item, "followup-evals": followup_evals, "posting-cleanup": posting_cleanup, "restore-items": restore_items, "ask-evals-real": ask_evals_real, "chat-audit": chat_audit}
    if task not in tasks:
        say(f"unknown task {task!r}; choose from {', '.join(tasks)}")
        return 2
    return tasks[task](secrets)


if __name__ == "__main__":
    sys.exit(main())
