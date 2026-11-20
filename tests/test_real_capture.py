"""Checks against a real capture from setup/capture_erp.py.

Real captures contain other students' data, so they are never committed.
Point PING_CAPTURE_DIR at an unzipped capture's network/ folder to run these;
otherwise they are skipped.
"""

import glob
import os
from datetime import datetime

import pytest

from ping.dates import find_moments
from ping.gate import BlockedRequest, check
from ping.matching import CompanyIndex
from ping.notices import analyze
from ping.parsers import parse_companies, parse_notice_page, parse_notices, parse_role_popup

CAP = os.environ.get("PING_CAPTURE_DIR")
pytestmark = pytest.mark.skipif(not CAP, reason="set PING_CAPTURE_DIR to a real capture's network/ folder")


def _files(pattern):
    return sorted(glob.glob(os.path.join(CAP or "", pattern)))


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _grid(qid_marker):
    for f in _files("*ERPMonitoring*"):
        s = _read(f)
        if qid_marker(s):
            return s
    pytest.skip("grid not in capture")


def test_companies_list():
    roles = parse_companies(_grid(lambda s: "TPJNFView(" in s))
    assert len(roles) > 50
    assert all(r["apply_end"] for r in roles)
    assert any(r["applied"] for r in roles)
    assert {r["currency"] for r in roles} >= {"INR"}


def test_role_popups():
    pops = [parse_role_popup(_read(f)) for f in _files("*TPJNFView.jsp*")]
    assert pops
    for p in pops:
        assert p["company"] and p["designation"] and p["form_type"]
        assert p["allowed"] and all(a["degree"] and a["department"] for a in p["allowed"])


def test_notices_and_analysis_never_crash():
    roles = parse_companies(_grid(lambda s: "TPJNFView(" in s))
    notices = parse_notices(_grid(lambda s: "ViewNotice(" in s))
    assert len(notices) > 100
    idx = CompanyIndex(roles)
    for n in notices:
        a = analyze(n, n["preview"], idx)
        assert a["kind"]
        for m in find_moments(n["preview"], datetime.fromisoformat(n["notice_time"])):
            assert m.at.year in (2025, 2026, 2027, 2028)


def test_notice_pages():
    for f in _files("*ShowContent.jsp*"):
        p = parse_notice_page(_read(f))
        assert p["header"].get("subject") and p["text"]


def test_every_link_in_the_captured_pages_that_does_something_is_blocked():
    import re
    risky = set()
    for f in _files("*.html"):
        for m in re.findall(r"""["']((?:https://erp\.iitkgp\.ac\.in)?/?[\w/]*(?:Action|TPFile|Apply|Upload|"""
                            r"""deactive|accept|cancel)[\w./?=&-]*)""", _read(f)):
            risky.add(m)
    for path in risky:
        url = path if path.startswith("http") else "https://erp.iitkgp.ac.in/TrainingPlacementSSO/" + path.lstrip("/")
        with pytest.raises(BlockedRequest):
            check("GET", url)
