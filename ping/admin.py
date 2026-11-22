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
from datetime import datetime
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
    for n in ("GEMINI_API_KEY", "GEMINI_API_KEY_EVALS", "PING_AI_LITE_MODEL"):
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
    r = requests.patch(url, headers=hdr, timeout=30, json={"site_url": live, "uri_allow_list": ",".join(new_list),
                                                           "external_anonymous_users_enabled": True,
                                                           "disable_signup": False, "mailer_autoconfirm": False})
    if r.status_code >= 300:
        say(f"updating the Auth settings failed: HTTP {r.status_code} {r.text[:200]}")
        return 1
    after = requests.get(url, headers=hdr, timeout=30).json()
    say(f"after:  site_url = {after.get('site_url')}; redirect allow-list = {(after.get('uri_allow_list') or '').split(',')}")
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
             "DASHBOARD_DEPLOY_TOKEN"]
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
    from .demo_from_real import add_sample_mails
    out = ROOT / "dashboard" / "demo-data.json"
    data = add_sample_mails(json.loads(out.read_text(encoding="utf-8")))
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
             "gemini-check": gemini_check, "functions-check": functions_check, "ask-ping-page": ask_ping_page, "rearm-schedule": rearm_schedule, "ask-ping-evals": ask_ping_evals, "relevance-evals": relevance_evals, "auth-config": auth_config, "auth-sessions": auth_sessions, "cleanup-demo": cleanup_demo, "demo-clock": demo_clock, "demo-refeed": demo_refeed, "jd-report": jd_report, "demo-jd": demo_jd, "push-setup": push_setup,
             "push-rotate": lambda sec: push_setup(sec, rotate=True), "push-check": push_check, "demo-mails": demo_mails, "mail-coverage": mail_coverage, "public-copy": public_copy, "schedule-setup": schedule_setup, "schedule-status": schedule_status, "log-scan": log_scan, "live-page": live_page}
    if task not in tasks:
        say(f"unknown task {task!r}; choose from {', '.join(tasks)}")
        return 2
    return tasks[task](secrets)


if __name__ == "__main__":
    sys.exit(main())
