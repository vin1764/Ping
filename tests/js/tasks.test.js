// A mail-only assignment with a 3-day deadline (the 24 Nov BlueStone case, made up): in To do with its type and link,
// in Today from 48 h before, and (tests/test_tasks.py) in the chat as a card with its link, pushed.
const { test } = require("node:test");
const assert = require("node:assert");
const F = require("../../dashboard/forms.js");
const T = require("../../dashboard/today.js");

const DUE = "2026-11-27T23:59:00+05:30";
const LINK = "https://drive.example.com/bluestone-assignment-brief";
const item = { id: "mail:m-bluestone", category: "todo", company: "BLUESTONE", level: "always", due_at: DUE,
  title: "BLUESTONE: submit the assignment by Fri 27 Nov 23:59.",
  details: { via: "email", source: "mail from BLUESTONE", todo: { action: "submit", task: "assignment", due: DUE, link: LINK } } };
const at = (h) => Date.parse(DUE) - h * 3600000;

test("To do: an assignment is a row with its type, deadline and the brief as its button", () => {
  const rows = F.tasks({ items: [item], roles: [], now: at(72) });
  assert.strictEqual(rows.length, 1);
  const r = rows[0];
  assert.deepStrictEqual([r.type, r.link, r.linkLabel, r.key, r.at], ["Assignment", LINK, "Open brief", "item:mail:m-bluestone", Date.parse(DUE)]);
  assert.strictEqual(F.taskState(r, new Map(), at(72)), "open");
  assert.strictEqual(F.taskState(r, new Map([["item:mail:m-bluestone", { filled: true }]]), at(72)), "done");
  assert.strictEqual(F.taskState(r, new Map([["item:mail:m-bluestone", { not_for_me: true }]]), at(72)), "notForMe");
  assert.strictEqual(F.taskState(r, new Map(), at(-1)), "past");
});

test("To do: forms stay forms; tests, interviews and applications for you are rows too", () => {
  const form = { ...item, id: "f", details: { todo: { action: "fill_form", due: DUE, link: "https://forms.gle/x" } } };
  const testIt = { id: "t", category: "test", company: "Groww", level: "always", event_at: DUE, title: "Groww test", details: { kind: "test" } };
  const roles = [{ id: "r1", company: "Zeta Global", designation: "Analyst", applied: false, effective_deadline: DUE },
                 { id: "r2", company: "Zeta Global", designation: "SDE", applied: false, effective_deadline: DUE },
                 { id: "r3", company: "Old Co", designation: "X", applied: true, effective_deadline: DUE }];
  const rows = F.tasks({ items: [form, testIt], roles, now: at(72) });
  assert.deepStrictEqual(rows.map((r) => r.type).sort(), ["Application (2 roles)", "Test"]);
});

test("Today: due within the next 48 hours, not before", () => {
  const rowsAt = (h) => T.build({ items: [item], now: at(h) }).rows.filter((r) => r.kind === "todo");
  assert.strictEqual(rowsAt(72).length, 0);                       // 3 days ahead: not yet on Today
  assert.strictEqual(rowsAt(47).length, 1);                       // 47 h ahead: on Today
  assert.strictEqual(rowsAt(47)[0].title, "BLUESTONE");
});
