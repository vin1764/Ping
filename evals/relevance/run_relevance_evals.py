"""Score "For you" per fixture persona: the classifier (ping/relevance.py, the same one the hourly run and the chat
use) marks each persona's roles in ONE call with that persona's targets text, and the marks are compared with the
labels in cases.json.

    python evals/relevance/run_relevance_evals.py        (needs GEMINI_API_KEY; Actions > Admin > relevance-evals)

Two personas with opposite targets (personas.json) over overlapping roles: a classifier that followed a fixed rule
instead of the stated targets would score well on one and badly on the other.
Writes evals/relevance/REPORT.md.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from ping import relevance
    from ping.cvs import cvs_text
    from ping.config import load_dotenv, load_secrets
    load_dotenv()
    cfg = load_secrets().ai
    spec = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    personas = {p["id"]: p for p in json.loads((HERE / "personas.json").read_text(encoding="utf-8"))["personas"]}
    roles = {r["id"]: r for r in json.loads((ROOT / "dashboard" / "demo-data.json").read_text(encoding="utf-8"))["roles"]}
    out = ["# Role relevance evals", "",
           "Each fixture persona's roles are marked by the classifier in one call with that persona's targets text "
           "(`personas.json`), and compared with labels that are correct for that text (`cases.json`). Re-run: "
           "Actions > Admin > `relevance-evals`.", "",
           "| persona | targets | roles | precision of \"For you\" | recall of \"For you\" | best CV right | not answered |",
           "|---|---|---|---|---|---|---|"]
    details = []
    for p in spec["personas"]:
        if not p.get("labels_confirmed"):
            out.append(f"| {p['persona']} | | | not scored (labels not confirmed) | | |")
            continue
        targets = personas[p["persona"]]["targets"]
        cvs = cvs_text(personas[p["persona"]].get("cvs"))
        rs = [dict(roles[c["role_id"]]) for c in p["cases"] if c["role_id"] in roles]
        for r in rs:
            r.pop("relevance", None)
        t0 = time.monotonic()
        before = relevance.stats["calls"]
        got = relevance.classify(rs, targets, cfg, cvs)
        secs, calls = time.monotonic() - t0, relevance.stats["calls"] - before
        tp = fp = fn = 0
        cv_ok = cv_n = 0
        wrong = []
        for c in p["cases"]:
            g = got.get(c["role_id"])
            if g is None:
                continue
            if g["relevant"] and c["for_you"]:
                tp += 1
            elif g["relevant"]:
                fp += 1
            elif c["for_you"]:
                fn += 1
            if c.get("best_cv") and g["relevant"]:
                cv_n += 1
                cv_ok += g.get("best_cv") == c["best_cv"]
                if g.get("best_cv") != c["best_cv"]:
                    wrong.append(f"| {p['persona']} | {c['company']} | {c['designation']} | CV: {c['best_cv']} | "
                                 f"CV: {g.get('best_cv') or '(none)'} | {g['reason']} |")
            if g["relevant"] != c["for_you"]:
                wrong.append(f"| {p['persona']} | {c['company']} | {c['designation']} | {'for you' if c['for_you'] else 'not'} | "
                             f"{'for you' if g['relevant'] else 'not'} | {g['reason']} |")
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        missing = len(p["cases"]) - len(got)
        out.append(f"| {p['persona']} | {targets} | {len(p['cases'])} | **{prec:.0%}** ({tp} of {tp + fp}) | "
                   f"**{rec:.0%}** ({tp} of {tp + fn}) | "
                   f"{f'**{cv_ok / cv_n:.0%}** ({cv_ok} of {cv_n})' if cv_n else 'n/a (no CVs)'} | {missing} |")
        details += wrong
        print(f"{p['persona']}: precision {prec:.0%}, recall {rec:.0%}, {missing} unanswered, {calls} call(s), {secs:.1f}s, "
              f"last error {relevance.stats['last_error']}")
    out += ["", "## Disagreements", "", "| persona | company | role | label | classifier | classifier's reason |",
            "|---|---|---|---|---|---|", *details]
    (HERE / "REPORT.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("wrote evals/relevance/REPORT.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
