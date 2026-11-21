import { asksToAct, stripRefusal, todayNote } from "./wording.ts";
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
