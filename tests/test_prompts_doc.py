"""docs/PROMPTS.md is generated from the source; this fails if someone changes a prompt, a model or a
timeout and forgets to regenerate it (python setup/export_prompts.py)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _exporter():
    spec = importlib.util.spec_from_file_location("export_prompts", ROOT / "setup" / "export_prompts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_prompts_doc_matches_the_source():
    exp = _exporter()
    assert (ROOT / "docs" / "PROMPTS.md").read_text(encoding="utf-8") == exp.render(), \
        "docs/PROMPTS.md is out of date: run python setup/export_prompts.py"


def test_every_prompt_is_in_the_doc_verbatim():
    from ping.ai import PROMPT
    doc = (ROOT / "docs" / "PROMPTS.md").read_text(encoding="utf-8")
    assert PROMPT.rstrip("\n") in doc
    ts = (ROOT / "supabase" / "functions" / "ask-ping" / "index.ts").read_text(encoding="utf-8")
    template = ts.split("const prompt = `", 1)[1].split("`;\n", 1)[0]
    assert template in doc
