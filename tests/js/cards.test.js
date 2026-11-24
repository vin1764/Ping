// The compact card's words (dashboard/cards.js): the deadline in relative words, and titles cleaned to what they add.
const { test } = require("node:test");
const assert = require("node:assert");
const C = require("../../dashboard/cards.js");

const now = Date.parse("2026-11-24T21:35:00+05:30");

test("deadline: relative when close, the date when not, never the weekday twice", () => {
  assert.equal(C.relDeadline("2026-11-24T23:59:00+05:30", now).text, "Today 23:59 · 2 h 24 m left");
  assert.equal(C.relDeadline("2026-11-24T23:59:00+05:30", now).level, "urgent");
  assert.equal(C.relDeadline("2026-11-24T22:00:00+05:30", now).text, "Today 22:00 · 25 m left");
  assert.equal(C.relDeadline("2026-11-25T20:00:00+05:30", now).text, "Tomorrow 20:00");
  assert.equal(C.relDeadline("2026-11-27T14:00:00+05:30", now).text, "Fri 27 Nov 14:00");
  assert.equal(C.relDeadline("2026-11-23T20:00:00+05:30", now).text, "Mon 23 Nov · past due");
  assert.equal(C.relDeadline("2026-11-24T15:00:00+05:30", now).text, "Today 15:00 · past due");
  assert.equal(C.relDeadline("2026-11-24T15:00:00+05:30", now, { event: true }).text, "Today 15:00 · over");
  assert.equal(C.relDeadline(null, now).text, "No deadline given");
});

test("titles: only what the first line doesn't already say", () => {
  assert.equal(C.cleanTitle("[URGENT] : CDC | NOMURA | Additonal Details", "Nomura"), "");
  assert.equal(C.cleanTitle("FJ Campus Recruitment application 2027 FT", "FischerJordan"), "");
  assert.equal(C.cleanTitle("Intellimation.AI | Preference Form", "Intellimation.ai Software"), "");
  assert.equal(C.cleanTitle("Groww | APM Additional Requirement Form", "Groww"), "APM");
  assert.equal(C.cleanTitle("Additional details for Senior Product Analyst", "Media.Net"), "Senior Product Analyst");
  assert.equal(C.cleanTitle("AXON DEVELOPERS | MDS OFFICE MANAGER STRATEGY", "AXON DEVELOPERS"), "MDS Office Manager Strategy");
  assert.equal(C.cleanTitle("Managment Trainee form", "Tolaram Group"), "Management Trainee");
  assert.equal(C.cleanTitle("Test slot booking", "Groww", ["test"]), "Slot booking");
  assert.equal(C.cleanTitle("", "Groww"), "");
});
