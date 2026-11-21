# Decisions

Judgement calls made while working unattended, one line each.

- 2026-11-21 19:30 IST: Two requests were open (make Ping generic + preferences by chat, then CV upload ... reviewer run). Done in this order: genericity, preferences by chat with per-profile classification (the reviewer run needs both), then the new parts in order; anything not reached by 21:45 IST is listed in the handoff as not done.
- 2026-11-21 19:30 IST: The demo persona's targets live only in `evals/relevance/personas.json` (a made-up student); the demo build and the tests read them from there. Examples in the README, the classifier docstring and the Profile placeholder are neutral.
- 2026-11-21 19:30 IST: Kept: department names in test fixtures and the made-up sample student (`ping/sample.py`), and Axis Bank's allowed departments in an Ask Ping eval: they are ERP facts or fictional fixtures, not a real student's data.
- 2026-11-21 19:30 IST: Kept: the owner's live URL and repo names in the README (they describe this deployment; a copy gets its own).
