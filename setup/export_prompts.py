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
DASH_YML = ROOT / ".github" / "workflows" / "dashboard.yml"
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


def relevance_prompt() -> dict:
    src = (ROOT / "ping" / "relevance.py").read_text(encoding="utf-8")
    cfg = CONFIG_PY.read_text(encoding="utf-8")
    first = _one(r'"model": ai\["model"\] or "([^"]+)"', cfg, "the default model")
    fallbacks = _one(r'"fallback_models": \[([^\]]*)\]', cfg, "the fallback models")
    return {
        "title": "Role relevance (\"For you\" or not)",
        "where": "`ping/relevance.py` (`PROMPT`, used by `classify`), called from the hourly run on GitHub Actions",
        "when": ("Once per role, for roles you're not ruled out of (eligibility is applied first), and again only when "
                 "the role's text or your \"What I'm looking for\" text changes (the answer is cached on the role)."),
        "input": (f"`{{targets}}`: your \"What I'm looking for\" text (first 600 characters); `{{cvs}}`: one summary "
                  "line per CV you uploaded (prompt 3), or nothing; `{{roles}}`: up to "
                  f"{_py_constant(src, 'BATCH')} roles, each with its id, company, title, a few role fields and the first "
                  f"{_py_constant(src, 'JD_CHARS')} characters of its job description (or \"none given; judge on the "
                  "title\"). Never your name, roll number, CGPA or mail."),
        "output": ("JSON list only: `id`, `relevant` (true/false), `reason` (cut to 8 words). Entries with an unknown id "
                   "or a non-boolean answer are dropped; roles without an answer are tried again next run."),
        "models": [first] + re.findall(r'"([^"]+)"', fallbacks),
        "settings": [
            "endpoint: the same OpenAI-compatible `/chat/completions` as the notice reader",
            "temperature: " + _one(r'"temperature": ([\d.]+)', src, "the relevance temperature"),
            f"timeout per model: {_one(r'timeout=(\d+)', src, 'the relevance timeout')} s; "
            f"all classification in one run: {_py_constant(src, 'BUDGET_SECONDS')} s",
        ],
        "prompt": _py_constant(src, "PROMPT"),
    }


def cv_prompt() -> dict:
    src = (ROOT / "ping" / "cvs.py").read_text(encoding="utf-8")
    cfg = CONFIG_PY.read_text(encoding="utf-8")
    first = _one(r'"model": ai\["model"\] or "([^"]+)"', cfg, "the default model")
    fallbacks = _one(r'"fallback_models": \[([^\]]*)\]', cfg, "the fallback models")
    return {
        "title": "CV summary (for \"Apply with\")",
        "where": "`ping/cvs.py` (`SUMMARY_PROMPT`, used by `summarise_new`), called from the hourly run on GitHub Actions",
        "when": "Once per CV you upload on the Profile page (up to 3), and again only when you replace that file.",
        "input": (f"`{{text}}`: the text of that one PDF, first {_py_constant(src, 'TEXT_CHARS')} characters, read on the "
                  "server from the private `cvs` bucket. The text is never logged or stored."),
        "output": ("JSON only: `focus`, `skills`, `experience`, `education`; kept as one line in the profile, with any "
                   "email or phone number removed. The classifier gets these lines (prompt 2)."),
        "models": [first] + re.findall(r'"([^"]+)"', fallbacks),
        "settings": ["endpoint: the same OpenAI-compatible `/chat/completions` as the notice reader",
                     "temperature: " + _one(r'"temperature": ([\d.]+)', src, "the CV temperature"),
                     f"timeout per model: {_one(r'timeout=(\d+)', src, 'the CV timeout')} s"],
        "prompt": _py_constant(src, "SUMMARY_PROMPT"),
    }


def ask_ping_prompt() -> dict:
    src = ASK_TS.read_text(encoding="utf-8")
    models_src = _one(r"const MODELS = \[(.*?)\];", src, "MODELS", re.S)
    main = _one(r'\|\| "([^"]+)"', models_src, "the main model")
    lite_default = _one(r'const LITE = Deno\.env\.get\("PING_AI_LITE_MODEL"\) \|\| "([^"]+)"', src, "LITE")
    # the value the deploy sets on the Supabase function secrets (.github/workflows/dashboard.yml)
    lite = _one(r'"PING_AI_LITE_MODEL=([^"]+)"', DASH_YML.read_text(encoding="utf-8"), "PING_AI_LITE_MODEL in dashboard.yml")
    backoff = [int(x.replace("_", "")) // 1000 for x in
               re.findall(r"[\d_]+", _one(r"const BACKOFF_MS = \[(.*?)\];", src, "BACKOFF_MS"))]
    budget = int(_one(r"const BUDGET_MS = ([\d_]+);", src, "BUDGET_MS").replace("_", ""))
    per = int(_one(r"const PER_MODEL_MS = ([\d_]+);", src, "PER_MODEL_MS").replace("_", ""))
    gen = _one(r"generationConfig: (\{[^}]*\})", src, "generationConfig")
    prompt = _one(r"const prompt = `(.*?)`;\n", src, "the ask-ping prompt", re.S)
    return {
        "title": "Ask Ping (the chat on the dashboard)",
        "where": "`supabase/functions/ask-ping/index.ts` (`const prompt`), a Supabase Edge Function; the Gemini keys "
                 "are Supabase function secrets and never reach the browser",
        "when": "Every question typed in the dashboard chat by the signed-in owner or a one-click demo session. If no "
                "model answers, the function answers from the data by rules (`supabase/functions/_shared/answer_rules.js`) "
                "and says so; the page uses the same rules if the function can't be reached. Demo sessions: 15 questions "
                "per session per hour, 100 per hour for all demo sessions together.",
        "input": "`${...}` parts are filled in per question from the caller's own rows (Row Level Security applies: "
                 "the owner's real data, or the anonymised demo for a demo session). See the template for each part.",
        "output": "Plain text, shown as Ping's chat reply. No JSON.",
        "models": [main, lite],
        "settings": [
            "endpoint: Gemini `generateContent`; key `GEMINI_API_KEY` for students and demo visitors, `GEMINI_API_KEY_EVALS` "
            "for evals and Admin checks (requests that prove they hold it with `x-ping-evals`); `PING_AI_MODEL` replaces "
            "the main model",
            f"order: the main model ({main}); when it's busy (429, 5xx, timeout) again after "
            f"{', '.join(f'{b} s' for b in backoff)}; then the lighter model once (`PING_AI_LITE_MODEL`, set to {lite} "
            f"by the deploy; {lite_default} if unset); then the rules answer",
            f"generation: `{gen}`",
            f"timeout per call: {per // 1000} s; whole answer: {budget // 1000} s (Supabase stops a function at 150 s)",
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
        "Ping sends text to a model in exactly four places. Everything else (reading the ERP, notices, PDFs, "
        "eligibility, the feed) is rules, with no model involved.",
        "",
    ]
    for i, p in enumerate((notice_prompt(), relevance_prompt(), cv_prompt(), ask_ping_prompt()), 1):
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
