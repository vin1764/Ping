"""The mailbox as a source, on the 20-mail fixture mailbox (evals/mail/fixture.py: 10 placement mails, 10 not).

    python evals/mail/run_mail_evals.py      -> evals/mail/results.json and evals/mail/REPORT.md

Checks: nothing of the 10 other mails is stored, and none of their bodies is even fetched; the OTP never is; the mail
that repeats an ERP notice becomes "also mailed to you" on that notice, not a message of its own; the form's deadline
is extracted; the roll number is found in the mailed PDF shortlist (only your row and the table heading kept).
"""

from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

from fixture import NAME, NOTICES, NOW, OTP_CODE, PROFILE, ROLES, ROLL, mailbox, mails  # noqa: E402

from ping import mail_source  # noqa: E402
from ping.items import build_items  # noqa: E402
from ping.mailbox import parse_head  # noqa: E402
from ping.matching import CompanyIndex  # noqa: E402
from ping.notices import analyze  # noqa: E402


def main() -> int:
    fx = mails()
    mb, imap = mailbox(fx)
    index = CompanyIndex(ROLES)
    rows, stats = mail_source.scan(mb, NOW - timedelta(days=14), index, ROLL, NAME)
    notices = [dict(n) for n in NOTICES]
    for n in notices:
        n["analysis"] = analyze(n, n["text"], index, ROLL, NAME)
    roles = [dict(r) for r in ROLES]
    fstats: dict = {}
    items = build_items(roles, notices, {}, PROFILE, NOW, rows, {}, stats=fstats)
    stored = json.dumps(rows, ensure_ascii=False)
    by_subject = {r["subject"]: r for r in rows}

    per_mail = []
    for m in fx:
        v = mail_source.scope(parse_head(m["uid"], m["raw"], None), index)
        r = by_subject.get(m["subject"])
        item = next((it for it in items if r and it["id"] == f"mail:{r['id']}"), None)
        per_mail.append({"uid": m["uid"], "label": m["label"], "placement": m["placement"], "kept": v.keep,
                         "because": v.because + (f":{v.signal}" if v.signal else ""),
                         "body_read": m["uid"] in imap.bodies_read, "stored": r is not None,
                         "kind": r and r["kind"], "company": r and r["company"], "due_at": r and r["due_at"],
                         "event_at": r and r["event_at"], "link": r and r["main_link"],
                         "pdf": r and (r["pdf"] or {}).get("status"),
                         "feed": item["title"] if item else ("also mailed to you on the ERP notice" if r else None)})
    noise = [m for m in fx if not m["placement"]]
    dup = next(r for r in rows if r["subject"].startswith("Groww online test"))
    groww = next(it for it in items if it["id"].startswith("notice:2026-2027:901"))
    form = next(r for r in rows if r["subject"].startswith("Pine Labs"))
    shortlist = next(r for r in rows if r["subject"].startswith("Goldman Sachs"))
    checks = {
        "no noise stored": not any(m["subject"] in stored for m in noise),
        "no noise body fetched": not ({m["uid"] for m in noise} & set(imap.bodies_read)),
        "OTP never stored": OTP_CODE not in stored and "OTP" not in stored,
        "read-only (no IMAP writes)": imap.writes == [],
        "ERP duplicate deduped": f"mail:{dup['id']}" not in {it["id"] for it in items}
                                 and (groww["details"].get("mail") or {}).get("note") == "also mailed to you",
        "form deadline extracted": form["kind"] == "form" and form["due_at"] == "2026-11-22T17:00:00+05:30",
        "roll found in the PDF": (shortlist["pdf"] or {}).get("status") == "yes" and ROLL in " ".join(shortlist["pdf"]["my_row"] or []),
        "all 10 placement mails kept": sum(1 for p in per_mail if p["placement"] and p["kept"]) == 10,
        "extraction matches the labels": all(
            all(((r["pdf"] or {}).get("status") if k == "pdf" else r.get(k)) == want for k, want in m["expect"].items() if k != "twin")
            for m in fx if m["placement"] for r in [by_subject[m["subject"]]]),
    }
    out = {"checks": checks, "scan": stats.as_dict(), "feed": {k: v for k, v in fstats.items() if k.startswith("mail")},
           "mails": per_mail}
    (HERE / "results.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")

    lines = ["# Mailbox as a source: fixture eval", "",
             "20 made-up mails (`evals/mail/fixture.py`) served by a fake IMAP server that records what Ping fetched. "
             "Run: `python evals/mail/run_mail_evals.py`. The exact filter is in `docs/SECURITY.md` (Mailbox).", "",
             "| check | result |", "|---|---|"]
    lines += [f"| {k} | {'pass' if v else '**FAIL**'} |" for k, v in checks.items()]
    s = stats.as_dict()
    lines += ["", f"Scan: {s['headers_seen']} mails' headers read, {s['kept']} kept and read in full, {s['bodies_read']} "
              f"bodies fetched, {s['attachments_read']} attachment(s), {s['otp_skipped']} OTP mail skipped. Dropped by rule: "
              + ", ".join(f"{k} {v}" for k, v in sorted(s["dropped"].items())) + ".",
              f"Feed: {fstats.get('mail_twins', 0)} mail repeated an ERP notice (also mailed to you), "
              f"{fstats.get('mail_only', 0)} became messages via email.", "",
              "| # | mail | kept (why) | body read | kind | company | due / when | in the feed |", "|---|---|---|---|---|---|---|---|"]
    for p in per_mail:
        when = p["due_at"] or p["event_at"] or ""
        lines.append(f"| {p['uid']} | {p['label']} | {'yes' if p['kept'] else 'no'} ({p['because']}) | "
                     f"{'yes' if p['body_read'] else 'no'} | {p['kind'] or ''} | {p['company'] or ''} | {when[:16]} | "
                     f"{(p['feed'] or '').replace('|', '/')} |")
    (HERE / "REPORT.md").write_text("\n".join(lines) + "\n")
    bad = [k for k, v in checks.items() if not v]
    print("\n".join(f"{'ok  ' if v else 'FAIL'} {k}" for k, v in checks.items()))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
