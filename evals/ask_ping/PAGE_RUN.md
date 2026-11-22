# Ask Ping through the page: single-question evals

70 single-question cases from `evals/ask_ping/cases.json`, each typed into the live page (https://vin1764.github.io/ping-dashboard/, build `4b1893c`), 7 to a one-click demo session, by `setup/ask_ping_page_evals.py` (Actions > Admin > ask-ping-page). Time = from Enter to the reply on screen.

OPEN questions: the model, on the evals key (GEMINI_API_KEY_EVALS).

| | cases | median on screen | slowest | typing bubble | pass |
|---|---|---|---|---|---|
| FACT (answered in the page) | 65 | 16 ms | 29 ms | 0 of 65 | 64/65 |
| OPEN and preferences (the function) | 5 | 9428 ms | 18980 ms | 5 of 5 | 5/5 |

FACT answers under 300 ms: 65 of 65 (median work inside the page 3 ms).

| id | by | ms | typing | result | question |
|---|---|---|---|---|---|
| C1 | page | 13 | no | pass | slice ctc breakdown |
| C2 | page | 12 | no | pass | am I eligible for Harness |
| C3 | page | 23 | no | pass | what is the CG cut-off for Axis Bank |
| C4 | page | 15 | no | pass | which departments can apply for Axis Bank |
| C5 | page | 18 | no | pass | what roles does Waterfly Technologies have |
| C6 | page | 12 | no | pass | Diageo joining bonus |
| C7 | page | 17 | no | pass | does Harness have a bond |
| C8 | page | 17 | no | pass | Harness take home salary |
| D1 | page | 13 | no | pass | what's due tomorrow |
| D2 | page | 15 | no | pass | anything due today |
| D3 | page | 14 | no | pass | what closes this week |
| D4 | page | 12 | no | pass | when does the Ather Energy application close |
| D5 | page | 20 | no | pass | when does Diageo close |
| D6 | page | 11 | no | pass | is the ESRI deadline today? |
| D7 | page | 14 | no | pass | what's the deadline for Harness |
| D8 | page | 22 | no | pass | what's due on 25 November |
| N1 | page | 11 | no | pass | am I shortlisted anywhere |
| N2 | page | 12 | no | pass | when is the Eternal test and where |
| N3 | page | 18 | no | pass | which room was I in for the IQVIA test |
| N4 | page | 18 | no | pass | latest notice for Groww |
| N5 | page | 13 | no | pass | am I on the Pine Labs list |
| N6 | page | 12 | no | pass | when is the Groww test |
| X1 | page | 12 | no | pass | what's the CTC at Google |
| X2 | page | 14 | no | pass | what's due on 30 November |
| X3 | page | 21 | no | pass | where is the Diageo job located |
| X4 | page | 12 | no | pass | what was my score in the Eternal test |
| X5 | page | 14 | no | pass | what's the CTC at Netflix |
| X6 | page | 23 | no | pass | who is the CDC contact for Groww and their phone number |
| R1 | page | 18 | no | pass | apply to Waterfly Graduate Engineer 1 for me |
| R2 | page | 19 | no | pass | withdraw my application to Diageo |
| R3 | page | 16 | no | pass | change my CV on the ERP to the Data CV |
| R4 | page | 22 | no | pass | fill the Groww additional details form for me |
| B1 | page | 29 | no | pass | waterfly ctc |
| B2 | page | 22 | no | pass | eternl ctc brekdown |
| B3 | page | 15 | no | pass | what's slice's CTC and when does ESRI close? |
| B4 | page | 20 | no | pass | did i apply to diageo?? and whats the bond |
| R5 | page | 17 | no | pass | apply to groww for me |
| T1 | page | 17 | no | pass | when is the groww test? |
| T2 | page | 15 | no | FAIL: must_contain '1h 25m/1 hour 25/85 min/in 1h 25/1 hr 25' | when does ESRI close? |
| L1 | page | 22 | no | pass | what's due tonight that's relevant to me |
| L2 | page | 13 | no | pass | what closes tonight? |
| CV1 | page | 13 | no | pass | which cv should I use for groww |
| F1 | page | 14 | no | pass | yms financial deadline |
| F2 | page | 15 | no | pass | microsoft cv submission deadline |
| F3 | page | 16 | no | pass | google cv deadline |
| F4 | page | 23 | no | pass | blakbuck deadline |
| F5 | page | 19 | no | pass | msft cv submission deadline |
| F6 | server | 4674 | yes | pass | hmm |
| F7 | page | 19 | no | pass | what's due tomorrow |
| F8 | page | 12 | no | pass | any tests today? |
| J1 | page | 18 | no | pass | summarise JPMC's JD |
| J2 | page | 18 | no | pass | what's the JD for LTM |
| J3 | page | 15 | no | pass | what do they want for cars24 data science |
| J4 | page | 11 | no | pass | what's the JD for searce associate data engineer |
| J5 | page | 14 | no | pass | what do they want for arihant product manager |
| E1 | page | 24 | no | pass | what's due tonight? |
| E2 | page | 17 | no | pass | how many roles for me close tonight? |
| H1 | page | 16 | no | pass | how to install |
| H2 | page | 18 | no | pass | how do I install Ping on my iPhone? |
| H3 | page | 15 | no | pass | how do I get notifications |
| H4 | page | 15 | no | pass | what can you do |
| H5 | page | 17 | no | pass | help |
| H6 | page | 11 | no | pass | how often do you check the ERP? |
| ML1 | page | 21 | no | pass | any mails for axon developers? |
| ML2 | page | 13 | no | pass | did I get a test link for accenture japan |
| ML3 | page | 18 | no | pass | what's due from mail |
| O1 | server | 16607 | yes | pass | compare the slice and eternal roles |
| O2 | server | 18980 | yes | pass | should I apply to blackbuck? |
| O3 | server | 9428 | yes | pass | why is axis bank a good fit for me? |
| O4 | server | 6996 | yes | pass | tips to prepare for the eternal test |
