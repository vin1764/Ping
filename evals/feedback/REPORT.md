# Feedback evals

Run Sun 22 Nov 23:31 UTC against the deployed `ask-ping` function, one demo session per run (anonymised demo data), the evals keys. Feedback is decided by rules, never by a model.

- **Model on: 12/12. Model off (no_ai): 12/12.** Same answer both ways: 11/12.
- The hide is saved (read back from the session's lists): yes (model on), yes (model off).

| case | message | model on | model off | answer (model on) |
|---|---|---|---|---|
| L1 the 23 Nov message, demo companies: a reply, two typos | `navy not relevantt for me` | ok | ok | Got it, Navi won't show as For you anymore. [Undo](#ask:undo) |
| L2 plain, a company | `Groww is not relevant` | ok | ok | Got it, Groww won't show as For you anymore. [Undo](#ask:undo) |
| L3 not interested in X | `not interested in moneyview` | ok | ok | Got it, Moneyview won't show as For you anymore. [Undo](#ask:undo) |
| L4 hide X, as a reply | `hide diageo` | ok | ok | Got it, Diageo won't show as For you anymore. [Undo](#ask:undo) |
| L5 one role | `ignore navi sde` | ok | ok | Got it, Navi — SDE-1 won't show as For you anymore. [Undo](#ask:undo) |
| L6 a role, in a sentence | `the data scientist role at moneyview is not for me` | ok | ok | Got it, Moneyview — Data Scientist won't show as For you anymore. [Undo](#ask:undo) |
| L7 a reply naming no company: one question with buttons | `not relevant` | ok | ok | Hide which one from For you? [Navi](#ask:hide%20Navi) [Diageo](#ask:hide%20Diageo) [Moneyview](#ask:hide%20Moneyview) [None](#ask:never%20mi |
| L8 remove X, a typo | `remove grow` | ok | ok | Got it, Groww won't show as For you anymore. [Undo](#ask:undo) |
| L9 show X again | `show navi again` | ok | ok | Got it, Navi will show as For you. [Undo](#ask:undo) |
| L10 X is relevant | `slice is relevant` | ok | ok | Got it, slice will show as For you. [Undo](#ask:undo) |
| L11 undo the last one | `undo` | ok | ok | Undone: slice is back to how it was. |
| L12 a question stays a question | `is groww relevant for me?` | ok | ok | Groww (Associate Product Manager) is relevant to your targets, but the deadline of Mon 16 Nov 16:00 has already passed.

Pay components:
- F |
