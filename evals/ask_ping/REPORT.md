# Ask Ping evals

_Run on 22 Nov 2026, 12:23 UTC against the deployed `ask-ping` function, from one-click demo sessions (anonymised demo data), snapshot time fixed at 2026-11-21T17:32:18+05:30 (cases marked 'as_of' use their own). Re-run with Actions > Admin > ask-ping-evals, or `python evals/ask_ping/run_ask_ping_evals.py`._

## In short

- **Single questions: 70 of 70 passed all their checks (100%).**
- **Conversations (follow-ups in one thread): 21 of 21 passed every turn; 39 of 39 turns passed.**
- Models that answered: rules (61), jd-summary (5), gemini-3.1-flash-lite (4)
- **Main model only (gemini-flash-latest): 0 of 0 single questions passed (n/a); 0 of 0 conversation turns (n/a).** The other answers came from the lighter model or the rules answer (marked in the table below).
- Latency: median 2.6 s, slowest 16.0 s
- Checks are deterministic (no model grades another model): required words or phrases, forbidden ones, numbers in any common format (28,00,000 = 28 L = 28 LPA), and a word limit.

## By category

| category | passed | out of | score |
|---|---|---|---|
| company facts | 8 | 8 | 100% |
| deadlines | 8 | 8 | 100% |
| notices | 6 | 6 | 100% |
| negative | 6 | 6 | 100% |
| read-only | 5 | 5 | 100% |
| robustness | 4 | 4 | 100% |
| time | 2 | 2 | 100% |
| lists | 2 | 2 | 100% |
| cvs | 1 | 1 | 100% |
| rules fallback (AI off) | 8 | 8 | 100% |
| job description (answered from the stored JD, no model call) | 5 | 5 | 100% |
| counts (the digest's for-you count) | 2 | 2 | 100% |
| help (Ping about itself) | 6 | 6 | 100% |
| placement mail (demo sample mails) | 3 | 3 | 100% |
| open questions (the model) | 4 | 4 | 100% |

## Failures

None.

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
| C1 | company facts | slice ctc breakdown | pass | rules | 6.0 |
| C2 | company facts | am I eligible for Harness | pass | rules | 5.0 |
| C3 | company facts | what is the CG cut-off for Axis Bank | pass | rules | 4.3 |
| C4 | company facts | which departments can apply for Axis Bank | pass | rules | 3.4 |
| C5 | company facts | what roles does Waterfly Technologies have | pass | rules | 2.7 |
| C6 | company facts | Diageo joining bonus | pass | rules | 2.5 |
| C7 | company facts | does Harness have a bond | pass | rules | 2.4 |
| C8 | company facts | Harness take home salary | pass | rules | 7.2 |
| D1 | deadlines | what's due tomorrow | pass | rules | 2.4 |
| D2 | deadlines | anything due today | pass | rules | 2.3 |
| D3 | deadlines | what closes this week | pass | rules | 2.1 |
| D4 | deadlines | when does the Ather Energy application close | pass | rules | 4.2 |
| D5 | deadlines | when does Diageo close | pass | rules | 3.3 |
| D6 | deadlines | is the ESRI deadline today? | pass | rules | 3.2 |
| D7 | deadlines | what's the deadline for Harness | pass | rules | 3.1 |
| D8 | deadlines | what's due on 25 November | pass | rules | 2.3 |
| N1 | notices | am I shortlisted anywhere | pass | rules | 2.2 |
| N2 | notices | when is the Eternal test and where | pass | rules | 7.8 |
| N3 | notices | which room was I in for the IQVIA test | pass | rules | 2.5 |
| N4 | notices | latest notice for Groww | pass | rules | 2.9 |
| N5 | notices | am I on the Pine Labs list | pass | rules | 3.2 |
| N6 | notices | when is the Groww test | pass | rules | 3.9 |
| X1 | negative | what's the CTC at Google | pass | rules | 2.9 |
| X2 | negative | what's due on 30 November | pass | rules | 2.4 |
| X3 | negative | where is the Diageo job located | pass | rules | 2.7 |
| X4 | negative | what was my score in the Eternal test | pass | rules | 2.4 |
| X5 | negative | what's the CTC at Netflix | pass | rules | 2.9 |
| X6 | negative | who is the CDC contact for Groww and their phone number | pass | rules | 2.4 |
| R1 | read-only | apply to Waterfly Graduate Engineer 1 for me | pass | rules | 2.5 |
| R2 | read-only | withdraw my application to Diageo | pass | rules | 3.2 |
| R3 | read-only | change my CV on the ERP to the Data CV | pass | rules | 2.3 |
| R4 | read-only | fill the Groww additional details form for me | pass | rules | 3.0 |
| B1 | robustness | waterfly ctc | pass | rules | 2.6 |
| B2 | robustness | eternl ctc brekdown | pass | rules | 2.5 |
| B3 | robustness | what's slice's CTC and when does ESRI close? | pass | rules | 2.5 |
| B4 | robustness | did i apply to diageo?? and whats the bond | pass | rules | 2.8 |
| R5 | read-only | apply to groww for me | pass | rules | 2.4 |
| T1 | time | when is the groww test? | pass | rules | 2.5 |
| T2 | time | when does ESRI close? | pass | rules | 2.4 |
| L1 | lists | what's due tonight that's relevant to me | pass | rules | 2.3 |
| L2 | lists | what closes tonight? | pass | rules | 2.6 |
| CV1 | cvs | which cv should I use for groww | pass | rules | 2.7 |
| F1 | rules fallback (AI off) | yms financial deadline | pass | rules | 2.6 |
| F2 | rules fallback (AI off) | microsoft cv submission deadline | pass | rules | 2.5 |
| F3 | rules fallback (AI off) | google cv deadline | pass | rules | 2.0 |
| F4 | rules fallback (AI off) | blakbuck deadline | pass | rules | 2.5 |
| F5 | rules fallback (AI off) | msft cv submission deadline | pass | rules | 2.3 |
| F6 | rules fallback (AI off) | hmm | pass | rules | 2.3 |
| F7 | rules fallback (AI off) | what's due tomorrow | pass | rules | 2.4 |
| F8 | rules fallback (AI off) | any tests today? | pass | rules | 2.2 |
| J1 | job description (answered from the stored JD, no model call) | summarise JPMC's JD | pass | jd-summary | 1.7 |
| J2 | job description (answered from the stored JD, no model call) | what's the JD for LTM | pass | jd-summary | 2.0 |
| J3 | job description (answered from the stored JD, no model call) | what do they want for cars24 data science | pass | jd-summary | 2.0 |
| J4 | job description (answered from the stored JD, no model call) | what's the JD for searce associate data engineer | pass | jd-summary | 1.7 |
| J5 | job description (answered from the stored JD, no model call) | what do they want for arihant product manager | pass | jd-summary | 1.7 |
| E1 | counts (the digest's for-you count) | what's due tonight? | pass | rules | 2.2 |
| E2 | counts (the digest's for-you count) | how many roles for me close tonight? | pass | rules | 2.4 |
| H1 | help (Ping about itself) | how to install | pass | rules | 4.5 |
| H2 | help (Ping about itself) | how do I install Ping on my iPhone? | pass | rules | 3.0 |
| H3 | help (Ping about itself) | how do I get notifications | pass | rules | 5.0 |
| H4 | help (Ping about itself) | what can you do | pass | rules | 6.4 |
| H5 | help (Ping about itself) | help | pass | rules | 3.0 |
| H6 | help (Ping about itself) | how often do you check the ERP? | pass | rules | 2.9 |
| ML1 | placement mail (demo sample mails) | any mails for axon developers? | pass | rules | 2.9 |
| ML2 | placement mail (demo sample mails) | did I get a test link for accenture japan | pass | rules | 2.7 |
| ML3 | placement mail (demo sample mails) | what's due from mail | pass | rules | 2.6 |
| O1 | open questions (the model) | compare the slice and eternal roles | pass | gemini-3.1-flash-lite | 16.0 |
| O2 | open questions (the model) | should I apply to blackbuck? | pass | gemini-3.1-flash-lite | 15.0 |
| O3 | open questions (the model) | why is axis bank a good fit for me? | pass | gemini-3.1-flash-lite | 6.2 |
| O4 | open questions (the model) | tips to prepare for the eternal test | pass | gemini-3.1-flash-lite | 14.7 |

The questions, checks and the data each expected answer comes from are in [`cases.json`](cases.json); every answer is in `results.json`.
