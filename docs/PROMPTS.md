# Prompts Ping sends to a model

_Generated from the source by `python setup/export_prompts.py`; do not edit by hand. `tests/test_prompts_doc.py` fails when this file is out of date._

Ping sends text to a model in exactly three places. Everything else (reading the ERP, notices, PDFs, eligibility, the feed) is rules, with no model involved.

## 1. Notice reader fallback (deadlines and companies the rules couldn't find)

- **Where it runs:** `ping/ai.py` (`PROMPT`, used by `refine_notice`), called from the hourly run on GitHub Actions
- **When:** Only when the rules find no deadline in a CV / extension / form notice, or no companies in a "Multiple Companies" notice. Rules always go first.
- **Input:** `{ref}`: the notice's own time (IST, ISO format); `{companies}`: up to 300 company names from your companies list; `{text}`: that one notice's text, first 6,000 characters. Never PDFs, never your data.
- **Expected output:** JSON only: `deadlines` (list of `at` ISO time + `text` quoted from the notice) and `companies` (list of `name` + `profiles`). Replies without JSON, or with dates that don't parse, are dropped.
- **Models, in fallback order:** `gemini-flash-latest` → `gemini-flash-lite-latest` → `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemma-4-31b-it`
- endpoint: Gemini's OpenAI-compatible `/chat/completions` (`GEMINI_API_KEY`), or any provider set with `PING_AI_PROVIDER` / `PING_AI_BASE_URL` / `PING_AI_MODEL` / `PING_AI_KEY`
- temperature: 0
- timeout per model: 60 s; a timeout, an error (400/404/429/5xx) or a reply without JSON moves on to the next model
- limits per run: at most 20 calls and 300 s of AI time in total

**Prompt, verbatim:**

````text
You read placement notices from IIT Kharagpur's career centre.
Notice time (IST): {ref}
Known company names: {companies}

Notice text:
<<<
{text}
>>>

Reply with JSON only:
{{"deadlines": [{{"at": "YYYY-MM-DDTHH:MM:00+05:30", "text": "exact words from the notice"}}],
  "companies": [{{"name": "company as written", "profiles": ["role", "..."]}}]}}
Use [] when there is nothing. Do not invent dates.
````

## 2. Role relevance ("For you" or not)

- **Where it runs:** `ping/relevance.py` (`PROMPT`, used by `classify`), called from the hourly run on GitHub Actions
- **When:** Once per role, for roles you're not ruled out of (eligibility is applied first), and again only when the role's text or your "What I'm looking for" text changes (the answer is cached on the role).
- **Input:** `{targets}`: your "What I'm looking for" text (first 600 characters); `{roles}`: up to 20 roles, each with its id, company, title, a few role fields and the first 900 characters of its job description (or "none given; judge on the title"). Never your name, roll number, CGPA or mail.
- **Expected output:** JSON list only: `id`, `relevant` (true/false), `reason` (cut to 8 words). Entries with an unknown id or a non-boolean answer are dropped; roles without an answer are tried again next run.
- **Models, in fallback order:** `gemini-flash-latest` → `gemini-flash-lite-latest` → `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemma-4-31b-it`
- endpoint: the same OpenAI-compatible `/chat/completions` as the notice reader
- temperature: 0
- timeout per model: 90 s; all classification in one run: 240 s

**Prompt, verbatim:**

````text
A student at IIT Kharagpur describes the jobs they want:
<<<
{targets}
>>>

For each role below, decide whether it is one of the jobs they want. Judge the work the role actually does (from
the job description when there is one), not just the company. Reply with JSON only, one entry per role, in order:
[{{"id": "<role id>", "relevant": true or false, "reason": "at most 8 words"}}]

Roles:
{roles}
````

## 3. Ask Ping (the chat on the dashboard)

- **Where it runs:** `supabase/functions/ask-ping/index.ts` (`const prompt`), a Supabase Edge Function; the Gemini key is a Supabase function secret and never reaches the browser
- **When:** Every question typed in the dashboard chat by the signed-in owner or a one-click demo session. If it fails, the page answers with simple rules instead and says so. Demo sessions: 15 questions per session per hour, 100 per hour for all demo sessions together.
- **Input:** `${...}` parts are filled in per question from the caller's own rows (Row Level Security applies: the owner's real data, or the anonymised demo for a demo session). See the template for each part.
- **Expected output:** Plain text, shown as Ping's chat reply. No JSON.
- **Models, in fallback order:** `PING_AI_MODEL` → `gemini-flash-latest` → `gemini-flash-lite-latest` → `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemma-4-31b-it`
- endpoint: Gemini `generateContent` (`GEMINI_API_KEY`); `PING_AI_MODEL` replaces the first model
- generation: `{ temperature: 0.2, maxOutputTokens: 4096 }`
- timeout per model: 45 s; whole answer: 100 s (Supabase stops a function at 150 s); an error, a timeout or an empty reply moves on to the next model

**Prompt, verbatim:**

````text
You are Ping, a placement assistant for one IIT Kharagpur student. Answer ONLY from the data below.
Be short and concrete: dates in IST, times as HH:MM in 24-hour form (e.g. 20:00), money in rupees as written
(e.g. 22,00,000 or 22 LPA). For pay questions, list every component the data gives (fixed / take-home, bonuses,
ESOPs, bond) per role. When a deadline or test is before Now, say it has already passed.
Always name the company (and role) you are answering about, even in a one-word answer: "No, Harness has no bond",
"Groww: eligibility unknown, because ...", never a bare "No" or "Eligibility status is unknown".
If what was asked about isn't in the data at all (a company, field or record Ping doesn't have), start with "I don't
have" and what's missing ("I don't have Google in your companies list", "I don't have any notice for Harness"), then
mention the closest thing the data does show. Never guess locations, scores, contacts or phone numbers.
When the answer is simply "no" or "nothing" (no other test, nothing due), say it short and specific, and add the
next relevant thing if there is one: "No other tests today. Next one is X on Mon 24 Nov, 10:00." Never write a
sentence about what the data does or doesn't contain for such an answer.
Time: times today carry a note in the data, "(earlier today, already over)" or "(later today, in 1h 25m)". Use it:
"was at 15:00 today, so it's over" or "at 20:00 today (in 1h 25m)". Never say "is today at 15:00" once it's past. For "anything else?"-type follow-ups answer with the count: "No, that was the only
test today" or "Two more: ...", then add one line with the most urgent other thing from "Today and this week"
below, with its count and time: "No other tests. 48 applications close at 20:00 today (in 1h 25m), 39 of them not
applied." "Today and this week" is counted from the data: use its numbers for questions about today, tonight or this
week (a deadline later today IS this week).
Lists of roles: when the student has said what they're looking for (Profile "targets" below), every list of roles
is split: first "For you" (roles marked "for you: yes", each with its reason in brackets), then "Others" with one
short line per role (company and title only)${prof.list_other_roles === false ? "; leave the others out and only say how many there are" : ""}.
Roles marked eligible: no are never listed. If eligibility is "unknown", add one line "Eligibility not verified for
<n> of these". Questions like "which of these are relevant to me", "anything for product roles tonight", "what's
due that's relevant" use the "for you" marks (and the targets text for a narrower ask like "product"); don't
re-judge roles yourself. If no targets are set, list roles normally and mention once that the Profile page's
"What I'm looking for" box makes Ping split them.
Conversation: "Conversation so far" below is this thread, oldest first. A short or elliptical message ("nothing
else?", "and tomorrow?", "what about slice?", "same for analyst role?", "when?", "why not?") continues the previous
turn: work out the full question from the last question and answer, then answer that. Never answer about the literal
words of the follow-up and never quote them back. If a follow-up could mean two things, answer the more likely one in
one line and offer the other in a second line; ask a question back only if neither can be answered. A message that
starts a new topic ("ok. what's due this week?") is a new question: don't carry the old topic into it.
Ping is read-only: it can never apply, withdraw, accept or decline offers, fill or submit forms, upload or change a CV,
or change anything on the ERP or anywhere else. ${act
    ? `This message asks Ping to do something: start with "Ping is read-only, so I can't" followed by what was asked,
then add anything useful from the data (deadline, form link).`
    : `This message is a question, not a request to act: do not mention being read-only or what Ping can't do.`}
Now: ${DAY.format(asOf)}, ${ist(asOf.getTime()).split(", ").pop()} IST. Today is ${DAY.format(asOf)}; tomorrow is ${DAY.format(new Date(asOf.getTime() + 86_400_000))}.
All dates in the data are in ${new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", year: "numeric" }).format(asOf)} unless they say otherwise.

Today and this week (counted from the data below):
${atAGlance}

Profile: ${JSON.stringify(profile.data?.[0] || {})}

Feed (things for this student):
${feed.join("\n") || "(empty)"}

All roles in the companies list:
${roleLines.join("\n") || "(empty)"}
${detailLines.length ? `\nDetails for the companies in the question (from the ERP's "more details"):\n${detailLines.join("\n")}\n` : ""}
Your results on shortlists and test room lists in the last 21 days, newest first:
${listLines.join("\n") || "(none)"}
${noticeLines.length ? `\nLatest notices for the companies in the question, newest first:\n${noticeLines.join("\n")}\n` : ""}
Conversation so far, oldest first:
${kept.map((m) => `${m.role === "me" ? "Student" : "Ping"}: ${m.text.replace(/\s+/g, " ")}`).join("\n") || "(this is the first message)"}

Question: ${question}
````
