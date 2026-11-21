# Prompts Ping sends to a model

_Generated from the source by `python setup/export_prompts.py`; do not edit by hand. `tests/test_prompts_doc.py` fails when this file is out of date._

Ping sends text to a model in exactly two places. Everything else (reading the ERP, notices, PDFs, eligibility, the feed) is rules, with no model involved.

## 1. Notice reader fallback (deadlines and companies the rules couldn't find)

- **Where it runs:** `ping/ai.py` (`PROMPT`, used by `refine_notice`), called from the hourly run on GitHub Actions
- **When:** Only when the rules find no deadline in a CV / extension / form notice, or no companies in a "Multiple Companies" notice. Rules always go first.
- **Input:** `{ref}`: the notice's own time (IST, ISO format); `{companies}`: up to 300 company names from your companies list; `{text}`: that one notice's text, first 6,000 characters. Never PDFs, never your data.
- **Expected output:** JSON only: `deadlines` (list of `at` ISO time + `text` quoted from the notice) and `companies` (list of `name` + `profiles`). Replies without JSON, or with dates that don't parse, are dropped.
- **Models, in fallback order:** `gemini-flash-latest` → `gemini-flash-lite-latest` → `gemini-2.0-flash`
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

## 2. Ask Ping (the chat on the dashboard)

- **Where it runs:** `supabase/functions/ask-ping/index.ts` (`const prompt`), a Supabase Edge Function; the Gemini key is a Supabase function secret and never reaches the browser
- **When:** Every question typed in the dashboard chat by a signed-in owner or reviewer. If it fails, the page answers with simple rules instead and says so.
- **Input:** `${...}` parts are filled in per question from the caller's own rows (Row Level Security applies: the owner's real data, or the reviewer's anonymised demo). See the template for each part.
- **Expected output:** Plain text, shown as Ping's chat reply. No JSON.
- **Models, in fallback order:** `PING_AI_MODEL` → `gemini-flash-latest` → `gemini-flash-lite-latest` → `gemini-2.0-flash`
- endpoint: Gemini `generateContent` (`GEMINI_API_KEY`); `PING_AI_MODEL` replaces the first model
- generation: `{ temperature: 0.2, maxOutputTokens: 4096 }`
- timeout per model: 45 s; whole answer: 100 s (Supabase stops a function at 150 s); an error, a timeout or an empty reply moves on to the next model

**Prompt, verbatim:**

````text
You are Ping, a placement assistant for one IIT Kharagpur student. Answer ONLY from the data below.
Be short and concrete: dates in IST, money in rupees as written (e.g. 22,00,000 or 22 LPA). For pay questions, list
every component the data gives (fixed / take-home, bonuses, ESOPs, bond) per role.
If the answer isn't in the data, say so in one sentence and mention what the data does show.
Now: ${DAY.format(asOf)}, ${ist(asOf.getTime()).split(", ").pop()} IST. Today is ${DAY.format(asOf)}; tomorrow is ${DAY.format(new Date(asOf.getTime() + 86_400_000))}.
All dates in the data are in ${new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", year: "numeric" }).format(asOf)} unless they say otherwise.

Profile: ${JSON.stringify(profile.data?.[0] || {})}

Feed (things for this student):
${feed.join("\n") || "(empty)"}

All roles in the companies list:
${roleLines.join("\n") || "(empty)"}
${detailLines.length ? `\nPay and bond details for the companies in the question (from the ERP's "more details"):\n${detailLines.join("\n")}\n` : ""}
Question: ${question}
````
