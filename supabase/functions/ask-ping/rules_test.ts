// The rules answers load and run inside the function's runtime (the same file the dashboard uses).
import "../_shared/answer_rules.js";
const Rules = (globalThis as any).PingRules;

Deno.test("rules answers load in Deno and answer about the company asked", () => {
  const a = Rules.answer("msft cv deadline", {
    now: "2026-11-21T17:30:00+05:30", lastChecked: "2026-11-21T17:11:00+05:30",
    roles: [{ id: "r", company: "Microsoft Corporation", designation: "Software Engineer", applied: false, deadline: "2026-11-08T16:00:00+05:30" }],
    items: [], notices: [{ company: "Microsoft", subject: "PPO", notice_time: "2026-11-11T17:59:00+05:30" }],
  });
  if (!a.text.startsWith("No open deadline for Microsoft in the ERP data (last checked Sat 21 Nov 17:11).")) throw new Error(a.text);
  if (!a.text.includes('Last Microsoft notice: "PPO", Wed 11 Nov 17:59.')) throw new Error(a.text);
});
