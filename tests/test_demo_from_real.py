"""The anonymiser: your details become fake ones, other students disappear, links survive."""

from ping.demo_from_real import FAKE_ROLL, Scrubber, _fake_row, verify

ME, NAME, MAIL = "23ZZ99999", "Asha Verma", "asha@example.com"


def scrub(t):
    return Scrubber(ME, NAME, MAIL).text(t)


def test_offer_lists_and_contacts_are_removed():
    t = ("Acme has extended the offer to the following student(s):[name] [name] - 22XY00000[name] [name] - 22XY00000"
         "The students are advised to accept.POCs: [name] (+91 9000000000), [name] (9000000000)")
    out = scrub(t)
    for gone in ("[name]", "[name]", "22XY00000", "[name]", "22XY00000", "[name]", "90000", "[name]", "9000000000"):
        assert gone not in out, gone
    assert "Acme has extended the offer" in out and "[contact removed]" in out


def test_back_to_back_roll_lists():
    out = scrub("Shortlist: 23CH3001023CH3002022EE10011 end")
    assert "CH300" not in out and "EE100" not in out


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
    assert verify({"x": "someone 22XY00000"}, ME, MAIL, NAME)
    assert verify({"x": "call 9876543210"}, ME, MAIL, NAME)
