# Ask Ping evals

_Run on 21 Nov 2026, 13:06 UTC against the deployed `ask-ping` function, from one-click demo sessions (anonymised demo data), snapshot time fixed at 2026-11-21T17:32:18+05:30. Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._

## In short

- **Single questions: 34 of 36 passed all their checks (94%).**
- **Conversations (follow-ups in one thread): 4 of 9 passed every turn; 13 of 18 turns passed.**
- Models that answered: gemini-flash-lite-latest (34), - (2)
- Latency: median 4.5 s, slowest 13.3 s
- Checks are deterministic (no model grades another model): required words or phrases, forbidden ones, numbers in any common format (28,00,000 = 28 L = 28 LPA), and a word limit.

## By category

| category | passed | out of | score |
|---|---|---|---|
| company facts | 8 | 8 | 100% |
| deadlines | 7 | 8 | 88% |
| notices | 5 | 6 | 83% |
| negative | 6 | 6 | 100% |
| read-only | 4 | 4 | 100% |
| robustness | 4 | 4 | 100% |

## Failures

### D6 (deadlines): is the ESRI deadline today?

- failed: no answer (HTTP 502)
- expected: ESRI Data Scientist I: Sat 21 Nov 20:00
- model -, 5.8 s

> (no answer: no answer from Gemini (gemini-flash-latest:429:82ms, gemini-flash-lite-latest:503:2093ms, gemini-2.0-flash:404:50ms))

### N2 (notices): when is the Eternal test and where

- failed: no answer (HTTP 502)
- expected: Eternal test Thu 19 Nov 19:15, Nalanda Classroom Complex, your room NR 121
- model -, 11.1 s

> (no answer: no answer from Gemini (gemini-flash-latest:429:58ms, gemini-flash-lite-latest:503:8147ms, gemini-2.0-flash:404:76ms))


## Conversations (multi-turn)

Each conversation runs in one fresh demo session; the function reads the thread from the database itself. A conversation passes only if every turn passes.

| id | turns | first question | follow-up(s) | result |
|---|---|---|---|---|
| M1 | 2 | any test today? | nothing else? | FAIL (turn 2) |
| M2 | 2 | meesho ctc | and slice? | pass |
| M3 | 2 | what's due tomorrow | and the day after? | FAIL (turn 2) |
| M4 | 2 | am I eligible for groww | why not? | FAIL (turn 2) |
| M5 | 2 | latest notice for harness | when is it? | FAIL (turn 2) |
| M6 | 2 | slice ctc breakdown | same for analyst role? | FAIL (turn 2) |
| M7 | 2 | when is the Eternal test | where? | pass |
| M8 | 2 | eternal ctc | ok. what's due this week? | pass |
| M9 | 2 | does diageo have a bond | and harness? | pass |

### Conversation failures

#### M1 turn 2: nothing else?

- failed: must_contain 'only|no other|no more|none|no further|nothing else today|no, '
- expected: today Sat 21 Nov (snapshot 17:32): the only test is Groww at 15:00, already over
- previous turn: "any test today?" → "Ping is read-only, so I can't check or change anything on the ERP, but the data shows one test today: Groww (Associate Product Manager) on Sat 21 Nov 15:00 (already passed)."
- model gemini-flash-lite-latest, 3.3 s

> The data does not show anything else.

#### M3 turn 2: and the day after?

- failed: must_contain '23|monday'
- expected: nothing falls on Sun 22 Nov or Mon 23 Nov
- previous turn: "what's due tomorrow" → "The data does not show anything due tomorrow (Sunday 22 November 2026), but it shows deadlines that were due today, Saturday 21 November 2026, at 20:00."
- model gemini-flash-lite-latest, 10.5 s

> The data does not show anything scheduled for the day after (Sunday 22 November 2026). The data does show deadlines and tests up to Saturday 21 November 2026.

#### M4 turn 2: why not?

- failed: must_contain 'department|degree|profile'
- expected: Groww APM: no CG cut-off, eligibility unknown because the demo profile has no department/degree; applied; deadline Mon 16 Nov passed
- previous turn: "am I eligible for groww" → "The data does not show whether you are eligible for Groww; it only shows that your eligibility status is unknown."
- model gemini-flash-lite-latest, 3.1 s

> Ping is read-only, so I can't apply for you. The data does not state why you were not on the Pine Labs shortlist (Software Development Engineer); the deadline to submit was Sun 22 Nov 20:00 (already passed).

#### M5 turn 2: when is it?

- failed: must_contain '14 oct|oct 14|14th oct|october 14|14 october|14-oct'
- expected: there are no notices for Harness; its only date is the application deadline Wed 14 Oct 12:00, long past
- previous turn: "latest notice for harness" → "The data does not show a notice for Harness. The data does show that the Harness Software Engineer I deadline was Wed 14 Oct 12:00 (already passed)."
- model gemini-flash-lite-latest, 2.6 s

> The data does not specify what "it" refers to; it shows deadlines and test schedules for multiple companies, such as Groww's test on Sat 21 Nov 15:00 (already passed) and various company deadlines on Sat 21 Nov 20:00.

#### M6 turn 2: same for analyst role?

- failed: must_contain 'esop'; numbers_present 2500000; numbers_present 1900000
- expected: slice APM 22L fixed + 2L retention + 4L ESOPs; Analyst 19L base + 2L retention + 4L ESOPs = 25,00,000
- previous turn: "slice ctc breakdown" → "**Analyst:**
- **Base Salary:** 19,00,000
- **Retention Bonus:** 2,00,000
- **ESOPs:** 4,00,000
- **1st Year CTC:** 25,00,000
- **Gross (per Annum):** 19,00,000
- **Joining Bonus:** 0
- **Relocation B"
- model gemini-flash-lite-latest, 12.4 s

> Ping is read-only, so I can't apply, withdraw, accept or decline offers, fill or submit forms, upload or change a CV, or change anything on the ERP or anywhere else. 
> 
> The data does not show details for an "analyst" role beyond what is listed for specific companies and roles (such as Auronova Consulting Analyst at 14,00,000 INR, DB Analyst at 35,59,500 INR, Deloitte Analyst at 13,00,000 INR, Houlihan Lokey Analyst at 28,00,000 INR, IQVIA Analyst at 13,77,000 INR, and YCP India Analyst at 13,77,600 INR).


## Every case

| id | category | question | result | model | seconds |
|---|---|---|---|---|---|
| C1 | company facts | slice ctc breakdown | pass | gemini-flash-lite-latest | 6.7 |
| C2 | company facts | am I eligible for Harness | pass | gemini-flash-lite-latest | 4.8 |
| C3 | company facts | what is the CG cut-off for Axis Bank | pass | gemini-flash-lite-latest | 5.0 |
| C4 | company facts | which departments can apply for Axis Bank | pass | gemini-flash-lite-latest | 3.2 |
| C5 | company facts | what roles does Waterfly Technologies have | pass | gemini-flash-lite-latest | 3.5 |
| C6 | company facts | Diageo joining bonus | pass | gemini-flash-lite-latest | 3.0 |
| C7 | company facts | does Harness have a bond | pass | gemini-flash-lite-latest | 2.9 |
| C8 | company facts | Harness take home salary | pass | gemini-flash-lite-latest | 2.7 |
| D1 | deadlines | what's due tomorrow | pass | gemini-flash-lite-latest | 2.7 |
| D2 | deadlines | anything due today | pass | gemini-flash-lite-latest | 12.2 |
| D3 | deadlines | what closes this week | pass | gemini-flash-lite-latest | 4.1 |
| D4 | deadlines | when does the Ather Energy application close | pass | gemini-flash-lite-latest | 2.5 |
| D5 | deadlines | when does Diageo close | pass | gemini-flash-lite-latest | 2.0 |
| D6 | deadlines | is the ESRI deadline today? | FAIL | - | 5.8 |
| D7 | deadlines | what's the deadline for Harness | pass | gemini-flash-lite-latest | 11.7 |
| D8 | deadlines | what's due on 25 November | pass | gemini-flash-lite-latest | 9.5 |
| N1 | notices | am I shortlisted anywhere | pass | gemini-flash-lite-latest | 4.5 |
| N2 | notices | when is the Eternal test and where | FAIL | - | 11.1 |
| N3 | notices | which room was I in for the IQVIA test | pass | gemini-flash-lite-latest | 4.5 |
| N4 | notices | latest notice for Groww | pass | gemini-flash-lite-latest | 11.2 |
| N5 | notices | am I on the Pine Labs list | pass | gemini-flash-lite-latest | 2.9 |
| N6 | notices | when is the Groww test | pass | gemini-flash-lite-latest | 3.7 |
| X1 | negative | what's the CTC at Google | pass | gemini-flash-lite-latest | 9.4 |
| X2 | negative | what's due on 30 November | pass | gemini-flash-lite-latest | 11.9 |
| X3 | negative | where is the Diageo job located | pass | gemini-flash-lite-latest | 3.4 |
| X4 | negative | what was my score in the Eternal test | pass | gemini-flash-lite-latest | 5.8 |
| X5 | negative | what's the CTC at Netflix | pass | gemini-flash-lite-latest | 13.3 |
| X6 | negative | who is the CDC contact for Groww and their phone number | pass | gemini-flash-lite-latest | 4.1 |
| R1 | read-only | apply to Waterfly Graduate Engineer 1 for me | pass | gemini-flash-lite-latest | 5.2 |
| R2 | read-only | withdraw my application to Diageo | pass | gemini-flash-lite-latest | 11.7 |
| R3 | read-only | change my CV on the ERP to the Data CV | pass | gemini-flash-lite-latest | 5.2 |
| R4 | read-only | fill the Groww additional details form for me | pass | gemini-flash-lite-latest | 4.0 |
| B1 | robustness | waterfly ctc | pass | gemini-flash-lite-latest | 4.0 |
| B2 | robustness | eternl ctc brekdown | pass | gemini-flash-lite-latest | 4.5 |
| B3 | robustness | what's slice's CTC and when does ESRI close? | pass | gemini-flash-lite-latest | 6.6 |
| B4 | robustness | did i apply to diageo?? and whats the bond | pass | gemini-flash-lite-latest | 4.0 |

The questions, checks and the data each expected answer comes from are in [`cases.json`](cases.json); every answer is in `results.json`.
