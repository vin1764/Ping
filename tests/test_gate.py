"""The read-only gate: everything Ping needs is allowed, every action is refused."""

import pytest

from ping.gate import RULES, BlockedRequest, DENY_WORDS, check

B = "https://erp.iitkgp.ac.in"

# Every action-like address seen in the real captured ERP pages.
FORBIDDEN = [
    ("GET", B + "/TrainingPlacementSSO/TPJNFViewAction.jsp?mode=ApplyCV1&rollno=X&year=2026-2027&com_id=1&jnf_id=1"),
    ("GET", B + "/TrainingPlacementSSO/TPJNFViewAction.jsp?mode=ApplyCV2&rollno=X&year=2026-2027&com_id=1&jnf_id=1"),
    ("POST", B + "/TrainingPlacementSSO/TPJNFViewAction.jsp"),
    ("GET", B + "/TrainingPlacementSSO/TPFile.jsp?file_for=NOTICE&year=2026-2027&id=1797"),
    ("GET", B + "/TrainingPlacementSSO/Notice.jsp?mode=deactive&yop=2026-2027&id=1797"),
    ("GET", B + "/TrainingPlacementSSO/AdmFilePDF.htm?type=CV&rollno=X&id=1"),
    ("GET", B + "/TrainingPlacementSSO/AdmFilePDF.htm?type=PPT&year=2026-2027&com_id=1"),
    ("GET", B + "/TrainingPlacementSSO/AdmFilePDF.htm?type=JNF&year=2026-2027&jnf_id=1&com_id=1&rollno=X"),
    ("GET", B + "/TrainingPlacementSSO/AdmFilePDF.htm?type=CV&year=2026-2027&jnf_id=1&com_id=1"),
    ("GET", B + "/TrainingPlacementSSO/AdmFilePDF.htm?type=NOTICE&year=2026-2027&jnf_id=1&com_id=1"),
    ("GET", B + "/TrainingPlacementSSO/DownloadDoc.jsp?filepath=x"),
    ("GET", B + "/TrainingPlacement/StudentResumePDF?yop=1&rollno=X&com_id=1&jnf_id=1&file_for=ERPRESUME"),
    ("GET", B + "/TrainingPlacementSSO/cvGenerate.jsp?resume_no=1"),
    ("GET", B + "/TrainingPlacementSSO/NOCApply.jsp"),
    ("GET", B + "/TrainingPlacementSSO/InternshipFeedback.jsp"),
    ("GET", B + "/TrainingPlacementSSO/JnfMoreDet.jsp?mode=ApplyCV1&rollno=X&year=1&com_id=1&jnf_id=1"),
    ("GET", B + "/TrainingPlacementSSO/ERPMonitoring.jsp?param1=x&excel=1&sendmail=1"),
    ("GET", B + "/TrainingPlacementSSO/ERPMonitoring.htm?action=saveData&jqqueryid=37"),
    ("GET", B + "/TrainingPlacementSSO/ERPMonitoring.htm?action=fetchData&jqqueryid=99"),
    ("POST", B + "/IIT_ERP3/searchmenu.htm"),
    ("GET", B + "/IIT_ERP3/switchacc.htm"),
    ("GET", B + "/SSOAdministration/signup.htm"),
    ("GET", B + "/SSOAdministration/forgot.htm"),
    ("GET", "https://evil.example.com/TrainingPlacementSSO/Notice.jsp"),
    ("GET", "http://erp.iitkgp.ac.in/TrainingPlacementSSO/Notice.jsp"),
    ("GET", B + "/pages/survey/placementsurvey.php?auth=1"),
]


@pytest.mark.parametrize("method,url", FORBIDDEN)
def test_actions_are_blocked(method, url):
    with pytest.raises(BlockedRequest):
        check(method, url, {"x": "1"} if method == "POST" else None)


def test_showmenu_only_opens_the_cdc_companies_page():
    ok = {"module_id": "26", "menu_id": "11", "link": B + "/TrainingPlacementSSO/TPStudent.jsp",
          "delegated_by": "", "module_name": "CDC", "parent_display_name": "Student",
          "display_name": "Application of Placement/Internship"}
    check("POST", B + "/IIT_ERP3/showmenu.htm", ok)
    for bad in ({"menu_id": "20", "link": B + "/TrainingPlacementSSO/NOCApply.jsp"},
                {"menu_id": "26", "link": B + "/TrainingPlacementSSO/InternshipFeedback.jsp"}):
        with pytest.raises(BlockedRequest):
            check("POST", B + "/IIT_ERP3/showmenu.htm", {**ok, **bad})


def test_extra_fields_are_blocked():
    with pytest.raises(BlockedRequest):
        check("GET", B + "/TrainingPlacementSSO/ShowContent.jsp?year=1&id=2&mode=deactive")
    with pytest.raises(BlockedRequest):
        check("POST", B + "/TrainingPlacementSSO/TPStudent.jsp", {"ssoToken": "t", "module_id": "26",
                                                                  "menu_id": "11", "apply": "1"})


def test_everything_ping_needs_is_allowed():
    check("GET", B + "/IIT_ERP3/")
    check("GET", "https://erp.iitkgp.ac.in:443/SSOAdministration/login.htm?sessionToken=a&requestedUrl=b")
    check("GET", B + "/TrainingPlacementSSO/ERPMonitoring.htm?action=fetchData&jqqueryid=37&_search=false"
                     "&nd=1&rows=20&page=1&sidx=&sord=asc")
    check("GET", B + "/TrainingPlacementSSO/TPJNFView.jsp?jnf_id=2&com_id=313&yop=2026-2027&user_type=SU&rollno=X")
    check("GET", B + "/TrainingPlacementSSO/JnfMoreDet.jsp?mode=jnfMoreDet&rollno=X&year=2026-2027&com_id=313&jnf_id=2")
    check("GET", B + "/TrainingPlacementSSO/AdmFilePDF.htm?type=NOTICE&year=2026-2027&id=1794")
    # a role's JD file and the company's file (as the companies page opens them)
    check("GET", B + "/TrainingPlacementSSO/AdmFilePDF.htm?type=JNF&year=2026-2027&jnf_id=4&com_id=433")
    check("GET", B + "/TrainingPlacementSSO/AdmFilePDF.htm?type=COM&year=2026-2027&com_id=433")
    check("GET", B + "/TrainingPlacementSSO/ShowContent.jsp?year=2026-2027&id=1794")


def test_no_allowed_path_contains_a_deny_word():
    for rule in RULES:
        assert not any(w in rule.path.lower() for w in DENY_WORDS), rule.path


def test_source_never_mentions_action_pages():
    """A second lock: the code itself must not contain the addresses of action pages."""
    import pathlib
    src = "".join(p.read_text() for p in pathlib.Path(__file__).resolve().parent.parent.joinpath("ping").glob("*.py")
                  if p.name != "gate.py")
    for word in ("TPJNFViewAction", "ApplyCV", "TPFile.jsp", "mode=deactive", "StudentResumePDF", "acceptoffer"):
        assert word not in src, word
