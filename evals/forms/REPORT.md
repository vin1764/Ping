# Forms evals

Run Mon 23 Nov 04:27 IST. **17/17 postings** land in the right form with the right deadline, history, sources, closed / sign-in state and 'looks like' offer; reposts in the chat: 2/2 are one 'deadline extended' line on the existing message (no new message).

Form pages read: {'followed': 4, 'read': 9, 'cached': 4, 'closed': 1, 'signin': 1, 'errors': 0}.

| posting | case | result | form |
|---|---|---|---|
| P1 | the full Google Form address | ok | `gform:1FAIpQLSdGrowwReg2026xx` |
| P2 | the same form by forms.gle, in mail | ok | `gform:1FAIpQLSdGrowwReg2026xx` |
| P3 | an extension repost with a different usp | ok | `gform:1FAIpQLSdGrowwReg2026xx` |
| P4 | a second, different form from the same company | ok | `gform:1FAIpQLSdGrowwSlot2026x` |
| P5 | formResponse with prefill parameters | ok | `gform:1FAIpQLSdZetaDetails26x` |
| P6 | notice and mail, different usp | ok | `gform:1FAIpQLSdZetaDetails26x` |
| P7 | a Microsoft form that no longer accepts responses | ok | `msform:KiteMSX12345` |
| P8 | a form that needs an institute sign-in | ok | `gform:1FAIpQLSdOrbitCVform26x` |
| P9 | a notice with no link | ok | `notice:2050` |
| P10 | the same notice posted again, still no link | ok | `notice:2050` |
| P11 | a bit.ly short link | ok | `gform:1FAIpQLSdPineReg2026xxx` |
| P12 | an extension through a different short link | ok | `gform:1FAIpQLSdPineReg2026xxx` |
| P13 | a Typeform | ok | `typeform:AbC123` |
| P14 | the same Typeform through lnkd.in, in mail | ok | `typeform:AbC123` |
| P15 | the same companies + purpose + deadline but a different link: its own form (two links are never one form) | ok | `url:careers.groww.example/apply/form` |
| P16 | one notice, several companies with their own forms: this company's form | ok | `gform:1FAIpQLSdLatticeAddl26x` |
| P17 | the same notice, another company's own form (the 23 Nov over-merge): its own row and its own link | ok | `gform:1FAIpQLSdKestrelOwn26x` |

Chat:
- P3: ok — Groww: fill the form by 2026-11-21T20:00:00+05:30.
- P12: ok — Pine Labs: fill the form by 2026-11-21T20:00:00+05:30.
