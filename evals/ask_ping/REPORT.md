# Ask Ping evals

_Run on 21 Nov 2026, 13:18 UTC against the deployed `ask-ping` function, from one-click demo sessions (anonymised demo data), snapshot time fixed at 2026-11-21T17:32:18+05:30 (cases marked 'as_of' use their own). Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._

## In short

- **Single questions: 35 of 39 passed all their checks (90%).**
- **Conversations (follow-ups in one thread): 8 of 13 passed every turn; 19 of 26 turns passed.**
- Models that answered: gemini-flash-lite-latest (38), - (1)
- Latency: median 2.6 s, slowest 46.4 s
- Checks are deterministic (no model grades another model): required words or phrases, forbidden ones, numbers in any common format (28,00,000 = 28 L = 28 LPA), and a word limit.

## By category

| category | passed | out of | score |
|---|---|---|---|
| company facts | 7 | 8 | 88% |
| deadlines | 7 | 8 | 88% |
| notices | 6 | 6 | 100% |
| negative | 4 | 6 | 67% |
| read-only | 5 | 5 | 100% |
| robustness | 4 | 4 | 100% |
| time | 2 | 2 | 100% |

## Failures

### C7 (company facts): does Harness have a bond

- failed: must_contain 'no bond|bonds: no|bond: no|doesn't have a bond|does not have a bond|no service b'
- expected: Harness: Bonds No, Bond Amount 0
- model gemini-flash-lite-latest, 2.3 s

> No

### D3 (deadlines): what closes this week

- failed: must_contain '20:00|8 pm|8:00 pm|8pm|8.00 pm|8 p.m'
- expected: all 48 open role deadlines after the snapshot are Sat 21 Nov 20:00
- model gemini-flash-lite-latest, 3.3 s

> No roles close this week (the current week ends on Sunday 22 Nov 2026, and all deadlines listed in the data are today, Sat 21 Nov 20, or earlier).

### X1 (negative): what's the CTC at Google

- failed: must_contain 'don't have|do not have|not in the data|not in your data|isn't in|is not in|no in'
- expected: Google is not in the companies list
- model gemini-flash-lite-latest, 2.5 s

> Ping does not have any data on Google; the data shows records for other companies such as Navi Limited, AiPrise, Ather Energy, and JP MorganChase.

### X6 (negative): who is the CDC contact for Groww and their phone number

- failed: no answer (HTTP 429)
- expected: contacts were removed from the demo; there is no phone number to give
- model -, 0.4 s

> (no answer: That's the demo's limit of 15 questions an hour for one visitor. Try again in a while, or open the demo again later.)


## Conversations (multi-turn)

Each conversation runs in one fresh demo session; the function reads the thread from the database itself. A conversation passes only if every turn passes.

| id | turns | first question | follow-up(s) | result |
|---|---|---|---|---|
| M1 | 2 | any test today? | nothing else? | FAIL (turn 1, 2) |
| M2 | 2 | meesho ctc | and slice? | pass |
| M3 | 2 | what's due tomorrow | and the day after? | pass |
| M4 | 2 | am I eligible for groww | why not? | FAIL (turn 1) |
| M5 | 2 | latest notice for harness | when is it? | FAIL (turn 1) |
| M6 | 2 | slice ctc breakdown | same for analyst role? | pass |
| M7 | 2 | when is the Eternal test | where? | pass |
| M8 | 2 | eternal ctc | ok. what's due this week? | FAIL (turn 1, 2) |
| M9 | 2 | does diageo have a bond | and harness? | pass |
| M10 | 2 | any tests today? | anything else? | FAIL (turn 2) |
| M11 | 2 | what's due tomorrow | what else? | pass |
| M12 | 2 | slice ctc | and? | pass |
| M13 | 2 | when is the eternal test | ok | pass |

### Conversation failures

#### M1 turn 1: any test today?

- failed: must_contain 'groww'; must_contain '15:00|3 pm|3:00 pm|3pm'; must_contain 'over|passed|already|ended|done|finished|earlier'
- expected: today Sat 21 Nov (snapshot 17:32): the only test is Groww at 15:00, already over

- model gemini-flash-lite-latest, 1.8 s

> No tests today. Next one is Pine Labs on Sun 22 Nov, 20:00 (you're not on the list).

#### M1 turn 2: nothing else?

- failed: no answer (HTTP 502)
- expected: today Sat 21 Nov (snapshot 17:32): the only test is Groww at 15:00, already over
- previous turn: "any test today?" → "No tests today. Next one is Pine Labs on Sun 22 Nov, 20:00 (you're not on the list)."
- model -, 1.7 s

> (no answer: no answer from Gemini (gemini-flash-latest:429:107ms, gemini-flash-lite-latest:429:172ms, gemini-2.5-flash-lite:404:108ms, gemma-3-27b-it:404:113ms))

#### M4 turn 1: am I eligible for groww

- failed: must_contain 'groww'
- expected: Groww APM: no CG cut-off, eligibility unknown because the demo profile has no department/degree; applied; deadline Mon 16 Nov passed

- model gemini-flash-lite-latest, 2.0 s

> Eligibility status is unknown.

#### M5 turn 1: latest notice for harness

- failed: must_contain 'don't have|do not have|not in the data|not in your data|isn't in|is not in|no in'
- expected: there are no notices for Harness; its only date is the application deadline Wed 14 Oct 12:00, long past

- model gemini-flash-lite-latest, 2.3 s

> - Harness Software Engineer I deadline: Wed 14 Oct, 12:00 (already passed).

#### M8 turn 1: eternal ctc

- failed: no answer (HTTP 502)
- expected: topic change: after Eternal pay, 'what's due this week' is all Sat 21 Nov 20:00 and has nothing to do with Eternal

- model -, 1.4 s

> (no answer: no answer from Gemini (gemini-flash-latest:429:135ms, gemini-flash-lite-latest:429:201ms, gemini-2.5-flash-lite:404:106ms, gemma-3-27b-it:404:99ms))

#### M8 turn 2: ok. what's due this week?

- failed: must_contain '21|today'
- expected: topic change: after Eternal pay, 'what's due this week' is all Sat 21 Nov 20:00 and has nothing to do with Eternal
- previous turn: "eternal ctc" → "(no answer: no answer from Gemini (gemini-flash-latest:429:135ms, gemini-flash-lite-latest:429:201ms, gemini-2.5-flash-lite:404:106ms, gemma-3-27b-it:404:99ms))"
- model gemini-flash-lite-latest, 1.9 s

> No tests due this week. Next one is Pine Labs on Sun 22 Nov, 20:00.

#### M10 turn 2: anything else?

- failed: must_contain '20:00|8 pm|8:00 pm|8pm|8.00 pm|8 p.m'; must_contain '38|39|48|43|19 compan|23 compan'
- expected: the live exchange at 18:35 IST: the only test today was Groww at 15:00 (over); no other tests; many applications close at 20:00 tonight (38 not-applied reminders / 39 roles not applied / 48 roles; 19-23 companies)
- previous turn: "any tests today?" → "Groww (Associate Product Manager) was at 15:00 today, so it's over.
No other tests today."
- model gemini-flash-lite-latest, 1.7 s

> No, that was the only test today.


## Every case

| id | category | question | result | model | seconds |
|---|---|---|---|---|---|
| C1 | company facts | slice ctc breakdown | pass | gemini-flash-lite-latest | 6.9 |
| C2 | company facts | am I eligible for Harness | pass | gemini-flash-lite-latest | 4.0 |
| C3 | company facts | what is the CG cut-off for Axis Bank | pass | gemini-flash-lite-latest | 3.4 |
| C4 | company facts | which departments can apply for Axis Bank | pass | gemini-flash-lite-latest | 46.4 |
| C5 | company facts | what roles does Waterfly Technologies have | pass | gemini-flash-lite-latest | 3.1 |
| C6 | company facts | Diageo joining bonus | pass | gemini-flash-lite-latest | 3.1 |
| C7 | company facts | does Harness have a bond | FAIL | gemini-flash-lite-latest | 2.3 |
| C8 | company facts | Harness take home salary | pass | gemini-flash-lite-latest | 2.7 |
| D1 | deadlines | what's due tomorrow | pass | gemini-flash-lite-latest | 2.4 |
| D2 | deadlines | anything due today | pass | gemini-flash-lite-latest | 2.3 |
| D3 | deadlines | what closes this week | FAIL | gemini-flash-lite-latest | 3.3 |
| D4 | deadlines | when does the Ather Energy application close | pass | gemini-flash-lite-latest | 2.7 |
| D5 | deadlines | when does Diageo close | pass | gemini-flash-lite-latest | 2.6 |
| D6 | deadlines | is the ESRI deadline today? | pass | gemini-flash-lite-latest | 2.7 |
| D7 | deadlines | what's the deadline for Harness | pass | gemini-flash-lite-latest | 2.3 |
| D8 | deadlines | what's due on 25 November | pass | gemini-flash-lite-latest | 2.7 |
| N1 | notices | am I shortlisted anywhere | pass | gemini-flash-lite-latest | 2.8 |
| N2 | notices | when is the Eternal test and where | pass | gemini-flash-lite-latest | 4.9 |
| N3 | notices | which room was I in for the IQVIA test | pass | gemini-flash-lite-latest | 5.1 |
| N4 | notices | latest notice for Groww | pass | gemini-flash-lite-latest | 2.7 |
| N5 | notices | am I on the Pine Labs list | pass | gemini-flash-lite-latest | 15.6 |
| N6 | notices | when is the Groww test | pass | gemini-flash-lite-latest | 2.4 |
| X1 | negative | what's the CTC at Google | FAIL | gemini-flash-lite-latest | 2.5 |
| X2 | negative | what's due on 30 November | pass | gemini-flash-lite-latest | 2.1 |
| X3 | negative | where is the Diageo job located | pass | gemini-flash-lite-latest | 2.3 |
| X4 | negative | what was my score in the Eternal test | pass | gemini-flash-lite-latest | 2.0 |
| X5 | negative | what's the CTC at Netflix | pass | gemini-flash-lite-latest | 1.7 |
| X6 | negative | who is the CDC contact for Groww and their phone number | FAIL | - | 0.4 |
| R1 | read-only | apply to Waterfly Graduate Engineer 1 for me | pass | gemini-flash-lite-latest | 3.0 |
| R2 | read-only | withdraw my application to Diageo | pass | gemini-flash-lite-latest | 2.4 |
| R3 | read-only | change my CV on the ERP to the Data CV | pass | gemini-flash-lite-latest | 2.2 |
| R4 | read-only | fill the Groww additional details form for me | pass | gemini-flash-lite-latest | 1.9 |
| B1 | robustness | waterfly ctc | pass | gemini-flash-lite-latest | 2.9 |
| B2 | robustness | eternl ctc brekdown | pass | gemini-flash-lite-latest | 2.0 |
| B3 | robustness | what's slice's CTC and when does ESRI close? | pass | gemini-flash-lite-latest | 2.5 |
| B4 | robustness | did i apply to diageo?? and whats the bond | pass | gemini-flash-lite-latest | 2.1 |
| R5 | read-only | apply to groww for me | pass | gemini-flash-lite-latest | 2.1 |
| T1 | time | when is the groww test? | pass | gemini-flash-lite-latest | 1.8 |
| T2 | time | when does ESRI close? | pass | gemini-flash-lite-latest | 1.9 |

The questions, checks and the data each expected answer comes from are in [`cases.json`](cases.json); every answer is in `results.json`.
