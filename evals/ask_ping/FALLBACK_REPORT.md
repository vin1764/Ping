# Ask Ping without the AI: fallback evals

_Run on 22 Nov 2026 07:38 IST (first run 01:50 IST, also 8 of 8) against the deployed `ask-ping` function (build 14a73c4) from one-click demo sessions, snapshot time 21 Nov 17:32 IST, with `no_ai: true` so every answer comes from the rules (`supabase/functions/_shared/answer_rules.js`), exactly what a student gets when Gemini is busy. Re-run: `python evals/ask_ping/run_ask_ping_evals.py --only F`._

**8 of 8 passed.**

| id | what it tests | question | result |
|---|---|---|---|
| F1 | (a) a company with an open deadline | yms financial deadline | pass |
| F2 | (b) a company with no open deadline (the reported bug) | microsoft cv submission deadline | pass |
| F3 | (c) a company not in the data | google cv deadline | pass |
| F4 | (d) a misspelled company | blakbuck deadline | pass |
| F5 | an alias (msft) | msft cv submission deadline | pass |
| F6 | no company, no intent | hmm | pass |
| F7 | intent + day, nothing due (a hidden item not about you left out) | what's due tomorrow | pass |
| F8 | tests today, one already over | any tests today? | pass |

## Answers, verbatim

### F1 yms financial deadline  [rules]  PASS

```text
YMS Financial: open deadlines (last checked Sat 21 Nov 17:32):
- Quant Researcher: application by Sat 21 Nov 20:00 (in 2h 28m) · not applied
No YMS Financial notice in the data yet.
You haven't applied to the YMS Financial role.
```

### F2 microsoft cv submission deadline  [rules]  PASS

```text
No open deadline for Microsoft in the ERP data (last checked Sat 21 Nov 17:32).
Last Microsoft notice: "PPO", Wed 11 Nov 17:59.
You haven't applied to the Microsoft role.
Microsoft Corporation test room list is out (Software Engineer). You're not on it.
```

### F3 google cv deadline  [rules]  PASS

```text
I don't have Google in your ERP data: no role on the companies list and no notice from it (last checked Sat 21 Nov 17:32).
```

### F4 blakbuck deadline  [rules]  PASS

```text
BlackBuck: open deadlines (last checked Sat 21 Nov 17:32):
- Associate Manager BlackBuck Leadership Program: application by Sat 21 Nov 20:00 (in 2h 28m) · not applied
Last BlackBuck notice: "PPT/Workshop/Seminars etc", Tue 17 Nov 08:14.
You haven't applied to the BlackBuck role.
```

### F5 msft cv submission deadline  [rules]  PASS

```text
No open deadline for Microsoft in the ERP data (last checked Sat 21 Nov 17:32).
Last Microsoft notice: "PPO", Wed 11 Nov 17:59.
You haven't applied to the Microsoft role.
Microsoft Corporation test room list is out (Software Engineer). You're not on it.
```

### F6 hmm  [rules]  PASS

```text
I couldn't tell what you meant. Here's what's due soon:
- AiPrise (Software Engineer I, Full Stack (Frontend Focused), Software Engineer I, Software Engineer II +1 more): application by Sat 21 Nov 20:00 (in 2h 28m) · not applied
- Astera Labs (Software Quality Assurance (SQA) Engineer): application by Sat 21 Nov 20:00 (in 2h 28m) · not applied
- Ather Energy (Product Ownership, Hardware Pack Engineering, Chief Engineer +2 more): application by Sat 21 Nov 20:00 (in 2h 28m) · applied to 1 of 5
- Auro Group (Data Analyst, AI/ML Software Engineer, Full Stack Developer +4 more): application by Sat 21 Nov 20:00 (in 2h 28m) · applied to 1 of 7
- Axis Bank (BIU (Business Intelligence Unit)): application by Sat 21 Nov 20:00 (in 2h 28m) · not applied
- Axon Developers (MDs Office, Manager Strategy): application by Sat 21 Nov 20:00 (in 2h 28m) · ✓ applied
- BlackBuck (Associate Manager BlackBuck Leadership Program): application by Sat 21 Nov 20:00 (in 2h 28m) · not applied
- Dassault Systemes (Software Engineer - Domain Engineering & AI Innovation-PG, AI Engineer-Data Scientist-PG): application by Sat 21 Nov 20:00 (in 2h 28m) · not applied
- Diageo (GBS MANAGEMENT TRAINEE): application by Sat 21 Nov 20:00 (in 2h 28m) · ✓ applied
- Esri (Data Scientist I): application by Sat 21 Nov 20:00 (in 2h 28m) · not applied
- Flipspaces Technology Labs (Entrepreneur-in-Residence): application by Sat 21 Nov 20:00 (in 2h 28m) · not applied
- Kalam Labs (legal name: Elixar Systems Pvt Ltd) (Avionics Engineer, Aerodynamics Engineer, Mechanical Engineer): application by Sat 21 Nov 20:00 (in 2h 28m) · not applied
- +10 more
```

### F7 what's due tomorrow  [rules]  PASS

```text
Nothing due tomorrow (Sun 22 Nov) in the ERP data (last checked Sat 21 Nov 17:32).
```

### F8 any tests today?  [rules]  PASS

```text
Tests and lists today (Sat 21 Nov):
- Groww test (Associate Product Manager) Sat 21 Nov 15:00. (over)

8 of 8 passed
```
