"""Finding and summarising a role's JD (ping/jd.py) on the shapes seen on the ERP. Made-up text throughout."""

from ping.jd import resolve, rules_summary, usable

SKILLS_RUN_ON = ("Building and pricing models, reviewing client portfolios, writing research notes and presenting them to "
                 "senior bankers\n\nRequired Skill Set: Interest in markets and curiosity \x95 Strong numerical skills, "
                 "aptitude and ability to learn new finance, industry & tech ideas \x95 Excel and market databases \x95 "
                 "Clear writing and speaking  Attention to detail")
INLINE_LABELS = ("Required Skill Set: Role: Build dependable data flows and keep them monitored. Skills: Python and SQL, "
                 "database basics, and some exposure to a cloud warehouse (any) and cloud basics (any provider).")
SECTIONED = """PRODUCT ANALYST – PAYMENTS
Department: Product
Location: Bengaluru / Pune
About the Role
We are a fast-growing company with millions of users across the country and a strong brand.
You will work closely with engineering and design to define metrics and analyse experiments.
Key Responsibilities
1. Metrics & Insight
• Define product metrics and dashboards.
• Analyse A/B tests and explain the results.
2. Roadmap
• Turn insights into roadmap proposals.
What you need to bring to the ‘table’
• Strong SQL
• Comfort with statistics
• Clear written communication
Note: a two-year service agreement applies."""


def test_rules_summary_on_run_on_and_bulleted_text():
    s = rules_summary(SKILLS_RUN_ON, "Research Analyst")
    assert s["do"] == ["Building and pricing models", "Reviewing client portfolios",
                       "Writing research notes and presenting them to senior bankers"]
    assert s["must_have"][0] == "Interest in markets and curiosity"
    assert "Excel and market databases" in s["must_have"]
    assert len(s["must_have"]) == 5 and all(len(x.split()) <= 13 for x in s["must_have"])


def test_rules_summary_on_labels_inside_a_line():
    s = rules_summary(INLINE_LABELS, "Data Engineer")
    assert s["do"] == ["Build dependable data flows and keep them monitored"]
    assert s["must_have"][:2] == ["Python and SQL", "Database basics"]


def test_rules_summary_on_sections_subheadings_and_unusual():
    s = rules_summary(SECTIONED, "Product Analyst")
    assert s["do"] == ["Define product metrics and dashboards", "Analyse A/B tests and explain the results",
                       "Turn insights into roadmap proposals"]          # numbered sub-headings are not duties
    assert s["must_have"] == ["Strong SQL", "Comfort with statistics", "Clear written communication"]
    assert s["location"] == "Bengaluru / Pune"
    assert any("service agreement" in x for x in s["unusual"])


def test_details_win_over_a_private_link_but_the_link_is_kept():
    role = {"job_description": "https://docs.google.com/document/d/abc/edit",
            "more_details": {"fields": {"Required Skill Set": INLINE_LABELS + " " + INLINE_LABELS}}}
    got = resolve(role, get_file=lambda kind: (b"", ""),
                  get_link=lambda url: {"jd_text": None, "jd_source": "link-unreadable", "jd_url": url, "jd_note": "401"})
    assert got["jd_source"] == "detail" and usable(got["jd_text"])
    assert got["jd_url"] == "https://docs.google.com/document/d/abc/edit"
    assert "couldn't be opened" in got["jd_note"]


def test_only_a_private_link():
    role = {"job_description": "JD: https://docs.google.com/document/d/abc/edit"}
    got = resolve(role, get_file=lambda kind: (b"", ""),
                  get_link=lambda url: {"jd_text": None, "jd_source": "link-unreadable", "jd_url": url, "jd_note": "401"})
    assert got == {"jd_text": None, "jd_source": "link-unreadable", "jd_url": "https://docs.google.com/document/d/abc/edit",
                   "jd_note": "401"}


def test_bullets_and_odd_characters_are_normalised():
    from ping.jd import clean
    assert clean(" Strong SQL\nPython\n Excel") == "• Strong SQL\n• Python\n• Excel"     # Symbol-font bullets
    assert clean("Skills:▪ SQL ▪ Python") == "Skills: • SQL • Python"
    assert clean("➢ Build models\n\x95 Ship") == "• Build models\n• Ship"
    assert clean("Good communi­cation​ skills") == "Good communication skills"
    assert clean("ﬁnance oﬃce") == "finance office"
    assert "�" not in clean("company�s team")
    assert clean("C++ and C# fine; 3.5 GPA; a*b") == "C++ and C# fine; 3.5 GPA; a*b"     # ordinary text untouched


def test_stored_jd_text_is_recleaned_without_fetching(monkeypatch):
    from ping.run import Runner
    r = Runner.__new__(Runner)
    r.counts = {}
    r.erp = None                                   # any fetch would fail
    role = {"id": "x", "job_description": " Strong SQL " * 40, "apply_end": "2026-11-22"}
    from ping.jd import jd_key
    stored = {"x": {"jd_key": jd_key(role), "jd_source": "inline", "jd_text": " Strong SQL"}}
    r._jds([role], stored)
    assert r.jd_updates == [{"id": "x", "jd_text": "• Strong SQL"}]
