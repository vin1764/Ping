# Forms evals

Run Sun 22 Nov 17:41 IST. **15/15 postings** land in the right form with the right deadline, history, sources, closed / sign-in state and 'looks like' offer; reposts in the chat: 2/2 are one 'deadline extended' line on the existing message (no new message).

Form pages read: {'followed': 4, 'read': 7, 'cached': 4, 'closed': 1, 'signin': 1, 'errors': 0}.

| posting | case | result | form |
|---|---|---|---|
| P1 | the full Google Form address | ok | `notice:2001` |
| P2 | the same form by forms.gle, in mail | ok | `notice:2001` |
| P3 | an extension repost with a different usp | ok | `notice:2001` |
| P4 | a second, different form from the same company | ok | `notice:2010` |
| P5 | formResponse with prefill parameters | ok | `notice:2020` |
| P6 | notice and mail, different usp | ok | `notice:2020` |
| P7 | a Microsoft form that no longer accepts responses | ok | `notice:2030` |
| P8 | a form that needs an institute sign-in | ok | `notice:2040` |
| P9 | a notice with no link | ok | `notice:2050` |
| P10 | the same notice posted again, still no link | ok | `notice:2050` |
| P11 | a bit.ly short link | ok | `notice:2060` |
| P12 | an extension through a different short link | ok | `notice:2060` |
| P13 | a Typeform | ok | `notice:2070` |
| P14 | the same Typeform through lnkd.in, in mail | ok | `notice:2070` |
| P15 | the same companies + purpose + deadline from another site: merged silently (no prompt) | ok | `notice:2001` |

Chat:
- P3: ok — Groww: fill the form by 2026-11-21T20:00:00+05:30.
- P12: ok — Pine Labs: fill the form by 2026-11-21T20:00:00+05:30.
