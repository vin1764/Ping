# Role relevance evals

Each fixture persona's roles are marked by the classifier in one call with that persona's targets text (`personas.json`), and compared with labels that are correct for that text (`cases.json`). Re-run: Actions > Admin > `relevance-evals`.

| persona | targets | roles | precision of "For you" | recall of "For you" | best CV right | not answered |
|---|---|---|---|---|---|---|
| demo | product, consulting, business/data analyst and finance roles; not core software engineering | 201 | **93%** (76 of 82) | **97%** (76 of 78) | **96%** (73 of 76) | 0 |
| core-software | software engineering roles: backend, frontend, full-stack and SDE; not data science, machine learning, product management, consulting, analyst, finance or core (non-software) engineering roles | 48 | **100%** (28 of 28) | **100%** (28 of 28) | n/a (no CVs) | 0 |

## Disagreements

| persona | company | role | label | classifier | classifier's reason |
|---|---|---|---|---|---|
| demo | Airbus India Private Limited | Associate Engineer Industrialisation_Robotics and Data Analytics_PG | not | for you | Data analytics role for industrial challenges |
| demo | Arihant Capital Markets Limited | Trading & WealthTech | for you | not | Trading technology role |
| demo | Ather Energy | Product Ownership | for you | not | Not product management; core tech role |
| demo | Auronova Consulting | Analyst | CV: Consulting CV | CV: Analytics & Finance CV | Risk management and quantitative modeling role |
| demo | Collins Aerospace | PGET - IP & Technology Research Analyst | not | for you | Intellectual property and technology strategy analyst |
| demo | EXL Service | Analytics - Consultant I | CV: Consulting CV | CV: Analytics & Finance CV | Analytics consultant role |
| demo | FischerJordan | Sr. Analyst | CV: Analytics & Finance CV | CV: Consulting CV | Senior analyst consulting and client-facing role |
| demo | KLA | Product Applications Engineer | not | for you | Product applications engineering role |
| demo | Nation with Namo | Associate | not | for you | Graduate impact leadership program associate role |
| demo | Telus Digital | Associate Project Manager | not | for you | Associate project manager role |
| demo | Urban Company | Senior Category Manager | not | for you | Senior category manager operations role |
