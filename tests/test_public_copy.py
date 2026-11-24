"""The public source copy (ping/public_copy.py): what history-only values it finds to replace."""
def test_roll_numbers_and_their_holders_are_found():
    # made-up values in the glued layout real offer notices use
    from ping.public_copy import HOLDER_RE, ROLL_RE
    t = "offer to the following student(s):TESTA PERSONA - 24QA10001Dummy Namesake - 24QB10002The students"
    assert ROLL_RE.findall(t) == ["24QA10001", "24QB10002"]
    assert [m.group(1) for m in HOLDER_RE.finditer(t)] == ["TESTA PERSONA", "Dummy Namesake"]
