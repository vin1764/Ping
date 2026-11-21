# Ask Ping evals

_Run on 21 Nov 2026, 17:51 UTC against the deployed `ask-ping` function, from one-click demo sessions (anonymised demo data), snapshot time fixed at 2026-11-21T17:32:18+05:30 (cases marked 'as_of' use their own). Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._

## In short

- **Single questions: 37 of 42 passed all their checks (88%).**
- **Conversations (follow-ups in one thread): 21 of 21 passed every turn; 39 of 39 turns passed.**
- Models that answered: gemini-flash-lite-latest (31), gemini-3.5-flash-lite (6), gemini-3.1-flash-lite (5)
- Latency: median 4.5 s, slowest 50.7 s
- Checks are deterministic (no model grades another model): required words or phrases, forbidden ones, numbers in any common format (28,00,000 = 28 L = 28 LPA), and a word limit.
- **Warning:** the demo data changed after the expected answers were written.

## By category

| category | passed | out of | score |
|---|---|---|---|
| company facts | 8 | 8 | 100% |
| deadlines | 8 | 8 | 100% |
| notices | 5 | 6 | 83% |
| negative | 5 | 6 | 83% |
| read-only | 5 | 5 | 100% |
| robustness | 2 | 4 | 50% |
| time | 2 | 2 | 100% |
| lists | 1 | 2 | 50% |
| cvs | 1 | 1 | 100% |

## Failures

### N2 (notices): when is the Eternal test and where

- failed: must_contain 'nr 121'
- expected: Eternal test Thu 19 Nov 19:15, Nalanda Classroom Complex, your room NR 121
- model gemini-flash-lite-latest, 2.7 s

> Eternal test was at 19:15 on Thu, 19 Nov 2026 (already passed) at Nalanda Classroom Complex.

### X2 (negative): what's due on 30 November

- failed: must_contain 'nothing|no deadline|none|don't see any|do not see any|no items|not see anything|'
- expected: nothing falls on 30 Nov
- model gemini-flash-lite-latest, 4.0 s

> I don't have any notice for 30 November. Next deadline is Pine Labs (Software Development Engineer) on Sun 22 Nov, 20:00.

### B2 (robustness): eternl ctc brekdown

- failed: numbers_present 5900000; numbers_present 4700000
- expected: Eternal (typo): SDE I / ML Scientist 59L, Product Analyst 47L; ETERNAL Assistant Program Manager 17L
- model gemini-3.5-flash-lite, 13.7 s

> Eternal (Software Development Engineer I):
> - Fixed / Take-home: Base Salary: 24,00,000 (Gross per annum: 24,00,000, Fixed take-home per annum: 24,00,000)
> - Bonuses: Yearly Cash Bonus: 35,00,000 (1st year: 5,00,000 | 2nd year: 10,00,000 | 3rd year: 10,00,000 | 4th year: 10,00,000); 1st Year CTC: 29,00,000; Joining Bonus, Retention Bonus, Relocation Bonus: 0
> - ESOPs: None
> - Bond: No (Bond Amount: 0)
> 
> Eternal (Product Analyst):
> - Fixed / Take-home: Base Salary: 21,00,000 (Gross per annum: 21,00,000, Fixed take-home per annum: 21,00,000)
> - Bonuses: Yearly Cash Bonus: 26,00,000 (1st year: 3,00,000 | 2nd year: 5,00,000 | 3rd year: 8,00,000 | 4th year: 10,00,000); 1st Year CTC: 24,00,000; Joining Bonus, Retention Bonus, Relocation Bonus: 0
> - ESOPs: None
> - Bond: No (Bond Amount: 0)
> 
> Eternal (Machine Learning Scientist):
> - Fixed / Take-home: Base Salary: 24,00,000 (Gross per annum: 24,00,000, Fixed take-home per annum: 24,00,000)
> - Bonuses: Yearly Cash Bonus: 35,00,000 (1st year: 5,00,000 | 2nd year: 10,00,000 | 3rd year: 10,00,000 | 4th year: 10,00,000); 1st Year CTC: 29,00,000; Joining Bonus, Retention Bonus, Relocation Bonus: 0
> - ESOPs: None
> - Bond: No (Bond Amount: 0)
> 
> ETERNAL (Assistant Program Manager):
> - Fixed / Take-home: Base Salary: 15,00,000 (Gross per annum: 17,00,000, Fixed take-home per annum: 15,00,000)
> - Bonuses: Variable: 2,00,000; 1st Year CTC: 17,00,000; Joining Bonus, Retention Bonus, Relocation Bonus: 0
> - ESOPs: None
> - Bond: No (Bond Amount: 0)

### B3 (robustness): what's slice's CTC and when does ESRI close?

- failed: numbers_present 2800000
- expected: two questions: slice 28L / 25L; ESRI Sat 21 Nov 20:00
- model gemini-flash-lite-latest, 3.3 s

> slice: 2500000 INR (19L base, 2L retention bonus, 4L ESOPs; fixed take-home 1900000, 0 joining bonus, 30000 relocation bonus, no bond). ESRI (Data Scientist I): closes Sat, 21 Nov, 20:00 (later today, in 2h 28m).

### L1 (lists): what's due tonight that's relevant to me

- failed: must_contain 'Others'
- expected: the ready-made list: deadline once in the heading, For you (unapplied, then ✓ applied), Others one 'Company — Role' line each, no reasons in chat
- model gemini-3.5-flash-lite, 3.5 s

> Close tonight 20:00 (in 1h 25m), Sat, 21 Nov — 17 for you, 9 applied:
> For you:
> - Auro Group(www.AuroIM.com) — Data Analyst
> - Axis Bank — BIU (Business Intelligence Unit)
> - BlackBuck — Associate Manager BlackBuck Leadership Program
> - Flipspaces Technology Labs Pvt. Ltd. — Entrepreneur-in-Residence
> - Waterfly Technologies — Growth and Strategist
> - Waterfly Technologies — Managment Consultant 2
> - Xion Multiventures Pvt Ltd — Trainee Trader & Research Analyst
> - YMS Financial Private Limited — Quant Researcher
> - Ather Energy — Product Ownership ✓ applied
> - Auro Group(www.AuroIM.com) — Product Manager ✓ applied
> - AXON DEVELOPERS — Manager Strategy ✓ applied
> - AXON DEVELOPERS — MDs Office ✓ applied
> - Diageo — GBS MANAGEMENT TRAINEE ✓ applied
> - LYSKRAFT Pvt Ltd — APM ✓ applied
> - PhysicsWallah Limited — Associate Product Manager (APM) ✓ applied
> - Searce Inc. — Associate Solutions Consultant ✓ applied
> - Waterfly Technologies — Management Consultant 1 ✓ applied


## Conversations (multi-turn)

Each conversation runs in one fresh demo session; the function reads the thread from the database itself. A conversation passes only if every turn passes.

| id | turns | first question | follow-up(s) | result |
|---|---|---|---|---|
| M1 | 2 | any test today? | nothing else? | pass |
| M2 | 2 | meesho ctc | and slice? | pass |
| M3 | 2 | what's due tomorrow | and the day after? | pass |
| M4 | 2 | am I eligible for groww | why not? | pass |
| M5 | 2 | latest notice for harness | when is it? | pass |
| M6 | 2 | slice ctc breakdown | same for analyst role? | pass |
| M7 | 2 | when is the Eternal test | where? | pass |
| M8 | 2 | eternal ctc | ok. what's due this week? | pass |
| M9 | 2 | does diageo have a bond | and harness? | pass |
| M10 | 2 | any tests today? | anything else? | pass |
| M11 | 2 | what's due tomorrow | what else? | pass |
| M12 | 2 | slice ctc | and? | pass |
| M13 | 2 | when is the eternal test | ok | pass |
| P1 | 2 | only show me product, consulting and analyst roles | what are my preferences? | pass |
| P2 | 2 | only show me product roles | also include data scientist roles | pass |
| P3 | 2 | only show me product and analyst roles | don't count SDE as relevant | pass |
| P4 | 1 | remind me 3 hours before deadlines |  | pass |
| P5 | 1 | stop listing other roles separately |  | pass |
| P6 | 2 | only show me finance roles | reset my preferences | pass |
| P7 | 2 | any product roles tonight? | what are my preferences? | pass |
| P8 | 1 | only show me product roles. what's due tonight? |  | pass |

### Conversation failures

None.

## Every case

| id | category | question | result | model | seconds |
|---|---|---|---|---|---|
| C1 | company facts | slice ctc breakdown | pass | gemini-flash-lite-latest | 50.7 |
| C2 | company facts | am I eligible for Harness | pass | gemini-flash-lite-latest | 5.7 |
| C3 | company facts | what is the CG cut-off for Axis Bank | pass | gemini-flash-lite-latest | 49.0 |
| C4 | company facts | which departments can apply for Axis Bank | pass | gemini-flash-lite-latest | 7.3 |
| C5 | company facts | what roles does Waterfly Technologies have | pass | gemini-flash-lite-latest | 6.0 |
| C6 | company facts | Diageo joining bonus | pass | gemini-flash-lite-latest | 3.8 |
| C7 | company facts | does Harness have a bond | pass | gemini-flash-lite-latest | 4.4 |
| C8 | company facts | Harness take home salary | pass | gemini-flash-lite-latest | 3.4 |
| D1 | deadlines | what's due tomorrow | pass | gemini-flash-lite-latest | 4.9 |
| D2 | deadlines | anything due today | pass | gemini-flash-lite-latest | 6.7 |
| D3 | deadlines | what closes this week | pass | gemini-flash-lite-latest | 3.6 |
| D4 | deadlines | when does the Ather Energy application close | pass | gemini-flash-lite-latest | 50.4 |
| D5 | deadlines | when does Diageo close | pass | gemini-flash-lite-latest | 7.8 |
| D6 | deadlines | is the ESRI deadline today? | pass | gemini-flash-lite-latest | 5.2 |
| D7 | deadlines | what's the deadline for Harness | pass | gemini-flash-lite-latest | 5.1 |
| D8 | deadlines | what's due on 25 November | pass | gemini-flash-lite-latest | 3.5 |
| N1 | notices | am I shortlisted anywhere | pass | gemini-flash-lite-latest | 3.1 |
| N2 | notices | when is the Eternal test and where | FAIL | gemini-flash-lite-latest | 2.7 |
| N3 | notices | which room was I in for the IQVIA test | pass | gemini-flash-lite-latest | 3.3 |
| N4 | notices | latest notice for Groww | pass | gemini-flash-lite-latest | 4.2 |
| N5 | notices | am I on the Pine Labs list | pass | gemini-flash-lite-latest | 3.5 |
| N6 | notices | when is the Groww test | pass | gemini-flash-lite-latest | 3.4 |
| X1 | negative | what's the CTC at Google | pass | gemini-flash-lite-latest | 45.1 |
| X2 | negative | what's due on 30 November | FAIL | gemini-flash-lite-latest | 4.0 |
| X3 | negative | where is the Diageo job located | pass | gemini-3.5-flash-lite | 4.3 |
| X4 | negative | what was my score in the Eternal test | pass | gemini-flash-lite-latest | 11.6 |
| X5 | negative | what's the CTC at Netflix | pass | gemini-3.1-flash-lite | 4.0 |
| X6 | negative | who is the CDC contact for Groww and their phone number | pass | gemini-flash-lite-latest | 3.2 |
| R1 | read-only | apply to Waterfly Graduate Engineer 1 for me | pass | gemini-flash-lite-latest | 12.6 |
| R2 | read-only | withdraw my application to Diageo | pass | gemini-flash-lite-latest | 3.4 |
| R3 | read-only | change my CV on the ERP to the Data CV | pass | gemini-flash-lite-latest | 4.2 |
| R4 | read-only | fill the Groww additional details form for me | pass | gemini-3.1-flash-lite | 3.8 |
| B1 | robustness | waterfly ctc | pass | gemini-3.5-flash-lite | 12.5 |
| B2 | robustness | eternl ctc brekdown | FAIL | gemini-3.5-flash-lite | 13.7 |
| B3 | robustness | what's slice's CTC and when does ESRI close? | FAIL | gemini-flash-lite-latest | 3.3 |
| B4 | robustness | did i apply to diageo?? and whats the bond | pass | gemini-3.5-flash-lite | 5.1 |
| R5 | read-only | apply to groww for me | pass | gemini-3.1-flash-lite | 4.9 |
| T1 | time | when is the groww test? | pass | gemini-3.5-flash-lite | 4.5 |
| T2 | time | when does ESRI close? | pass | gemini-3.1-flash-lite | 5.0 |
| L1 | lists | what's due tonight that's relevant to me | FAIL | gemini-3.5-flash-lite | 3.5 |
| L2 | lists | what closes tonight? | pass | gemini-3.1-flash-lite | 4.9 |
| CV1 | cvs | which cv should I use for groww | pass | gemini-flash-lite-latest | 3.8 |

The questions, checks and the data each expected answer comes from are in [`cases.json`](cases.json); every answer is in `results.json`.
