"""Card lines (ping/summaries.py): the type label, the fact check, the rules' line, and a run's model calls (faked)."""

from datetime import datetime

from ping import summaries as S
from ping.config import IST

DUE = "2026-11-27T23:59:00+05:30"
RISA_TEXT = ("Urgent\n[URGENT] | RISA LABS | All students who are eligible and have applied for the APM - Growth and APM - Growth (US) "
             "roles must fill the form below by 27th November 2026, 11:59 PM: https://forms.gle/risa. Shortlisted students will "
             "also submit the assignment by the same deadline.")


def item(**kw):
    base = {"id": "notice:2026-2027:1874:0", "category": "info", "company": "RISA Labs", "level": "always",
            "title": "RISA Labs update (Urgent): All students who are eligible and have applied for the APM - Growth ...",
            "first_seen": "2026-11-25T00:37:00+00:00", "details": {}}
    base.update(kw)
    return base


def test_labels_are_the_type_not_update():
    assert S.label(item(category="todo", details={"todo": {"action": "fill_form"}})) == "Form"
    assert S.label(item(category="todo", details={"todo": {"action": "submit", "task": "assignment"}})) == "Assignment"
    assert S.label(item(category="todo", details={"todo": {"action": "submit", "task": "cv"}})) == "CV submission"
    assert S.label(item(category="deadline", title="BLUESTONE (3 roles) deadline extended to Mon 23 Nov 20:00")) == "Deadline change"
    assert S.label(item(category="shortlist")) == "Shortlist"
    assert S.label(item(category="test", details={"kind": "test"})) == "Test"
    assert S.label(item()) == "Info"


def test_the_check_keeps_a_faithful_line_and_rejects_invented_facts():
    it = item(due_at=DUE)
    assert S.check("APM Growth applicants: fill this form by Fri 27 Nov 23:59.", RISA_TEXT, it) is None
    assert S.check("APM Growth applicants: fill this form by Fri 28 Nov 23:59.", RISA_TEXT, it).startswith("date not")
    assert S.check("APM Growth applicants: fill this form by Fri 27 Nov 18:00.", RISA_TEXT, it).startswith("time not")
    assert S.check("SDE applicants: fill this form by Fri 27 Nov 23:59.", RISA_TEXT, it).startswith("name not")
    assert S.check("Fill https://forms.gle/other by Fri 27 Nov 23:59.", RISA_TEXT, it).startswith("link not")
    assert S.check("50 applicants: fill this form by Fri 27 Nov 23:59.", RISA_TEXT, it).startswith("number not")
    assert S.check("x" * 120, RISA_TEXT, it).startswith("too long")
    assert S.check("APM Growth applicants must fill the form…", RISA_TEXT, it) == "cut short"


def test_the_rules_line_is_whole_and_clean():
    todo = item(category="todo", due_at=DUE, details={"todo": {"action": "submit", "task": "assignment"}})
    assert S.rules_line(todo, RISA_TEXT) == "Submit the assignment by Fri 27 Nov 23:59."
    info = S.rules_line(item(), RISA_TEXT)
    assert "…" not in info and "[URGENT]" not in info and "|" not in info and not info.upper().startswith("RISA")
    assert len(info) <= S.MAX_CHARS and info.endswith((".", "!", "?"))
    moved = item(category="deadline", due_at="2026-11-23T20:00:00+05:30", title="BLUESTONE (3 roles) deadline extended to Mon 23 Nov 20:00")
    assert S.rules_line(moved, "") == "Deadline moved to Mon 23 Nov 20:00."
    assert S.rules_line(item(category="shortlist", pdf_status="no"), "") == "The shortlist is out: check it for your name."


class FakeWriter(S.Writer):
    def __init__(self, answers, **kw):
        super().__init__(groq_key="g", budget=kw.get("budget", 20), sleep=lambda s: None)
        self.answers = list(answers)
        self.prompts = []

    def call(self, prompt):
        self.budget -= 1
        self.prompts.append(prompt)
        a = self.answers.pop(0) if self.answers else None
        return (a, "groq") if a else None


def test_a_run_writes_lines_yours_first_falls_back_and_keeps_them():
    mine = item(id="a", level="always", due_at=DUE)
    other = item(id="b", level="show", company="Other Co", title="Other Co: pre-placement talk on Fri 27 Nov 18:00")
    notices = {"2026-2027:1874": {"subject": "Urgent", "text": RISA_TEXT}}
    mine["details"]["notice_key"] = "2026-2027:1874"
    w = FakeWriter(["APM Growth applicants: fill this form by Fri 27 Nov 23:59.", "Join the talk at 9 PM on Sat 28 Nov."])
    stats = S.apply([other, mine], {}, notices, {}, w, log=lambda *_: None)
    assert "RISA Labs" in w.prompts[0]                                   # yours first
    assert mine["details"]["summary"] == "APM Growth applicants: fill this form by Fri 27 Nov 23:59."
    assert mine["details"]["summary_by"] == "groq" and mine["details"]["label"] == "Info"
    assert other["details"]["summary_by"] == "rules" and other["details"]["summary_why"].startswith(("time not", "date not"))
    assert stats["model"] == 1 and stats["rejected"] == 1
    # the next run keeps them (no call), until the text changes
    w2 = FakeWriter([])
    S.apply([dict(mine, details={"notice_key": "2026-2027:1874"})], {"a": mine}, notices, {}, w2, log=lambda *_: None)
    assert w2.prompts == []


def test_no_room_left_means_the_rules_line_now_and_the_model_next_run():
    it = item(id="c", due_at=DUE, details={"notice_key": "k"})
    w = FakeWriter(["x"], budget=0)
    S.apply([it], {}, {"k": {"text": RISA_TEXT}}, {}, w, log=lambda *_: None)
    assert it["details"]["summary_by"] == "rules" and it["details"]["summary_pending"] is True
    w2 = FakeWriter(["APM Growth applicants: fill this form by Fri 27 Nov 23:59."])
    nxt = item(id="c", due_at=DUE, details={"notice_key": "k"})
    S.apply([nxt], {"c": it}, {"k": {"text": RISA_TEXT}}, {}, w2, log=lambda *_: None)
    assert nxt["details"]["summary_by"] == "groq"


def test_the_date_format_matches_the_cards():
    assert S.fmt(DUE) == "Fri 27 Nov 23:59"
    assert S.fmt(datetime(2026, 12, 3, 9, 5, tzinfo=IST).isoformat()) == "Thu 3 Dec 09:05"
