"""Admin summaries-backfill: open and last-7-days cards get their line and type; only details change (no post, no push)."""

from datetime import datetime, timedelta, timezone

from ping import admin

NOW = datetime.now(timezone.utc)


class Store:
    def __init__(self, *a):
        soon = (NOW + timedelta(days=2)).isoformat()
        old = (NOW - timedelta(days=30)).isoformat()
        self.rows = {"items": [
            {"id": "notice:2026-2027:1874:0", "category": "todo", "company": "RISA Labs", "level": "always", "notice_id": 1874,
             "title": "RISA Labs: submit the assignment by Fri 27 Nov 23:59", "due_at": soon, "first_seen": old,
             "details": {"todo": {"action": "submit", "task": "assignment"}, "notice_key": "2026-2027:1874"}, "is_sample": False},
            {"id": "notice:2026-2027:1900:0", "category": "info", "company": "Other Co", "level": "show", "notice_id": 1900,
             "title": "Other Co update (Urgent): [URGENT] | OTHER CO | Venue changed", "first_seen": NOW.isoformat(),
             "details": {}, "is_sample": False},
            {"id": "notice:2026-2027:1000:0", "category": "info", "company": "Old Co", "level": "show", "notice_id": 1000,
             "title": "Old Co: something", "first_seen": old, "details": {}, "is_sample": False}],
            "notices": [{"id": "2026-2027:1874", "notice_id": 1874, "subject": "Urgent", "text": "Shortlisted students must submit the assignment by 27th November 2026, 11:59 PM."},
                        {"id": "2026-2027:1900", "notice_id": 1900, "subject": "Venue", "text": "[URGENT] | OTHER CO | The venue for the talk has changed to Room 101. Please be on time."}],
            "emails": []}
        self.patches = []

    def select(self, table, filters=None, columns="*"):
        if table == "items":
            return [r for r in self.rows["items"] if (filters or {}).get("is_sample") != "is.true"]
        return list(self.rows.get(table, []))

    def _req(self, method, table, params=None, json=None, headers=None):
        assert method == "PATCH" and table == "items" and set(json) == {"details"}
        self.patches.append((params["id"].removeprefix("eq."), json["details"]))


def test_backfill_writes_lines_silently(monkeypatch, capsys):
    st = Store()
    monkeypatch.setattr(admin, "SupabaseStore", lambda *a: st)
    monkeypatch.setenv("SUMMARY_CALLS", "0")

    class Sec:
        supabase_url, supabase_key = "x", "y"
    assert admin.summaries_backfill(Sec) == 0
    got = dict(st.patches)
    assert set(got) == {"notice:2026-2027:1874:0", "notice:2026-2027:1900:0"}       # the 30-day-old closed card is left
    assert got["notice:2026-2027:1874:0"]["label"] == "Assignment"
    line = got["notice:2026-2027:1900:0"]["summary"]
    assert "[URGENT]" not in line and "|" not in line and line.endswith(".")
    assert "no message posted, no push" in capsys.readouterr().out
