# Prompts Ping sends to a model

_Generated from the source by `python setup/export_prompts.py`; do not edit by hand. `tests/test_prompts_doc.py` fails when this file is out of date._

Ping sends text to a model in exactly six places. Everything else (reading the ERP, notices, PDFs, eligibility, the feed) is rules, with no model involved.

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
- **Input:** `{targets}`: your "What I'm looking for" text (first 600 characters); `{cvs}`: one summary line per CV you uploaded (prompt 3), or nothing; `{{roles}}`: up to 250 roles, each with its id, company, title, a few role fields and the first 400 characters of its job description (or "none given; judge on the title"). Never your name, roll number, CGPA or mail.
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
{cvs}
For each role below, decide whether it is one of the jobs they want. Judge the work the role actually does (from
the job description when there is one), not just the company. If what they want and their CVs disagree, what they
want wins. Reply with JSON only, one entry per role, in order:
[{{"id": "<role id>", "relevant": true or false, "best_cv": "<label of the CV to apply with, or empty>", "reason": "at most 8 words"}}]

Roles:
{roles}
````

## 3. CV summary (for "Apply with")

- **Where it runs:** `ping/cvs.py` (`SUMMARY_PROMPT`, used by `summarise_new`), called from the hourly run on GitHub Actions
- **When:** Once per CV you upload on the Profile page (up to 3), and again only when you replace that file.
- **Input:** `{text}`: the text of that one PDF, first 12000 characters, read on the server from the private `cvs` bucket. The text is never logged or stored.
- **Expected output:** JSON only: `focus`, `skills`, `experience`, `education`; kept as one line in the profile, with any email or phone number removed. The classifier gets these lines (prompt 2).
- **Models, in fallback order:** `gemini-flash-latest` → `gemini-flash-lite-latest` → `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemma-4-31b-it`
- endpoint: the same OpenAI-compatible `/chat/completions` as the notice reader
- temperature: 0
- timeout per model: 60 s

**Prompt, verbatim:**

````text
Summarise this CV so it can be matched to job roles. Reply with JSON only, at most 300 tokens:
{{"focus": "the kind of roles this CV is written for, in a few words",
  "skills": ["at most 8 skills or tools"],
  "experience": ["at most 4 internships, projects or positions, a few words each"],
  "education": "degree and field, in a few words"}}
Never include the person's name, email, phone number, address, roll number or any other ID.

CV text:
<<<
{text}
>>>
````

## 4. Ask Ping (the chat on the dashboard)

- **Where it runs:** `supabase/functions/ask-ping/index.ts` (`const prompt`), a Supabase Edge Function; the Groq and Gemini keys are Supabase function secrets and never reach the browser
- **When:** Only OPEN questions typed in the dashboard chat (summaries, "why", comparisons, advice, a follow-up with nothing new): every message is routed first (`route()` in `supabase/functions/_shared/answer_rules.js`), and FACT questions (what's due, tests and rooms, shortlists, CTC and its parts, bond, eligibility, which CV, applied, notices, a company's roles, counts), feedback ("X not relevant", "undo"), requests to act and "ok" are answered by rules with no model call. If no model answers, or the reply has a number that isn't in its FACTS, the rules answer instead. Demo sessions: 15 questions per session per hour, 100 per hour for all demo sessions together.
- **Input:** `${...}` parts are filled in per question from the caller's own rows (Row Level Security applies: the owner's real data, or the anonymised demo for a demo session). See the template for each part. Groq gets the same prompt made compact: "All roles in the companies list" becomes only the roles of the companies in the question, the feed its newest 25 lines, and it's sent only if under 16,000 characters.
- **Expected output:** Plain text, shown as Ping's chat reply. No JSON.
- **Models, in fallback order:** `groq/openai/gpt-oss-120b` → `gemini-3.1-flash-lite`
- Groq: OpenAI-compatible `chat/completions` (`supabase/functions/_shared/openai_compat.ts`); key `GROQ_API_KEY` for students and demo visitors, `GROQ_API_KEY_EVALS` for evals (no evals key: evals skip Groq); `PING_GROQ_MODEL` replaces the model; reasoning effort low, at most 1,500 tokens out
- Gemini: `generateContent`; key `GEMINI_API_KEY`, or `GEMINI_API_KEY_EVALS` for evals and Admin checks (requests that prove they hold it with `x-ping-evals`); `PING_CHAT_MODEL` replaces the model
- order: Groq once with 6 s; then gemini-3.1-flash-lite for at most 10 s, once more after 500 ms when it's busy (429, 5xx, timeout); 15 s in all; then the rules answer
- generation (Gemini): `{ temperature: 0, maxOutputTokens: 700 }`
- after the reply: every number, time and amount in it must be in the prompt's FACTS part, or the next in the chain answers, and in the end the rules (logged `model_count_mismatch`)
- logged per answer: which provider and model answered (`model`), every try with its status and time (`tried`)

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
Eligibility questions ("am I eligible for X"): always give the role's CG cut-off and the student's CGPA from Profile
("CG cut-off 7.5, your CGPA 8.0: met"), then anything that can't be checked (department, degree, backlogs).
"What's due" questions (today, tonight, tomorrow, this week): name the companies and roles, with the time, by
copying the role list block for each closing time; a count alone is not an answer. "This week" includes today: if
"Today and this week" shows deadlines, they are due this week.
Only when "Today and this week" and the role lists show nothing for the day asked about, start with "Nothing is
due on <day>". When the answer is simply "no" or
"nothing" (no other test, nothing due), say it short and specific, and add the
next relevant thing if there is one: "No other tests today. Next one is X on Mon 24 Nov, 10:00." Never write a
sentence about what the data does or doesn't contain for such an answer.
Time: times today carry a note in the data, "(earlier today, already over)" or "(later today, in 1h 25m)". Use it:
"was at 15:00 today, so it's over" or "at 20:00 today (in 1h 25m)". Never say "is today at 15:00" once it's past. For "anything else?"-type follow-ups answer with the count: "No, that was the only
test today" or "Two more: ...", then add one line with the most urgent other thing from "Today and this week"
below, with its count and time: "No other tests. 48 applications close at 20:00 today (in 1h 25m), 39 of them not
applied: Ather Energy, Auro Group, Axis Bank, BlackBuck, Diageo +15 more." Never give a count without the names that
"Today and this week" lists after it (the first 5, then "+N more"). "Today and this week" is counted from the data: use its numbers for questions about today, tonight or this
week (a deadline later today IS this week).
Numbers: you may phrase, never compute. Every number, time, count, amount and company name in your answer must be
copied from FACTS below: never add, subtract, count or convert yourself. If FACTS has no number for something,
say you don't have it. An answer with a number that isn't in FACTS is thrown away.
Lists of roles: "Role lists by closing time" below is ready-made. When an answer lists roles that close at one of
those times, copy that time's whole block exactly: its heading (the deadline is said once, there; "8 for you" means
for you and not applied yet), "For you", "Applied" (each with "✓ applied"), then "Others", one "Company — Role" line
each (keep Others unless the question narrows the list). Don't add
reasons, deadlines or groupings per line, and don't merge roles of one company into one line. To narrow a list
("only product ones"), drop lines but keep the format.
Lists (shortlists, tests, rooms, results): never tell the student they are not on a list. If their roll number
wasn't found, say "I couldn't find your roll number in the <company> <list> (posted <time>). Please check the list
yourself." If the file wasn't read reliably, say so and ask them to check it. Say which notice and when it was read.
CVs: the student's CVs are ${cvLabels.length ? cvLabels.map((l: string) => `"${l}"`).join(", ") : "not uploaded yet"}. For "which cv for X" or "what
should I apply to with my <label>", use "apply with" in the role lines and answer "Apply with: <label>" per role
(if no CV fits a role, leave its Apply with line out; never write "no CV fits it best"). Write plain text: no
**bold** or other markdown except "- " list lines, and company names without their bracketed website. ${cvLabels.length ? "" : 'With no CVs uploaded, say "Add your CVs on the Profile page (My CVs)" instead.'}
Roles marked eligible: no are never listed. If eligibility is "unknown" because the Profile has no department or
degree, say once "Add your department and degree on the Profile page to check eligibility". Questions like "which of these are relevant to me", "anything for product roles tonight", "what's
due that's relevant" use the "for you" marks (and the targets text for a narrower ask like "product"); don't
re-judge roles yourself. If no targets are set, list roles normally and mention once that the Profile page's
"What I'm looking for" box makes Ping split them.
Conversation: "Conversation so far" below is this thread, oldest first. A short or elliptical message ("nothing
else?", "and tomorrow?", "what about slice?", "same for analyst role?", "when?", "why not?") continues the previous
turn: work out the full question from the last question and answer, then answer that. Never answer about the literal
words of the follow-up and never quote them back. If a follow-up could mean two things, answer the more likely one in
one line and offer the other in a second line; ask a question back only if neither can be answered. A message that
starts a new topic ("ok. what's due this week?") is a new question: don't carry the old topic into it.
Replies: a "[replying to ...]" line after the question is the message the student replied to; it says which companies
are meant, the question says what is wanted. A statement ("ok", "this one isn't for me", "already did it") is not a
request for data: answer it in one line and never list the status of every company in the quoted message.
Ping is read-only: it can never apply, withdraw, accept or decline offers, fill or submit forms, upload or change a CV,
or change anything on the ERP or anywhere else. ${act
    ? `This message asks Ping to do something: start with "Ping is read-only, so I can't" followed by what was asked,
then add anything useful from the data (deadline, form link).`
    : `This message is a question, not a request to act: do not mention being read-only or what Ping can't do.`}
FACTS start here.
${ruledFacts ? `Ping's own answer from the data (the rules), for: ${routed.resolved || ask}\n${ruledFacts}\n\n` : ""}Now: ${DAY.format(asOf)}, ${ist(asOf.getTime()).split(", ").pop()} IST. Today is ${DAY.format(asOf)}; tomorrow is ${DAY.format(new Date(asOf.getTime() + 86_400_000))}.
All dates in the data are in ${new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", year: "numeric" }).format(asOf)} unless they say otherwise.

Today and this week (counted from the data below):
${atAGlance}

Profile: ${JSON.stringify(prof)}

Role lists by closing time (next 7 days):
${blocks || "(no open deadlines)"}

Feed (things for this student):
${feed.join("\n") || "(empty)"}

All roles in the companies list:
${roleLines.join("\n") || "(empty)"}
${detailLines.length ? `\nDetails for the companies in the question (from the ERP's "more details"):\n${detailLines.join("\n")}\n` : ""}
Your results on shortlists and test room lists in the last 21 days, newest first:
${listLines.join("\n") || "(none)"}
${noticeLines.length ? `\nLatest notices for the companies in the question, newest first:\n${noticeLines.join("\n")}\n` : ""}
FACTS end here.

Conversation so far, oldest first:
${convo || "(this is the first message)"}

Question: ${ask}${replyNote}
````

## 5. Ask Ping: reading the question

- **Where it runs:** `supabase/functions/_shared/understand.js` (`prompt`), called by `supabase/functions/ask-ping/index.ts` before the rules route the question
- **When:** Every chat question that isn't feedback. The answer is never the model's: it only says what the question is about, and the rules fetch and say every fact.
- **Input:** The question, the last 6 turns, every listed company's name, and the roles of the companies in the conversation.
- **Expected output:** One JSON object {company, role, fact, source, is_followup, scope}. Checked against the data: a company or role it doesn't have becomes null, an unknown fact "other", an unknown source "any". What the question left out is added to it for the rules ("what all roles?" -> "what all roles? RISA Labs").
- **Models, in fallback order:** `groq/openai/gpt-oss-120b` → `gemini-3.1-flash-lite`
- Groq `openai/gpt-oss-120b` (reasoning low, at most 700 tokens out), then Gemini `gemini-3.1-flash-lite` with what's left of the cap; keys as for the chat (eval keys for evals)
- cap 3 s: past it, or unreadable, the rules route the question as asked

**Prompt, verbatim:**

````text
You read a student's message to a placement assistant. Reply with ONE JSON object and nothing else:
{"company": string|null, "role": string|null, "fact": one of ${JSON.stringify(FACTS)}, "source": one of ${JSON.stringify(SOURCES)}, "is_followup": true|false, "scope": "one"|"all"}
- company: the company the message is about, written as in the list below; if the message names none but continues the conversation, the company the conversation is about; null if none.
- role: a role of that company from the list below if the message names or means one; else null.
- fact: what is asked (jd = job description, ctc = pay, eligibility, deadline, form, test, shortlist, roles = which roles, cv = which CV to use; other).
- source: where the student wants it looked up (erp, notice, mail, form) if they say so; else any.
- is_followup: the message only makes sense with the earlier messages.
- scope: "all" when the message asks about every role / every company ("all roles", "everything"), else "one".
Never invent a company or role that isn't in the lists.

Companies: ${(companies || []).slice(0, 200).join("; ")}
Roles of the companies in the conversation: ${(roles || []).slice(0, 60).join("; ") || "(none)"}

Conversation, oldest first:
${convo || "(none)"}

Message: ${question}
````

## 6. Ask Ping: wording the reply

- **Where it runs:** `supabase/functions/_shared/understand.js` (`composePrompt`), called by `supabase/functions/ask-ping/index.ts` after the rules answered
- **When:** Every rules answer of 40 characters or more.
- **Input:** The question and the rules' answer (every fact fetched).
- **Expected output:** The answer reworded. Kept only if every date, time, number, company, role, status word and link in it is in the rules' answer and no link or button of it is dropped (`verify`); otherwise the rules' answer is sent as it is.
- **Models, in fallback order:** `groq/openai/gpt-oss-120b` → `gemini-3.1-flash-lite`
- Groq `openai/gpt-oss-120b` (reasoning low, at most 700 tokens out), then Gemini `gemini-3.1-flash-lite` with what's left of the cap; keys as for the chat (eval keys for evals)
- cap 2.5 s: past it, the rules' answer is sent as it is

**Prompt, verbatim:**

````text
Rewrite this answer from a placement assistant so it reads naturally for a hurried student: short, plain, no greeting, no sign-off. Use ONLY what the answer says: do not add, drop or change any company, role, date, time, number, status or link. Keep every markdown link and button exactly as written, e.g. [Open](https://...) or [Associate Product Manager](#ask:...). Keep it at most as long as the answer. Reply with the rewritten answer only.

Student asked: ${question}

Answer:
${answer}
````
