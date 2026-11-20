// "Ask Ping": answers questions about YOUR feed and roles with Gemini.
// The Gemini key lives only here. Only your own items/roles/profile are sent
// (never PDFs, never other students' data).
import { cors, json, ownerClient } from "../_shared/owner.ts";

const MODELS = [Deno.env.get("PING_AI_MODEL") || "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"];

function ist(iso?: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-GB", { timeZone: "Asia/Kolkata", weekday: "short", day: "2-digit",
    month: "short", hour: "2-digit", minute: "2-digit" });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  const sb = await ownerClient(req);
  if (!sb) return json({ error: "not allowed" }, 403);
  const key = Deno.env.get("GEMINI_API_KEY");
  if (!key) return json({ error: "GEMINI_API_KEY is not set for this function" }, 500);
  const { question } = await req.json().catch(() => ({ question: "" }));
  if (!question || String(question).length > 500) return json({ error: "ask a question (max 500 characters)" }, 400);

  const [items, roles, profile] = await Promise.all([
    sb.from("items").select("level,category,title,company,due_at,event_at,first_seen")
      .neq("level", "hidden").eq("dismissed", false).order("first_seen", { ascending: false }).limit(150),
    sb.from("roles").select("company,designation,applied,effective_deadline,eligible,ctc,currency,cgpa_cutoff").limit(400),
    sb.from("profile").select("department,degree,cgpa,active_backlogs,interested_companies,not_interested_companies").limit(1),
  ]);
  const feed = (items.data || []).map((i) =>
    `- [${i.level}] ${i.title}${i.due_at ? ` (due ${ist(i.due_at)})` : ""}${i.event_at ? ` (at ${ist(i.event_at)})` : ""}`);
  const roleLines = (roles.data || []).map((r) =>
    `- ${r.company} | ${r.designation} | applied: ${r.applied ? "yes" : "no"} | deadline: ${ist(r.effective_deadline)}` +
    ` | eligible: ${r.eligible === true ? "yes" : r.eligible === false ? "no" : "unknown"} | CTC ${r.ctc ?? "?"} ${r.currency ?? ""}`);
  const prompt = `You are Ping, a placement assistant for one IIT Kharagpur student. Answer ONLY from the data below.
Be short and concrete (dates in IST). If the data doesn't say, say you don't know.
Now: ${ist(new Date().toISOString())} IST.

Profile: ${JSON.stringify(profile.data?.[0] || {})}

Feed (things for this student):
${feed.join("\n") || "(empty)"}

All roles in the companies list:
${roleLines.join("\n") || "(empty)"}

Question: ${question}`;

  for (const model of MODELS) {
    const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": key },
      body: JSON.stringify({ contents: [{ role: "user", parts: [{ text: prompt }] }],
                             generationConfig: { temperature: 0.2, maxOutputTokens: 600 } }),
    });
    if (r.status === 404 || r.status === 400) continue; // model retired: try the next
    if (!r.ok) return json({ error: `Gemini said ${r.status}` }, 502);
    const out = await r.json();
    const answer = out?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text || "").join("") || "";
    return json({ answer: answer.trim() || "I couldn't come up with an answer." });
  }
  return json({ error: "no Gemini model available" }, 502);
});
