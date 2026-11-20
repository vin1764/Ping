"""The role 'more details' popup, in the layout seen on the real ERP (company info only)."""

from ping.eligibility import backlog_allows
from ping.parsers import parse_more_details


def row(*pairs):
    cells = "".join(f'<div class="col-xs-3 text-left"> <div>{k} :</div> </div>'
                    f'<div class="col-xs-3"> <div><b>{v}</b></div> </div>' for k, v in pairs)
    return f'<div class="row"> {cells} </div>'


PAGE = f"""<html><body><div class="container-fluid">
<input type="hidden" name="mode" id="mode"><input type="hidden" name="jnf_id" id="jnf_id" value="3">
<h4>Job Profile</h4><table class="table table-bordered"><thead><tr><th>Form Type</th><th>Designation</th>
<th>Cost to Company per year</th></tr></thead><tbody><tr><td>PLACEMENT</td><td>Engineer</td><td>1815000 INR</td></tr>
</tbody></table><h4>Job Description</h4><div>Build things.</div>
<h4>Other Details</h4>
{row(("CTC Breakup", "1815000"), ("Gross (per Annum)", "1815000"))}
{row(("Fixed Take Home Salary (per Annum)", "1500000"), ("Base Salary", "1500000"))}
{row(("Joining Bonus, if any", "400000"), ("Relocation Bonus, if any", "0"))}
{row(("Bonds", "No"), ("Bond Duration", ""), ("Bond Amount", "0"))}
{row(("1st Year CTC", "2215000"))}
{row(("Is there a CGPA Criteria?", "Yes"), ("If Yes, minimum CGPA required", "7.5"))}
{row(("Backlog Eligibility", "Candidates should not have any active backlogs."))}
<h4>Selection Details</h4>
{row(("Shortlist from resumes", "No"), ("Written Test", "Yes"), ("If Yes, Mode", "Online"))}
</div></body></html>"""


def test_more_details_layout():
    d = parse_more_details(PAGE)
    assert d["fields"]["1st Year CTC"] == "2215000"
    assert d["fields"]["Fixed Take Home Salary (per Annum)"] == "1500000"
    assert d["backlog_rule"] == "Candidates should not have any active backlogs."
    assert backlog_allows(d["backlog_rule"]) is False
    assert d["min_cgpa"] == "7.5"
    assert d["selection_details"] == {"Shortlist from resumes": "No", "Written Test": "Yes", "If Yes, Mode": "Online"}
    assert d["has_written_test"] is True


def test_no_written_test_and_na_backlog():
    page = PAGE.replace("<b>Yes</b></div> </div><div class=\"col-xs-3 text-left\"> <div>If Yes, Mode",
                        "<b>No</b></div> </div><div class=\"col-xs-3 text-left\"> <div>If Yes, Mode")
    page = page.replace("Candidates should not have any active backlogs.", "N/A")
    d = parse_more_details(page)
    assert d["has_written_test"] is False
    assert backlog_allows(d["backlog_rule"]) is None
