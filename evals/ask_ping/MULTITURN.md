# Multi-turn and re-check evals (page)

Run 2026-11-22T09:09:36.480Z on https://vin1764.github.io/ping-dashboard/, demo session. 14/14 passed (7 conversations, model on and off).

A re-check in the demo answers from the snapshot (the demo can't log in to the ERP) and says so; for the owner it is a live, read-only fetch of that company's notices and files.

| case | model | result | turns |
|---|---|---|---|
| M1 | on | pass | "check firstclub" → page: No open deadline for FirstClub in the ERP data (last checked Sat 21 Nov 18:04). FirstClub <br>"check again" → recheck: Demo: Ping can't log in to the ERP here, so this is the snapshot's reading of FirstClub (1 |
| M2 | on | pass | "check firstclub" → page: No open deadline for FirstClub in the ERP data (last checked Sat 21 Nov 18:04). FirstClub <br>"check erp for latest updates, don't answer on old data" → recheck: Demo: Ping can't log in to the ERP here, so this is the snapshot's reading of FirstClub (1 |
| M3 | on | pass | "firstclub shortlist?" → page: No FirstClub shortlist or result that names you or leaves you out in the data.<br>"I got a call, I think I'm there" → recheck: Demo: Ping can't log in to the ERP here, so this is the snapshot's reading of FirstClub (1 |
| M4 | on | pass | "what's due tonight" → page: Close tonight 20:00 (in 1h 55m), Sat 21 Nov — 8 for you, 9 applied: For you: Auro Group — <br>"and groww?" → page: No open deadline for Groww in the ERP data (last checked Sat 21 Nov 18:04). Groww (Associa |
| M5 | on | pass | "groww ctc" → page: Groww (Associate Product Manager): CTC 32,00,000 INR: Bonds: No; Base Salary: 20,00,000; B<br>"ok what's due tonight" → page: Close tonight 20:00 (in 1h 55m), Sat 21 Nov — 8 for you, 9 applied: For you: Auro Group —  |
| R1 | on | pass | "am I on the firstclub shortlist" → page: No FirstClub shortlist or result that names you or leaves you out in the data.<br>"are you sure? that's wrong" → recheck: Demo: Ping can't log in to the ERP here, so this is the snapshot's reading of FirstClub (1 |
| R2 | on | pass | "groww ctc" → page: Groww (Associate Product Manager): CTC 32,00,000 INR: Bonds: No; Base Salary: 20,00,000; B<br>"recheck firstclub" → recheck: Demo: Ping can't log in to the ERP here, so this is the snapshot's reading of FirstClub (1 |
| M1 | off | pass | "check firstclub" → page: No open deadline for FirstClub in the ERP data (last checked Sat 21 Nov 18:04). FirstClub <br>"check again" → recheck: Demo: Ping can't log in to the ERP here, so this is the snapshot's reading of FirstClub (1 |
| M2 | off | pass | "check firstclub" → page: No open deadline for FirstClub in the ERP data (last checked Sat 21 Nov 18:04). FirstClub <br>"check erp for latest updates, don't answer on old data" → recheck: Demo: Ping can't log in to the ERP here, so this is the snapshot's reading of FirstClub (1 |
| M3 | off | pass | "firstclub shortlist?" → page: No FirstClub shortlist or result that names you or leaves you out in the data.<br>"I got a call, I think I'm there" → recheck: Demo: Ping can't log in to the ERP here, so this is the snapshot's reading of FirstClub (1 |
| M4 | off | pass | "what's due tonight" → page: Close tonight 20:00 (in 1h 55m), Sat 21 Nov — 8 for you, 9 applied: For you: Auro Group — <br>"and groww?" → page: No open deadline for Groww in the ERP data (last checked Sat 21 Nov 18:04). Groww (Associa |
| M5 | off | pass | "groww ctc" → page: Groww (Associate Product Manager): CTC 32,00,000 INR: Bonds: No; Base Salary: 20,00,000; B<br>"ok what's due tonight" → page: Close tonight 20:00 (in 1h 55m), Sat 21 Nov — 8 for you, 9 applied: For you: Auro Group —  |
| R1 | off | pass | "am I on the firstclub shortlist" → page: No FirstClub shortlist or result that names you or leaves you out in the data.<br>"are you sure? that's wrong" → recheck: Demo: Ping can't log in to the ERP here, so this is the snapshot's reading of FirstClub (1 |
| R2 | off | pass | "groww ctc" → page: Groww (Associate Product Manager): CTC 32,00,000 INR: Bonds: No; Base Salary: 20,00,000; B<br>"recheck firstclub" → recheck: Demo: Ping can't log in to the ERP here, so this is the snapshot's reading of FirstClub (1 |
