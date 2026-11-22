# Role relevance evals

Each fixture persona's roles are marked by the classifier in one call with that persona's targets text (`personas.json`), and compared with labels that are correct for that text (`cases.json`). Re-run: Actions > Admin > `relevance-evals`.

| persona | targets | roles | precision of "For you" | recall of "For you" | best CV right | not answered |
|---|---|---|---|---|---|---|
| demo | product, consulting, business/data analyst and finance roles; not core software engineering | 201 | **79%** (77 of 98) | **99%** (77 of 78) | **95%** (73 of 77) | 0 |
| core-software | software engineering roles: backend, frontend, full-stack and SDE; not data science, machine learning, product management, consulting, analyst, finance or core (non-software) engineering roles | 48 | **100%** (28 of 28) | **100%** (28 of 28) | n/a (no CVs) | 0 |

## Disagreements

| persona | company | role | label | classifier | classifier's reason |
|---|---|---|---|---|---|
| demo | Airbus India Private Limited | Associate Engineer Industrialisation_Robotics and Data Analytics_PG | not | for you | Data analytics role for industrial challenges |
| demo | Arihant Capital Markets Limited | Data Scientist / ML Engineer | not | for you | Data science role fits data analyst preference |
| demo | Arihant Capital Markets Limited | Trading & WealthTech | CV: Analytics & Finance CV | CV: Product CV | AI product manager role fits product preference |
| demo | Ather Energy | Data Office | not | for you | Data science and ML role |
| demo | Ather Energy | Product Ownership | for you | not | Manufacturing leadership program, not PM |
| demo | Auro Group(www.AuroIM.com) | Sales & Business Development | not | for you | Business development role fits consulting/business track |
| demo | Cars24 | Data Science | not | for you | Data science role |
| demo | Collins Aerospace | PGET - IP & Technology Research Analyst | not | for you | IP and technology research analyst role |
| demo | DB | Analyst | CV: Analytics & Finance CV | CV: Consulting CV | Investment banking and corporate support analyst role |
| demo | ESRI | Data Scientist I | not | for you | Data scientist role |
| demo | EXL Service | Analytics - Consultant I | CV: Consulting CV | CV: Analytics & Finance CV | Analytics consultant role |
| demo | EY Global Delivery Services India LLP | Senior Analyst - Data Scientist | not | for you | Data scientist role |
| demo | FischerJordan | Sr. Analyst | CV: Analytics & Finance CV | CV: Consulting CV | Senior analyst client consulting role |
| demo | INFO EDGE INDIA LIMITED | Data Scientist | not | for you | Data scientist role |
| demo | KLA | Product Applications Engineer | not | for you | Product applications and client-facing technical consulting role |
| demo | Moneyview Ltd | Data Scientist | not | for you | Data scientist role |
| demo | Nation with Namo | Associate | not | for you | Graduate impact leadership program associate role |
| demo | Navi Limited | Data Scientist I, Navi | not | for you | Data scientist role |
| demo | NoBroker.com | Associate Data Scientist | not | for you | Associate data scientist role |
| demo | Purplle | ALDI Graduate Engineering Trainee | not | for you | Accelerated leadership development management trainee role |
| demo | Searce Inc. | Associate Data Engineer | not | for you | Data engineer role |
| demo | SLB | Datascientist | not | for you | Data scientist role |
| demo | Swiggy Limited | Data Scientist 1 | not | for you | Data scientist role |
| demo | Telus Digital | Associate Project Manager | not | for you | Associate project manager product role |
| demo | Tredence Analytics | DATA SCIENTIST | not | for you | Data scientist analytics role |
| demo | Urban Company | Senior Category Manager | not | for you | Senior category manager general management role |
