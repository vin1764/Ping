

def test_feedback_lists_decide_for_you():
    """'X not relevant' / 'Y is relevant' said in the chat (profile lists) win over Ping's own marks."""
    from ping.items import pinned
    p = {"hidden_roles": ["r3"], "shown_roles": ["r9"], "not_interested_companies": ["Piramal Finance"],
         "interested_companies": ["Zeta"]}
    assert pinned({"id": "r3", "company": "Zeta"}, p) is False          # a hidden role, even at an always-shown company
    assert pinned({"id": "r9", "company": "Piramal Finance Limited"}, p) is True
    assert pinned({"id": "r1", "company": "PIRAMAL FINANCE LIMITED"}, p) is False
    assert pinned({"id": "r2", "company": "Zeta"}, p) is True
    assert pinned({"id": "r5", "company": "Groww"}, p) is None
