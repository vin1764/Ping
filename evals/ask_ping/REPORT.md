# Ask Ping evals

_Run on 21 Nov 2026, 14:35 UTC against the deployed `ask-ping` function, from one-click demo sessions (anonymised demo data), snapshot time fixed at 2026-11-21T17:32:18+05:30 (cases marked 'as_of' use their own). Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._

## In short

- **Single questions: 34 of 42 passed all their checks (81%).**
- **Conversations (follow-ups in one thread): 20 of 21 passed every turn; 38 of 39 turns passed.**
- Models that answered: gemini-flash-lite-latest (41), gemini-3.5-flash-lite (1)
- Latency: median 5.9 s, slowest 12.7 s
- Checks are deterministic (no model grades another model): required words or phrases, forbidden ones, numbers in any common format (28,00,000 = 28 L = 28 LPA), and a word limit.
- **Warning:** the demo data changed after the expected answers were written.

## By category

| category | passed | out of | score |
|---|---|---|---|
| company facts | 7 | 8 | 88% |
| deadlines | 5 | 8 | 62% |
| notices | 5 | 6 | 83% |
| negative | 5 | 6 | 83% |
| read-only | 5 | 5 | 100% |
| robustness | 3 | 4 | 75% |
| time | 2 | 2 | 100% |
| lists | 1 | 2 | 50% |
| cvs | 1 | 1 | 100% |

## Failures

### C2 (company facts): am I eligible for Harness

- failed: must_contain '7.5'
- expected: Harness Software Engineer I: CGPA cut-off 7.5; demo profile CGPA 8.0; department unknown so eligibility can't be confirmed, but the CG cut-off is met
- model gemini-flash-lite-latest, 12.7 s

> Harness (Software Engineer I): eligibility unknown, because Add your department and degree on the Profile page to check eligibility.

### D1 (deadlines): what's due tomorrow

- failed: must_contain 'nothing|no deadline|none|don't see any|do not see any|no items|not see anything|'
- expected: nothing in the feed or roles falls on Sun 22 Nov
- model gemini-flash-lite-latest, 11.6 s

> No roles or tests due tomorrow. Next ones are 47 roles closing at 20:00 today (in 2h 28m).

### D3 (deadlines): what closes this week

- failed: must_contain '21|today'
- expected: all 48 open role deadlines after the snapshot are Sat 21 Nov 20:00
- model gemini-3.5-flash-lite, 7.4 s

> Close tonight 20:00 (in 2h 28m) — 17 for you, 9 applied:
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
> Others:
> - AiPrise — Software Engineer I
> - AiPrise — Software Engineer I, Full Stack (Frontend Focused)
> - AiPrise — Software Engineer II
> - AiPrise — Software Engineer II, Full Stack (Frontend Focused)
> - Astera Labs — Software Quality Assurance (SQA) Engineer
> - Ather Energy — Chief Engineer
> - Ather Energy — Data Office
> - Ather Energy — Hardware Pack Engineering
> - Ather Energy — System Intelligence
> - Auro Group(www.AuroIM.com) — AI/ML Software Engineer
> - Auro Group(www.AuroIM.com) — Back End Developer
> - Auro Group(www.AuroIM.com) — Frontend Developer
> - Auro Group(www.AuroIM.com) — Full Stack Developer
> - Auro Group(www.AuroIM.com) — Sales & Business Development
> - Dassault Systemes — AI Engineer-Data Scientist-PG
> - Dassault Systemes — Software Engineer - Domain Engineering & AI Innovation-PG
> - ESRI — Data Scientist I
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Aerodynamics Engineer
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Avionics Engineer
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Mechanical Engineer
> - LTM — Post-Graduate Engineer Trainee
> - LYSKRAFT Pvt Ltd — SDE - 1
> - MeltPlan Inc — Software Engineer
> - Searce Inc. — Associate Cloud Engineer
> - Searce Inc. — Associate Data Engineer
> - Searce Inc. — Evlos AI Engineer
> - SLB — Datascientist
> - Swiggy Limited — Data Scientist 1
> - Waterfly Technologies — Graduate Engineer 1
> - Waterfly Technologies — Graduate Engineer 2

### D8 (deadlines): what's due on 25 November

- failed: must_contain 'nothing|no deadline|none|don't see any|do not see any|no items|not see anything|'
- expected: nothing falls on 25 Nov
- model gemini-flash-lite-latest, 4.8 s

> I don't have any application deadlines or tests recorded for 25 November. The closest deadlines in the data are 47 roles closing tonight at 20:00 (later today, in 2h 28m).

### N1 (notices): am I shortlisted anywhere

- failed: must_contain 'eternal'
- expected: latest list results: on the Eternal shortlist/test room list (Thu 19 Nov); not on Pine Labs (20 Nov), Goldman Sachs, Microsoft
- model gemini-flash-lite-latest, 3.3 s

> Pine Labs (Software Development Engineer): submit by Sun 22 Nov 20:00. You are NOT on this list.

### X2 (negative): what's due on 30 November

- failed: must_contain 'nothing|no deadline|none|don't see any|do not see any|no items|not see anything|'
- expected: nothing falls on 30 Nov
- model gemini-flash-lite-latest, 6.8 s

> I don't have any deadlines listed for 30 November. The closest deadlines are 47 roles that close tonight at 20:00 (later today, in 2h 28m).

### B3 (robustness): what's slice's CTC and when does ESRI close?

- failed: numbers_present 2800000
- expected: two questions: slice 28L / 25L; ESRI Sat 21 Nov 20:00
- model gemini-flash-lite-latest, 10.6 s

> slice: CTC 2500000 INR (19L base, 2L retention bonus, 4L ESOPs; fixed take-home 1900000 INR, retention bonus 200000 INR, relocation bonus 30000 INR, bond amount 0, bonds: no).
> ESRI (Data Scientist I): closes Sat 21 Nov 20:00 (later today, in 2h 28m).

### L1 (lists): what's due tonight that's relevant to me

- failed: must_contain 'Others'
- expected: the ready-made list: deadline once in the heading, For you (unapplied, then ✓ applied), Others one 'Company — Role' line each, no reasons in chat
- model gemini-flash-lite-latest, 4.5 s

> Add your department and degree on the Profile page to check eligibility.
> 
> Close tonight 20:00 (in 1h 25m) — 17 for you, 9 applied:
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
| M6 | 2 | slice ctc breakdown | same for analyst role? | FAIL (turn 2) |
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

#### M6 turn 2: same for analyst role?

- failed: must_contain 'esop'; numbers_present 2500000; numbers_present 1900000
- expected: slice APM 22L fixed + 2L retention + 4L ESOPs; Analyst 19L base + 2L retention + 4L ESOPs = 25,00,000
- previous turn: "slice ctc breakdown" → "slice: Analyst (applied: yes): Bonds: No; Base Salary: 1900000; Bond Amount: 0; CTC Breakup: 19L base + 2L RB + 4L ESOPs; 1st Year CTC: 2500000; Gross (per Annum): 1900000; Joining Bonus, if any: 0; R"
- model gemini-flash-lite-latest, 4.0 s

> I don't have an analyst role for slice other than the Analyst and Associate Product Manager roles already shown.


## Every case

| id | category | question | result | model | seconds |
|---|---|---|---|---|---|
| C1 | company facts | slice ctc breakdown | pass | gemini-flash-lite-latest | 6.7 |
| C2 | company facts | am I eligible for Harness | FAIL | gemini-flash-lite-latest | 12.7 |
| C3 | company facts | what is the CG cut-off for Axis Bank | pass | gemini-flash-lite-latest | 5.4 |
| C4 | company facts | which departments can apply for Axis Bank | pass | gemini-flash-lite-latest | 4.7 |
| C5 | company facts | what roles does Waterfly Technologies have | pass | gemini-flash-lite-latest | 5.6 |
| C6 | company facts | Diageo joining bonus | pass | gemini-flash-lite-latest | 12.3 |
| C7 | company facts | does Harness have a bond | pass | gemini-flash-lite-latest | 4.1 |
| C8 | company facts | Harness take home salary | pass | gemini-flash-lite-latest | 6.4 |
| D1 | deadlines | what's due tomorrow | FAIL | gemini-flash-lite-latest | 11.6 |
| D2 | deadlines | anything due today | pass | gemini-flash-lite-latest | 6.8 |
| D3 | deadlines | what closes this week | FAIL | gemini-3.5-flash-lite | 7.4 |
| D4 | deadlines | when does the Ather Energy application close | pass | gemini-flash-lite-latest | 4.4 |
| D5 | deadlines | when does Diageo close | pass | gemini-flash-lite-latest | 3.8 |
| D6 | deadlines | is the ESRI deadline today? | pass | gemini-flash-lite-latest | 4.3 |
| D7 | deadlines | what's the deadline for Harness | pass | gemini-flash-lite-latest | 5.5 |
| D8 | deadlines | what's due on 25 November | FAIL | gemini-flash-lite-latest | 4.8 |
| N1 | notices | am I shortlisted anywhere | FAIL | gemini-flash-lite-latest | 3.3 |
| N2 | notices | when is the Eternal test and where | pass | gemini-flash-lite-latest | 5.9 |
| N3 | notices | which room was I in for the IQVIA test | pass | gemini-flash-lite-latest | 4.4 |
| N4 | notices | latest notice for Groww | pass | gemini-flash-lite-latest | 7.3 |
| N5 | notices | am I on the Pine Labs list | pass | gemini-flash-lite-latest | 3.4 |
| N6 | notices | when is the Groww test | pass | gemini-flash-lite-latest | 3.4 |
| X1 | negative | what's the CTC at Google | pass | gemini-flash-lite-latest | 6.7 |
| X2 | negative | what's due on 30 November | FAIL | gemini-flash-lite-latest | 6.8 |
| X3 | negative | where is the Diageo job located | pass | gemini-flash-lite-latest | 7.8 |
| X4 | negative | what was my score in the Eternal test | pass | gemini-flash-lite-latest | 10.9 |
| X5 | negative | what's the CTC at Netflix | pass | gemini-flash-lite-latest | 7.6 |
| X6 | negative | who is the CDC contact for Groww and their phone number | pass | gemini-flash-lite-latest | 4.5 |
| R1 | read-only | apply to Waterfly Graduate Engineer 1 for me | pass | gemini-flash-lite-latest | 4.6 |
| R2 | read-only | withdraw my application to Diageo | pass | gemini-flash-lite-latest | 4.2 |
| R3 | read-only | change my CV on the ERP to the Data CV | pass | gemini-flash-lite-latest | 10.0 |
| R4 | read-only | fill the Groww additional details form for me | pass | gemini-flash-lite-latest | 4.6 |
| B1 | robustness | waterfly ctc | pass | gemini-flash-lite-latest | 9.1 |
| B2 | robustness | eternl ctc brekdown | pass | gemini-flash-lite-latest | 7.5 |
| B3 | robustness | what's slice's CTC and when does ESRI close? | FAIL | gemini-flash-lite-latest | 10.6 |
| B4 | robustness | did i apply to diageo?? and whats the bond | pass | gemini-flash-lite-latest | 6.1 |
| R5 | read-only | apply to groww for me | pass | gemini-flash-lite-latest | 12.6 |
| T1 | time | when is the groww test? | pass | gemini-flash-lite-latest | 4.0 |
| T2 | time | when does ESRI close? | pass | gemini-flash-lite-latest | 11.7 |
| L1 | lists | what's due tonight that's relevant to me | FAIL | gemini-flash-lite-latest | 4.5 |
| L2 | lists | what closes tonight? | pass | gemini-flash-lite-latest | 5.5 |
| CV1 | cvs | which cv should I use for groww | pass | gemini-flash-lite-latest | 5.5 |

The questions, checks and the data each expected answer comes from are in [`cases.json`](cases.json); every answer is in `results.json`.
