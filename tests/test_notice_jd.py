"""JD documents on notices and in mail (ping/pdfs.py classify, ping/notice_jd.py): kept whole, linked to the company's
roles, split by role heading. Student lists never are. Made-up text shaped like the real RISA Labs notice."""

from ping import notice_jd, pdfs
from ping.matching import CompanyIndex

JD = """RISA Labs - Job Descriptions (Placement 2026-27)
About the company: RISA Labs builds AI agents for oncology workflows.

Associate Product Manager
Responsibilities: own the roadmap for one product line; write PRDs; work with engineering.
Requirements: strong analytical skills, SQL. CTC: 24 LPA. Location: Bangalore.

Software Development Engineer
Responsibilities: build backend services in Python and Go.
Requirements: data structures, system design. CTC: 30 LPA. Location: Bangalore.
Contact: hr@risa.example, 98765 43210
"""
ROLES = [{"id": "r1", "company": "RISA LABS PRIVATE LIMITED", "designation": "Associate Product Manager", "jd_source": "none"},
         {"id": "r2", "company": "RISA LABS PRIVATE LIMITED", "designation": "Software Development Engineer", "jd_source": "none"},
         {"id": "r3", "company": "RISA LABS PRIVATE LIMITED", "designation": "Data Analyst", "jd_source": "inline",
          "jd_text": "its own JD"}]
NOTICE = {"id": "2026-2027:1841", "year": "2026-2027", "notice_id": 1841, "company": "RISA LABS PRIVATE LIMITED",
          "notice_time": "2026-11-24T10:15:00+05:30", "analysis": {"kind": "info", "targets": [{"company": "RISA LABS PRIVATE LIMITED"}]}}


def test_a_jd_is_classified_and_kept_whole_without_contacts():
    assert pdfs.classify(JD, 0) == "jd"
    doc = pdfs.jd_document(JD)
    assert "Software Development Engineer" in doc and "Associate Product Manager" in doc
    assert "98765" not in doc and "hr@risa.example" not in doc


def test_student_lists_are_never_jds():
    shortlist = "List of shortlisted students\nS.No Name Roll No\n1 A Person 22XY10042\n" + JD
    assert pdfs.classify(shortlist, 1) == "list"
    assert pdfs.classify("The following students are shortlisted for the interview. Responsibilities CTC location " * 5, 0) == "list"


def test_one_pdf_for_several_roles_is_split_by_role_heading():
    parts = notice_jd.split_by_role(pdfs.jd_document(JD), ROLES[:2])
    apm, sde = parts["r1"], parts["r2"]
    assert apm[1] and sde[1]                                       # each role's own section
    assert "PRDs" in apm[0] and "Go." not in apm[0] and "About the company" in apm[0]
    assert "Python and Go" in sde[0] and "PRDs" not in sde[0]


def test_roles_without_a_jd_take_the_notice_one_and_say_where_from():
    roles = [dict(r) for r in ROLES]
    ups, stats = notice_jd.apply({NOTICE["id"]: {"status": "jd", "context": pdfs.jd_document(JD)}}, {NOTICE["id"]: NOTICE},
                                 roles, CompanyIndex(roles))
    by = {u["id"]: u for u in ups}
    assert set(by) == {"r1", "r2"}                                  # r3 keeps its own JD
    assert by["r1"]["jd_source"] == "notice" and by["r1"]["jd_note"] == "the PDF on notice 1841 (24 Nov)"
    assert "id=1841" in by["r1"]["jd_url"] and "type=NOTICE" in by["r1"]["jd_url"]
    assert stats["roles_gained"] == 2 and stats["sections"] == 2
    # a second run changes nothing
    ups2, stats2 = notice_jd.apply({NOTICE["id"]: {"status": "jd", "context": pdfs.jd_document(JD)}}, {NOTICE["id"]: NOTICE},
                                   roles, CompanyIndex(roles))
    assert ups2 == [] and stats2["roles_gained"] == 0


def test_a_jd_in_placement_mail_fills_the_roles_too():
    roles = [dict(r) for r in ROLES]
    mail = {"id": "m1", "company": "RISA LABS PRIVATE LIMITED", "received_at": "2026-11-22T09:00:00+05:30",
            "sender": "CDC <cdc@institute.example>", "subject": "RISA Labs JDs",
            "pdf": {"status": "jd", "file": "RISA_JD.pdf", "context": pdfs.jd_document(JD)}}
    ups, stats = notice_jd.apply({}, {}, roles, CompanyIndex(roles), mails=[mail])
    assert {u["id"] for u in ups} == {"r1", "r2"}
    assert ups[0]["jd_source"] == "mail" and ups[0]["jd_note"] == "the 22 Nov mail from CDC (PDF attached)"


def test_coverage_counts_facts_the_documents_add():
    roles = [dict(r) for r in ROLES]
    notice_jd.apply({NOTICE["id"]: {"status": "jd", "context": pdfs.jd_document(JD)}}, {NOTICE["id"]: NOTICE}, roles, CompanyIndex(roles))
    cov = notice_jd.coverage(roles)
    assert cov["from_docs"] == 2 and cov["doc_facts"]["ctc"] == 2


def test_the_same_pdf_posted_again_is_one_document_the_first_posting():
    roles = [dict(r) for r in ROLES]
    again = {**NOTICE, "id": "2026-2027:1860", "notice_id": 1860, "notice_time": "2026-11-24T17:54:00+05:30"}
    doc = {"status": "jd", "context": pdfs.jd_document(JD)}
    ups, _ = notice_jd.apply({NOTICE["id"]: doc, again["id"]: dict(doc)}, {NOTICE["id"]: NOTICE, again["id"]: again},
                             roles, CompanyIndex(roles))
    assert {u["jd_note"] for u in ups} == {"the PDF on notice 1841 (24 Nov; posted again as 1860)"}
    assert all("id=1841" in u["jd_url"] for u in ups)
