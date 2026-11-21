import { assertEquals } from "jsr:@std/assert@1";
import { quiet, reminderBody } from "./rules.ts";

const at = (hm: string) => new Date(`2026-11-21T${hm}:00+05:30`);
Deno.test("quiet hours follow the check window, across midnight", () => {
  const w = { check_from: "06:00", check_to: "01:00" };
  assertEquals(quiet(at("05:59"), w), true);
  assertEquals(quiet(at("06:00"), w), false);
  assertEquals(quiet(at("23:30"), w), false);
  assertEquals(quiet(at("00:59"), w), false);
  assertEquals(quiet(at("01:00"), w), true);
  assertEquals(quiet(at("12:00"), { check_from: "09:00", check_to: "21:00" }), false);
  assertEquals(quiet(at("22:00"), { check_from: "09:00", check_to: "21:00" }), true);
  assertEquals(quiet(at("03:00"), {}), true);               // the default window 06:00-01:00
});
Deno.test("a reminder says how long is left when it's sent", () => {
  assertEquals(reminderBody("Groww test at 15:00 · room 304", "2026-11-21T15:00:00+05:30", at("13:00")), "Groww test at 15:00 · room 304 (in 2 h)");
  assertEquals(reminderBody("Groww test at 15:00", "2026-11-21T15:00:00+05:30", at("13:05")), "Groww test at 15:00 (in 1 h 55 m)");
  assertEquals(reminderBody("Groww test at 15:00", "2026-11-21T15:00:00+05:30", at("14:30")), "Groww test at 15:00 (in 30 m)");
});
