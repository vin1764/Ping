# Ask Ping evals

_Run on 21 Nov 2026, 14:48 UTC against the deployed `ask-ping` function, from one-click demo sessions (anonymised demo data), snapshot time fixed at 2026-11-21T17:32:18+05:30 (cases marked 'as_of' use their own). Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._

## In short

- **Single questions: 38 of 42 passed all their checks (90%).**
- **Conversations (follow-ups in one thread): 20 of 21 passed every turn; 38 of 39 turns passed.**
- Models that answered: gemini-flash-lite-latest (42)
- Latency: median 5.0 s, slowest 49.1 s
- Checks are deterministic (no model grades another model): required words or phrases, forbidden ones, numbers in any common format (28,00,000 = 28 L = 28 LPA), and a word limit.
- **Warning:** the demo data changed after the expected answers were written.

## By category

| category | passed | out of | score |
|---|---|---|---|
| company facts | 7 | 8 | 88% |
| deadlines | 6 | 8 | 75% |
| notices | 6 | 6 | 100% |
| negative | 6 | 6 | 100% |
| read-only | 5 | 5 | 100% |
| robustness | 4 | 4 | 100% |
| time | 2 | 2 | 100% |
| lists | 1 | 2 | 50% |
| cvs | 1 | 1 | 100% |

## Failures

### C2 (company facts): am I eligible for Harness

- failed: must_contain '7.5'
- expected: Harness Software Engineer I: CGPA cut-off 7.5; demo profile CGPA 8.0; department unknown so eligibility can't be confirmed, but the CG cut-off is met
- model gemini-flash-lite-latest, 5.0 s

> Harness (Software Engineer I): eligibility unknown, because Add your department and degree on the Profile page to check eligibility.

### D2 (deadlines): anything due today

- failed: must_contain 'aiprise'; must_contain 'waterfly'; must_contain 'auro'
- expected: today Sat 21 Nov: 41 reminders/deadlines all at 20:00 (AiPrise, Ather, Auro Group, Waterfly, Searce, ...)
- model gemini-flash-lite-latest, 5.0 s

> Nothing due today except 47 roles at 22 companies closing at 20:00 (later today, in 2h 28m).

### D3 (deadlines): what closes this week

- failed: must_contain '20:00|8 pm|8:00 pm|8pm|8.00 pm|8 p.m'
- expected: all 48 open role deadlines after the snapshot are Sat 21 Nov 20:00
- model gemini-flash-lite-latest, 17.2 s

> Sat, 21 Nov: 47 roles at 22 companies (38 not applied, 9 applied; 17 for you)

### L1 (lists): what's due tonight that's relevant to me

- failed: must_contain 'Others'
- expected: the ready-made list: deadline once in the heading, For you (unapplied, then ✓ applied), Others one 'Company — Role' line each, no reasons in chat
- model gemini-flash-lite-latest, 11.0 s

> Close tonight 20:00 (in 1h 25m), Sat, 21 Nov — 17 for you, 9 applied:
> For you:
> - Auro Group(www.AuroIM.com) — Data Analyst (apply with Analytics & Finance CV)
> - Axis Bank — BIU (Business Intelligence Unit) (apply with Analytics & Finance CV)
> - BlackBuck — Associate Manager BlackBuck Leadership Program (apply with Consulting CV)
> - Flipspaces Technology Labs Pvt. Ltd. — Entrepreneur-in-Residence (apply with Consulting CV)
> - Waterfly Technologies — Growth and Strategist (apply with Consulting CV)
> - Waterfly Technologies — Managment Consultant 2 (apply with Consulting CV)
> - Xion Multiventures Pvt Ltd — Trainee Trader & Research Analyst (apply with Analytics & Finance CV)
> - YMS Financial Private Limited — Quant Researcher (apply with Analytics & Finance CV)
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
| M8 | 2 | eternal ctc | ok. what's due this week? | FAIL (turn 2) |
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

#### M8 turn 2: ok. what's due this week?

- failed: must_contain '20:00|8 pm|8:00 pm|8pm|8.00 pm|8 p.m'; must_contain '21|today'
- expected: topic change: after Eternal pay, 'what's due this week' is all Sat 21 Nov 20:00 and has nothing to do with Eternal
- previous turn: "eternal ctc" → "Eternal: Software Development Engineer I has a CTC of 59,00,000 INR (Base Salary: 24,00,000 INR, yearly cash bonus: 35,00,000 INR over 4 years, no bonds, no joining/retention/relocation bonus).
Produc"
- model gemini-flash-lite-latest, 5.0 s

> Nothing is due this week. Next application deadlines are on Monday, 23 November 2026.


## Every case

| id | category | question | result | model | seconds |
|---|---|---|---|---|---|
| C1 | company facts | slice ctc breakdown | pass | gemini-flash-lite-latest | 15.8 |
| C2 | company facts | am I eligible for Harness | FAIL | gemini-flash-lite-latest | 5.0 |
| C3 | company facts | what is the CG cut-off for Axis Bank | pass | gemini-flash-lite-latest | 5.0 |
| C4 | company facts | which departments can apply for Axis Bank | pass | gemini-flash-lite-latest | 11.1 |
| C5 | company facts | what roles does Waterfly Technologies have | pass | gemini-flash-lite-latest | 5.7 |
| C6 | company facts | Diageo joining bonus | pass | gemini-flash-lite-latest | 49.1 |
| C7 | company facts | does Harness have a bond | pass | gemini-flash-lite-latest | 14.0 |
| C8 | company facts | Harness take home salary | pass | gemini-flash-lite-latest | 5.4 |
| D1 | deadlines | what's due tomorrow | pass | gemini-flash-lite-latest | 6.4 |
| D2 | deadlines | anything due today | FAIL | gemini-flash-lite-latest | 5.0 |
| D3 | deadlines | what closes this week | FAIL | gemini-flash-lite-latest | 17.2 |
| D4 | deadlines | when does the Ather Energy application close | pass | gemini-flash-lite-latest | 4.4 |
| D5 | deadlines | when does Diageo close | pass | gemini-flash-lite-latest | 9.9 |
| D6 | deadlines | is the ESRI deadline today? | pass | gemini-flash-lite-latest | 4.4 |
| D7 | deadlines | what's the deadline for Harness | pass | gemini-flash-lite-latest | 4.6 |
| D8 | deadlines | what's due on 25 November | pass | gemini-flash-lite-latest | 4.4 |
| N1 | notices | am I shortlisted anywhere | pass | gemini-flash-lite-latest | 8.1 |
| N2 | notices | when is the Eternal test and where | pass | gemini-flash-lite-latest | 10.4 |
| N3 | notices | which room was I in for the IQVIA test | pass | gemini-flash-lite-latest | 10.1 |
| N4 | notices | latest notice for Groww | pass | gemini-flash-lite-latest | 6.6 |
| N5 | notices | am I on the Pine Labs list | pass | gemini-flash-lite-latest | 4.7 |
| N6 | notices | when is the Groww test | pass | gemini-flash-lite-latest | 11.4 |
| X1 | negative | what's the CTC at Google | pass | gemini-flash-lite-latest | 4.6 |
| X2 | negative | what's due on 30 November | pass | gemini-flash-lite-latest | 4.1 |
| X3 | negative | where is the Diageo job located | pass | gemini-flash-lite-latest | 4.2 |
| X4 | negative | what was my score in the Eternal test | pass | gemini-flash-lite-latest | 11.5 |
| X5 | negative | what's the CTC at Netflix | pass | gemini-flash-lite-latest | 6.5 |
| X6 | negative | who is the CDC contact for Groww and their phone number | pass | gemini-flash-lite-latest | 4.7 |
| R1 | read-only | apply to Waterfly Graduate Engineer 1 for me | pass | gemini-flash-lite-latest | 4.6 |
| R2 | read-only | withdraw my application to Diageo | pass | gemini-flash-lite-latest | 4.0 |
| R3 | read-only | change my CV on the ERP to the Data CV | pass | gemini-flash-lite-latest | 4.5 |
| R4 | read-only | fill the Groww additional details form for me | pass | gemini-flash-lite-latest | 4.8 |
| B1 | robustness | waterfly ctc | pass | gemini-flash-lite-latest | 5.0 |
| B2 | robustness | eternl ctc brekdown | pass | gemini-flash-lite-latest | 4.7 |
| B3 | robustness | what's slice's CTC and when does ESRI close? | pass | gemini-flash-lite-latest | 4.3 |
| B4 | robustness | did i apply to diageo?? and whats the bond | pass | gemini-flash-lite-latest | 4.3 |
| R5 | read-only | apply to groww for me | pass | gemini-flash-lite-latest | 4.4 |
| T1 | time | when is the groww test? | pass | gemini-flash-lite-latest | 4.4 |
| T2 | time | when does ESRI close? | pass | gemini-flash-lite-latest | 7.2 |
| L1 | lists | what's due tonight that's relevant to me | FAIL | gemini-flash-lite-latest | 11.0 |
| L2 | lists | what closes tonight? | pass | gemini-flash-lite-latest | 11.5 |
| CV1 | cvs | which cv should I use for groww | pass | gemini-flash-lite-latest | 7.4 |

The questions, checks and the data each expected answer comes from are in [`cases.json`](cases.json); every answer is in `results.json`.
