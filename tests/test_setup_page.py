"""setup.html is built from docs/SETUP.md at every deploy (setup/build_setup_page.py). These checks fail if the two
could say different things, if a section the page promises is missing, or if the page leaks a placeholder, a dead
link or a name it must not carry."""

import html
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_setup_page", ROOT / "setup" / "build_setup_page.py")
page = importlib.util.module_from_spec(spec)
spec.loader.exec_module(page)
DOC = (ROOT / "docs" / "SETUP.md").read_text(encoding="utf-8")


def text_of(h: str) -> str:
    inline = re.sub(r"</?(?:code|strong|a)\b[^>]*>", "", h)          # inline tags join text, block tags separate it
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", inline))).strip()


def test_every_line_of_the_doc_is_on_the_page():
    out = text_of(page.render())
    body = DOC.split("\n## ", 1)[1]
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("```") or re.fullmatch(r"\|[-| :]+\|", s):
            continue
        s = re.sub(r"^(#+|-|\d+\.)\s+", "", s)
        for cell in (c for c in s.strip("|").split("|") if c.strip()):
            words = re.sub(r"\s+", " ", re.sub(r"\*\*|`|\[([^\]]+)\]\([^)]+\)", r"\1", cell)).strip()
            words = words.replace(page.PLACEHOLDER, "available on request")
            assert words in out, f"on the doc but not the page: {words[:80]}"


def test_sections_in_order_and_steps_numbered():
    h = page.render()
    heads = re.findall(r"<h2[^>]*>(.*?)</h2>", h)
    assert heads == ["What you get", "What it never does", "What you need", "Steps", "How long it takes",
                     "If something goes wrong", "Privacy"]
    steps = re.search(r'<h2 id="steps">.*?<ol>(.*?)</ol>', h, re.S).group(1)
    assert 7 <= steps.count("<li>") <= 9
    for cmd in ("python setup/new_student_setup.py", "gh workflow run admin.yml -f task=schedule-setup", "git clone"):
        assert cmd in html.unescape(h), cmd
    for secret in ("ERP_USER_ID", "ERP_PASSWORD", "ERP_SECQ_1", "MAIL_APP_PASSWORD", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
                   "GEMINI_API_KEY", "PING_GITHUB_TOKEN", "DASHBOARD_DEPLOY_TOKEN"):
        assert secret in h, secret
    assert len(re.findall(r"<li>", re.search(r'<h2 id="if-something-goes-wrong">.*?<ul>(.*?)</ul>', h, re.S).group(1))) == 3


def test_source_repo_is_one_placeholder_and_no_dead_link():
    assert DOC.count(page.PLACEHOLDER) == 1
    h = page.render()
    assert page.PLACEHOLDER not in h
    if not page.SOURCE_REPO_URL:
        assert "Source repo: available on request" in text_of(h)
    for href in re.findall(r'href="([^"]*)"', h):
        assert href and href != "#" and "SOURCE" not in href, href


def test_no_other_product_or_working_name():
    from ping.demo_from_real import BANNED_WORDS
    low = page.render().lower() + DOC.lower()
    for word in BANNED_WORDS:
        assert word.lower() not in low
