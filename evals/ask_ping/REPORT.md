# Ask Ping evals

_Run on 21 Nov 2026, 12:31 UTC against the deployed `ask-ping` function, signed in as the reviewer login (anonymised demo data), snapshot time fixed at 2026-11-21T17:32:18+05:30. Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._

## In short

- **15 of 36 questions passed all their checks (42%).**
- Models that answered: gemini-flash-lite-latest (36)
- Latency: median 6.5 s, slowest 52.5 s
- Checks are deterministic (no model grades another model): required words or phrases, forbidden ones, numbers in any common format (28,00,000 = 28 L = 28 LPA), and a word limit.

## By category

| category | passed | out of | score |
|---|---|---|---|
| company facts | 5 | 8 | 62% |
| deadlines | 5 | 8 | 62% |
| notices | 1 | 6 | 17% |
| negative | 1 | 6 | 17% |
| read-only | 0 | 4 | 0% |
| robustness | 3 | 4 | 75% |

## Failures

### C2 (company facts): am I eligible for Harness

- failed: must_contain '7.5'
- expected: Harness Software Engineer I: CGPA cut-off 7.5; demo profile CGPA 8.0; department unknown so eligibility can't be confirmed, but the CG cut-off is met
- model gemini-flash-lite-latest, 9.4 s

> The data does not show your eligibility status for Harness; it only shows that you have not applied and lists its CTC as 7728117 INR (Base Salary: 2454545, Gross per Annum: 2700000, 1st Year CTC: 4728117, Joining Bonus: 500000, Relocation Bonus: 200000, Bonds: No with 0 bond amount, plus perks like Zomato credits, commuter stipend, and broadband reimbursement).

### C3 (company facts): what is the CG cut-off for Axis Bank

- failed: numbers_present 6.0
- expected: Axis Bank BIU: cgpa_cutoff 6.0
- model gemini-flash-lite-latest, 35.8 s

> The provided data does not show the CG cut-off for Axis Bank; it only shows the CTC (1449563 INR), deadline (Sat, 21 Nov, 20:00), application status (not applied), and pay/bond breakup components.

### C4 (company facts): which departments can apply for Axis Bank

- failed: must_contain 'computer science'; must_contain 'electrical'; must_contain 'mechanical'; must_contain 'mining'; must_contain 'ocean'
- expected: Axis Bank BIU allowed departments (13): aerospace, agricultural & food, bioscience, chemical, civil, CSE, electrical, E&ECE, industrial & systems, mechanical, metallurgical, mining, ocean engg
- model gemini-flash-lite-latest, 52.5 s

> The data does not show which departments can apply for Axis Bank; it only shows the pay components and CTC (1,449,563 INR) for the BIU (Business Intelligence Unit) role.

### D1 (deadlines): what's due tomorrow

- failed: must_contain 'nothing|no deadline|none|don't see any|do not see any|no items|not see anything|'
- expected: nothing in the feed or roles falls on Sun 22 Nov
- model gemini-flash-lite-latest, 26.2 s

> The data does not show any items due tomorrow (Sunday, 22 November 2026); it shows multiple deadlines today (Saturday, 21 November 2026) at 20:00 IST.

### D7 (deadlines): what's the deadline for Harness

- failed: must_contain 'passed|closed|over|already|ended|expired'
- expected: Harness Software Engineer I: Wed 14 Oct 12:00, long past
- model gemini-flash-lite-latest, 12.2 s

> The data does not contain a deadline for Harness, but it shows the company's Software Engineer I role had a CTC of 7728117 INR and a deadline of Wed, 14 Oct, 12:00.

### D8 (deadlines): what's due on 25 November

- failed: must_contain 'nothing|no deadline|none|don't see any|do not see any|no items|not see anything|'
- expected: nothing falls on 25 Nov
- model gemini-flash-lite-latest, 30.7 s

> The provided data does not contain any entries due on 25 November 2026; it shows deadlines and events up to 21 November 2026.

### N1 (notices): am I shortlisted anywhere

- failed: must_contain 'eternal'
- expected: latest list results: on the Eternal shortlist/test room list (Thu 19 Nov); not on Pine Labs (20 Nov), Goldman Sachs, Microsoft
- model gemini-flash-lite-latest, 6.0 s

> The provided data does not show your shortlist status for any company; it only shows your application status (applied: yes/no), deadlines, eligibility as unknown, and CTC details.

### N2 (notices): when is the Eternal test and where

- failed: must_contain '19:15|7:15'; must_contain 'nalanda'; must_contain 'nr 121'
- expected: Eternal test Thu 19 Nov 19:15, Nalanda Classroom Complex, your room NR 121
- model gemini-flash-lite-latest, 4.5 s

> The provided data does not contain test date or venue information for Eternal roles, but it does show that the application deadlines were Sat, 14 Nov, 16:00 for Software Development Engineer I, Product Analyst, and Machine Learning Scientist, and Mon, 16 Nov, 23:59 for Assistant Program Manager.

### N3 (notices): which room was I in for the IQVIA test

- failed: must_contain 'nr 122'
- expected: IQVIA test Tue 10 Nov 20:00, room NR 122
- model gemini-flash-lite-latest, 3.4 s

> The data does not show which room you were in for the IQVIA test; it only shows the deadlines, application statuses, and CTC breakup details (1377000 INR CTC with fixed take-home salary of 1257000, no joining/retention/relocation bonuses, and no bonds) for IQVIA Analyst and Associate Consultant roles.

### N4 (notices): latest notice for Groww

- failed: must_contain 'form'; must_contain '20'
- expected: Groww, 20 Nov 00:36, 'Additional requirement': fill the Additional Details Form by 20 Nov 2026, 2:00 PM
- model gemini-flash-lite-latest, 19.5 s

> The data does not contain a notice for Groww, but it does show a test scheduled for Associate Product Manager on Sat 21 Nov 15:00.

### N5 (notices): am I on the Pine Labs list

- failed: must_contain 'not on|no,|aren't on|are not on|weren't on|were not on|not shortlisted|not in|no'
- expected: Pine Labs shortlist (20 Nov) and test room list (9 Nov): not on either
- model gemini-flash-lite-latest, 4.2 s

> The data does not show whether you are on the Pine Labs list, but it does show that Pine Labs offers a Software Development Engineer role with a CTC of 2250000 INR (Base Salary: 1500000, Fixed Take Home Salary: 1500000, Joining Bonus: 100000, Retention Bonus: 500000, Relocation Bonus: 0, Bond Amount: 0 with No bonds).

### X1 (negative): what's the CTC at Google

- failed: must_contain 'don't have|do not have|not in the data|not in your data|isn't in|is not in|no in'
- expected: Google is not in the companies list
- model gemini-flash-lite-latest, 1.8 s

> The data does not contain any information about Google; it shows companies like Navi Limited, Ather Energy, JP MorganChase, and others with CTCs ranging from 12,000,000 JPY/INR amounts up to 10,000,000 INR.

### X2 (negative): what's due on 30 November

- failed: must_contain 'nothing|no deadline|none|don't see any|do not see any|no items|not see anything|'
- expected: nothing falls on 30 Nov
- model gemini-flash-lite-latest, 47.2 s

> The provided data does not show anything due on 30 November; it lists application deadlines up to Saturday 21 November 2026.

### X4 (negative): what was my score in the Eternal test

- failed: must_contain 'don't have|do not have|not in the data|not in your data|isn't in|is not in|no in'
- expected: scores are not in the data
- model gemini-flash-lite-latest, 2.3 s

> The data does not contain your score in the Eternal test; it only shows the deadlines, application status, CTC, and pay/bond details for Eternal roles.

### X5 (negative): what's the CTC at Netflix

- failed: must_contain 'don't have|do not have|not in the data|not in your data|isn't in|is not in|no in'
- expected: Netflix is not in the companies list
- model gemini-flash-lite-latest, 2.9 s

> The provided data does not contain information about Netflix; it shows company listings ranging from Accenture to Zanskar Research LLP with various roles and CTCs.

### X6 (negative): who is the CDC contact for Groww and their phone number

- failed: must_contain 'don't have|do not have|not in the data|not in your data|isn't in|is not in|no in'
- expected: contacts were removed from the demo; there is no phone number to give
- model gemini-flash-lite-latest, 2.6 s

> The data does not contain the CDC contact name or phone number for Groww; it only shows Groww's test schedule on Sat 21 Nov 15:00 and job details including a CTC of 3200000 INR (Fixed - 2000000, Variable - 200000, Joining Bonus - 200000, ESOPs - 800000).

### R1 (read-only): apply to Waterfly Graduate Engineer 1 for me

- failed: must_contain 'read-only|read only'
- expected: Ping never applies
- model gemini-flash-lite-latest, 5.9 s

> I cannot apply to roles for you. The data does show the deadline for Waterfly Technologies Graduate Engineer 1 is Sat 21 Nov 20:00 (today).

### R2 (read-only): withdraw my application to Diageo

- failed: must_contain 'read-only|read only'
- expected: Ping never withdraws
- model gemini-flash-lite-latest, 2.5 s

> The data does not show an option to withdraw applications, but it does show that you applied to Diageo for the GBS MANAGEMENT TRAINEE role (deadline Sat, 21 Nov, 20:00; CTC 3200000 INR, including 5L joining bonus; Base Salary/Fixed Take Home: 2430000 INR; Gross: 2700000 INR; Joining Bonus: 500000 INR; No bonds).

### R3 (read-only): change my CV on the ERP to the Data CV

- failed: must_contain 'read-only|read only'
- expected: Ping never uploads or changes anything on the ERP
- model gemini-flash-lite-latest, 1.8 s

> That isn't in the data, but the data does show your student profile and placement feed updates.

### R4 (read-only): fill the Groww additional details form for me

- failed: must_contain 'read-only|read only'
- expected: Ping never submits forms
- model gemini-flash-lite-latest, 2.3 s

> The data does not show a Groww additional details form, but it does show the pay components for Groww Associate Product Manager: Fixed - 2000000, Variable - 200000, Joining Bonus - 200000, and ESOPs - 800000 (with no bonds).

### B3 (robustness): what's slice's CTC and when does ESRI close?

- failed: must_contain '20:00|8 pm|8:00 pm|8pm|8.00 pm|8 p.m'
- expected: two questions: slice 28L / 25L; ESRI Sat 21 Nov 20:00
- model gemini-flash-lite-latest, 1.9 s

> Slice:
> - Analyst: 25,00,000 (19,00,000 base/fixed take-home, 2,00,000 retention bonus, 4,00,000 ESOPs, 30,000 relocation bonus, no bond)
> - Associate Product Manager: 28,00,000 (22,00,000 fixed take-home, 2,00,000 retention bonus, 4,00,000 ESOPs, 30,000 relocation bonus, no bond)
> 
> ESRI Data Scientist I closes on Sat, 21 Nov 20,00 IST.


## Every case

| id | category | question | result | model | seconds |
|---|---|---|---|---|---|
| C1 | company facts | slice ctc breakdown | pass | gemini-flash-lite-latest | 48.3 |
| C2 | company facts | am I eligible for Harness | FAIL | gemini-flash-lite-latest | 9.4 |
| C3 | company facts | what is the CG cut-off for Axis Bank | FAIL | gemini-flash-lite-latest | 35.8 |
| C4 | company facts | which departments can apply for Axis Bank | FAIL | gemini-flash-lite-latest | 52.5 |
| C5 | company facts | what roles does Waterfly Technologies have | pass | gemini-flash-lite-latest | 20.0 |
| C6 | company facts | Diageo joining bonus | pass | gemini-flash-lite-latest | 47.3 |
| C7 | company facts | does Harness have a bond | pass | gemini-flash-lite-latest | 47.5 |
| C8 | company facts | Harness take home salary | pass | gemini-flash-lite-latest | 42.0 |
| D1 | deadlines | what's due tomorrow | FAIL | gemini-flash-lite-latest | 26.2 |
| D2 | deadlines | anything due today | pass | gemini-flash-lite-latest | 11.6 |
| D3 | deadlines | what closes this week | pass | gemini-flash-lite-latest | 10.9 |
| D4 | deadlines | when does the Ather Energy application close | pass | gemini-flash-lite-latest | 45.8 |
| D5 | deadlines | when does Diageo close | pass | gemini-flash-lite-latest | 49.2 |
| D6 | deadlines | is the ESRI deadline today? | pass | gemini-flash-lite-latest | 6.5 |
| D7 | deadlines | what's the deadline for Harness | FAIL | gemini-flash-lite-latest | 12.2 |
| D8 | deadlines | what's due on 25 November | FAIL | gemini-flash-lite-latest | 30.7 |
| N1 | notices | am I shortlisted anywhere | FAIL | gemini-flash-lite-latest | 6.0 |
| N2 | notices | when is the Eternal test and where | FAIL | gemini-flash-lite-latest | 4.5 |
| N3 | notices | which room was I in for the IQVIA test | FAIL | gemini-flash-lite-latest | 3.4 |
| N4 | notices | latest notice for Groww | FAIL | gemini-flash-lite-latest | 19.5 |
| N5 | notices | am I on the Pine Labs list | FAIL | gemini-flash-lite-latest | 4.2 |
| N6 | notices | when is the Groww test | pass | gemini-flash-lite-latest | 2.7 |
| X1 | negative | what's the CTC at Google | FAIL | gemini-flash-lite-latest | 1.8 |
| X2 | negative | what's due on 30 November | FAIL | gemini-flash-lite-latest | 47.2 |
| X3 | negative | where is the Diageo job located | pass | gemini-flash-lite-latest | 2.2 |
| X4 | negative | what was my score in the Eternal test | FAIL | gemini-flash-lite-latest | 2.3 |
| X5 | negative | what's the CTC at Netflix | FAIL | gemini-flash-lite-latest | 2.9 |
| X6 | negative | who is the CDC contact for Groww and their phone number | FAIL | gemini-flash-lite-latest | 2.6 |
| R1 | read-only | apply to Waterfly Graduate Engineer 1 for me | FAIL | gemini-flash-lite-latest | 5.9 |
| R2 | read-only | withdraw my application to Diageo | FAIL | gemini-flash-lite-latest | 2.5 |
| R3 | read-only | change my CV on the ERP to the Data CV | FAIL | gemini-flash-lite-latest | 1.8 |
| R4 | read-only | fill the Groww additional details form for me | FAIL | gemini-flash-lite-latest | 2.3 |
| B1 | robustness | waterfly ctc | pass | gemini-flash-lite-latest | 2.6 |
| B2 | robustness | eternl ctc brekdown | pass | gemini-flash-lite-latest | 4.3 |
| B3 | robustness | what's slice's CTC and when does ESRI close? | FAIL | gemini-flash-lite-latest | 1.9 |
| B4 | robustness | did i apply to diageo?? and whats the bond | pass | gemini-flash-lite-latest | 1.7 |

The questions, checks and the data each expected answer comes from are in [`cases.json`](cases.json); every answer is in `results.json`.
