# Ping evals

Two eval suites, each repeatable, each with expected answers written by reading the data (never by running
the model being tested).

| suite | what it measures | current score | report | re-run |
|---|---|---|---|---|
| **Parser evals** | How Ping reads the ERP's notices and PDFs with rules: company, kind of notice, deadline, test time, venue, form link, "are you in this PDF", your room. 31 development + 15 held-out real CDC notices (other students' details removed) and 7 PDF/Excel layouts seen in the real run. | **Held-out: 56 of 58 checks (97%)**, the fair number. Development: 143 of 143 (100%), optimistic because Ping was fixed using these. | [PARSER_REPORT.md](PARSER_REPORT.md) | `python evals/run_evals.py` |
| **Ask Ping evals** | The chat's answers from the deployed `ask-ping` function, signed in as the reviewer (anonymised demo data), with the snapshot time fixed: company facts, deadlines, notices and tests, refusing to invent things, refusing actions (Ping is read-only), and typos / two questions in one. 36 questions with deterministic checks (required and forbidden phrases, numbers in any format, word limits). | _first run in progress_ | [ask_ping/REPORT.md](ask_ping/REPORT.md) | Actions > Admin > `ask-ping-evals`, or `python evals/ask_ping/run_ask_ping_evals.py` |

Also in this folder: `real_run.json` (numbers from the real runs: login time, notices, PDFs, merged repeats),
`notices.json` and `companies.json` (the parser eval inputs), `ask_ping/cases.json` (the Ask Ping questions,
checks and where each expected answer comes from).
