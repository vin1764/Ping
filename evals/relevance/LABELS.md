# Relevance labels

Labels are what is correct for each **fixture persona's** targets text (made-up students in `personas.json`), not for any real student. Scored by `run_relevance_evals.py` (Actions > Admin > `relevance-evals`).

## Persona `demo`

Targets: **product, consulting, business/data analyst and finance roles; not core software engineering**

The 31 rows first marked '?' were re-read against the persona's text, and the other 170 re-checked; management-trainee, founder's-office and strategy tracks count as consulting/business, data scientist roles don't count as analyst roles, quant research/trading counts as finance.

Labels changed in the consistency pass:

- Collins Aerospace — PGET - IP & Technology Research Analyst: for you -> not (IP and technology research is none of product, consulting, analyst or finance)
- Telus Digital — Associate Project Manager: for you -> not (project delivery management is none of product, consulting, analyst or finance)
- Urban Company — Senior Category Manager: for you -> not (category operations management is none of product, consulting, analyst or finance)

| # | company | role | label | reason |
|---|---|---|---|---|
| 1 | Accenture India Private Limited | Elite Technology Engineer | not | software engineering |
| 2 | Accenture Japan | Digital Consultant | **for you** | technology consulting for clients |
| 3 | Accenture Solutions Private Limited | I&E- AI and Data PG FTE | not | AI and data engineering; JD only in an email |
| 4 | Accordion India | AI_ML Engineer 2 | not | ML engineering |
| 5 | Accordion India | Data & AI Analyst 2 | **for you** | business research and data analysis |
| 6 | Accordion India | Data & AI Engineer 2 | not | data engineering |
| 7 | AiPrise | Software Engineer I | not | software engineering |
| 8 | AiPrise | Software Engineer I, Full Stack (Frontend Focused) | not | frontend software engineering |
| 9 | AiPrise | Software Engineer II | not | software engineering |
| 10 | AiPrise | Software Engineer II, Full Stack (Frontend Focused) | not | frontend software engineering |
| 11 | AIRAMATRIX PRIVATE LIMITED | Trainee Engineer | not | AI / image-processing engineering |
| 12 | Airbus India Private Limited | Associate Engineer - Advanced Engineering & System Studies_PG | not | core aerospace engineering |
| 13 | Airbus India Private Limited | Associate Engineer - Cabin_PG | not | core aerospace engineering |
| 14 | Airbus India Private Limited | Associate Engineer - Flight Physics_PG | not | core aerospace engineering |
| 15 | Airbus India Private Limited | Associate Engineer - Industrialisation_PG | not | manufacturing engineering |
| 16 | Airbus India Private Limited | Associate Engineer - Propulsion System Engineer_PG | not | core propulsion engineering |
| 17 | Airbus India Private Limited | Associate Engineer Industrialisation_Robotics and Data Analytics_PG | not | industrial robotics and data engineering |
| 18 | Allegro Capital Advisors | Investment Banking Analyst | **for you** | investment banking analyst |
| 19 | Amazon | Software Development Engineer I | not | software engineering |
| 20 | American Express | Management Trainee - Data Science & Analytics | **for you** | data science and analytics trainee |
| 21 | Arihant Capital Markets Limited | AI/ML Engineer | not | ML engineering |
| 22 | Arihant Capital Markets Limited | Backend Engineer | not | backend engineering |
| 23 | Arihant Capital Markets Limited | Customer Data Analytics & Engagement Specialist (CleverTap) | **for you** | customer data analytics |
| 24 | Arihant Capital Markets Limited | Data Scientist / ML Engineer | not | data science / ML engineering |
| 25 | Arihant Capital Markets Limited | PRODUCT MANAGER | **for you** | product management |
| 26 | Arihant Capital Markets Limited | Quantitative Research / Algorithmic Trading | **for you** | quant research and trading |
| 27 | Arihant Capital Markets Limited | Trading & WealthTech | **for you** | trading and wealth-tech (finance) |
| 28 | Astera Labs | Software Quality Assurance (SQA) Engineer | not | software QA engineering |
| 29 | Ather Energy | Chief Engineer | not | core engineering |
| 30 | Ather Energy | Data Office | not | ML engineering |
| 31 | Ather Energy | Hardware Pack Engineering | not | mechanical design |
| 32 | Ather Energy | Product Ownership | **for you** | product ownership track |
| 33 | Ather Energy | System Intelligence | not | engineering; no JD |
| 34 | Auro Group(www.AuroIM.com) | AI/ML Software Engineer | not | ML engineering |
| 35 | Auro Group(www.AuroIM.com) | Back End Developer | not | backend engineering |
| 36 | Auro Group(www.AuroIM.com) | Data Analyst | **for you** | data analyst |
| 37 | Auro Group(www.AuroIM.com) | Frontend Developer | not | frontend engineering |
| 38 | Auro Group(www.AuroIM.com) | Full Stack Developer | not | full stack engineering |
| 39 | Auro Group(www.AuroIM.com) | Product Manager | **for you** | product management |
| 40 | Auro Group(www.AuroIM.com) | Sales & Business Development | not | sales and business development |
| 41 | Auronova Consulting | Analyst | **for you** | risk management consulting |
| 42 | Avathon | Associate Software Engineer | not | software engineering |
| 43 | Axis Bank | BIU (Business Intelligence Unit) | **for you** | business intelligence and analytics |
| 44 | AXON DEVELOPERS | Manager Strategy | **for you** | strategy and process improvement |
| 45 | AXON DEVELOPERS | MDs Office | **for you** | MD's office, strategy and execution |
| 46 | Axxela Research & Analytics Private Limited | Trainee Analyst | **for you** | commodities and fixed income trading |
| 47 | BlackBuck | Associate Manager BlackBuck Leadership Program | **for you** | general management leadership program |
| 48 | BlackRock | AI & ML Engineer (Aladdin Engineering) Analyst | not | ML engineering |
| 49 | BlackRock | Aladdin Data Engineering Analyst | not | data engineering |
| 50 | Capital One Services India Pvt. Ltd. | Associate (Software Engineer) | not | software engineering |
| 51 | Capital One Services India Pvt. Ltd. | Associate - BusinessAnalyst | **for you** | business analyst |
| 52 | Cars24 | AI/ML | not | ML engineering; no JD |
| 53 | Cars24 | Data Science | not | data science; no JD |
| 54 | Cars24 | Generative AI | not | generative AI engineering; no JD |
| 55 | Cars24 | Software Engineering | not | software engineering; no JD |
| 56 | Cognizant Technology Solutions | Ace Frontier Engineer Associate | not | AI engineering |
| 57 | Cognizant Technology Solutions | Ace Frontier Engineer Senior Associate | not | AI engineering |
| 58 | Collins Aerospace | PGET - Advanced Methods | not | core aerospace engineering |
| 59 | Collins Aerospace | PGET - AI/ML | not | AI/ML engineering |
| 60 | Collins Aerospace | PGET - Autonomous & Intelligent Aerospace Systems | not | aerospace systems engineering |
| 61 | Collins Aerospace | PGET - IP & Technology Research Analyst | not | IP and technology strategy analyst (not in the persona's list) |
| 62 | Collins Aerospace | PGET - Mechanical Design | not | mechanical design |
| 63 | Collins Aerospace | PGET - Microelectronics | not | microelectronics engineering |
| 64 | Collins Aerospace | PGET - Power Electronics | not | power electronics engineering |
| 65 | Commonwealth Bank of Australia | Graduate Engineering | not | software engineering |
| 66 | D. E. Shaw India | Technology Developer | not | software development |
| 67 | Dassault Systemes | AI Engineer-Data Scientist-PG | not | AI engineering / data science |
| 68 | Dassault Systemes | Software Engineer - Domain Engineering & AI Innovation-PG | not | software engineering |
| 69 | DB | Analyst | **for you** | investment banking analyst |
| 70 | Deloitte | Analyst | **for you** | technology consulting |
| 71 | DELOITTE TOUCHE TOHMATSU INDIA LLP | Consultant | EAD OIDS ER&I | **for you** | consulting |
| 72 | Diageo | GBS MANAGEMENT TRAINEE | **for you** | management trainee |
| 73 | Energy Aspects | Energy Market Analyst | **for you** | energy market research analyst |
| 74 | ESRI | Data Scientist I | not | data science |
| 75 | ETERNAL | Assistant Program Manager | **for you** | program management and strategy |
| 76 | Eternal | Machine Learning Scientist | not | ML research |
| 77 | Eternal | Product Analyst | **for you** | product analyst |
| 78 | Eternal | Software Development Engineer I | not | software engineering |
| 79 | EXL Service | Analytics - Consultant I | **for you** | analytics consulting |
| 80 | ExxonMobil Services & Technology Private Limited | Marine Engineer-PG | not | marine engineering |
| 81 | EY Global Delivery Services India LLP | Senior Analyst - Data Scientist | not | data science / ML |
| 82 | EY Global Delivery Services India LLP | Senior Analyst - Supply Chain Management | **for you** | supply chain and transaction consulting |
| 83 | EY Parthenon | Associate Consultant | **for you** | strategy consulting |
| 84 | Finarb | AI Engineer | not | AI engineering |
| 85 | Finarb | Data Engineer | not | data engineering |
| 86 | Finarb | Full Stack Developer | not | full stack engineering |
| 87 | FirstClub | Product Management | **for you** | product management |
| 88 | FischerJordan | Software Engineer (SWE)- Frontend Web Developer | not | frontend engineering |
| 89 | FischerJordan | Software Engineer - Backend Web Developer | not | backend engineering |
| 90 | FischerJordan | Sr. Analyst | **for you** | client-facing business analyst |
| 91 | Flipkart | AI Engineer | not | AI engineering |
| 92 | Flipspaces Technology Labs Pvt. Ltd. | Entrepreneur-in-Residence | **for you** | entrepreneur-in-residence, business building |
| 93 | GDi Partners | Associate Consultant | **for you** | impact consulting |
| 94 | Glean Search Technologies India Private Limited | Software Engineer - India | not | software engineering |
| 95 | Glean Search Technologies India Private Limited | Software Engineer - US | not | software engineering |
| 96 | Goldman Sachs | Quantitative Strategist | **for you** | quant strategist (finance) |
| 97 | Groww | Associate Product Manager | **for you** | product management |
| 98 | Hakimo AI | Applied ML Engineer | not | ML engineering |
| 99 | Hakimo AI | Associate Product Manager | **for you** | product management |
| 100 | Hakimo AI | Cloud Infrastructure & Platform Engineer (DevOps / SRE) | not | DevOps / infrastructure |
| 101 | Hakimo AI | Founders Office Analyst | **for you** | founder's office analyst |
| 102 | Hakimo AI | Full Stack Software Engineer | not | full stack engineering |
| 103 | Harness | Software Engineer I | not | software engineering |
| 104 | HILABS | AI Engineer | not | AI engineering |
| 105 | HILABS | Associate Product Manager | **for you** | product management |
| 106 | Houlihan Lokey Advisory (India) Private Limited | Analyst | not | JD is DevOps platform engineering |
| 107 | ICICI LOMBARD | Actuarial Analyst | **for you** | actuarial analyst (finance) |
| 108 | IDFC FIRST Bank | Associate Data Analyst | **for you** | data analyst |
| 109 | IDFC FIRST Bank | Associate Data Scientist-AI Labs | not | data science / ML |
| 110 | IDFC FIRST Bank | Associate Product Manager-AI | **for you** | AI product management |
| 111 | Indus Insights | Associate | **for you** | consulting associate |
| 112 | INFO EDGE INDIA LIMITED | Data Scientist | not | data science |
| 113 | InMobi Privated Limited and Glance Private Limited | SDEI | not | software engineering |
| 114 | Insurity Solutions India Private Limited | Software Engineer I | not | software engineering |
| 115 | IQVIA | Analyst | **for you** | healthcare analytics analyst; no JD |
| 116 | IQVIA | Associate Consultant | **for you** | consulting; no JD |
| 117 | IvyCap Ventures | Investment Analyst | **for you** | venture investment analyst |
| 118 | Ixana | IC Design Engineer II | not | chip design |
| 119 | Ixana | IC Design Engineer III | not | chip design |
| 120 | Ixana | Silicon Engineer | not | chip design |
| 121 | JP MorganChase | Commercial & Investment Bank Research & Analytics, Global Research - Full Time Analyst | **for you** | investment banking research and analytics |
| 122 | Kalam Labs (legal name: Elixar Systems Pvt Ltd) | Aerodynamics Engineer | not | aerodynamics engineering |
| 123 | Kalam Labs (legal name: Elixar Systems Pvt Ltd) | Avionics Engineer | not | avionics engineering |
| 124 | Kalam Labs (legal name: Elixar Systems Pvt Ltd) | Mechanical Engineer | not | mechanical engineering |
| 125 | KLA | Product Applications Engineer | not | semiconductor applications engineering |
| 126 | LANDEED (JOHN SALT PVT LIMITED) | AI/ML Engineer (Post-Training) | not | ML engineering |
| 127 | LANDEED (JOHN SALT PVT LIMITED) | Full Stack Engineer | not | full stack engineering |
| 128 | LAT AEROSPACE | Engineer | not | aerospace engineering |
| 129 | LTM | Post-Graduate Engineer Trainee | not | engineering trainee; JD only as a link |
| 130 | LYSKRAFT Pvt Ltd | APM | **for you** | product management |
| 131 | LYSKRAFT Pvt Ltd | SDE - 1 | not | software engineering |
| 132 | MathWorks India Private Limited | Engineer (Dual Degree, Masters) in Engineering Development Group | not | engineering development |
| 133 | MathWorks India Private Limited | Technical Writer | not | technical writing |
| 134 | Media.Net | Senior Product Analyst | **for you** | product analyst |
| 135 | Meesho | Senior Assosiate - Business Management | **for you** | business management |
| 136 | MeltPlan Inc | Software Engineer | not | full stack engineering |
| 137 | Microsoft Corporation | Software Engineer | not | software engineering |
| 138 | Moneyview Ltd | Business Analyst | **for you** | business analyst |
| 139 | Moneyview Ltd | Data Scientist | not | data science |
| 140 | Mygate | Software Developer Engineer | not | software engineering |
| 141 | Nation with Namo | Associate | not | political campaign leadership program |
| 142 | NATWEST | Software Engineer | not | software engineering |
| 143 | Navi Limited | AI strategy Operations | **for you** | AI strategy and operations |
| 144 | Navi Limited | Associate Product Manager I | **for you** | product management |
| 145 | Navi Limited | Data Scientist I, Navi | not | data science |
| 146 | Navi Limited | SDE-1 | not | software engineering |
| 147 | NexusOne | Data/App Engineer | not | data and app engineering |
| 148 | NoBroker.com | Applied Scientist | not | applied ML research |
| 149 | NoBroker.com | Associate Data Scientist | not | data science / ML |
| 150 | OLA | Founder's Program - General Management | **for you** | general management founder's program |
| 151 | OLA | Founder's Program Technology | not | technology founder's program |
| 152 | OLA | Graduate Engineer Trainee (GET) Product Engineering & Advanced Manufacturing | not | product engineering and manufacturing |
| 153 | OLA | Graduate Engineer Trainee (GET) Software, Cloud Engineering & AI | not | software and cloud engineering |
| 154 | Phyagents, Inc. | Machine Learning Engineer, Robotic Foundation Models | not | ML engineering |
| 155 | Phyagents, Inc. | Software Engineer, Gen AI & Robotics | not | software engineering |
| 156 | PhysicsWallah Limited | Associate Product Manager (APM) | **for you** | product management |
| 157 | Pine Labs | Software Development Engineer | not | software engineering |
| 158 | Plutus Research Private Limited | Quantitative Analyst | **for you** | quant analyst (finance) |
| 159 | Plutus Research Private Limited | Trading Systems Developer | not | trading systems development |
| 160 | Pocket FM | Management Trainee | **for you** | management trainee; JD only as a link |
| 161 | Porter | Associate Product Manager (APM) | **for you** | product management |
| 162 | Porter | Software Development Engineer - 1 | not | software engineering |
| 163 | Prism (Oyo) | Young Leader | **for you** | program management leadership track |
| 164 | Prodigal Technologies Inc. | Associate Consultant | **for you** | consulting for financial institutions |
| 165 | Purplle | ALDI Graduate Engineering Trainee | not | engineering trainee; JD only in mail |
| 166 | Route Mobile Limited | Business Analyst | **for you** | business analyst |
| 167 | Route Mobile Limited | SDE 1 | not | software engineering |
| 168 | RV Capital | Risk Analyst | **for you** | risk analyst (finance) |
| 169 | Searce Inc. | Associate Cloud Engineer | not | cloud engineering |
| 170 | Searce Inc. | Associate Data Engineer | not | data engineering |
| 171 | Searce Inc. | Associate Solutions Consultant | **for you** | solutions consulting |
| 172 | Searce Inc. | Evlos AI Engineer | not | AI engineering |
| 173 | SLB | Datascientist | not | data science |
| 174 | slice | Analyst | **for you** | analytics analyst |
| 175 | slice | Associate Product Manager | **for you** | product management |
| 176 | SQUAREPOINT CAPITAL | Desk Quant Analyst | **for you** | desk quant analyst (finance) |
| 177 | SQUAREPOINT CAPITAL | Graduate Software Developer | not | software development |
| 178 | SQUAREPOINT CAPITAL | Infrastructure Engineer | not | infrastructure engineering |
| 179 | Sun Valley Investment Group through Sun Valley Resources Private Limited | Research Analyst | **for you** | commodities research analyst |
| 180 | Swiggy Limited | Data Scientist 1 | not | data science; no JD |
| 181 | Takshashila Consulting | Business Analyst | **for you** | consulting business analyst |
| 182 | TATA AIG General Insurance | Senior Engineer Trainee - Analytics | **for you** | insurance analytics; JD attached only |
| 183 | TCG DIGITAL SOLUTIONS PVT. LTD. | Consultant / Product Developer | **for you** | analytics consulting |
| 184 | Telus Digital | Associate Project Manager | not | project management (not in the persona's list) |
| 185 | Tiger Analytics | Trainee Analyst | **for you** | analytics trainee |
| 186 | Tolaram Group | Management Trainee Enterprise Transformation | **for you** | management trainee, transformation |
| 187 | Tredence Analytics | DATA SCIENTIST | not | data science / ML |
| 188 | Trexquant (India) Business Consulting LLP | Quantitative Researcher | **for you** | quant research (finance) |
| 189 | Urban Company | Senior Category Manager | not | category and business operations (not in the persona's list) |
| 190 | Warner Music Group | Software Engineer - 1 | not | backend engineering |
| 191 | Waterfly Technologies | Graduate Engineer 1 | not | core engineering |
| 192 | Waterfly Technologies | Graduate Engineer 2 | not | core engineering |
| 193 | Waterfly Technologies | Growth and Strategist | **for you** | growth and strategy |
| 194 | Waterfly Technologies | Management Consultant 1 | **for you** | management consulting |
| 195 | Waterfly Technologies | Managment Consultant 2 | **for you** | management consulting |
| 196 | WhiteOak Capital | Research Executive | **for you** | investment research |
| 197 | windflow | AI Engineer | not | AI engineering |
| 198 | Xion Multiventures Pvt Ltd | Trainee Trader & Research Analyst | **for you** | trading and research analyst |
| 199 | YCP India Private Limited (Formerly Known as Auctus Advisors Pvt. Ltd.) | Analyst | **for you** | consulting business analyst |
| 200 | YMS Financial Private Limited | Quant Researcher | **for you** | quant research (finance) |
| 201 | Zanskar Research LLP | Infrastructure Developer | not | low-latency infrastructure engineering |

## Persona `core-software`

Targets: **software engineering roles: backend, frontend, full-stack and SDE; not data science, machine learning, product management, consulting, analyst, finance or core (non-software) engineering roles**

48 demo roles: 28 software engineering roles, 20 that the persona's text excludes.

| # | company | role | label | reason |
|---|---|---|---|---|
| 1 | AiPrise | Software Engineer I | **for you** | software engineering |
| 2 | AiPrise | Software Engineer I, Full Stack (Frontend Focused) | **for you** | software engineering |
| 3 | AiPrise | Software Engineer II | **for you** | software engineering |
| 4 | AiPrise | Software Engineer II, Full Stack (Frontend Focused) | **for you** | software engineering |
| 5 | Amazon | Software Development Engineer I | **for you** | software engineering |
| 6 | Auro Group(www.AuroIM.com) | Back End Developer | **for you** | software engineering |
| 7 | Auro Group(www.AuroIM.com) | Frontend Developer | **for you** | software engineering |
| 8 | Auro Group(www.AuroIM.com) | Full Stack Developer | **for you** | software engineering |
| 9 | Capital One Services India Pvt. Ltd. | Associate (Software Engineer) | **for you** | software engineering |
| 10 | D. E. Shaw India | Technology Developer | **for you** | software engineering |
| 11 | Finarb | Full Stack Developer | **for you** | software engineering |
| 12 | FischerJordan | Software Engineer (SWE)- Frontend Web Developer | **for you** | software engineering |
| 13 | FischerJordan | Software Engineer - Backend Web Developer | **for you** | software engineering |
| 14 | Glean Search Technologies India Private Limited | Software Engineer - India | **for you** | software engineering |
| 15 | Harness | Software Engineer I | **for you** | software engineering |
| 16 | Insurity Solutions India Private Limited | Software Engineer I | **for you** | software engineering |
| 17 | LYSKRAFT Pvt Ltd | SDE - 1 | **for you** | software engineering |
| 18 | MeltPlan Inc | Software Engineer | **for you** | software engineering |
| 19 | Microsoft Corporation | Software Engineer | **for you** | software engineering |
| 20 | Mygate | Software Developer Engineer | **for you** | software engineering |
| 21 | NATWEST | Software Engineer | **for you** | software engineering |
| 22 | Navi Limited | SDE-1 | **for you** | software engineering |
| 23 | Pine Labs | Software Development Engineer | **for you** | software engineering |
| 24 | Porter | Software Development Engineer - 1 | **for you** | software engineering |
| 25 | Route Mobile Limited | SDE 1 | **for you** | software engineering |
| 26 | SQUAREPOINT CAPITAL | Graduate Software Developer | **for you** | software engineering |
| 27 | Warner Music Group | Software Engineer - 1 | **for you** | software engineering |
| 28 | Hakimo AI | Full Stack Software Engineer | **for you** | software engineering |
| 29 | Groww | Associate Product Manager | not | product management |
| 30 | slice | Associate Product Manager | not | product management |
| 31 | slice | Analyst | not | analytics |
| 32 | ESRI | Data Scientist I | not | data science |
| 33 | Swiggy Limited | Data Scientist 1 | not | data science |
| 34 | Goldman Sachs | Quantitative Strategist | not | quant finance |
| 35 | Indus Insights | Associate | not | consulting |
| 36 | EY Parthenon | Associate Consultant | not | strategy consulting |
| 37 | Kalam Labs (legal name: Elixar Systems Pvt Ltd) | Avionics Engineer | not | avionics (hardware) |
| 38 | Ixana | IC Design Engineer II | not | chip design |
| 39 | Airbus India Private Limited | Associate Engineer - Cabin_PG | not | aerospace engineering |
| 40 | Hakimo AI | Applied ML Engineer | not | machine learning |
| 41 | Accordion India | AI_ML Engineer 2 | not | machine learning |
| 42 | Moneyview Ltd | Business Analyst | not | business analyst |
| 43 | Navi Limited | Data Scientist I, Navi | not | data science |
| 44 | Media.Net | Senior Product Analyst | not | product analyst |
| 45 | Plutus Research Private Limited | Quantitative Analyst | not | quant finance |
| 46 | Collins Aerospace | PGET - Mechanical Design | not | mechanical design |
| 47 | Eternal | Machine Learning Scientist | not | machine learning research |
| 48 | Diageo | GBS MANAGEMENT TRAINEE | not | management trainee |
