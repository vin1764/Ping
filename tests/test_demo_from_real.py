"""The anonymiser: your details become fake ones, other students disappear, links survive."""

from ping.demo_from_real import FAKE_ROLL, Scrubber, _fake_row, verify

ME, NAME, MAIL = "23ZZ99999", "Asha Verma", "asha@example.com"


def scrub(t):
    return Scrubber(ME, NAME, MAIL).text(t)


def test_offer_lists_and_contacts_are_removed():
    # made-up names, rolls and numbers, in the glued layout real CDC notices use
    t = ("Acme has extended the offer to the following student(s):TESTA PERSONA - 22XY10051Dummy Namesake - 22XY10052"
         "The students are advised to accept.POCs: Coordinator Alpha (+91 90000 12345), Coordinator Beta (9000012346)")
    out = scrub(t)
    for gone in ("TESTA", "PERSONA", "22XY10051", "Dummy", "22XY10052", "Alpha", "12345", "Beta", "9000012346", "+91"):
        assert gone not in out, gone
    assert "Acme has extended the offer" in out and "POCs: [contact removed]" in out


def test_phone_numbers_in_any_grouping_are_removed():
    for phone in ("+91 900 001 2347", "9000 012 348", "(+91) 90000-12349", "0 90000 12350", "91 9000012351",
                  "+919000012352", "900.001.2353"):
        out = scrub(f"call {phone} today")
        assert not any(ch.isdigit() for ch in out) and "+91" not in out, (phone, out)
    assert scrub("Notice time 21-11-2026 00:07") == "Notice time 21-11-2026 00:07"  # a date is not a phone


def test_names_on_contact_lines_go_but_the_role_word_stays():
    out = scrub("For queries, Placement coordinator: Sample Person (+91 90000 12354)\n\nCDC, IIT Kharagpur")
    assert out.startswith("For queries, Placement coordinator: [contact removed]") and "Sample" not in out
    out = scrub("POC: Testname [contact removed], [contact removed]CDC, IIT Kharagpur")
    assert out == "POC: [contact removed]CDC, IIT Kharagpur"


def test_meetings_and_recruiting_emails_are_removed():
    t = ("PPT at 6 PM. Link: https://acme.zoom.us/j/90000123?pwd=abc Meeting ID: 900 0012 3456\nPasscode: Xy12Ab\n"
         "Also meet.google.com/abc-defg-hij or teams.microsoft.com/meet/123?p=Q. Mail hiring@acme-test.com")
    out = scrub(t)
    assert "zoom.us" not in out and "meet.google" not in out and "teams.microsoft" not in out
    assert "Meeting ID: [removed]" in out and "Passcode: [removed]" in out and "Xy12Ab" not in out
    assert "careers@example.com" in out and "acme-test.com" not in out
    glued = scrub("held at 1 PM.Link: https://teams.microsoft.com/meet/123?p=QMeeting ID: 900 111 222 333 444Passcode: Ab12CdAll")
    assert "900 111" not in glued and "Ab12Cd" not in glued and "ID: [removed]" in glued, glued
    assert "https://forms.gle/AB12CD34EF56" in scrub("form https://forms.gle/AB12CD34EF56")  # other links stay


def test_back_to_back_roll_lists():
    out = scrub("Shortlist: 22XY1005122XY1005222XY10053 end")
    assert "XY1005" not in out


def test_my_details_become_fake_and_links_survive():
    out = scrub(f"You ({ME}, {NAME}, {MAIL}) fill https://forms.gle/AB12CD34EF56 by 4 PM. Cut-off 8.5 is above your 7.9")
    assert FAKE_ROLL in out and "Demo Student" in out and "[email removed]" in out
    assert "https://forms.gle/AB12CD34EF56" in out
    assert "7.9" not in out and "your CGPA" in out


def test_my_pdf_row_gets_the_fake_name():
    assert _fake_row(["Roll No", "Name", "Room"], [FAKE_ROLL, "ASHA VERMA", "V2"]) == [FAKE_ROLL, "DEMO STUDENT", "V2"]
    assert _fake_row(["Roll No", "Room No"], [FAKE_ROLL, "NC231"]) == [FAKE_ROLL, "NC231"]


def test_verify_catches_leftovers():
    assert verify({"x": "fine text"}, ME, MAIL, NAME) == []
    assert verify({"x": f"roll {ME}"}, ME, MAIL, NAME)
    assert verify({"x": "someone 22XY10055"}, ME, MAIL, NAME)
    assert verify({"x": "call 9000012356"}, ME, MAIL, NAME)


def test_final_check_fails_the_build_on_any_leftover():
    from ping.demo_from_real import DENYLIST, final_check
    assert final_check({"x": "fine text, deadline 21-11-2026 16:00, CTC 2800000"}) == []
    assert final_check({"x": "landline 3222 28 2001"})             # any ten-digit number
    assert final_check({"x": "call +91 now"})                     # a stray +91
    assert final_check({"x": "https://example.org/?id=9000012357"})  # links are checked too
    for name in DENYLIST:
        assert final_check({"x": f"contact {name.lower()} please"}), name
    assert final_check({"x": "ID: 900 111 222 333 444"}) and final_check({"x": "Passcode: Ab12Cd"})
    assert final_check({"x": "mail hr@acme-test.com"}) and not final_check({"x": "mail careers@example.com"})


def test_the_fake_roll_itself_survives():
    assert scrub(f"roll {FAKE_ROLL}") == f"roll {FAKE_ROLL}"
