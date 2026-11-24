import { asksToAct, glance, stripRefusal, todayNote, fitPrompt } from "./wording.ts";
const eq = (a: unknown, b: unknown) => { if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`${JSON.stringify(a)} != ${JSON.stringify(b)}`); };

Deno.test("only requests to act get the refusal", () => {
  for (const q of ["apply to groww for me", "withdraw my application to Diageo", "change my CV on the ERP to the Data CV",
                   "fill the Groww additional details form for me", "can you accept the Eternal offer", "please submit it"]) {
    eq([q, asksToAct(q)], [q, true]);
  }
  for (const q of ["anything else?", "what else?", "and?", "ok", "why not?", "same for analyst role?", "any tests today?",
                   "am I eligible to apply for groww?", "when does the form close?", "did I apply to diageo?", "what's due today"]) {
    eq([q, asksToAct(q)], [q, false]);
  }
});

Deno.test("a stray refusal is removed from an answer to a question", () => {
  eq(stripRefusal("Ping is read-only, so I can't apply for you. No other tests today."), "No other tests today.");
  eq(stripRefusal("No other tests today.\nPing is read-only, so I can't do that."), "No other tests today.");
  eq(stripRefusal("No other tests today."), "No other tests today.");
});

Deno.test("times today say over or how long to go", () => {
  const now = new Date("2026-11-21T13:05:00Z"); // 18:35 IST
  eq(todayNote("2026-11-21T09:30:00Z", now), " (earlier today, already over)");   // 15:00 IST
  eq(todayNote("2026-11-21T14:30:00Z", now), " (later today, in 1h 25m)");        // 20:00 IST
  eq(todayNote("2026-11-22T04:30:00Z", now), "");                                 // tomorrow
});

Deno.test("today and this week, counted", () => {
  const now = new Date("2026-11-21T13:05:00Z"); // Sat 18:35 IST
  const g = glance(
    [{ title: "Groww test (Associate Product Manager)", at: "2026-11-21T15:00:00+05:30" },
     { title: "Groww test (Associate Product Manager)", at: "2026-11-21T15:00:00+05:30" },
     { title: "Pine Labs test", at: "2026-11-23T10:00:00+05:30" }],
    [{ company: "ESRI", applied: false, effective_deadline: "2026-11-21T14:30:00Z" },
     { company: "SLB", applied: true, effective_deadline: "2026-11-21T14:30:00Z" },
     { company: "ICICI", applied: false, effective_deadline: "2026-11-21T10:30:00Z" },
     { company: "Pine Labs", applied: false, effective_deadline: "2026-11-22T14:30:00Z" },
     { company: "Next Week", applied: false, effective_deadline: "2026-11-23T14:30:00Z" }], now);
  eq(g.split("\n"), [
    "Tests and events today (1): Groww test (Associate Product Manager) at 15:00 (earlier today, already over)",
    "Application deadlines still open today: 2 roles at 2 companies (1 not applied, 1 applied: ESRI, SLB) close at 20:00 (later today, in 1h 25m)",
    "Application deadlines from now to the end of this week (Sunday; today counts as this week): Sat 21 Nov 20:00: 2 roles at 2 companies (1 not applied, 1 applied: ESRI, SLB); Sun 22 Nov 20:00: 1 role at 1 company (1 not applied, 0 applied: Pine Labs)",
  ]);
});

const assert = (c: boolean) => { if (!c) throw new Error("assertion failed"); };
const assertEquals = eq;
Deno.test("fitPrompt cuts the least needed sections, at line ends, to the limit", () => {
  const feed = Array.from({ length: 40 }, (_, i) => `- feed line ${i} with some words to make it long enough`).join("\n");
  const convo = Array.from({ length: 30 }, (_, i) => `Student: question ${i} asked about something long`).join("\n");
  const blocks = "Close tonight 20:00:\n- Groww — APM";
  const prompt = `INSTRUCTIONS\nFeed:\n${feed}\nLists:\n${blocks}\nConversation:\n${convo}\nQuestion: why?`;
  const out = fitPrompt(prompt, [feed, { text: convo, oldestFirst: true }, blocks], 1500)!;
  const some = fitPrompt(prompt, [feed, { text: convo, oldestFirst: true }, blocks], 2600)!;
  assert(some.length <= 2600 && some.includes("feed line 0") && !some.includes("feed line 39"));
  assert(out.length <= 1500);
  assert(out.includes("INSTRUCTIONS") && out.includes("Question: why?") && out.includes("- Groww — APM"));
  assert(!out.includes("feed line 39"));
  assert(out.includes("question 29"));                                       // the conversation keeps its latest turns
  assertEquals(fitPrompt("x".repeat(3000), [], 1500), null);
  assertEquals(fitPrompt(prompt, [feed], 100_000), prompt);
});
