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
