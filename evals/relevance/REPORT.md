# Role relevance evals

Each fixture persona's roles are marked by the classifier in one call with that persona's targets text (`personas.json`), and compared with labels that are correct for that text (`cases.json`). Re-run: Actions > Admin > `relevance-evals`.

| persona | targets | roles | precision of "For you" | recall of "For you" | best CV right | not answered | model that answered |
|---|---|---|---|---|---|---|---|
| demo | product, consulting, business/data analyst and finance roles; not core software engineering | 201 | **90%** (76 of 84) | **99%** (76 of 77) | **92%** (70 of 76) | 1 | gemini-flash-lite-latest (200) |
| core-software | software engineering roles: backend, frontend, full-stack and SDE; not data science, machine learning, product management, consulting, analyst, finance or core (non-software) engineering roles | 48 | **100%** (28 of 28) | **100%** (28 of 28) | n/a (no CVs) | 0 | gemini-flash-lite-latest (48) |

## Disagreements

| persona | company | role | label | classifier | classifier's reason |
|---|---|---|---|---|---|
| demo | Accordion India | Data & AI Analyst 2 | CV: Analytics & Finance CV | CV: Product CV | Business requirements analysis and analytical projects |
| demo | Airbus India Private Limited | Associate Engineer Industrialisation_Robotics and Data Analytics_PG | not | for you | Data analytics applied to industrial operations |
| demo | Arihant Capital Markets Limited | Customer Data Analytics & Engagement Specialist (CleverTap) | CV: Analytics & Finance CV | CV: Product CV | Customer data analytics and engagement role |
| demo | Arihant Capital Markets Limited | Trading & WealthTech | CV: Analytics & Finance CV | CV: Product CV | AI product manager role |
| demo | Ather Energy | Product Ownership | for you | not | Product ownership technical rotational program |
| demo | AXON DEVELOPERS | Manager Strategy | CV: Consulting CV | CV: Product CV | Manager strategy focusing on process automation and AI |
| demo | Cars24 | Data Science | not | for you | Data science role |
| demo | Collins Aerospace | PGET - IP & Technology Research Analyst | not | for you | IP and technology research and strategy analyst |
| demo | EXL Service | Analytics - Consultant I | CV: Consulting CV | CV: Analytics & Finance CV | Analytics consultant solving business problems |
| demo | FischerJordan | Sr. Analyst | CV: Analytics & Finance CV | CV: Consulting CV | Senior analyst consulting with clients and providing recommendations |
| demo | KLA | Product Applications Engineer | not | for you | Product applications engineer bridging technical and customer roles |
| demo | Nation with Namo | Associate | not | for you | Graduate leadership program associate role |
| demo | Purplle | ALDI Graduate Engineering Trainee | not | for you | Accelerated leadership development trainee role |
| demo | Telus Digital | Associate Project Manager | not | for you | Associate project manager role |
| demo | Urban Company | Senior Category Manager | not | for you | Senior category manager handling operations and strategy |
