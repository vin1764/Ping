# Ping evals

Three eval suites, each repeatable, each with expected answers written by reading the data (never by running
the model being tested).

| suite | what it measures | current score | report | re-run |
|---|---|---|---|---|
| **Parser evals** | How Ping reads the ERP's notices and PDFs with rules: company, kind of notice, deadline, test time, venue, form link, "are you in this PDF", your room. 31 development + 15 held-out real CDC notices (other students' details removed) and 7 PDF/Excel layouts seen in the real run. | **Held-out: 56 of 58 checks (97%)**, the fair number. Development: 143 of 143 (100%), optimistic because Ping was fixed using these. | [PARSER_REPORT.md](PARSER_REPORT.md) | `python evals/run_evals.py` |
| **Ask Ping evals** | The chat's answers from the deployed `ask-ping` function, from one-click demo sessions (anonymised demo data), with the snapshot time fixed: company facts, deadlines, notices and tests, refusing to invent things, refusing actions only when asked to act (Ping is read-only), times today ("was at 15:00, so it's over" / "in 1h 25m"), and typos / two questions in one. 39 single questions and 13 two-turn conversations (follow-ups like "nothing else?", "and slice?", "why not?", "ok") with deterministic checks (required and forbidden phrases, numbers in any format, word limits). | **Single questions: 35 of 39 (90%). Conversations: 13 of 13 (26 of 26 turns).** Before conversation memory: 34 of 36 single, 4 of 9 conversations (13 of 18 turns). | [ask_ping/REPORT.md](ask_ping/REPORT.md) | Actions > Admin > `ask-ping-evals`, or `python evals/ask_ping/run_ask_ping_evals.py` |
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
