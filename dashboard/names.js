/* Company names for display. The ERP sometimes puts the company's website in brackets ("Auro Group(www.AuroIM.com)");
 * on screen that part goes and double spaces go. Display only: the raw ERP name stays in the data (links, search and
 * Ask Ping use it). Tested in tests/js/names.test.js. */
(function (root) {
  "use strict";
  const URLISH = /https?:\/\/|www\.|\b[a-z0-9-]+\.(?:com|in|io|ai|co|org|net|tech|app|dev|gg|me)\b/i;
  function cleanName(name) {
    const raw = String(name == null ? "" : name);
    let s = raw, prev;
    do {
      prev = s;
      s = s.replace(/\[([^\]]*)\]\(([^()]*)\)/g, (m, t, u) => (URLISH.test(t + u) ? t : m))   // [text](url)
           .replace(/\s*\(([^()]*)\)/g, (m, inner) => (URLISH.test(inner) ? "" : m));          // (www.x.com)
    } while (s !== prev);
    s = s.replace(/\s{2,}/g, " ").replace(/\s+([,.;:])/g, "$1").trim();
    return s || raw.trim();
  }
  // "Company — Role" rows inside messages: the company part, cleaned the same way
  function cleanRowText(text) {
    const t = String(text == null ? "" : text), i = t.indexOf(" — ");
    return i > 0 ? cleanName(t.slice(0, i)) + t.slice(i) : cleanName(t);
  }
  const api = { cleanName, cleanRowText };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PingNames = api;
})(typeof window !== "undefined" ? window : globalThis);
