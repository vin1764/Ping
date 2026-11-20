"""Which company (and which of its roles) is a notice about?

Notice board names and companies-list names differ ("ICICI LOMBARD" vs
"ICICI Lombard General Insurance Company Limited", "PINELABS" vs "Pine Labs").
We compare word sets after dropping legal words, and refuse to guess when
two companies fit equally well.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

STOP = {  # legal words only; dropping more makes "Accenture Solutions" == "Accenture India"
    "pvt", "private", "privated", "ltd", "limited", "inc", "llp", "llc", "co", "company",
    "corporation", "corp", "the", "of", "and", "plc", "gmbh", "pte",
}
GENERIC_HINTS = re.compile(
    r"multiple compan|placement schedule|cdc|instruction|important|general|all compan|"
    r"schedule for|cv building|workshop|seminar|session|guideline|notice|students?\b|internship 20|"
    r"placement 20|registration", re.I)


def tokens(name: str, keep_stop: bool = False) -> list[str]:
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"\(.*?\)|www\.\S+|https?://\S+", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    words = [w for w in s.split() if w]
    if keep_stop:
        return words
    core = [w for w in words if w not in STOP]
    return core or words


def compact(name: str) -> str:
    return "".join(tokens(name, keep_stop=False))


def similarity(a: str, b: str) -> float:
    ta, tb = set(tokens(a)), set(tokens(b))
    if not ta or not tb:
        return 0.0
    ca, cb = compact(a), compact(b)
    if ca == cb:
        return 1.0
    if ta <= tb or tb <= ta:
        return 0.95
    if len(ca) >= 4 and len(cb) >= 4 and (ca in cb or cb in ca):
        return 0.9
    inter = len(ta & tb)
    score = 0.85 * inter / len(ta | tb)
    wa, wb = tokens(a), tokens(b)
    if wa[0] == wb[0] and len(wa[0]) >= 4:
        score = max(score, 0.6)  # same distinctive first word: a candidate, never a sure match
    return score


@dataclass
class Match:
    query: str
    company: str | None          # confident pick, or None
    score: float
    candidates: list[tuple[str, float]] = field(default_factory=list)

    @property
    def unsure(self) -> bool:
        return self.company is None and bool(self.candidates)


class CompanyIndex:
    """Companies from the companies list. Entries whose names are the same
    apart from capitals/punctuation ("Eternal" and "ETERNAL") count as one."""

    def __init__(self, roles: list[dict]):
        self.roles = roles
        self.by_company: dict[str, list[dict]] = {}
        names: dict[str, str] = {}
        for r in roles:
            key = compact(r["company"]) or r["company"]
            name = names.setdefault(key, r["company"])
            self.by_company.setdefault(name, []).append(r)
        self._names = names

    def canonical(self, company: str) -> str:
        return self._names.get(compact(company) or company, company)

    def match(self, name: str, hint_text: str = "") -> Match:
        scored = sorted(((c, similarity(name, c)) for c in self.by_company), key=lambda x: -x[1])
        scored = [x for x in scored if x[1] >= 0.4]
        if not scored:
            return Match(name, None, 0.0)
        top = scored[0][1]
        tied = [c for c, s in scored if s >= top - 0.01]
        if top >= 0.9 and len(tied) == 1:
            return Match(name, tied[0], top, scored[:3])
        if top >= 0.6 and hint_text:
            # several companies fit (e.g. three Accenture entities): use role names in the text
            hits = [c for c in tied if any(_mentions(hint_text, r["designation"]) for r in self.by_company[c])]
            if len(hits) == 1:
                return Match(name, hits[0], top, scored[:3])
        return Match(name, None, top, scored[:3])

    def scan_text(self, text: str) -> list[str]:
        """Companies whose full core name appears in free text."""
        norm = " " + " ".join(tokens(text, keep_stop=True)) + " "
        found = []
        for c in self.by_company:
            core = tokens(c)
            if not core or len("".join(core)) < 3:
                continue
            if f" {' '.join(core)} " in norm:
                found.append(c)
        return found


def is_generic(company_col: str) -> bool:
    return bool(GENERIC_HINTS.search(company_col or "")) or not (company_col or "").strip()


def _mentions(text: str, designation: str) -> bool:
    d = " ".join(tokens(designation, keep_stop=True))
    t = " " + " ".join(tokens(text, keep_stop=True)) + " "
    return len(d) >= 4 and f" {d} " in t


def roles_named_in(text: str, roles: list[dict]) -> list[dict]:
    return [r for r in roles if _mentions(text, r["designation"])]
