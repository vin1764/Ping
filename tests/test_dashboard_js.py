"""The dashboard's pure JavaScript (dashboard/onboarding.js, dashboard/names.js) is tested with Node's own test runner (tests/js/)."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_onboarding_script():
    files = sorted(str(p) for p in (ROOT / "tests" / "js").glob("*.test.js"))
    out = subprocess.run(["node", "--test", *files], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-2000:]
