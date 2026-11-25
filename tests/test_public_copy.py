"""The public source copy (ping/public_copy.py): what history-only values it finds to replace."""
def test_roll_numbers_and_their_holders_are_found():
    # made-up values in the glued layout real offer notices use
    from ping.public_copy import HOLDER_RE, ROLL_RE
    t = "offer to the following student(s):TESTA PERSONA - 24QA10001Dummy Namesake - 24QB10002The students"
    assert ROLL_RE.findall(t) == ["24QA10001", "24QB10002"]
    assert [m.group(1) for m in HOLDER_RE.finditer(t)] == ["TESTA PERSONA", "Dummy Namesake"]


def test_made_up_numbers_stay_and_a_group_is_never_replaced_inside_a_longer_number():
    import re
    from ping.public_copy import _fake
    assert _fake("9876543210") and _fake("98765 43210") and _fake("9000012345") and _fake("9999999999")
    assert not _fake("9123456780")
    # the copy's rule for a history number's group "9876": only where it stands alone
    rule = re.compile(r"(?<![0-9])" + re.escape("9876") + r"(?![0-9])")
    assert not rule.search("Contact: hr@x.example, 98765 43210") and rule.search("call 9876 now")
