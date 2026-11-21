# Ping evals

Three eval suites, each repeatable, each with expected answers written by reading the data (never by running
the model being tested).

| suite | what it measures | current score | report | re-run |
|---|---|---|---|---|
| **Parser evals** | How Ping reads the ERP's notices and PDFs with rules: company, kind of notice, deadline, test time, venue, form link, "are you in this PDF", your room. 31 development + 15 held-out real CDC notices (other students' details removed) and 7 PDF/Excel layouts seen in the real run. | **Held-out: 56 of 58 checks (97%)**, the fair number. Development: 143 of 143 (100%), optimistic because Ping was fixed using these. | [PARSER_REPORT.md](PARSER_REPORT.md) | `python evals/run_evals.py` |
| **Ask Ping evals** | The chat's answers from the deployed `ask-ping` function, from one-click demo sessions (anonymised demo data, the demo persona's targets and made-up CVs), with the snapshot time fixed: company facts, deadlines, notices and tests, refusing to invent things, refusing actions only when asked to act, times today, role lists in one format, the CV to apply with, and typos / two questions in one. 42 single questions and 21 conversations: 13 follow-up conversations ("nothing else?", "and slice?", "ok") and 8 preference-by-chat conversations (set, append, exclude, reminder hours, list others, reset, show, and a question that must NOT change anything). Deterministic checks. | **Single questions: 37 of 42 (88%). Conversations: 21 of 21 (39 of 39 turns).** Before conversation memory: 34 of 36 single, 4 of 9 conversations. | [ask_ping/REPORT.md](ask_ping/REPORT.md) | Actions > Admin > `ask-ping-evals` |
| **Role relevance evals** | Whether "For you" (and the CV to apply with) follows the student's stated targets: two made-up personas with opposite targets (`relevance/personas.json`), 201 + 48 demo roles labelled for each persona's text, each persona's roles marked in one classifier call. | **demo persona: precision 93% (76 of 82), recall 97% (76 of 78), best CV right 96% (73 of 76). core-software persona: precision 100% (28 of 28), recall 100% (28 of 28).** | [relevance/REPORT.md](relevance/REPORT.md) | Actions > Admin > `relevance-evals` |

Also in this folder: `real_run.json` (numbers from the real runs: login time, notices, PDFs, merged repeats),
`notices.json` and `companies.json` (the parser eval inputs), `ask_ping/cases.json` (the Ask Ping questions,
checks and where each expected answer comes from).

## Ask Ping: what changed between the two runs

The first run (15 of 36) showed that the function wasn't giving Gemini the data some questions need (CG
cut-off, departments, your shortlist / room results, the latest notices) and that the prompt never said Ping is
read-only. Both were fixed in `supabase/functions/ask-ping/index.ts`. Separately, two shared phrase lists in the
checks missed "does not contain" / "does not show any" although those answers correctly said there was nothing;
that change is recorded in `ask_ping/cases.json` (`check_changes`). No other check was changed.

The 4 failures left are the model's: a "Yes." that contradicts "Bonds: No" (C7), a missing room number (N2),
and two answers over the word limit or quoting other companies' pay when asked about one that isn't in the data
(X3, X5). X5 is arguable: nothing about the missing company was invented. See [ask_ping/REPORT.md](ask_ping/REPORT.md).

## Ask Ping: conversation memory (21 Nov)

Ask Ping now reads the last 10 messages of the thread (about 2,000 tokens) in the function. Three runs, checks
unchanged:

| run | single questions | conversations |
|---|---|---|
| before memory | 34 of 36 | 4 of 9 (13 of 18 turns) |
| with memory, the read-only refusal only for requests to act, times today | 35 of 39 | 8 of 13 (19 of 26 turns) |
| after one prompt fix (counted "today and this week" summary, name the company, "I don't have" first) and working fallback models | **35 of 39** | **13 of 13 (26 of 26 turns)** |

The 4 single-question failures left: "am I eligible for Harness" doesn't quote the 7.5 cut-off (C2); "anything due
today" gives the count (48 roles at 23 companies close at 20:00) but not the company names the check asks for (D2);
"what's due on 25 / 30 November" answer "I don't have any deadlines for 25 November" where the check expects
"nothing / no deadline" (D8, X2): a side effect of the fix's "start with I don't have" rule. Not changed after the
one allowed fix round.

## Ask Ping: preferences, list format and CVs (21 Nov, evening)

| run | single questions | conversations |
|---|---|---|
| with preferences by chat, ready-made role lists, CVs | 34 of 42 | 20 of 21 (38 of 39 turns) |
| after one fix (lists only for deadline/role questions, date in the list heading, "Nothing is due on <day>") | **38 of 42** | **20 of 21 (38 of 39 turns)** |

Still failing: C2 (doesn't quote the 7.5 cut-off), D2 (gives counts, not the company names), D3 (the week's list
without the time), L1 (a "relevant to me" list without Others: treated as narrowing, see docs/DECISIONS.md), and
M8 turn 2. Checks unchanged.

## Ask Ping: closing round (21 Nov, 23:11 IST)

The 4 failures left after the evening runs were fixed, checks unchanged: C2 (eligibility now quotes the CG cut-off and
your CGPA), D2 (what's due names the companies), D3 and M8 turn 2 (the week summary carries times; "this week"
includes today). All four pass, and conversations are **21 of 21 (39 of 39 turns)**. Single questions: **37 of 42**.
Four other cases that passed in the previous run failed in this one: N2 (room number left out), X2 ("I don't have
any notice" instead of "nothing"), B2 and B3 (one CTC figure left out each). In this run Gemini's free tier
answered 11 questions from fallback models (gemini-3.5-flash-lite, gemini-3.1-flash-lite) after rate-limiting
the main one; B2 was answered by a fallback. L1 is as decided in docs/DECISIONS.md. No further fix round.
