import { decide } from "./guard.ts";
const now = new Date("2026-11-21T13:41:00Z");
const run = (id: number, status: string, minsAgo: number) =>
  ({ id, status, created_at: new Date(now.getTime() - minsAgo * 60_000).toISOString() });
Deno.test("starts when the last run was over 50 minutes ago", () => {
  if (!decide([run(1, "completed", 60)], now).start) throw new Error("should start");
});
Deno.test("skips when a run started within 50 minutes", () => {
  if (decide([run(1, "completed", 20)], now).start) throw new Error("should skip");
});
Deno.test("skips when a run is in progress or queued", () => {
  if (decide([run(1, "in_progress", 90)], now).start) throw new Error("in progress");
  if (decide([run(2, "queued", 1)], now).start) throw new Error("queued");
});
Deno.test("ignores the run that is asking (GitHub's own cron)", () => {
  if (!decide([run(7, "in_progress", 0), run(1, "completed", 61)], now, 7).start) throw new Error("own run ignored");
});

// the schedule a student sets (onboarding step f, or "check every 30 minutes" in the chat)
const at = (istHHMM: string) => {            // a time today in IST
  const [h, m] = istHHMM.split(":").map(Number);
  return new Date(Date.UTC(2026, 10, 21, h, m) - 330 * 60_000);
};
const runAt = (id: number, t: Date, minsAgo: number) => ({ id, status: "completed", created_at: new Date(t.getTime() - minsAgo * 60_000).toISOString() });
Deno.test("every 30 minutes: starts 30 min after the last run; hourly would not", () => {
  const t = at("10:11");
  if (!decide([runAt(1, t, 30)], t, undefined, { every_minutes: 30 }).start) throw new Error("30-min schedule");
  if (decide([runAt(1, t, 30)], t, undefined, { every_minutes: 60 }).start) throw new Error("hourly");
});
Deno.test("every 2 hours: skips the hourly tick, starts at 2 h", () => {
  const t = at("12:11");
  if (decide([runAt(1, t, 60)], t, undefined, { every_minutes: 120 }).start) throw new Error("only 1 h");
  if (!decide([runAt(1, t, 120)], t, undefined, { every_minutes: 120 }).start) throw new Error("2 h");
});
Deno.test("hours: nothing outside the window, a window past midnight wraps", () => {
  const s = { from: "08:00", to: "22:00" };
  if (decide([], at("07:41"), undefined, s).start) throw new Error("before 08:00");
  if (!decide([], at("08:11"), undefined, s).start) throw new Error("08:11");
  if (decide([], at("22:11"), undefined, s).start) throw new Error("after 22:00");
  const night = { from: "06:00", to: "01:00" };
  if (!decide([], at("00:41"), undefined, night).start) throw new Error("00:41 is inside 06:00-01:00");
  if (decide([], at("03:11"), undefined, night).start) throw new Error("03:11 is outside");
});
