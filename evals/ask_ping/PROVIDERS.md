# Providers on the live keys

Run Tue 24 Nov 15:23 UTC: 20 open-ended questions as a demo visitor (anonymised demo data, live keys), chain Groq -> Gemini flash-lite -> rules. A try succeeds when the provider answered (HTTP 200 with text); latency is that try's own time.

| provider | tried | answered | success | median latency |
|---|---|---|---|---|
| groq | 17 | 0 | 0% | n/a |
| gemini flash-lite | 28 | 0 | 0% | n/a |
| rules (fallback or FACT) | - | 20 | - | - |

Answered by: rules 20

| question | answered by | seconds | tries | answer (start) |
|---|---|---|---|---|
| why should I prioritise the Groww APM role? | rules | 12.2 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:503:2218ms, gemini-3.1-flash-lite:503:1907ms | No open deadline for Groww in the ERP data (last checked Sat 21 Nov 17:32). Groww (Associate Product Manager): |
| compare the Navi and slice roles for me | rules | 15.1 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:503:1204ms, gemini-3.1-flash-lite:TimeoutError:8295ms | No open deadline for Navi in the ERP data (last checked Sat 21 Nov 17:32). Navi (Data Scientist I, Navi): clos |
| which of tonight's roles fit a product person best and why? | rules | 15.0 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:TimeoutError:10006ms | Close tonight 20:00 (in 2h 28m), Sat 21 Nov — 8 for you, 9 applied: For you: - Auro Group — Data Analyst (appl |
| explain what the Accordion data role involves | rules | 14.1 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:503:2573ms, gemini-3.1-flash-lite:TimeoutError:6927ms | No open deadline for Accordion India in the ERP data (last checked Sat 21 Nov 17:32). Accordion India (Data &  |
| should I apply to Axis Bank BIU? | rules | 14.7 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:TimeoutError:10001ms | Axis Bank: open deadlines (last checked Sat 21 Nov 17:32): - BIU (Business Intelligence Unit): application by  |
| give me a plan for today's deadlines | rules | 3.4 | - | I don't have Plan in your ERP data: no role on the companies list and no notice from it (last checked Sat 21 N |
| what's the difference between the IDFC FIRST Bank roles? | rules | 14.0 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:TimeoutError:10008ms | No open deadline for IDFC FIRST Bank in the ERP data (last checked Sat 21 Nov 17:32). IDFC FIRST Bank (Associa |
| tips to prepare for the Groww test | rules | 20.0 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:TimeoutError:10001ms | - Groww test (Associate Product Manager) Sat 21 Nov 15:00. (earlier today, over)  (Gemini busy: answered from  |
| is the BlackBuck leadership program worth it? | rules | 7.7 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:503:816ms, gemini-3.1-flash-lite:503:1209ms | BlackBuck: open deadlines (last checked Sat 21 Nov 17:32): - Associate Manager BlackBuck Leadership Program: a |
| summarise this week for me in three lines | rules | 3.1 | - | I don't have Lines in your ERP data: no role on the companies list and no notice from it (last checked not yet |
| which role closing tonight pays best, and why would I pick it? | rules | 9.6 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:503:4622ms, gemini-3.1-flash-lite:503:1356ms | I don't have Pays Pick in your ERP data: no role on the companies list and no notice from it (last checked Sat |
| what do you think about Cars24's roles for a data person? | rules | 2.8 | - | I can: read the ERP's companies list, notices and attached lists (I keep only your own row and the table headi |
| help me decide between Eternal and Porter | rules | 11.1 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:503:3395ms, gemini-3.1-flash-lite:503:1164ms | No open deadline for Eternal in the ERP data (last checked Sat 21 Nov 17:32). Eternal (Assistant Program Manag |
| what should I do first tonight? | rules | 5.8 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:503:996ms, gemini-3.1-flash-lite:503:1082ms | Close tonight 20:00 (in 2h 28m), Sat 21 Nov — 8 for you, 9 applied: For you: - Auro Group — Data Analyst (appl |
| why is Auro Group a fit for me? | rules | 10.6 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:503:4708ms, gemini-3.1-flash-lite:503:1689ms | Auro Group: open deadlines (last checked Sat 21 Nov 17:32): - Data Analyst, AI/ML Software Engineer, Full Stac |
| compare Moneyview's two roles | rules | 7.4 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:503:1387ms, gemini-3.1-flash-lite:503:2168ms | No open deadline for Moneyview in the ERP data (last checked Sat 21 Nov 17:32). Moneyview (Business Analyst):  |
| explain the Waterfly management consultant role | rules | 7.1 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:503:2486ms, gemini-3.1-flash-lite:503:690ms | Waterfly Technologies: open deadlines (last checked Sat 21 Nov 17:32): - Graduate Engineer 2, Growth and Strat |
| how should I prepare for HPCL's CV submission? | rules | 13.6 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:TimeoutError:10001ms | No open deadline for Hpcl in the ERP data (last checked Sat 21 Nov 17:32). Last Hpcl notice: "CV Submission",  |
| recommend three roles for me this week | rules | 7.7 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:503:681ms, gemini-3.1-flash-lite:503:1877ms | Close tonight 20:00 (in 2h 28m), Sat 21 Nov — 8 for you, 9 applied: For you: - Auro Group — Data Analyst (appl |
| what are the pros and cons of the Arihant Capital roles? | rules | 13.9 | groq/openai/gpt-oss-120b:skipped(prompt too big), gemini-3.1-flash-lite:TimeoutError:10001ms | No open deadline for Arihant Capital Markets in the ERP data (last checked Sat 21 Nov 17:32). Arihant Capital  |
