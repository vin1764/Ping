"""docs/HELP.md is what Ping says about itself: help.js (bundled into the page and the function) must match it,
and it must stay generic (no student's name, department or preference)."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_help_js_matches_help_md():
    r = subprocess.run([sys.executable, str(ROOT / "setup" / "build_help.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_help_is_bundled_everywhere():
    assert "_shared/help.js" in (ROOT / "dashboard" / "build.sh").read_text()
    html = (ROOT / "dashboard" / "index.html").read_text()
    assert html.index('src="help.js"') < html.index('src="answer_rules.js"')
    assert '"help.js"' in (ROOT / "dashboard" / "sw.js").read_text()
    assert 'import "../_shared/help.js"' in (ROOT / "supabase" / "functions" / "ask-ping" / "index.ts").read_text()


def test_help_is_generic():
    md = (ROOT / "docs" / "HELP.md").read_text()
    assert not re.search(r"\b\d{2}[A-Z]{2}\d{5}\b", md)                 # no roll number
    for word in ("COMPUTER SCIENCE", "B.TECH", "Demo Student", "Ping"):
        assert word.lower() not in md.lower()
