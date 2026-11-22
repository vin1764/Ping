# Ask Ping evals

_Run on 22 Nov 2026, 12:03 UTC against the deployed `ask-ping` function, from one-click demo sessions (anonymised demo data), snapshot time fixed at 2026-11-21T17:32:18+05:30 (cases marked 'as_of' use their own). Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._

## In short

- **Single questions: 56 of 70 passed all their checks (80%).**
- **Conversations (follow-ups in one thread): 19 of 21 passed every turn; 36 of 39 turns passed.**
- Models that answered: rules (62), jd-summary (5), gemini-3.1-flash-lite (3)
- **Main model only (gemini-flash-latest): 0 of 0 single questions passed (n/a); 0 of 0 conversation turns (n/a).** The other answers came from the lighter model or the rules answer (marked in the table below).
- Latency: median 5.1 s, slowest 20.3 s
- Checks are deterministic (no model grades another model): required words or phrases, forbidden ones, numbers in any common format (28,00,000 = 28 L = 28 LPA), and a word limit.

## By category

| category | passed | out of | score |
|---|---|---|---|
| company facts | 8 | 8 | 100% |
| deadlines | 5 | 8 | 62% |
| notices | 5 | 6 | 83% |
| negative | 6 | 6 | 100% |
| read-only | 5 | 5 | 100% |
| robustness | 4 | 4 | 100% |
| time | 0 | 2 | 0% |
| lists | 0 | 2 | 0% |
| cvs | 1 | 1 | 100% |
| rules fallback (AI off) | 7 | 8 | 88% |
| job description (answered from the stored JD, no model call) | 5 | 5 | 100% |
| counts (the digest's for-you count) | 0 | 2 | 0% |
| help (Ping about itself) | 6 | 6 | 100% |
| placement mail (demo sample mails) | 0 | 3 | 0% |
| open questions (the model) | 4 | 4 | 100% |

## Failures

### D1 (deadlines): what's due tomorrow

- failed: must_contain 'nothing|no deadline|none|don't see any|do not see any|no items|not see anything|'; max_words 60 (had 540)
- expected: nothing in the feed or roles falls on Sun 22 Nov
- model rules, 7.4 s

> Close tomorrow 20:00, Sun 22 Nov — 11 for you, 9 applied:
> For you:
> - Auro Group — Data Analyst (apply with Analytics & Finance CV)
> - Auro Group — Sales & Business Development (apply with Consulting CV)
> - Axis Bank — BIU (Business Intelligence Unit) (apply with Analytics & Finance CV)
> - Dassault Systemes — AI Engineer-Data Scientist-PG (apply with Analytics & Finance CV)
> - Flipspaces Technology Labs — Entrepreneur-in-Residence (apply with Consulting CV)
> - Piramal Finance — Credit Risk & AI Analytics Data Scientist (BIU) (apply with Analytics & Finance CV)
> - SLB — Datascientist (apply with Analytics & Finance CV)
> - Waterfly Technologies — Growth and Strategist (apply with Consulting CV)
> - Waterfly Technologies — Managment Consultant 2 (apply with Consulting CV)
> - Xion Multiventures — Trainee Trader & Research Analyst (apply with Analytics & Finance CV)
> - YMS Financial — Quant Researcher (apply with Analytics & Finance CV)
> Applied:
> - Ather Energy — Product Ownership ✓ applied
> - Auro Group — Product Manager ✓ applied
> - Axon Developers — Manager Strategy ✓ applied
> - Axon Developers — MDs Office ✓ applied
> - Diageo — GBS MANAGEMENT TRAINEE ✓ applied
> - Lyskraft — APM ✓ applied
> - PhysicsWallah — Associate Product Manager (APM) ✓ applied
> - Searce — Associate Solutions Consultant ✓ applied
> - Waterfly Technologies — Management Consultant 1 ✓ applied
> Others (31):
> - AiPrise — Software Engineer I
> - AiPrise — Software Engineer I, Full Stack (Frontend Focused)
> - AiPrise — Software Engineer II
> - AiPrise — Software Engineer II, Full Stack (Frontend Focused)
> - Astera Labs — Software Quality Assurance (SQA) Engineer
> - Ather Energy — Chief Engineer
> - Ather Energy — Data Office
> - Ather Energy — Hardware Pack Engineering
> - Ather Energy — System Intelligence
> - Auro Group — AI/ML Software Engineer
> - Auro Group — Back End Developer
> - Auro Group — Frontend Developer
> - Auro Group — Full Stack Developer
> - Cashfree Payments India — SDE 1
> - Dassault Systemes — Software Engineer - Domain Engineering & AI Innovation-PG
> - Esri — Data Scientist I
> - Intellimation.ai Software — AIML Engineer
> - Intellimation.ai Software — Algorithm Engineer
> - Intellimation.ai Software — Software Engineer
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Aerodynamics Engineer
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Avionics Engineer
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Mechanical Engineer
> - LTM — Post-Graduate Engineer Trainee
> - Lyskraft — SDE - 1
> - MeltPlan — Software Engineer
> - Piramal Finance — SDE 1 (Technology)
> - Searce — Associate Cloud Engineer
> - Searce — Associate Data Engineer
> - Searce — Evlos AI Engineer
> - Waterfly Technologies — Graduate Engineer 1
> - Waterfly Technologies — Graduate Engineer 2
> 
> Forms and submissions due tomorrow (Sun 22 Nov):
> - Ather Energy (System Intelligence, Product Ownership, Chief Engineer +2 more): form by Sun 22 Nov 20:00
> - Auro Group (Back End Developer, Data Analyst, Full Stack Developer +4 more): form by Sun 22 Nov 20:00
> - LTM (Post-Graduate Engineer Trainee): form by Sun 22 Nov 20:00
> - Piramal Finance (SDE 1 (Technology), Credit Risk & AI Analytics Data Scientist (BIU)): CV submission by Sun 22 Nov 20:00
> - SLB (Datascientist): form by Sun 22 Nov 20:00

### D2 (deadlines): anything due today

- failed: must_contain 'aiprise'; must_contain 'waterfly'; must_contain 'auro'
- expected: today Sat 21 Nov: 41 reminders/deadlines all at 20:00 (AiPrise, Ather, Auro Group, Waterfly, Searce, ...)
- model rules, 6.4 s

> Close tonight 20:00 (in 2h 28m), Sat 21 Nov — 1 for you, 0 applied:
> For you:
> - BlackBuck — Associate Manager BlackBuck Leadership Program (apply with Consulting CV)
> Others (1):
> - Swiggy — Data Scientist 1

### D6 (deadlines): is the ESRI deadline today?

- failed: must_contain 'yes|today'
- expected: ESRI Data Scientist I: Sat 21 Nov 20:00
- model rules, 4.7 s

> Esri: open deadlines (last checked Sat 21 Nov 17:32):
> - Data Scientist I: application by Sun 22 Nov 20:00 · not applied
> No Esri notice in the data yet.
> You haven't applied to the Esri role.

### N4 (notices): latest notice for Groww

- failed: must_contain 'form'; must_contain '20'
- expected: Groww, 20 Nov 00:36, 'Additional requirement': fill the Additional Details Form by 20 Nov 2026, 2:00 PM
- model rules, 5.3 s

> Last Groww notice: "Urgent", Sat 21 Nov 14:50.
> Ping's message about it: Groww (Associate Product Manager): submit by Sat 21 Nov 16:30.
> You applied to: Associate Product Manager.
> Groww (Associate Product Manager): submit by Sat 21 Nov 16:30.

### T1 (time): when is the groww test?

- failed: max_words 50 (had 54)
- expected: at 18:35 IST the Groww test (15:00 today) is over
- model rules, 5.7 s

> - Groww (Associate Product Manager): submit by Sat 21 Nov 16:30. (earlier today, over) · Respective Locations · you're on the list
> - You're on the Groww shortlist (Associate Product Manager). Test Sat 21 Nov 15:00, Respective Locations. (earlier today, over)
> - Groww test (Associate Product Manager) Sat 21 Nov 15:00. (earlier today, over)

### T2 (time): when does ESRI close?

- failed: must_contain '1h 25m|1 hour 25|85 min|in 1h 25|1 hr 25'
- expected: ESRI Data Scientist I closes 20:00 today: at 18:35 that's in 1h 25m
- model rules, 7.1 s

> Esri: open deadlines (last checked Sat 21 Nov 18:35):
> - Data Scientist I: application by Sun 22 Nov 20:00 · not applied
> No Esri notice in the data yet.
> You haven't applied to the Esri role.

### L1 (lists): what's due tonight that's relevant to me

- failed: must_contain '✓ applied'
- expected: the ready-made list: deadline once in the heading, For you (unapplied, then ✓ applied), Others one 'Company — Role' line each, no reasons in chat
- model rules, 4.7 s

> Close tonight 20:00 (in 1h 25m), Sat 21 Nov — 1 for you, 0 applied:
> For you:
> - BlackBuck — Associate Manager BlackBuck Leadership Program (apply with Consulting CV)
> Others (1):
> - Swiggy — Data Scientist 1

### L2 (lists): what closes tonight?

- failed: must_contain '✓ applied'
- expected: any list of roles closing tonight uses the same format
- model rules, 3.8 s

> Close tonight 20:00 (in 1h 25m), Sat 21 Nov — 1 for you, 0 applied:
> For you:
> - BlackBuck — Associate Manager BlackBuck Leadership Program (apply with Consulting CV)
> Others (1):
> - Swiggy — Data Scientist 1

### F7 (rules fallback (AI off)): what's due tomorrow

- failed: must_contain 'Nothing due tomorrow'
- expected: no company, a deadline intent and a day: nothing in the feed or roles falls on Sun 22 Nov. The Pine Labs submission that day is for a shortlist the student isn't on (hidden in the feed), so it must not be listed.
- model rules, 5.2 s

> Close tomorrow 20:00, Sun 22 Nov — 11 for you, 9 applied:
> For you:
> - Auro Group — Data Analyst (apply with Analytics & Finance CV)
> - Auro Group — Sales & Business Development (apply with Consulting CV)
> - Axis Bank — BIU (Business Intelligence Unit) (apply with Analytics & Finance CV)
> - Dassault Systemes — AI Engineer-Data Scientist-PG (apply with Analytics & Finance CV)
> - Flipspaces Technology Labs — Entrepreneur-in-Residence (apply with Consulting CV)
> - Piramal Finance — Credit Risk & AI Analytics Data Scientist (BIU) (apply with Analytics & Finance CV)
> - SLB — Datascientist (apply with Analytics & Finance CV)
> - Waterfly Technologies — Growth and Strategist (apply with Consulting CV)
> - Waterfly Technologies — Managment Consultant 2 (apply with Consulting CV)
> - Xion Multiventures — Trainee Trader & Research Analyst (apply with Analytics & Finance CV)
> - YMS Financial — Quant Researcher (apply with Analytics & Finance CV)
> Applied:
> - Ather Energy — Product Ownership ✓ applied
> - Auro Group — Product Manager ✓ applied
> - Axon Developers — Manager Strategy ✓ applied
> - Axon Developers — MDs Office ✓ applied
> - Diageo — GBS MANAGEMENT TRAINEE ✓ applied
> - Lyskraft — APM ✓ applied
> - PhysicsWallah — Associate Product Manager (APM) ✓ applied
> - Searce — Associate Solutions Consultant ✓ applied
> - Waterfly Technologies — Management Consultant 1 ✓ applied
> Others (31):
> - AiPrise — Software Engineer I
> - AiPrise — Software Engineer I, Full Stack (Frontend Focused)
> - AiPrise — Software Engineer II
> - AiPrise — Software Engineer II, Full Stack (Frontend Focused)
> - Astera Labs — Software Quality Assurance (SQA) Engineer
> - Ather Energy — Chief Engineer
> - Ather Energy — Data Office
> - Ather Energy — Hardware Pack Engineering
> - Ather Energy — System Intelligence
> - Auro Group — AI/ML Software Engineer
> - Auro Group — Back End Developer
> - Auro Group — Frontend Developer
> - Auro Group — Full Stack Developer
> - Cashfree Payments India — SDE 1
> - Dassault Systemes — Software Engineer - Domain Engineering & AI Innovation-PG
> - Esri — Data Scientist I
> - Intellimation.ai Software — AIML Engineer
> - Intellimation.ai Software — Algorithm Engineer
> - Intellimation.ai Software — Software Engineer
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Aerodynamics Engineer
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Avionics Engineer
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Mechanical Engineer
> - LTM — Post-Graduate Engineer Trainee
> - Lyskraft — SDE - 1
> - MeltPlan — Software Engineer
> - Piramal Finance — SDE 1 (Technology)
> - Searce — Associate Cloud Engineer
> - Searce — Associate Data Engineer
> - Searce — Evlos AI Engineer
> - Waterfly Technologies — Graduate Engineer 1
> - Waterfly Technologies — Graduate Engineer 2
> 
> Forms and submissions due tomorrow (Sun 22 Nov):
> - Ather Energy (System Intelligence, Product Ownership, Chief Engineer +2 more): form by Sun 22 Nov 20:00
> - Auro Group (Back End Developer, Data Analyst, Full Stack Developer +4 more): form by Sun 22 Nov 20:00
> - LTM (Post-Graduate Engineer Trainee): form by Sun 22 Nov 20:00
> - Piramal Finance (SDE 1 (Technology), Credit Risk & AI Analytics Data Scientist (BIU)): CV submission by Sun 22 Nov 20:00
> - SLB (Datascientist): form by Sun 22 Nov 20:00

### E1 (counts (the digest's for-you count)): what's due tonight?

- failed: must_contain '8 for you'
- expected: The 20:00 reminder digest says '38 applications you haven't applied to close tonight — 8 for you' and Today says '8 for you · 9 applied'. Ask Ping must give the same 8 (for you and not applied yet), not 17 (for you including the 9 already applied). Bug seen live on 22 Nov: 'Close tonight 20:00 — 17 for you, 9 applied'.
- model rules, 4.7 s

> Close tonight 20:00 (in 1h 25m), Sat 21 Nov — 1 for you, 0 applied:
> For you:
> - BlackBuck — Associate Manager BlackBuck Leadership Program (apply with Consulting CV)
> Others (1):
> - Swiggy — Data Scientist 1

### E2 (counts (the digest's for-you count)): how many roles for me close tonight?

- failed: must_contain '8 for you'
- expected: The same count asked as a count: 8, as in the digest.
- model rules, 4.0 s

> 2 roles close today (Sat 21 Nov).
> 
> Close tonight 20:00 (in 1h 25m), Sat 21 Nov — 1 for you, 0 applied:
> For you:
> - BlackBuck — Associate Manager BlackBuck Leadership Program (apply with Consulting CV)
> Others (1):
> - Swiggy — Data Scientist 1

### ML1 (placement mail (demo sample mails)): any mails for axon developers?

- failed: must_contain 'fill the form'; must_contain 'https://example.com/forms/ping-demo-details'
- expected: The demo's sample form mail: its message with the link.
- model rules, 5.1 s

> Placement mail about Axon Developers (newest first):
> - AXON DEVELOPERS interview: Wed 25 Nov 11:00 · via email
>   https://example.com/interview/ping-demo

### ML2 (placement mail (demo sample mails)): did I get a test link for accenture japan

- failed: must_contain 'online test'; must_contain 'https://assess.example.com/test/ping-demo'
- expected: The demo's sample test-link mail.
- model rules, 4.3 s

> No test link from Accenture Japan, Accenture India in your mail or on the ERP so far (last checked Sat 21 Nov 17:32). I read placement mail only: from the placement office, companies on your list, test platforms, or with words like test, shortlist, interview, form, offer.

### ML3 (placement mail (demo sample mails)): what's due from mail

- failed: must_contain 'Axon'; must_contain 'Accenture Japan'
- expected: Mail-only deadlines, soonest first.
- model rules, 4.4 s

> Due from your mail:
> - Futures First Info Services Pvt. Ltd: take the online test by Sat 28 Nov 23:59 · via email
>   https://assess.example.com/test/ping-demo


## Conversations (multi-turn)

Each conversation runs in one fresh demo session; the function reads the thread from the database itself. A conversation passes only if every turn passes.

| id | turns | first question | follow-up(s) | result |
|---|---|---|---|---|
| M1 | 2 | any test today? | nothing else? | pass |
| M2 | 2 | meesho ctc | and slice? | pass |
| M3 | 2 | what's due tomorrow | and the day after? | FAIL (turn 1, 2) |
| M4 | 2 | am I eligible for groww | why not? | pass |
| M5 | 2 | latest notice for harness | when is it? | pass |
| M6 | 2 | slice ctc breakdown | same for analyst role? | pass |
| M7 | 2 | when is the Eternal test | where? | pass |
| M8 | 2 | eternal ctc | ok. what's due this week? | pass |
| M9 | 2 | does diageo have a bond | and harness? | pass |
| M10 | 2 | any tests today? | anything else? | FAIL (turn 2) |
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

#### M3 turn 1: what's due tomorrow

- failed: must_contain 'nothing|no deadline|none|don't see any|do not see any|no items|not see anything|'; max_words 60 (had 540)
- expected: nothing falls on Sun 22 Nov or Mon 23 Nov

- model rules, 6.0 s

> Close tomorrow 20:00, Sun 22 Nov — 11 for you, 9 applied:
> For you:
> - Auro Group — Data Analyst (apply with Analytics & Finance CV)
> - Auro Group — Sales & Business Development (apply with Consulting CV)
> - Axis Bank — BIU (Business Intelligence Unit) (apply with Analytics & Finance CV)
> - Dassault Systemes — AI Engineer-Data Scientist-PG (apply with Analytics & Finance CV)
> - Flipspaces Technology Labs — Entrepreneur-in-Residence (apply with Consulting CV)
> - Piramal Finance — Credit Risk & AI Analytics Data Scientist (BIU) (apply with Analytics & Finance CV)
> - SLB — Datascientist (apply with Analytics & Finance CV)
> - Waterfly Technologies — Growth and Strategist (apply with Consulting CV)
> - Waterfly Technologies — Managment Consultant 2 (apply with Consulting CV)
> - Xion Multiventures — Trainee Trader & Research Analyst (apply with Analytics & Finance CV)
> - YMS Financial — Quant Researcher (apply with Analytics & Finance CV)
> Applied:
> - Ather Energy — Product Ownership ✓ applied
> - Auro Group — Product Manager ✓ applied
> - Axon Developers — Manager Strategy ✓ applied
> - Axon Developers — MDs Office ✓ applied
> - Diageo — GBS MANAGEMENT TRAINEE ✓ applied
> - Lyskraft — APM ✓ applied
> - PhysicsWallah — Associate Product Manager (APM) ✓ applied
> - Searce — Associate Solutions Consultant ✓ applied
> - Waterfly Technologies — Management Consultant 1 ✓ applied
> Others (31):
> - AiPrise — Software Engineer I
> - AiPrise — Software Engineer I, Full Stack (Frontend Focused)
> - AiPrise — Software Engineer II
> - AiPrise — Software Engineer II, Full Stack (Frontend Focused)
> - Astera Labs — Software Quality Assurance (SQA) Engineer
> - Ather Energy — Chief Engineer
> - Ather Energy — Data Office
> - Ather Energy — Hardware Pack Engineering
> - Ather Energy — System Intelligence
> - Auro Group — AI/ML Software Engineer
> - Auro Group — Back End Developer
> - Auro Group — Frontend Developer
> - Auro Group — Full Stack Developer
> - Cashfree Payments India — SDE 1
> - Dassault Systemes — Software Engineer - Domain Engineering & AI Innovation-PG
> - Esri — Data Scientist I
> - Intellimation.ai Software — AIML Engineer
> - Intellimation.ai Software — Algorithm Engineer
> - Intellimation.ai Software — Software Engineer
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Aerodynamics Engineer
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Avionics Engineer
> - Kalam Labs (legal name: Elixar Systems Pvt Ltd) — Mechanical Engineer
> - LTM — Post-Graduate Engineer Trainee
> - Lyskraft — SDE - 1
> - MeltPlan — Software Engineer
> - Piramal Finance — SDE 1 (Technology)
> - Searce — Associate Cloud Engineer
> - Searce — Associate Data Engineer
> - Searce — Evlos AI Engineer
> - Waterfly Technologies — Graduate Engineer 1
> - Waterfly Technologies — Graduate Engineer 2
> 
> Forms and submissions due tomorrow (Sun 22 Nov):
> - Ather Energy (System Intelligence, Product Ownership, Chief Engineer +2 more): form by Sun 22 Nov 20:00
> - Auro Group (Back End Developer, Data Analyst, Full Stack Developer +4 more): form by Sun 22 Nov 20:00
> - LTM (Post-Graduate Engineer Trainee): form by Sun 22 Nov 20:00
> - Piramal Finance (SDE 1 (Technology), Credit Risk & AI Analytics Data Scientist (BIU)): CV submission by Sun 22 Nov 20:00
> - SLB (Datascientist): form by Sun 22 Nov 20:00

#### M3 turn 2: and the day after?

- failed: max_words 60 (had 103)
- expected: nothing falls on Sun 22 Nov or Mon 23 Nov
- previous turn: "what's due tomorrow" → "Close tomorrow 20:00, Sun 22 Nov — 11 for you, 9 applied:
For you:
- Auro Group — Data Analyst (apply with Analytics & Finance CV)
- Auro Group — Sales & Business Development (apply with Consulting CV"
- model rules, 4.6 s

> Close Mon 23 Nov 10:00 — 0 for you, 4 applied:
> For you:
> - none
> Applied:
> - Bluestone — Associate Product Manager ✓ applied
> - Bluestone — Content Generalist ✓ applied
> - Bluestone — Management Trainee (Marketing) ✓ applied
> - Nomura — Analyst ✓ applied
> Others (1):
> - Bluestone — Frontend Developer
> 
> Close Mon 23 Nov 20:00 — 1 for you, 0 applied:
> For you:
> - Futures First Info Services — Trainee International Markets (apply with Analytics & Finance CV)
> 
> Forms and submissions due on Mon 23 Nov:
> - Futures First Info Services (Trainee International Markets): CV submission by Mon 23 Nov 16:00

#### M10 turn 2: anything else?

- failed: must_contain '38|39|48|43|19 compan|23 compan'
- expected: the live exchange at 18:35 IST: the only test today was Groww at 15:00 (over); no other tests; many applications close at 20:00 tonight (38 not-applied reminders / 39 roles not applied / 48 roles; 19-23 companies)
- previous turn: "any tests today?" → "Tests and lists today (Sat 21 Nov):
- You're on the Meesho shortlist (Senior Assosiate - Business Management). Test Sat 21 Nov 15:00, Respective Location. (earlier today, over)
- You're on the Groww s"
- model rules, 3.9 s

> No other test today: those 3 are all. 2 roles close at 20:00 today (in 1h 25m), 2 not applied (1 for you): BlackBuck.


## Every case

| id | category | question | result | model | seconds |
|---|---|---|---|---|---|
| C1 | company facts | slice ctc breakdown | pass | rules | 8.1 |
| C2 | company facts | am I eligible for Harness | pass | rules | 5.2 |
| C3 | company facts | what is the CG cut-off for Axis Bank | pass | rules | 8.3 |
| C4 | company facts | which departments can apply for Axis Bank | pass | rules | 7.4 |
| C5 | company facts | what roles does Waterfly Technologies have | pass | rules | 5.7 |
| C6 | company facts | Diageo joining bonus | pass | rules | 6.7 |
| C7 | company facts | does Harness have a bond | pass | rules | 5.4 |
| C8 | company facts | Harness take home salary | pass | rules | 4.5 |
| D1 | deadlines | what's due tomorrow | FAIL | rules | 7.4 |
| D2 | deadlines | anything due today | FAIL | rules | 6.4 |
| D3 | deadlines | what closes this week | pass | rules | 4.8 |
| D4 | deadlines | when does the Ather Energy application close | pass | rules | 5.4 |
| D5 | deadlines | when does Diageo close | pass | rules | 7.4 |
| D6 | deadlines | is the ESRI deadline today? | FAIL | rules | 4.7 |
| D7 | deadlines | what's the deadline for Harness | pass | rules | 5.0 |
| D8 | deadlines | what's due on 25 November | pass | rules | 5.1 |
| N1 | notices | am I shortlisted anywhere | pass | rules | 5.7 |
| N2 | notices | when is the Eternal test and where | pass | rules | 6.1 |
| N3 | notices | which room was I in for the IQVIA test | pass | rules | 5.2 |
| N4 | notices | latest notice for Groww | FAIL | rules | 5.3 |
| N5 | notices | am I on the Pine Labs list | pass | rules | 4.5 |
| N6 | notices | when is the Groww test | pass | rules | 4.1 |
| X1 | negative | what's the CTC at Google | pass | rules | 4.0 |
| X2 | negative | what's due on 30 November | pass | rules | 4.1 |
| X3 | negative | where is the Diageo job located | pass | rules | 4.2 |
| X4 | negative | what was my score in the Eternal test | pass | rules | 4.1 |
| X5 | negative | what's the CTC at Netflix | pass | rules | 4.3 |
| X6 | negative | who is the CDC contact for Groww and their phone number | pass | rules | 4.1 |
| R1 | read-only | apply to Waterfly Graduate Engineer 1 for me | pass | rules | 4.3 |
| R2 | read-only | withdraw my application to Diageo | pass | rules | 4.1 |
| R3 | read-only | change my CV on the ERP to the Data CV | pass | rules | 8.2 |
| R4 | read-only | fill the Groww additional details form for me | pass | rules | 5.6 |
| B1 | robustness | waterfly ctc | pass | rules | 8.9 |
| B2 | robustness | eternl ctc brekdown | pass | rules | 6.0 |
| B3 | robustness | what's slice's CTC and when does ESRI close? | pass | rules | 4.6 |
| B4 | robustness | did i apply to diageo?? and whats the bond | pass | rules | 5.4 |
| R5 | read-only | apply to groww for me | pass | rules | 8.7 |
| T1 | time | when is the groww test? | FAIL | rules | 5.7 |
| T2 | time | when does ESRI close? | FAIL | rules | 7.1 |
| L1 | lists | what's due tonight that's relevant to me | FAIL | rules | 4.7 |
| L2 | lists | what closes tonight? | FAIL | rules | 3.8 |
| CV1 | cvs | which cv should I use for groww | pass | rules | 5.1 |
| F1 | rules fallback (AI off) | yms financial deadline | pass | rules | 4.4 |
| F2 | rules fallback (AI off) | microsoft cv submission deadline | pass | rules | 5.8 |
| F3 | rules fallback (AI off) | google cv deadline | pass | rules | 5.2 |
| F4 | rules fallback (AI off) | blakbuck deadline | pass | rules | 4.9 |
| F5 | rules fallback (AI off) | msft cv submission deadline | pass | rules | 4.8 |
| F6 | rules fallback (AI off) | hmm | pass | rules | 5.5 |
| F7 | rules fallback (AI off) | what's due tomorrow | FAIL | rules | 5.2 |
| F8 | rules fallback (AI off) | any tests today? | pass | rules | 3.9 |
| J1 | job description (answered from the stored JD, no model call) | summarise JPMC's JD | pass | jd-summary | 3.4 |
| J2 | job description (answered from the stored JD, no model call) | what's the JD for LTM | pass | jd-summary | 2.8 |
| J3 | job description (answered from the stored JD, no model call) | what do they want for cars24 data science | pass | jd-summary | 2.9 |
| J4 | job description (answered from the stored JD, no model call) | what's the JD for searce associate data engineer | pass | jd-summary | 2.9 |
| J5 | job description (answered from the stored JD, no model call) | what do they want for arihant product manager | pass | jd-summary | 2.9 |
| E1 | counts (the digest's for-you count) | what's due tonight? | FAIL | rules | 4.7 |
| E2 | counts (the digest's for-you count) | how many roles for me close tonight? | FAIL | rules | 4.0 |
| H1 | help (Ping about itself) | how to install | pass | rules | 6.4 |
| H2 | help (Ping about itself) | how do I install Ping on my iPhone? | pass | rules | 5.5 |
| H3 | help (Ping about itself) | how do I get notifications | pass | rules | 4.7 |
| H4 | help (Ping about itself) | what can you do | pass | rules | 4.5 |
| H5 | help (Ping about itself) | help | pass | rules | 4.3 |
| H6 | help (Ping about itself) | how often do you check the ERP? | pass | rules | 7.6 |
| ML1 | placement mail (demo sample mails) | any mails for axon developers? | FAIL | rules | 5.1 |
| ML2 | placement mail (demo sample mails) | did I get a test link for accenture japan | FAIL | rules | 4.3 |
| ML3 | placement mail (demo sample mails) | what's due from mail | FAIL | rules | 4.4 |
| O1 | open questions (the model) | compare the slice and eternal roles | pass | gemini-3.1-flash-lite | 16.9 |
| O2 | open questions (the model) | should I apply to blackbuck? | pass | rules | 16.8 |
| O3 | open questions (the model) | why is axis bank a good fit for me? | pass | gemini-3.1-flash-lite | 20.3 |
| O4 | open questions (the model) | tips to prepare for the eternal test | pass | gemini-3.1-flash-lite | 17.0 |

The questions, checks and the data each expected answer comes from are in [`cases.json`](cases.json); every answer is in `results.json`.
