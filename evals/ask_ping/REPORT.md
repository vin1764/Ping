# Ask Ping evals

_Run on 21 Nov 2026, 13:32 UTC against the deployed `ask-ping` function, from one-click demo sessions (anonymised demo data), snapshot time fixed at 2026-11-21T17:32:18+05:30 (cases marked 'as_of' use their own). Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._

## In short

- **Single questions: 35 of 39 passed all their checks (90%).**
- **Conversations (follow-ups in one thread): 13 of 13 passed every turn; 26 of 26 turns passed.**
- Models that answered: gemini-flash-lite-latest (34), gemini-3.1-flash-lite (4), gemini-3.5-flash-lite (1)
- Latency: median 2.3 s, slowest 10.4 s
- Checks are deterministic (no model grades another model): required words or phrases, forbidden ones, numbers in any common format (28,00,000 = 28 L = 28 LPA), and a word limit.

## By category

| category | passed | out of | score |
|---|---|---|---|
| company facts | 7 | 8 | 88% |
| deadlines | 6 | 8 | 75% |
| notices | 6 | 6 | 100% |
| negative | 5 | 6 | 83% |
| read-only | 5 | 5 | 100% |
| robustness | 4 | 4 | 100% |
| time | 2 | 2 | 100% |

## Failures

### C2 (company facts): am I eligible for Harness

- failed: must_contain '7.5'
- expected: Harness Software Engineer I: CGPA cut-off 7.5; demo profile CGPA 8.0; department unknown so eligibility can't be confirmed, but the CG cut-off is met
- model gemini-flash-lite-latest, 3.0 s

> Harness: eligibility unknown, because the data does not show your eligibility status.

### D2 (deadlines): anything due today

- failed: must_contain 'aiprise'; must_contain 'waterfly'; must_contain 'auro'
- expected: today Sat 21 Nov: 41 reminders/deadlines all at 20:00 (AiPrise, Ather, Auro Group, Waterfly, Searce, ...)
- model gemini-flash-lite-latest, 2.2 s

> 48 applications at 23 companies close at 20:00 today (in 2h 28m), 39 of them not applied.

### D8 (deadlines): what's due on 25 November

- failed: must_contain 'nothing|no deadline|none|don't see any|do not see any|no items|not see anything|'
- expected: nothing falls on 25 Nov
- model gemini-flash-lite-latest, 2.2 s

> I don't have any deadlines for 25 November in your companies list. The closest are 48 application deadlines closing at 20:00 today (in 2h 28m).

### X2 (negative): what's due on 30 November

- failed: must_contain 'nothing|no deadline|none|don't see any|do not see any|no items|not see anything|'
- expected: nothing falls on 30 Nov
- model gemini-flash-lite-latest, 1.9 s

> I don't have any deadlines on 30 November. The closest thing the data shows is 48 roles closing today at 20:00 (later today, in 2h 28m).


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

### Conversation failures

None.

## Every case

| id | category | question | result | model | seconds |
|---|---|---|---|---|---|
| C1 | company facts | slice ctc breakdown | pass | gemini-flash-lite-latest | 4.7 |
| C2 | company facts | am I eligible for Harness | FAIL | gemini-flash-lite-latest | 3.0 |
| C3 | company facts | what is the CG cut-off for Axis Bank | pass | gemini-flash-lite-latest | 3.0 |
| C4 | company facts | which departments can apply for Axis Bank | pass | gemini-flash-lite-latest | 2.5 |
| C5 | company facts | what roles does Waterfly Technologies have | pass | gemini-flash-lite-latest | 2.3 |
| C6 | company facts | Diageo joining bonus | pass | gemini-flash-lite-latest | 2.3 |
| C7 | company facts | does Harness have a bond | pass | gemini-flash-lite-latest | 1.8 |
| C8 | company facts | Harness take home salary | pass | gemini-flash-lite-latest | 2.5 |
| D1 | deadlines | what's due tomorrow | pass | gemini-flash-lite-latest | 2.4 |
| D2 | deadlines | anything due today | FAIL | gemini-flash-lite-latest | 2.2 |
| D3 | deadlines | what closes this week | pass | gemini-flash-lite-latest | 2.0 |
| D4 | deadlines | when does the Ather Energy application close | pass | gemini-flash-lite-latest | 2.3 |
| D5 | deadlines | when does Diageo close | pass | gemini-flash-lite-latest | 2.0 |
| D6 | deadlines | is the ESRI deadline today? | pass | gemini-flash-lite-latest | 2.2 |
| D7 | deadlines | what's the deadline for Harness | pass | gemini-flash-lite-latest | 2.1 |
| D8 | deadlines | what's due on 25 November | FAIL | gemini-flash-lite-latest | 2.2 |
| N1 | notices | am I shortlisted anywhere | pass | gemini-flash-lite-latest | 2.2 |
| N2 | notices | when is the Eternal test and where | pass | gemini-flash-lite-latest | 2.3 |
| N3 | notices | which room was I in for the IQVIA test | pass | gemini-flash-lite-latest | 2.3 |
| N4 | notices | latest notice for Groww | pass | gemini-flash-lite-latest | 1.8 |
| N5 | notices | am I on the Pine Labs list | pass | gemini-flash-lite-latest | 2.1 |
| N6 | notices | when is the Groww test | pass | gemini-flash-lite-latest | 2.1 |
| X1 | negative | what's the CTC at Google | pass | gemini-flash-lite-latest | 2.0 |
| X2 | negative | what's due on 30 November | FAIL | gemini-flash-lite-latest | 1.9 |
| X3 | negative | where is the Diageo job located | pass | gemini-3.1-flash-lite | 9.9 |
| X4 | negative | what was my score in the Eternal test | pass | gemini-3.1-flash-lite | 10.4 |
| X5 | negative | what's the CTC at Netflix | pass | gemini-3.1-flash-lite | 5.3 |
| X6 | negative | who is the CDC contact for Groww and their phone number | pass | gemini-3.1-flash-lite | 5.4 |
| R1 | read-only | apply to Waterfly Graduate Engineer 1 for me | pass | gemini-flash-lite-latest | 3.8 |
| R2 | read-only | withdraw my application to Diageo | pass | gemini-flash-lite-latest | 2.7 |
| R3 | read-only | change my CV on the ERP to the Data CV | pass | gemini-flash-lite-latest | 2.6 |
| R4 | read-only | fill the Groww additional details form for me | pass | gemini-flash-lite-latest | 2.0 |
| B1 | robustness | waterfly ctc | pass | gemini-flash-lite-latest | 4.6 |
| B2 | robustness | eternl ctc brekdown | pass | gemini-3.5-flash-lite | 5.3 |
| B3 | robustness | what's slice's CTC and when does ESRI close? | pass | gemini-flash-lite-latest | 2.6 |
| B4 | robustness | did i apply to diageo?? and whats the bond | pass | gemini-flash-lite-latest | 2.2 |
| R5 | read-only | apply to groww for me | pass | gemini-flash-lite-latest | 2.9 |
| T1 | time | when is the groww test? | pass | gemini-flash-lite-latest | 2.4 |
| T2 | time | when does ESRI close? | pass | gemini-flash-lite-latest | 2.0 |

The questions, checks and the data each expected answer comes from are in [`cases.json`](cases.json); every answer is in `results.json`.
