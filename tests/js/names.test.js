const test = require("node:test");
const assert = require("node:assert");
const { cleanName, cleanRowText, displayName } = require("../../dashboard/names.js");

test("a website in brackets is dropped from the display name", () => {
  assert.strictEqual(cleanName("Auro Group(www.AuroIM.com)"), "Auro Group");
  assert.strictEqual(cleanName("Auro Group([www.AuroIM.com](https://www.AuroIM.com))"), "Auro Group");
  assert.strictEqual(cleanName("Acme Labs (https://acme.io/careers)"), "Acme Labs");
  assert.strictEqual(cleanName("Zeta (zeta.tech)"), "Zeta");
});

test("other brackets, spacing and empty names", () => {
  assert.strictEqual(cleanName("Axis Bank  Ltd"), "Axis Bank");   // never "Ltd" / "Private Limited" on screen
  assert.strictEqual(cleanName("Tata Steel (Jamshedpur)"), "Tata Steel (Jamshedpur)");
  assert.strictEqual(cleanName("BIU (Business Intelligence Unit)"), "BIU (Business Intelligence Unit)");
  assert.strictEqual(cleanName("  Flipspaces Technology Labs Pvt. Ltd. "), "Flipspaces Technology Labs");
  assert.strictEqual(cleanName("(www.only.com)"), "(www.only.com)");   // nothing left: keep the raw name
  assert.strictEqual(cleanName(null), "");
});

test("rows in messages: only the company part changes", () => {
  assert.strictEqual(cleanRowText("Auro Group(www.AuroIM.com) — Data Analyst (www.example.com)"),
                     "Auro Group — Data Analyst (www.example.com)");
  assert.strictEqual(cleanRowText("Axis Bank — BIU (Business Intelligence Unit)"), "Axis Bank — BIU (Business Intelligence Unit)");
});

test("shouty names on screen: title case for several words, one word as written", () => {
  assert.strictEqual(displayName("FUTURES FIRST"), "Futures First");
  assert.strictEqual(displayName("TATA AIG"), "Tata AIG");
  assert.strictEqual(displayName("AIRAMATRIX"), "AIRAMATRIX");
  assert.strictEqual(displayName("Auro Group(www.AuroIM.com)"), "Auro Group");
});
