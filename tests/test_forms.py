"""The forms list (ping/forms.py): one row per form whatever the notice or mail around it says, reposts and extensions
merged with their history, ticks that silence reminders."""

from datetime import datetime, timedelta

from ping import forms, push
from ping.config import IST

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=IST)
G = "https://docs.google.com/forms/d/e/1FAIpQLSdTestForm0123456789/viewform"


def todo(iid, company, link, due, *, notice=None, mail=None, subject="Additional requirement form", level="show"):
    d = {"todo": {"action": "fill_form", "link": link, "due": due}, "subject": subject}
    if link:
        d["forms"] = [link]
    if notice:
        d["notice_time"] = notice[1]
    if mail:
        d["mail"] = {"id": mail[0], "received_at": mail[1], "link": link}
        d["via"] = "email" if not notice else None
    return {"id": iid, "category": "todo", "company": company, "title": f"{company}: fill the form by {due}.",
            "due_at": due, "level": level, "notice_id": notice[0] if notice else None, "role_ids": [], "details": d}


def test_canonical_keys_whatever_the_wrapping():
    assert forms.key_of(G + "?usp=sf_link") == forms.key_of(G) == forms.key_of(G.replace("viewform", "formResponse"))
    assert forms.key_of("https://docs.google.com/forms/d/1AbCdEfGhIjKlMnOp/edit#responses") == "gform:1AbCdEfGhIjKlMnOp"
    assert forms.key_of("https://forms.office.com/Pages/ResponsePage.aspx?id=AbC123xyz&embed=true") == "msform:AbC123xyz"
    assert forms.key_of("https://forms.zohopublic.in/acme/form/Reg/formperma/aBcDeFgHiJkL?x=1") == "zoho:aBcDeFgHiJkL"
    assert forms.key_of("https://acme.typeform.com/to/AbC123?utm=x") == "typeform:AbC123"
    assert forms.key_of("https://form.jotform.com/231234567890123") == "jotform:231234567890123"
    assert forms.key_of("mailto:cdc@example.com") is None
    # a short link is followed to the form it points to (no cookies, nothing submitted)
    final, key = forms.resolve("https://forms.gle/AbCdEf123", fetch=lambda u: G + "?usp=send_form")
    assert key == forms.key_of(G)


def test_the_same_form_by_notice_and_by_mail_is_one_row_with_both_sources():
    items = [todo("notice:1791:todo0", "Groww", G, "2026-11-21T20:00:00+05:30", notice=("1791", "2026-11-20T10:00:00+05:30")),
             todo("mail:m1", "Groww", G + "?usp=sf_link", "2026-11-21T20:00:00+05:30", mail=("m1", "2026-11-20T11:00:00+05:30"))]
    rows = forms.build(items, now=NOW)
    assert len(rows) == 1
    r = rows[0]
    assert [s["type"] for s in r["sources"]] == ["notice", "mail"]
    assert r["item_ids"] == ["notice:1791:todo0", "mail:m1"]
    assert r["purpose"] == "additional requirement"


def test_a_repost_with_a_later_deadline_moves_it_and_keeps_the_history():
    items = [todo("notice:1791:todo0", "Groww", G, "2026-11-21T20:00:00+05:30", notice=("1791", "2026-11-20T10:00:00+05:30")),
             todo("notice:1796:todo0", "Groww", G, "2026-11-22T20:00:00+05:30", notice=("1796", "2026-11-21T09:00:00+05:30"))]
    r = forms.build(items, now=NOW)[0]
    assert r["due_at"] == "2026-11-22T20:00:00+05:30"
    assert r["deadline_history"] == [{"from": "2026-11-21T20:00:00+05:30", "to": "2026-11-22T20:00:00+05:30",
                                      "at": "2026-11-21T09:00:00+05:30", "source": {"type": "notice", "id": "1796", "at": "2026-11-21T09:00:00+05:30"}}]
    assert [s["id"] for s in r["sources"]] == ["1791", "1796"]
    # a later run keeps the history and the first-seen time
    again = forms.build(items[1:], previous={r["key"]: r}, now=NOW + timedelta(hours=1))[0]
    assert again["deadline_history"] == r["deadline_history"] and again["first_seen"] == r["first_seen"]
    assert {s["id"] for s in again["sources"]} == {"1791", "1796"}


def test_two_different_forms_from_one_company_stay_apart():
    other = "https://docs.google.com/forms/d/e/1FAIpQLSdOtherForm987654321/viewform"
    items = [todo("n1:todo0", "Groww", G, "2026-11-21T20:00:00+05:30", notice=("1", "2026-11-20T10:00:00+05:30"), subject="Registration form"),
             todo("n2:todo0", "Groww", other, "2026-11-21T20:00:00+05:30", notice=("2", "2026-11-20T11:00:00+05:30"), subject="Test slot preference form")]
    rows = forms.build(items, now=NOW)
    assert len(rows) == 2
    assert {r["purpose"] for r in rows} == {"registration", "test slot"}


def test_a_ticked_form_gets_no_mail_reminder_and_the_queue_row_carries_its_key():
    due = (NOW + timedelta(hours=5)).isoformat()
    it = todo("mail:m9", "Axon", "https://example.com/forms/axon", due, mail=("m9", NOW.isoformat()))
    it["details"]["via"] = "email"
    rows = forms.build([it], now=NOW)
    forms.mark_items([it], rows, filled=set())
    q = push.mail_reminders([it], {"reminder_hours": 2}, NOW)
    assert len(q) == 1 and q[0]["form_key"] == rows[0]["key"]          # send-push re-checks the tick at send time
    forms.mark_items([it], rows, filled={rows[0]["key"]})
    assert it["details"]["form"]["filled"] is True
    assert push.mail_reminders([it], {"reminder_hours": 2}, NOW) == []


def test_only_your_own_ticks_count():
    assert forms.filled_keys([{"form_key": "a", "filled": True, "is_demo": False}, {"form_key": "b", "filled": True, "is_demo": True},
                              {"form_key": "c", "filled": False, "is_demo": False}]) == {"a"}


def test_purposes():
    assert forms.purpose_of("Registration form for Groww") == "registration"
    assert forms.purpose_of("PPT RSVP: Slice") == "PPT RSVP"
    assert forms.purpose_of("CV Submission", "submit your CV") == "CV submission"
    assert forms.purpose_of("Test slot booking") == "test slot"
    assert forms.purpose_of("Fill the form") == "form"


def test_form_pages_closed_signin_and_short_links():
    from ping import form_pages
    closed = form_pages.parse("<html><title>Kite reg</title><body>This form is no longer accepting responses.</body></html>",
                              "https://docs.google.com/forms/d/e/x/closedform")
    assert closed["closed"] and closed["title"] == "Kite reg"
    signin = form_pages.parse("<html>Sign in</html>", "https://accounts.google.com/v3/signin/identifier?continue=x")
    assert signin["signin_required"] and not signin["closed"]
    # a short link is followed to the form and stops there (never on to a sign-in page), cached by its own key
    calls = []

    def get(url, stop=None):
        calls.append(url)
        return G + "?usp=send_form", ""
    r = form_pages.Reader({}, get=get, now=NOW)
    assert forms.key_of(r.follow("https://forms.gle/Zz9")) == forms.key_of(G)
    r.follow("https://forms.gle/Zz9")
    assert len(calls) == 1 and r.stats["cached"] == 1
    # only public web addresses
    assert not form_pages._allowed("http://127.0.0.1/x") and not form_pages._allowed("http://localhost/x")


def test_a_repost_in_the_chat_is_one_line_on_the_first_message():
    from ping.dedupe import dedupe
    first = todo("notice:1791:0:todo0", "Groww", G, "2026-11-21T20:00:00+05:30", notice=("1791", "2026-11-20T10:00:00+05:30"))
    again = todo("notice:1796:0:todo0", "Groww", G + "?usp=sf_link", "2026-11-22T20:00:00+05:30", notice=("1796", "2026-11-21T09:00:00+05:30"))
    other = todo("notice:1797:0:todo0", "Groww", "https://docs.google.com/forms/d/e/1FAIpQLSdOtherForm987654321/viewform",
                 "2026-11-23T20:00:00+05:30", notice=("1797", "2026-11-21T10:00:00+05:30"), subject="Test slot form")
    out, stats = dedupe([first, again, other], NOW)
    assert again["level"] == "hidden" and first["level"] != "hidden" and first["due_at"] == "2026-11-22T20:00:00+05:30"
    assert first["details"]["extended"][0]["to"] == "2026-11-22T20:00:00+05:30"
    assert not any(":update:" in i["id"] for i in out)                     # no new "Update" message
    assert other["level"] != "hidden"                                      # a different form from Groww stays
    assert stats["form_extensions"] == 1


# ---------------------------------------------------------------------------- 22 Nov: notice 1815 (anonymised)
CO = ["Lattice Co", "ICOR LOMBARD", "AMARIX PRIVATE LIMITED", "Teal General Insurance", "Pira Finance", "JOVIS",
      "Aster Energy", "Aura Group(www.AuraIM.com)", "Finaro", "SLX", "BlueBuck"]
LINKS = [f"https://forms.gle/Form{i:02d}abcdEFGH" for i in range(9)]


OWN = {t: min(t, 8) for t in range(len(CO))}       # companies 0-7 a form each; 8, 9 and 10 share the 9th


def notice_1815(own=True):
    """One notice: 'Additional requirement' for 11 companies with their own forms (9 links; the last three companies
    share one). The notice reader gives each company its own form (ping/notices.py link_owners). own=False: what it
    did before, every company a to-do per link. The same notice by mail, with the first company's link."""
    out = []
    for t, co in enumerate(CO):
        for k, link in enumerate(LINKS):
            if own and OWN[t] != k:
                continue
            it = todo(f"notice:1815:{t}:todo{k}", co, link, "2026-11-22T20:00:00+05:30", notice=("1815", "2026-11-22T10:35:00+05:30"),
                      subject="Additional requirement")
            it["details"]["forms"] = list(LINKS)
            out.append(it)
    mail = todo("mail:m1815", CO[0], LINKS[0], "2026-11-22T20:00:00+05:30", mail=("m1815", "2026-11-22T10:40:00+05:30"),
                subject="Additional requirement")
    mail["details"]["forms"] = list(LINKS)
    return out + [mail]


def test_a_notice_with_a_form_per_company_is_one_row_per_form():
    rows = forms.build(notice_1815(), fetch=lambda u: u, now=NOW)
    assert len(rows) == 9 and all(forms.stored(r)["looks_like"] == [] for r in rows)
    by_link = {r["link"]: r for r in rows}
    assert by_link[LINKS[0]]["companies"] == [CO[0]]
    assert [(s["type"], s["id"]) for s in by_link[LINKS[0]]["sources"]] == [("notice", "1815"), ("mail", "m1815")]
    assert sorted(by_link[LINKS[8]]["companies"]) == sorted(CO[8:])
    # the same notice the next day with a later deadline, companies in another order: the same 9 rows, moved
    again = [dict(i, id=i["id"].replace("1815", "1820"), details={**i["details"], "notice_time": "2026-11-23T09:00:00+05:30",
             "todo": {**i["details"]["todo"], "due": "2026-11-23T20:00:00+05:30"}}, notice_id="1820", due_at="2026-11-23T20:00:00+05:30")
             for i in reversed(notice_1815()[:-1])]
    rows2 = forms.build(notice_1815() + again, previous={r["key"]: r for r in rows}, fetch=lambda u: u, now=NOW)
    assert sorted(r["key"] for r in rows2) == sorted(r["key"] for r in rows)
    assert all(r["due_at"] == "2026-11-23T20:00:00+05:30" and len(r["deadline_history"]) == 1 for r in rows2)


def test_two_different_links_are_never_one_form():
    a = todo("notice:1:todo0", "Groww", "https://forms.gle/AAAA1111", "2026-11-22T20:00:00+05:30", notice=("1", "2026-11-21T10:00:00+05:30"),
             subject="LTM | Additional Details Form")
    b = todo("notice:2:todo0", "Groww", "https://forms.gle/BBBB2222", "2026-11-22T20:00:00+05:30", notice=("2", "2026-11-21T11:00:00+05:30"),
             subject="LTM | Additional Details Form")
    pages = {"short:forms.gle/AAAA1111": {"title": "LTM | Additional Details Form"}, "short:forms.gle/BBBB2222": {"title": "LTM | Additional Details Form"}}
    rows = forms.build([a, b], pages=pages, fetch=lambda u: u, now=NOW)
    assert len(rows) == 2
    # the old reading, every company a to-do per link, can't chain them either: still one row per link
    rows = forms.build(notice_1815(own=False), fetch=lambda u: u, now=NOW)
    assert len(rows) == 9 and all(len(r["form_keys"]) == 1 for r in rows)


def test_an_over_merged_row_splits_and_the_tick_stays_with_the_form_it_showed():
    items = notice_1815()
    keys = [forms.key_of(l) for l in LINKS]
    old_key = "notice:1815"
    old = {old_key: {"key": old_key, "first_seen": "2026-11-22T10:35:00+05:30", "title": "LTM | Additional Details Form",
                     "link": LINKS[0], "item_ids": [i["id"] for i in items], "merged_keys": keys,
                     "deadline_history": [{"from": "x", "to": "y"}]}}
    pages = {k: {"title": f"Form {n}"} for n, k in enumerate(keys)}
    pages[keys[3]] = {"title": "LTM | Additional Details Form"}          # the form that was shown on the merged row
    rows = forms.build(items, previous=old, pages=pages, fetch=lambda u: u, now=NOW)
    assert len(rows) == 9 and len({r["key"] for r in rows}) == 9
    kept = [r for r in rows if r["key"] == old_key]
    assert len(kept) == 1 and kept[0]["companies"] == [CO[3]]            # by its page title
    assert all(r["deadline_history"] == [] for r in rows)                # the old row's mixed history isn't copied
    ticks = [{"owner_id": "me", "form_key": old_key, "filled": True, "filled_at": "x", "is_demo": False}]
    assert forms.carry_ticks(ticks, old, rows) == []                     # the tick stays on that one row only
    assert forms.filled_keys(ticks) & {r["key"] for r in rows} == {old_key}


def test_link_owners_reads_a_form_per_company():
    from ping.notices import link_owners
    text = ("Additional requirement. 1. RISA Labs: https://forms.gle/RisaA1 2. Diageo and Finaro: https://forms.gle/DiagB2 "
            "3. Pira Finance https://forms.gle/PiraC3")
    t = [{"name": "RISA Labs"}, {"name": "Diageo"}, {"name": "Finaro"}, {"name": "Pira Finance"}]
    own = link_owners(text, ["https://forms.gle/RisaA1", "https://forms.gle/DiagB2", "https://forms.gle/PiraC3"], t)
    assert own == {"https://forms.gle/RisaA1": [0], "https://forms.gle/DiagB2": [1, 2], "https://forms.gle/PiraC3": [3]}
    # one form for everyone: every company gets it
    assert link_owners("Fill https://forms.gle/One1 RISA Labs Diageo", ["https://forms.gle/One1"], t[:2]) == {"https://forms.gle/One1": None}


def test_the_form_page_title_says_whose_form_it_is():
    """23 Nov: a notice gave 13 companies 13 links with no way to tell them apart in the text; each form's title names
    its company ('RISA LABS | Preference Form'). The row gets that company only; the others' to-dos for it are hidden."""
    items = notice_1815(own=False)
    keys = [forms.key_of(l) for l in LINKS]
    names = ["Lattice Co | Additional Details Form", "ICOR LOMBARD | Additional Details Form", "AMARIX | Preference Form",
             "Teal General Insurance | Additional Details", "Pira Finance | Preference Form", "Jovis | Additional Details Form",
             "Aster Energy | Additional Details Form", "Aura Group | Preference Form", "Finaro | Preference Form"]
    pages = {k: {"title": t} for k, t in zip(keys, names)}
    rows = forms.build(items, pages=pages, fetch=lambda u: u, now=NOW)
    by_link = {r["link"]: r for r in rows}
    assert [by_link[l]["companies"] for l in LINKS] == [[c] for c in CO[:9]]
    assert sorted(by_link[LINKS[0]]["item_ids"]) == ["mail:m1815", "notice:1815:0:todo0"]
    forms.mark_items(items, rows, set())
    shown = [i for i in items if i["level"] != "hidden"]
    assert len(shown) == 9 + 1 + 2 * 9                     # each company its own form; 9 and 10 named in no title keep all
    assert all(i["details"].get("hidden_because") == "another company's form in the same notice" for i in items if i["level"] == "hidden")
