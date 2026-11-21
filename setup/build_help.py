"""docs/HELP.md -> supabase/functions/_shared/help.js (what Ping says about itself; docs/HELP.md says how).

    python setup/build_help.py          write help.js
    python setup/build_help.py --check  exit 1 if help.js doesn't match docs/HELP.md (tests/test_help_doc.py)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "HELP.md"
OUT = ROOT / "supabase" / "functions" / "_shared" / "help.js"
TOPICS = ("overview", "install", "notifications", "checks", "can", "preferences", "data")
PLATFORMS = ("windows", "mac", "android", "ios", "other")


def parse(md: str) -> dict:
    doc: dict = {}
    topic = plat = None
    for line in md.splitlines():
        m2, m3 = re.match(r"^## (\w+)\s*$", line), re.match(r"^### (\w+)\s*$", line)
        if m2:
            topic, plat = m2.group(1), None
            doc[topic] = {"text": [], "platforms": {}}
            continue
        if m3 and topic:
            plat = m3.group(1)
            doc[topic]["platforms"][plat] = []
            continue
        if topic is None:
            continue
        (doc[topic]["platforms"][plat] if plat else doc[topic]["text"]).append(line)
    out = {}
    for t, v in doc.items():
        out[t] = {"text": "\n".join(v["text"]).strip()}
        if v["platforms"]:
            out[t]["platforms"] = {p: "\n".join(x).strip() for p, x in v["platforms"].items()}
    missing = [t for t in TOPICS if t not in out] + [p for p in PLATFORMS if p not in out.get("install", {}).get("platforms", {})]
    if missing:
        raise SystemExit(f"docs/HELP.md is missing: {', '.join(missing)}")
    return out


def render(doc: dict) -> str:
    body = json.dumps(doc, indent=1, ensure_ascii=False)
    return ("/* GENERATED from docs/HELP.md by setup/build_help.py: edit the .md and run the script (a test checks they\n"
            " * match). What Ping says about itself; answer_rules.js picks the topic and, for installing, the platform. */\n"
            "(function (root) {\n  \"use strict\";\n  const HELP = " + body + ";\n"
            "  if (typeof module !== \"undefined\" && module.exports) module.exports = HELP;\n"
            "  else root.PingHelp = HELP;\n"
            "})(typeof window !== \"undefined\" ? window : globalThis);\n")


def main(argv: list[str]) -> int:
    js = render(parse(SRC.read_text()))
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text() != js:
            print("help.js is out of date: run python setup/build_help.py")
            return 1
        return 0
    OUT.write_text(js)
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
