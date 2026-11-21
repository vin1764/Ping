// Quiet hours and the reminder's wording, without network code (tested in rules_test.ts).

const HM = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const mins = (hm: string) => { const [h, m] = hm.split(":").map(Number); return (h % 24) * 60 + (m || 0); };

// Inside the student's check window (IST; it may run past midnight, e.g. 06:00-01:00) notifications may go out;
// outside it is quiet.
export function quiet(now: Date, w: { check_from?: string | null; check_to?: string | null }): boolean {
  const from = mins(w.check_from || "06:00"), to = mins(w.check_to || "01:00"), t = mins(HM.format(now));
  if (from === to) return false;
  return from < to ? !(t >= from && t < to) : !(t >= from || t < to);
}

// "Groww test at 15:00 · room 304" + " (in 1 h 55 m)" worked out when it's sent
export function reminderBody(body: string | null, eventAt: string | null, now: Date): string {
  if (!eventAt) return body || "";
  const left = Math.round((new Date(eventAt).getTime() - now.getTime()) / 60000);
  if (left <= 0) return body || "";
  const h = Math.floor(left / 60), m = left % 60;
  return `${body || ""} (in ${h ? `${h} h` : ""}${h && m ? " " : ""}${m ? `${m} m` : ""})`.trim();
}
