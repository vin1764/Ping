"""Forms evals: 15 postings through the same code as the hourly run (ping/forms.py, ping/form_pages.py) against a
fake web (evals/forms/cases.json: short links and form pages; no network). A posting scores when it lands in the
right form with nothing else in it and that form has the expected deadline (and history), sources, closed /
sign-in state and 'looks like' offer. Also: reposts in the chat are one 'deadline extended' line, not a new message.

    python evals/forms/run_forms_evals.py      -> evals/forms/REPORT.md (and a section in evals/REPORT.md)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from ping import forms  # noqa: E402
from ping.config import IST  # noqa: E402
from ping.dedupe import dedupe  # noqa: E402
from ping.form_pages import Reader  # noqa: E402

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=IST)


def page_html(p: dict) -> str:
    if p.get("closed"):
        return f"<html><head><title>{p.get('title', '')}</title></head><body>This form is no longer accepting responses.</body></html>"
    data = [None, ["", [[i, f"Q{i}", None, 0] for i in range(p.get("questions") or 0)], None, None, None, None, None, None, p.get("title", "")]]
    return (f"<html><head><meta property=\"og:title\" content=\"{p.get('title', '')}\"><title>{p.get('title', '')}</title></head><body>"
            f"<script>var FB_PUBLIC_LOAD_DATA_ = {json.dumps(data)};</script></body></html>")


def fake_get(spec):
    pages = spec["pages"]

    def get(url, stop=None):
        seen = 0
        while seen < 6:
            seen += 1
            if stop and stop(url):
                return url, ""
            base = url.split("?")[0].split("#")[0]
            base = base.replace("/formResponse", "/viewform")
            p = pages.get(url) or pages.get(base)
            if p is None:
                raise ConnectionError("no such page")
            if p.get("redirect"):
                url = p["redirect"]
                continue
            if p.get("signin"):
                return "https://accounts.google.com/v3/signin/identifier?continue=" + url, "<html>Sign in</html>"
            return url, page_html(p)
        raise ValueError("too many redirects")
    return get


def item(p):
    d = {"todo": {"action": "fill_form", "link": p["link"], "due": p["due"]}, "subject": p["subject"]}
    if p["link"]:
        d["forms"] = [p["link"]]
    nid = None
    if p.get("notice"):
        nid, d["notice_time"] = p["notice"]
    if p.get("mail"):
        d["mail"] = {"id": p["mail"][0], "received_at": p["mail"][1], "link": p["link"]}
        d["via"] = "email"
    iid = f"notice:{nid}:0:todo0" if nid else f"mail:{p['mail'][0]}"
    return {"id": iid, "category": "todo", "company": p["company"], "title": f"{p['company']}: fill the form by {p['due']}.",
            "due_at": p["due"], "level": "show", "notice_id": nid, "role_ids": [], "details": d, "first_seen": d.get("notice_time")}


def main() -> int:
    spec = json.loads((HERE / "cases.json").read_text())
    posts = spec["postings"]
    items = [item(p) for p in posts]
    reader = Reader({}, get=fake_get(spec), now=NOW, per_run=50, budget_s=30)
    rows = forms.build(items, fetch=reader.follow, now=NOW)
    pages = reader.read_rows(rows)
    rows = forms.build(items, pages=pages, fetch=reader.follow, now=NOW)
    by_item = {iid: r for r in rows for iid in r["item_ids"]}
    want_groups = {}
    for p, it in zip(posts, items):
        want_groups.setdefault(p["form"], set()).add(it["id"])
    key_of_form = {f: (by_item.get(next(iter(ids))) or {}).get("key") for f, ids in want_groups.items()}
    results = []
    for p, it in zip(posts, items):
        r = by_item.get(it["id"])
        why = []
        if not r:
            why.append("not in any form")
        else:
            if set(r["item_ids"]) != want_groups[p["form"]]:
                why.append(f"grouped with {sorted(set(r['item_ids']) ^ want_groups[p['form']])}")
            exp = spec["forms"].get(p["form"], {})
            if "due" in exp and r["due_at"] != exp["due"]:
                why.append(f"deadline {r['due_at']}")
            if "moves" in exp and len(r["deadline_history"]) != exp["moves"]:
                why.append(f"{len(r['deadline_history'])} deadline moves")
            if "sources" in exp and len(r["sources"]) != exp["sources"]:
                why.append(f"{len(r['sources'])} sources")
            if exp.get("closed") and not r["closed"]:
                why.append("not marked closed")
            if exp.get("signin_required") and not r["signin_required"]:
                why.append("sign-in not seen")
            if forms.stored(r)["looks_like"]:
                why.append("a merge prompt (Ping never asks)")
            if exp.get("looks_like") is False and r.get("looks_like"):
                why.append(f"offered as like {r['looks_like']}")
            if isinstance(exp.get("looks_like"), str):
                if not any(x["key"] == key_of_form[exp["looks_like"]] for x in r.get("looks_like") or []):
                    why.append("not offered as 'looks like' the other form")
        results.append({"id": p["id"], "case": p["case"], "ok": not why, "why": why, "form": (r or {}).get("key")})
    # the chat: a repost of a notice form is one 'deadline extended' line on the first message, not a new message
    chat_items = [dict(i, details=dict(i["details"])) for i in items if i["id"].startswith("notice:")]
    out, stats = dedupe(chat_items, NOW)
    reposts = {"P3": "notice:2005:0:todo0", "P12": "notice:2061:0:todo0"}
    chat_ok = []
    for pid, iid in reposts.items():
        rep = next(i for i in out if i["id"] == iid)
        firsts = [i for i in out if (i.get("details") or {}).get("extended") and any(e["id"] == iid for e in i["details"]["extended"])]
        ok = rep["level"] == "hidden" and len(firsts) == 1 and firsts[0]["level"] != "hidden" and not any(":update:" in i["id"] for i in out if iid in i["id"])
        chat_ok.append((pid, ok, firsts[0]["title"] if firsts else ""))
    score = sum(r["ok"] for r in results)
    lines = ["# Forms evals", "", f"Run {datetime.now(IST):%a %d %b %H:%M} IST. **{score}/{len(results)} postings** land in the right form with the right deadline, "
             f"history, sources, closed / sign-in state and 'looks like' offer; reposts in the chat: {sum(o for _, o, _ in chat_ok)}/{len(chat_ok)} "
             "are one 'deadline extended' line on the existing message (no new message).", "",
             f"Form pages read: {reader.stats}.", "", "| posting | case | result | form |", "|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['case']} | {'ok' if r['ok'] else 'FAIL: ' + '; '.join(r['why'])} | `{r['form']}` |" for r in results]
    lines += ["", "Chat:", *[f"- {pid}: {'ok' if ok else 'FAIL'} — {t}" for pid, ok, t in chat_ok]]
    (HERE / "REPORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if score == len(results) and all(o for _, o, _ in chat_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
