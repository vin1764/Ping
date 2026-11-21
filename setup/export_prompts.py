"""Write docs/PROMPTS.md from the source code, so the document can't drift from what Ping actually sends.

Every prompt is copied verbatim from where it lives (ping/ai.py and supabase/functions/ask-ping/index.ts),
together with the settings read from the same files: the models in fallback order, timeouts, limits and
generation settings. tests/test_prompts_doc.py fails if docs/PROMPTS.md is out of date.

    python setup/export_prompts.py           # rewrite docs/PROMPTS.md
    python setup/export_prompts.py --check   # exit 1 if it is out of date
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AI_PY = ROOT / "ping" / "ai.py"
CONFIG_PY = ROOT / "ping" / "config.py"
ASK_TS = ROOT / "supabase" / "functions" / "ask-ping" / "index.ts"
OUT = ROOT / "docs" / "PROMPTS.md"


def _py_constant(src: str, name: str):
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit(f"{name} not found")


def _one(pattern: str, src: str, what: str, flags=0) -> str:
    m = re.search(pattern, src, flags)
    if not m:
        raise SystemExit(f"could not find {what}; update setup/export_prompts.py")
    return m.group(1)


def notice_prompt() -> dict:
    src = AI_PY.read_text(encoding="utf-8")
    cfg = CONFIG_PY.read_text(encoding="utf-8")
    first = _one(r'"model": ai\["model"\] or "([^"]+)"', cfg, "the default notice model")
    fallbacks = _one(r'"fallback_models": \[([^\]]*)\]', cfg, "the notice fallback models")
    models = [first] + re.findall(r'"([^"]+)"', fallbacks)
    timeout = _one(r"timeout=(\d+)", src, "the notice timeout")
    return {
        "title": "Notice reader fallback (deadlines and companies the rules couldn't find)",
        "where": "`ping/ai.py` (`PROMPT`, used by `refine_notice`), called from the hourly run on GitHub Actions",
        "when": ("Only when the rules find no deadline in a CV / extension / form notice, or no companies in a "
                 "\"Multiple Companies\" notice. Rules always go first."),
        "input": ("`{ref}`: the notice's own time (IST, ISO format); `{companies}`: up to 300 company names from your "
                  "companies list; `{text}`: that one notice's text, first 6,000 characters. Never PDFs, never your data."),
        "output": ("JSON only: `deadlines` (list of `at` ISO time + `text` quoted from the notice) and `companies` (list of "
                   "`name` + `profiles`). Replies without JSON, or with dates that don't parse, are dropped."),
        "models": models,
        "settings": [
            "endpoint: Gemini's OpenAI-compatible `/chat/completions` (`GEMINI_API_KEY`), or any provider set with "
            "`PING_AI_PROVIDER` / `PING_AI_BASE_URL` / `PING_AI_MODEL` / `PING_AI_KEY`",
            "temperature: " + _one(r'"temperature": ([\d.]+)', src, "the notice temperature"),
            f"timeout per model: {timeout} s; a timeout, an error "
            "(400/404/429/5xx) or a reply without JSON moves on to the next model",
            f"limits per run: at most {_py_constant(src, 'MAX_CALLS')} calls and {_py_constant(src, 'BUDGET_SECONDS')} s "
            "of AI time in total",
        ],
        "prompt": _py_constant(src, "PROMPT"),
    }


def ask_ping_prompt() -> dict:
    src = ASK_TS.read_text(encoding="utf-8")
    models_src = _one(r"const MODELS = \[(.*?)\];", src, "MODELS")
    models = re.findall(r'"([^"]+)"', models_src)
    budget = int(_one(r"const BUDGET_MS = ([\d_]+);", src, "BUDGET_MS").replace("_", ""))
    per = int(_one(r"const PER_MODEL_MS = ([\d_]+);", src, "PER_MODEL_MS").replace("_", ""))
    gen = _one(r"generationConfig: (\{[^}]*\})", src, "generationConfig")
    prompt = _one(r"const prompt = `(.*?)`;\n", src, "the ask-ping prompt", re.S)
    return {
        "title": "Ask Ping (the chat on the dashboard)",
        "where": "`supabase/functions/ask-ping/index.ts` (`const prompt`), a Supabase Edge Function; the Gemini key "
                 "is a Supabase function secret and never reaches the browser",
        "when": "Every question typed in the dashboard chat by a signed-in owner or reviewer. If it fails, the page "
                "answers with simple rules instead and says so.",
        "input": "`${...}` parts are filled in per question from the caller's own rows (Row Level Security applies: "
                 "the owner's real data, or the reviewer's anonymised demo). See the template for each part.",
        "output": "Plain text, shown as Ping's chat reply. No JSON.",
        "models": models,
        "settings": [
            "endpoint: Gemini `generateContent` (`GEMINI_API_KEY`); `PING_AI_MODEL` replaces the first model",
            f"generation: `{gen}`",
            f"timeout per model: {per // 1000} s; whole answer: {budget // 1000} s (Supabase stops a function at 150 s); "
            "an error, a timeout or an empty reply moves on to the next model",
        ],
        "prompt": prompt,
    }


def render() -> str:
    lines = [
        "# Prompts Ping sends to a model",
        "",
        "_Generated from the source by `python setup/export_prompts.py`; do not edit by hand. "
        "`tests/test_prompts_doc.py` fails when this file is out of date._",
        "",
        "Ping sends text to a model in exactly two places. Everything else (reading the ERP, notices, PDFs, "
        "eligibility, the feed) is rules, with no model involved.",
        "",
    ]
    for i, p in enumerate((notice_prompt(), ask_ping_prompt()), 1):
        lines += [
            f"## {i}. {p['title']}", "",
            f"- **Where it runs:** {p['where']}",
            f"- **When:** {p['when']}",
            f"- **Input:** {p['input']}",
            f"- **Expected output:** {p['output']}",
            "- **Models, in fallback order:** " + " → ".join(f"`{m}`" for m in p["models"]),
        ]
        lines += [f"- {s}" for s in p["settings"]]
        lines += ["", "**Prompt, verbatim:**", "", "````text", p["prompt"].rstrip("\n"), "````", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("docs/PROMPTS.md is out of date: run python setup/export_prompts.py")
            return 1
        print("docs/PROMPTS.md is up to date")
        return 0
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
