import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def _no_internet_for_jd_links(monkeypatch):
    """Job description links are never fetched from the internet in tests (a test may set its own fetcher)."""
    import ping.jd as jd
    monkeypatch.setattr(jd, "from_link", lambda url, session=None: {
        "jd_text": None, "jd_source": "link-unreadable", "jd_url": url, "jd_note": "not fetched in tests"})


@pytest.fixture(autouse=True)
def _posting_on(monkeypatch):
    """Tests run with posting on (the deployed run is paused until PING_POSTING=on); tests/test_posting.py covers the guard."""
    monkeypatch.setenv("PING_POSTING", "on")


@pytest.fixture(autouse=True)
def _no_model_calls_for_card_lines(monkeypatch):
    """A run in tests never calls a model for card lines, even when a key is set in the shell (rules lines only)."""
    monkeypatch.setenv("PING_SUMMARY_CALLS", "0")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
