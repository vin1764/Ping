"""The guard in front of the public ping-dashboard repo blocks every kind of leak it promises to."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("guard", ROOT / "setup" / "check_public_build.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


@pytest.fixture()
def site(tmp_path):
    for name in guard.EXPECTED:
        (tmp_path / name).write_text("ok, deadline 21-11-2026 20:00, call 90000 12345", encoding="utf-8")
    return tmp_path


def test_a_clean_build_passes(site):
    assert guard.problems_in(site, "22XY10042", "me@example.org") == []


@pytest.mark.parametrize("leak", ["sb_secret_abc", "service_role", "AIzaSyExample", "+91 ", "call 9123456780",
                                  "landline 3222 28 2001", "roll 22XY10042", "mail ME@example.org",
                                  bytes.fromhex("696e7374696e6374").decode().upper()])
def test_each_leak_blocks_the_deploy(site, leak):
    (site / "demo-data.json").write_text(f"text {leak} text", encoding="utf-8")
    assert guard.problems_in(site, "22XY10042", "me@example.org")


def test_unexpected_files_block_the_deploy(site):
    (site / ".env").write_text("x", encoding="utf-8")
    assert guard.problems_in(site) == ["unexpected files: ['.env']"]
