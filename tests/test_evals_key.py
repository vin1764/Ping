"""The evals proof the Python side sends is the one the function computes (ask-ping/evals_key_test.ts has the
same vector), and nothing runs an eval without the evals key."""

import pytest

from ping.evals_key import eval_headers, evals_proof


def test_same_hmac_as_the_function():
    assert evals_proof("test-evals-key") == "72fa44938fecbcc05c30613f630e95836283df39e9f0b620179d0c72bed6d706"


def test_no_evals_key_no_eval(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY_EVALS", raising=False)
    with pytest.raises(SystemExit, match="never use the live Gemini key"):
        eval_headers()
    monkeypatch.setenv("GEMINI_API_KEY_EVALS", "k")
    assert set(eval_headers()) == {"x-ping-evals"}
