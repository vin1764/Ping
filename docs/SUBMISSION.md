# Ping: submission

**Live:** https://vin1764.github.io/ping-dashboard/ (click **View demo**; no account needed)

Ping reads one student's placement ERP every hour (companies list, notice board, the PDFs attached to notices, and
the institute mailbox), keeps only what concerns that student, and tells them in a chat. It only reads: it cannot
apply, submit, upload or accept anything. The demo is an anonymised snapshot of a real run on 21 Nov 2026: real
companies, roles, pay, deadlines and notices; a made-up student with made-up CVs.

## What to try (in the demo's chat box)

1. A company question: `slice ctc breakdown`
2. A deadline question: `what's due tonight?`
3. A follow-up: `anything else?`
4. A preference change: `only show me product and consulting roles` (the lists in the chat re-split at once)
5. `which cv for groww`
6. `apply for me` (Ping is read-only and says so)

## Documents

| document | what's in it |
|---|---|
| [docs/PROMPTS.md](PROMPTS.md) | every prompt Ping sends to a model, verbatim, generated from the source (a test fails if it drifts) |
| [evals/REPORT.md](../evals/REPORT.md) | the eval suites and their scores: parser, Ask Ping (single questions and conversations), role relevance per persona |
| [docs/ONE_PAGER_FACTS.md](ONE_PAGER_FACTS.md) | the numbers, each with its source: runs, schedule, evals, latency, cost |
| [docs/SECURITY.md](SECURITY.md) | who can read and write what (tables, CV storage), secrets, rate limits, demo isolation |
| [docs/SETUP.md](SETUP.md) | how a student sets up their own copy, and what the first hour looks like |
| [docs/BUILD_PROMPTS.md](BUILD_PROMPTS.md) | every prompt given to the coding agent while building Ping, in order |
| [docs/REVIEWER_RUN.md](REVIEWER_RUN.md) | a stranger's run of the live demo, answers verbatim with HTTP codes and timings |
