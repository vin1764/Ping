"""The page answers FACT questions itself; a message that sets preferences must still reach the ask-ping function.
answer_rules.js carries a copy of prefs.ts's patterns to tell them apart: the two must not drift."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_prefs_patterns_are_the_same_in_the_page_and_the_function():
    ts = (ROOT / "supabase" / "functions" / "ask-ping" / "prefs.ts").read_text()
    js = (ROOT / "supabase" / "functions" / "_shared" / "answer_rules.js").read_text()
    pats = re.findall(r"^const ([A-Z_]+) = (/.*/[a-z]*);\s*$", ts, re.M)
    assert len(pats) >= 13
    for name, rx in pats:
        assert f"    {name}: {rx},\n" in js, f"{name} differs between prefs.ts and answer_rules.js"
