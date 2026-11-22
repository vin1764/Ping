"""Builds setup.html (the "Set up Ping for yourself" page next to the dashboard) from docs/SETUP.md, at every
deploy, so the page and the doc can't drift (tests/test_setup_page.py checks both).

    python setup/build_setup_page.py _site/setup.html

Only the Markdown that docs/SETUP.md uses: headings, paragraphs, bullet and numbered lists (with indented code
blocks and tables inside them), tables, `code`, **bold** and [links](url). Everything is HTML-escaped.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "SETUP.md"

# The public source repo: the one place it's set. Empty until there is one; then the page says
# "Source repo: available on request" and links nowhere.
SOURCE_REPO_URL = ""
PLACEHOLDER = "SOURCE_REPO_URL"


def _inline(text: str) -> str:
    out, pos = [], 0
    for m in re.finditer(r"`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)\s]+)\)", text):
        out.append(html.escape(text[pos:m.start()], quote=False))
        if m.group(1) is not None:
            out.append(f"<code>{html.escape(m.group(1), quote=False)}</code>")
        elif m.group(2) is not None:
            out.append(f"<strong>{_inline(m.group(2))}</strong>")
        else:
            out.append(f'<a href="{html.escape(m.group(4))}" rel="noopener">{html.escape(m.group(3), quote=False)}</a>')
        pos = m.end()
    out.append(html.escape(text[pos:], quote=False))
    return "".join(out)


def _source_line(line: str) -> str:
    if PLACEHOLDER not in line:
        return line
    if SOURCE_REPO_URL:
        return line.replace(PLACEHOLDER, f"[{SOURCE_REPO_URL}]({SOURCE_REPO_URL})")
    return line.replace(PLACEHOLDER, "available on request")


def _table(rows: list[str]) -> str:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], [c for c in cells[1:] if not all(re.fullmatch(r":?-{3,}:?", x) for x in c)]
    return ('<div class="table-wrap"><table><thead><tr>' + "".join(f"<th>{_inline(c)}</th>" for c in head) +
            "</tr></thead><tbody>" + "".join("<tr>" + "".join(f'<td data-label="{html.escape(head[k] if k < len(head) else "")}">{_inline(c)}</td>'
                                         for k, c in enumerate(r)) + "</tr>" for r in body) +
            "</tbody></table></div>")


def _blocks(lines: list[str]) -> str:
    """Markdown lines (already de-indented) -> HTML."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(lines[i + 1:j]), quote=False)}</code></pre>")
            i = j + 1
            continue
        h = re.match(r"(#{1,3}) (.+)", line)
        if h:
            n = len(h.group(1))
            slug = re.sub(r"[^a-z0-9]+", "-", h.group(2).lower()).strip("-")
            out.append(f'<h{n} id="{slug}">{_inline(h.group(2))}</h{n}>')
            i += 1
            continue
        if line.startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.append(_table(lines[i:j]))
            i = j
            continue
        lm = re.match(r"(- |\d+\. )", line)
        if lm:
            ordered = lm.group(1) != "- "
            items: list[list[str]] = []
            while i < len(lines):
                cur = lines[i]
                m = re.match(r"(- |\d+\. )(.*)", cur)
                if m and (m.group(1) != "- ") == ordered:
                    items.append([m.group(2)])
                    i += 1
                elif not cur.strip() and i + 1 < len(lines) and re.match(r"- " if not ordered else r"\d+\. ", lines[i + 1]):
                    i += 1                     # a blank line between two items of the same list
                elif cur.startswith("   ") or (not cur.strip() and i + 1 < len(lines) and lines[i + 1].startswith("   ")):
                    items[-1].append(cur[3:] if cur.startswith("   ") else "")
                    i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_item(it)}</li>" for it in items) + f"</{tag}>")
            continue
        j = i
        while j < len(lines) and lines[j].strip() and not re.match(r"(#{1,3} |- |\d+\. |```|\|)", lines[j]):
            j += 1
        out.append(f"<p>{_inline(' '.join(l.strip() for l in lines[i:j]))}</p>")
        i = j
    return "\n".join(out)


def _item(lines: list[str]) -> str:
    first, rest = lines[0], lines[1:]
    if not any(l.strip() for l in rest):
        return _inline(first)
    return f"<p>{_inline(first)}</p>" + _blocks(rest)


def render(doc: str | None = None) -> str:
    text = doc if doc is not None else DOC.read_text(encoding="utf-8")
    lines = [_source_line(l) for l in text.splitlines()]
    title = lines[0].lstrip("# ").strip()
    # the first paragraph talks about this file itself; the page doesn't need it
    body = lines[1:]
    k = next((n for n, l in enumerate(body) if l.startswith("## ")), 0)
    content = _blocks(body[k:])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{html.escape(title)} · Ping</title>
  <meta name="description" content="How to run your own copy of Ping: what you get, what you need, the steps, privacy.">
  <link rel="icon" href="icons/ping.svg" type="image/svg+xml">
  <link rel="stylesheet" href="style.css">
  <script>try {{ const t = JSON.parse(localStorage.getItem("ping-theme")); if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; }} catch (e) {{}}</script>
</head>
<body class="doc">
  <header class="top">
    <a class="brand" href="./"><span class="avatar" aria-hidden="true"><svg viewBox="96,110,320,320"><path class="mk-b" d="M140,136h232a44,44,0,0,1,44,44v136a44,44,0,0,1-44,44H238l-78,62v-62h-20a44,44,0,0,1-44-44V180a44,44,0,0,1,44-44z"/><circle class="mk-c" cx="256" cy="248" r="28"/><path class="mk-a" d="M202,200a68,68,0,0,0,0,96M310,200a68,68,0,0,1,0,96"/></svg></span>
      <span><strong>Ping</strong><span class="sub">back to sign in</span></span></a>
  </header>
  <main class="page doc-page">
    <h1>{_inline(title)}</h1>
{content}
  </main>
</body>
</html>
"""


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site" / "setup.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
