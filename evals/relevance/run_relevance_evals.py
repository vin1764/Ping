"""Score "For you": the demo roles' marks (what the demo shows, from Gemini via Admin > demo-refeed) against the
labels in cases.json, once the owner has confirmed them.

    python evals/relevance/run_relevance_evals.py

Refuses to score until cases.json says labels_confirmed: true (the labels are Claude's proposal until then).
Writes evals/relevance/REPORT.md: precision and recall of "For you", and every disagreement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from ping.relevance import tag
    spec = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    if not spec.get("labels_confirmed"):
        print("Not scored: the labels in evals/relevance/cases.json are a proposal until you correct them "
              "(see LABELS.md) and set labels_confirmed to true.")
        return 0
    demo = json.loads((ROOT / "dashboard" / "demo-data.json").read_text(encoding="utf-8"))
    roles = {r["id"]: r for r in demo["roles"]}
    rows, missing = [], []
    for c in spec["cases"]:
        r = roles.get(c["role_id"])
        got, why = tag(r, spec["targets"]) if r else (None, "")
        if got is None:
            missing.append(c)
            continue
        rows.append({**c, "got": got == "for_you", "got_why": why})
    tp = sum(1 for x in rows if x["got"] and x["for_you"])
    fp = sum(1 for x in rows if x["got"] and not x["for_you"])
    fn = sum(1 for x in rows if not x["got"] and x["for_you"])
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    out = ["# Role relevance evals", "",
           f"Targets: **{spec['targets']}**. {len(rows)} demo roles scored against the confirmed labels"
           + (f"; {len(missing)} not marked (ruled out by eligibility, or not classified yet)." if missing else "."), "",
           f"- **Precision of \"For you\": {precision:.0%}** ({tp} of {tp + fp} roles marked For you are right)",
           f"- **Recall of \"For you\": {recall:.0%}** ({tp} of {tp + fn} roles that are for you were marked)", "",
           "## Disagreements", "", "| company | role | label | Ping | Ping's reason |", "|---|---|---|---|---|"]
    for x in rows:
        if x["got"] != x["for_you"]:
            out.append(f"| {x['company']} | {x['designation']} | {'for you' if x['for_you'] else 'not'} | "
                       f"{'for you' if x['got'] else 'not'} | {x['got_why']} |")
    (HERE / "REPORT.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"precision {precision:.0%}, recall {recall:.0%} ({len(rows)} roles); wrote evals/relevance/REPORT.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
