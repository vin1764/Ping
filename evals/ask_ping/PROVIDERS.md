# Providers on the live keys

Run Tue 24 Nov 15:32 UTC: 20 open-ended questions as a demo visitor (anonymised demo data, live keys), chain Groq -> Gemini flash-lite -> rules. A try succeeds when the provider answered (HTTP 200 with text); latency is that try's own time.

| provider | tried | answered | success | median latency |
|---|---|---|---|---|
| groq | 19 | 8 | 42% | 1.0 s |
| gemini flash-lite | 23 | 1 | 4% | 4.5 s |
| rules (fallback or FACT) | - | 12 | - | - |

Answered by: rules 12, groq 7, gemini flash-lite 1

| question | answered by | seconds | tries | answer (start) |
|---|---|---|---|---|
| why should I prioritise the Groww APM role? | groq | 9.4 | groq/openai/gpt-oss-120b:200:700ms | Groww – Associate Product Manager: - Base Salary: 2,000,000 ₹ - Variable: 200,000 ₹ - Joining Bonus: 200,000 ₹ |
| compare the Navi and slice roles for me | groq | 8.2 | groq/openai/gpt-oss-120b:200:1297ms | Navi (Associate Manager – AI Strategy & Operations, Bangalore): - Deadline: Sun 1 Nov 16:00 (already passed) - |
| which of tonight's roles fit a product person best and why? | rules | 8.9 | groq/openai/gpt-oss-120b:429:39ms, gemini-3.1-flash-lite:503:970ms, gemini-3.1-flash-lite:503:575ms | Close tonight 20:00 (in 2h 28m), Sat 21 Nov — 8 for you, 9 applied: For you: - Auro Group — Data Analyst (appl |
| explain what the Accordion data role involves | rules | 6.2 | groq/openai/gpt-oss-120b:429:45ms, gemini-3.1-flash-lite:503:495ms, gemini-3.1-flash-lite:503:297ms | No open deadline for Accordion India in the ERP data (last checked Sat 21 Nov 17:32). Accordion India (Data &  |
| should I apply to Axis Bank BIU? | groq | 6.7 | groq/openai/gpt-oss-120b:200:1242ms | Axis Bank — BIU (Business Intelligence Unit):  - CG cut‑off 6, your CGPA ? : cannot check (profile lacks CGPA/ |
| give me a plan for today's deadlines | rules | 9.9 | groq/openai/gpt-oss-120b:429:109ms, gemini-3.1-flash-lite:503:3579ms, gemini-3.1-flash-lite:503:2152ms | I don't have Plan in your ERP data: no role on the companies list and no notice from it (last checked Sat 21 N |
| what's the difference between the IDFC FIRST Bank roles? | rules | 8.6 | groq/openai/gpt-oss-120b:429:42ms, gemini-3.1-flash-lite:503:1571ms, gemini-3.1-flash-lite:503:1679ms | No open deadline for IDFC FIRST Bank in the ERP data (last checked Sat 21 Nov 17:32). IDFC FIRST Bank (Associa |
| tips to prepare for the Groww test | groq | 6.8 | groq/openai/gpt-oss-120b:200:919ms | I don't have any tips for preparing for the Groww test in the data. |
| is the BlackBuck leadership program worth it? | rules | 13.7 | groq/openai/gpt-oss-120b:429:83ms, gemini-3.1-flash-lite:503:5852ms, gemini-3.1-flash-lite:503:391ms | BlackBuck: open deadlines (last checked Sat 21 Nov 17:32): - Associate Manager BlackBuck Leadership Program: a |
| summarise this week for me in three lines | rules | 3.8 | - | I don't have Lines in your ERP data: no role on the companies list and no notice from it (last checked not yet |
| which role closing tonight pays best, and why would I pick it? | groq | 6.8 | groq/openai/gpt-oss-120b:200:2142ms | I don't have any pay details for the roles closing tonight.  Close tonight 20:00 (in 2h 28m), Sat 21 Nov — 8 f |
| what do you think about Cars24's roles for a data person? | rules | 14.5 | groq/openai/gpt-oss-120b:429:110ms, gemini-3.1-flash-lite:503:3492ms, gemini-3.1-flash-lite:TimeoutError:6009ms | No open deadline for Cars24 in the ERP data (last checked Sat 21 Nov 17:32). Cars24 (Data Science): closed Tue |
| help me decide between Eternal and Porter | rules | 14.5 | groq/openai/gpt-oss-120b:200:1164ms, gemini-3.1-flash-lite:503:913ms, gemini-3.1-flash-lite:503:3351ms | No open deadline for Eternal in the ERP data (last checked Sat 21 Nov 17:32). Eternal (Assistant Program Manag |
| what should I do first tonight? | gemini flash-lite | 10.9 | groq/openai/gpt-oss-120b:429:37ms, gemini-3.1-flash-lite:200:4514ms | Apply to the 8 roles for you that close at 20:00 tonight (in 2h 28m):  Close tonight 20:00 (in 2h 28m), Sat 21 |
| why is Auro Group a fit for me? | rules | 9.5 | groq/openai/gpt-oss-120b:429:41ms, gemini-3.1-flash-lite:503:1771ms, gemini-3.1-flash-lite:503:299ms | Auro Group: open deadlines (last checked Sat 21 Nov 17:32): - Data Analyst, AI/ML Software Engineer, Full Stac |
| compare Moneyview's two roles | groq | 5.7 | groq/openai/gpt-oss-120b:200:645ms | Moneyview Ltd — Business Analyst - Base Salary: 1,600,000 INR - Variable: 200,000 INR - Retention Bonus: 700,0 |
| explain the Waterfly management consultant role | rules | 7.4 | groq/openai/gpt-oss-120b:429:42ms, gemini-3.1-flash-lite:503:1374ms, gemini-3.1-flash-lite:503:1003ms | Waterfly Technologies: open deadlines (last checked Sat 21 Nov 17:32): - Graduate Engineer 2, Growth and Strat |
| how should I prepare for HPCL's CV submission? | rules | 7.4 | groq/openai/gpt-oss-120b:429:46ms, gemini-3.1-flash-lite:503:760ms, gemini-3.1-flash-lite:503:1581ms | No open deadline for Hpcl in the ERP data (last checked Sat 21 Nov 17:32). Last Hpcl notice: "CV Submission",  |
| recommend three roles for me this week | groq | 5.0 | groq/openai/gpt-oss-120b:200:472ms | - Auro Group — Data Analyst (apply with Analytics & Finance CV) - Axis Bank — BIU (Business Intelligence Unit) |
| what are the pros and cons of the Arihant Capital roles? | rules | 7.1 | groq/openai/gpt-oss-120b:429:41ms, gemini-3.1-flash-lite:503:726ms, gemini-3.1-flash-lite:503:1610ms | No open deadline for Arihant Capital Markets in the ERP data (last checked Sat 21 Nov 17:32). Arihant Capital  |
