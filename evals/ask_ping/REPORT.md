# Ask Ping evals

_Run on 21 Nov 2026, 12:40 UTC against the deployed `ask-ping` function, signed in as the reviewer login (anonymised demo data), snapshot time fixed at 2026-11-21T17:32:18+05:30. Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._

## In short

- **32 of 36 questions passed all their checks (89%).**
- Models that answered: gemini-flash-lite-latest (36)
- Latency: median 3.3 s, slowest 47.9 s
- Checks are deterministic (no model grades another model): required words or phrases, forbidden ones, numbers in any common format (28,00,000 = 28 L = 28 LPA), and a word limit.

## By category

| category | passed | out of | score |
|---|---|---|---|
| company facts | 7 | 8 | 88% |
| deadlines | 8 | 8 | 100% |
| notices | 5 | 6 | 83% |
| negative | 4 | 6 | 67% |
| read-only | 4 | 4 | 100% |
| robustness | 4 | 4 | 100% |

## Failures

### C7 (company facts): does Harness have a bond

- failed: max_words 60 (had 77)
- expected: Harness: Bonds No, Bond Amount 0
- model gemini-flash-lite-latest, 47.9 s

> Yes.
> 
> **Harness | Software Engineer I**
> - Bonds: No (Bond Amount: 0)
> - CTC Breakup: 7,728,117 INR
> - 1st Year CTC: 4,728,117 INR
> - Gross (per Annum): 2,700,000 INR
> - Joining Bonus: 500,000 INR
> - Retention Bonus: 0
> - Relocation Bonus: 200,000 INR
> - Fixed Take Home Salary (per Annum): 2,700,000 INR
> - Base Salary: 2,454,545 INR
> - Other perks/benefits: Zomato credits - 1700/ week, Commuter stipend - 3000 / month, Broadband reimbursement - 2100 / month

### N2 (notices): when is the Eternal test and where

- failed: must_contain 'nr 121'
- expected: Eternal test Thu 19 Nov 19:15, Nalanda Classroom Complex, your room NR 121
- model gemini-flash-lite-latest, 3.3 s

> The Eternal test was on Thu 19 Nov 2026 at 19:15 at Nalanda Classroom Complex (already passed).

### X3 (negative): where is the Diageo job located

- failed: max_words 70 (had 81)
- expected: the data has no location for Diageo (no location field at all)
- model gemini-flash-lite-latest, 3.5 s

> The data does not show the job location for Diageo. The data does show the following details for Diageo GBS Management Trainee: deadline Sat 21 Nov 20:00 (applied: yes), CTC 32,00,000 INR (includes 5,00,000 joining bonus), 1st Year CTC 32,00,000 INR, Gross per annum 27,00,000 INR, Base Salary 24,30,000 INR, Fixed Take Home Salary per annum 24,30,000 INR, Joining Bonus 5,00,000 INR, Retention Bonus 0, Relocation Bonus 0, Bond Amount 0, Bonds No, written test Yes, and CG cut-off none given.

### X5 (negative): what's the CTC at Netflix

- failed: must_not_contain 'lpa'
- expected: Netflix is not in the companies list
- model gemini-flash-lite-latest, 2.5 s

> The data does not show Netflix, but it lists CTCs for other companies such as Eternal (59 LPA), Microsoft Corporation (5,637,500 INR), and Amazon (4,838,500 INR).


## Every case

| id | category | question | result | model | seconds |
|---|---|---|---|---|---|
| C1 | company facts | slice ctc breakdown | pass | gemini-flash-lite-latest | 5.2 |
| C2 | company facts | am I eligible for Harness | pass | gemini-flash-lite-latest | 18.6 |
| C3 | company facts | what is the CG cut-off for Axis Bank | pass | gemini-flash-lite-latest | 4.3 |
| C4 | company facts | which departments can apply for Axis Bank | pass | gemini-flash-lite-latest | 3.9 |
| C5 | company facts | what roles does Waterfly Technologies have | pass | gemini-flash-lite-latest | 8.6 |
| C6 | company facts | Diageo joining bonus | pass | gemini-flash-lite-latest | 3.3 |
| C7 | company facts | does Harness have a bond | FAIL | gemini-flash-lite-latest | 47.9 |
| C8 | company facts | Harness take home salary | pass | gemini-flash-lite-latest | 4.0 |
| D1 | deadlines | what's due tomorrow | pass | gemini-flash-lite-latest | 3.6 |
| D2 | deadlines | anything due today | pass | gemini-flash-lite-latest | 9.7 |
| D3 | deadlines | what closes this week | pass | gemini-flash-lite-latest | 6.2 |
| D4 | deadlines | when does the Ather Energy application close | pass | gemini-flash-lite-latest | 3.1 |
| D5 | deadlines | when does Diageo close | pass | gemini-flash-lite-latest | 2.4 |
| D6 | deadlines | is the ESRI deadline today? | pass | gemini-flash-lite-latest | 7.6 |
| D7 | deadlines | what's the deadline for Harness | pass | gemini-flash-lite-latest | 3.0 |
| D8 | deadlines | what's due on 25 November | pass | gemini-flash-lite-latest | 2.7 |
| N1 | notices | am I shortlisted anywhere | pass | gemini-flash-lite-latest | 2.5 |
| N2 | notices | when is the Eternal test and where | FAIL | gemini-flash-lite-latest | 3.3 |
| N3 | notices | which room was I in for the IQVIA test | pass | gemini-flash-lite-latest | 1.7 |
| N4 | notices | latest notice for Groww | pass | gemini-flash-lite-latest | 8.3 |
| N5 | notices | am I on the Pine Labs list | pass | gemini-flash-lite-latest | 2.4 |
| N6 | notices | when is the Groww test | pass | gemini-flash-lite-latest | 1.7 |
| X1 | negative | what's the CTC at Google | pass | gemini-flash-lite-latest | 31.1 |
| X2 | negative | what's due on 30 November | pass | gemini-flash-lite-latest | 4.1 |
| X3 | negative | where is the Diageo job located | FAIL | gemini-flash-lite-latest | 3.5 |
| X4 | negative | what was my score in the Eternal test | pass | gemini-flash-lite-latest | 3.3 |
| X5 | negative | what's the CTC at Netflix | FAIL | gemini-flash-lite-latest | 2.5 |
| X6 | negative | who is the CDC contact for Groww and their phone number | pass | gemini-flash-lite-latest | 3.2 |
| R1 | read-only | apply to Waterfly Graduate Engineer 1 for me | pass | gemini-flash-lite-latest | 3.0 |
| R2 | read-only | withdraw my application to Diageo | pass | gemini-flash-lite-latest | 2.6 |
| R3 | read-only | change my CV on the ERP to the Data CV | pass | gemini-flash-lite-latest | 2.8 |
| R4 | read-only | fill the Groww additional details form for me | pass | gemini-flash-lite-latest | 3.2 |
| B1 | robustness | waterfly ctc | pass | gemini-flash-lite-latest | 3.4 |
| B2 | robustness | eternl ctc brekdown | pass | gemini-flash-lite-latest | 2.6 |
| B3 | robustness | what's slice's CTC and when does ESRI close? | pass | gemini-flash-lite-latest | 2.6 |
| B4 | robustness | did i apply to diageo?? and whats the bond | pass | gemini-flash-lite-latest | 2.5 |

The questions, checks and the data each expected answer comes from are in [`cases.json`](cases.json); every answer is in `results.json`.
