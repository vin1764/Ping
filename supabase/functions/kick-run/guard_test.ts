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
