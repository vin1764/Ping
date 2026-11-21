# Ping evals

Two eval suites, each repeatable, each with expected answers written by reading the data (never by running
the model being tested).

| suite | what it measures | current score | report | re-run |
|---|---|---|---|---|
| **Parser evals** | How Ping reads the ERP's notices and PDFs with rules: company, kind of notice, deadline, test time, venue, form link, "are you in this PDF", your room. 31 development + 15 held-out real CDC notices (other students' details removed) and 7 PDF/Excel layouts seen in the real run. | **Held-out: 56 of 58 checks (97%)**, the fair number. Development: 143 of 143 (100%), optimistic because Ping was fixed using these. | [PARSER_REPORT.md](PARSER_REPORT.md) | `python evals/run_evals.py` |
| **Ask Ping evals** | The chat's answers from the deployed `ask-ping` function, signed in as the reviewer (anonymised demo data), with the snapshot time fixed: company facts, deadlines, notices and tests, refusing to invent things, refusing actions (Ping is read-only), and typos / two questions in one. 36 questions with deterministic checks (required and forbidden phrases, numbers in any format, word limits). | **32 of 36 questions (89%)** after one fix to the function (first run: 15 of 36, 42%). By category: company facts 7/8, deadlines 8/8, notices 5/6, no-hallucination 4/6, read-only 4/4, robustness 4/4. Every answer came from the fallback model `gemini-flash-lite-latest`. | [ask_ping/REPORT.md](ask_ping/REPORT.md) | Actions > Admin > `ask-ping-evals`, or `python evals/ask_ping/run_ask_ping_evals.py` |

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
