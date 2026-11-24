# Declutter pass: what left the collapsed cards, and where it went

Only what renders changed; the data, the logic and the dedupe are as they were. Every card now has at most three
lines of text (company + task, the deadline in relative words, the role) and one button row (one primary button, ⋯).
A tap on the card or on ⋯ opens the detail in place. Screenshots at 390 px: `before-*.png` (live, build 239e2cc) and
`after-*.png` (this change), from `node setup/declutter_shots.js before|after <url>`, which also fails if a collapsed
card is taller than 3 lines or still shows a notice number, "posted N times" or a raw "[URGENT]" title.

| page | removed from the collapsed view | where it is now |
|---|---|---|
| Forms | "posted N times: notice 1839, notice 1859, +2 more" | detail: "Posted · first …, last … (N times)" and one Notice button per posting, by date |
| Forms | "deadline moved A → B" line | detail: "Moved"; the card shows a small "extended" chip while it's open |
| Forms | purpose as the task ("Additional requirement") | line 1 says Form / CV submission / Test; detail: "For · Additional requirement" |
| Forms | "Notice" and "Show in chat" buttons | detail (⋯) |
| Forms | the absolute date + "in 5 days" pill | line 2, one relative phrase ("Today 23:59 · 2 h 24 m left", "Tomorrow 20:00", "Mon 23 Nov · past due") |
| Forms | the raw form title ("Intellimation.AI \| Preference Form") | detail: "Title"; line 3 shows a title only if it adds something (cleaned) |
| Forms | group heading "· notice 1815 · 3 forms" | "<cleaned subject> · 3 forms" (no number) |
| Forms | "Past due (not filled)" open with 18 cards | folded: "Past due · 18 ›"; a tap shows the cards |
| Forms | 4-line intro | one line: "Tick a form once you've filled it and its reminders stop. Ping never fills or submits a form." |
| Today | "posted 12:34" on notice rows | gone (the notice's time is in the chat message) |
| Today | "31 others not applied · per a notice (00:02)" | the sheet (chips: Not applied / For you / All) |
| Today | countdown pill on the right, "by 20:00" in the title | line 2: "Today 20:00 · 1 h 55 m left" |
| Today | "via email" pill | the sheet card's detail / the chat message |
| Today sheet | "not applied", "For you / Other", reason, "Apply with" lines, Notice, Show in chat, extra form links | line 3: role · Apply with CV; the rest in the detail (Fit, Status, Your row, Notice, Show in chat) |
| Today sheet | "Open on ERP" + "Form link" + "Notice" + "Show in chat" (4 buttons) | one primary ("Open form", else "Apply on ERP"); the others behind ⋯ |
| Companies | CTC, "For you", "Apply with <CV>", "Not eligible" pills, "Closes Sat 21 Nov 20:00" + pill | one status chip (Shortlisted / Applied / Closed / Not eligible / Eligible) and the next deadline in relative words; CTC, criteria, JD and CV in the role's detail sheet (tap) |
| Chat | kicker ("FORM · in 5 days · via email"), the full sentence title, "Details ▾" footer | line 1 company · task, line 2 relative time, line 3 role or room; full sentence, list, "Via email", "Deadline extended: A → B" and Details in the expanded view |
| Chat | "(notice 1613)" after "Deadline extended: …" | gone |
| Chat | digest lists (up to 8 rows inline) | line 3 names the first 3 companies (+N); "See all N" opens the sheet; the list is in the expanded view |
| Chat | the reply quote on two lines | one line: sender, then the quoted text (ellipsis) |
| All updates | "You applied" tag, due line, company link, Open notice, PDF, mail links, Done (one row of 6–7 links) | the same compact card; all of those in the detail |
| Profile | roll number in full | masked ("22XY•••42"); the edit form shows it in full |
| Profile | CV summaries (a paragraph each) | "What Ping read from it" (tap to open) |
| Profile | seven cards in one list | three groups: You · Checks and alerts · App and account |

Kept as is: the header ("checked 22 min ago · next 22:11"), the Closed / Filled one-line form rows, "Which company is
that?" questions (their choices are the action), the role detail sheet.
