"""'For you' or not: cached per role, re-asked only when the role or your targets change; lists split."""

import json
from datetime import timedelta

from ping import relevance
from ping.items import build_items
from tests.test_digests import DUE, PROFILE, role, visible

TARGETS = "product, consulting, business/data analyst and finance roles; not core software engineering"
CFG = {"provider": "openai_compatible", "base_url": "https://example.invalid/v1", "key": "k", "model": "m",
       "fallback_models": ["m2"]}


class FakeGemini:
    """Answers like Gemini: 'product'/'analyst' in the title -> relevant. Records what it was sent."""

    def __init__(self, fail_first=False):
        self.prompts, self.fail_first = [], fail_first

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.prompts.append(json["messages"][0]["content"])
        if self.fail_first and len(self.prompts) == 1:
            return _Resp(429, {"error": {"message": "busy"}})
        ids = [l.split("[id: ", 1)[1].rstrip("]") for l in json["messages"][0]["content"].splitlines() if l.startswith("[id: ")]
        titles = [l.split("Title: ", 1)[1] for l in json["messages"][0]["content"].splitlines() if l.startswith("Title: ")]
        out = [{"id": i, "relevant": any(w in t.lower() for w in ("product", "analyst")),
                "reason": "product management role with roadmap ownership and strategy" if "product" in t.lower()
                else "core software engineering"} for i, t in zip(ids, titles)]
        out.append({"id": "made-up", "relevant": True, "reason": "x"})      # unknown ids are dropped
        return _Resp(200, {"choices": [{"message": {"content": "```json\n" + _dumps(out) + "\n```"}}]})


def _dumps(x):
    return json.dumps(x)


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


def roles_with_text():
    rs = [role(1, "Alpha"), role(2, "Beta"), role(3, "Gamma")]
    rs[0]["designation"], rs[0]["job_description"] = "Associate Product Manager", "Own the roadmap for payments."
    rs[1]["designation"], rs[1]["job_description"] = "Software Engineer I", "Build backend services in Go."
    rs[2]["designation"], rs[2]["job_description"] = "Business Analyst", None          # no JD on the ERP
    return rs


def test_classify_once_cached_and_reasked_only_on_change(monkeypatch):
    fake = FakeGemini(fail_first=True)
    monkeypatch.setattr(relevance.requests, "post", fake)
    rs = roles_with_text()
    found = relevance.classify(rs, TARGETS, CFG)
    assert set(found) == {"r1", "r2", "r3"}
    assert len(fake.prompts) == 2              # one batch; the first model was busy, the fallback answered
    assert found["r1"]["relevant"] and not found["r2"]["relevant"] and found["r3"]["relevant"]
    assert len(found["r1"]["reason"].split()) <= 8
    assert found["r3"]["jd_missing"] and "judge on the title" in fake.prompts[-1]
    # what Gemini sees: the targets and the roles' own text, nothing about the student
    assert TARGETS in fake.prompts[-1] and PROFILE["roll"] not in fake.prompts[-1]
    for r in rs:
        r["relevance"] = found[r["id"]]
    assert relevance.classify(rs, TARGETS, CFG) == {} and len(fake.prompts) == 2     # cached: no call
    rs[1]["job_description"] = "Now a product analytics role."                         # the role's text changed
    assert [r["id"] for r in rs if relevance.needs(r, TARGETS)] == ["r2"]
    assert all(relevance.needs(r, TARGETS + "; also quant") for r in rs)                # your targets changed
    assert relevance.tag(rs[0], TARGETS)[0] == "for_you" and relevance.tag(rs[1], TARGETS)[0] is None   # r2 is stale
    assert relevance.tag(rs[2], TARGETS) == ("for_you", "core software engineering (JD missing)")
    assert relevance.tag(rs[0], "") == (None, "")                                      # no targets: no split


def test_digest_lists_for_you_first_then_others(monkeypatch):
    monkeypatch.setattr(relevance.requests, "post", FakeGemini())
    rs = roles_with_text()
    found = relevance.classify(rs, TARGETS, CFG)
    for r in rs:
        r["relevance"] = found[r["id"]]
    now = DUE - timedelta(hours=20)
    items = {it["id"]: it for it in build_items(rs, [], {}, {**PROFILE, "targets": TARGETS}, now)}
    d = [v for v in visible(items).values() if v["category"] == "digest"][0]
    groups = d["details"]["list"]
    assert [g["head"] for g in groups] == ["For you", "Others (1)"]
    assert [r["text"] for r in groups[0]["rows"]] == ["Alpha — Associate Product Manager", "Gamma — Business Analyst"]
    assert groups[0]["rows"][1]["note"].endswith("(JD missing)")
    assert groups[1]["collapsed"] and groups[1]["rows"][0]["note"] == ""
    # "Always list other roles separately" off: the others are only counted
    items2 = {it["id"]: it for it in build_items(rs, [], {}, {**PROFILE, "targets": TARGETS, "list_other_roles": False}, now)}
    d2 = [v for v in visible(items2).values() if v["category"] == "digest"][0]
    assert [g["head"] for g in d2["details"]["list"]][-1].startswith("1 other role not shown")


def test_ineligible_roles_are_never_classified_or_listed(monkeypatch):
    fake = FakeGemini()
    monkeypatch.setattr(relevance.requests, "post", fake)
    rs = roles_with_text()
    rs[0]["erp_messages"] = ["Company requirement has CGPA cut off greater than yours"]
    from ping.eligibility import evaluate
    open_ = [r for r in rs if evaluate(r, PROFILE)["eligible"] is not False]
    relevance.classify(open_, TARGETS, CFG)
    assert "Alpha" not in fake.prompts[0]
    items = build_items(rs, [], {}, {**PROFILE, "targets": TARGETS}, DUE - timedelta(hours=20))
    assert not any("Alpha" in json.dumps(it["details"].get("list", [])) for it in items if it["category"] == "digest")
