"""How a listed company is recognised in a mail (ping/mail_source.py, rules v3): by its own domain or by its full name,
never by a parent company or a first word alone ("icici" is not ICICI Lombard, "futures" is not Futures First).

  sender's domain   a label equal to the company's name written together ("pinelabs", "zsassociates"), its initials
                    ("jpmc"), initials then the rest ("jpmchase"), or a short name that is the whole label ("ey" in
                    in.ey.com, "zs" in zs.com); never the domain's ending ("finlatics.info" is not Info Edge)
  name / subject /  the company's name without legal and generic endings ("Accenture" for Accenture Solutions Private
  body              Limited, "Futures First" for Futures First Info Services, "ICICI Lombard"), as whole words; or the
                    name written together ("PineLabs")
"""

from __future__ import annotations

import re

from .matching import CompanyIndex, compact, tokens

GENERIC = {"solutions", "services", "technologies", "technology", "india", "consulting", "software", "systems", "info",
           "global", "delivery", "group", "private", "limited", "pvt", "ltd", "llp", "inc", "co", "corporation", "corp",
           "company", "enterprises", "industries", "international", "labs", "ventures", "analytics", "partners"}
COMMON_WORDS = {"test", "online", "interview", "form", "data", "first", "new", "united", "general", "national", "global",
                "media", "power", "capital", "financial", "finance", "bank", "health", "energy", "digital", "network"}
NOT_A_NAME = {"com", "co", "in", "org", "net", "io", "ac", "edu", "mail", "email", "gmail", "info", "news", "customer",
              "custcomm", "alerts", "notifications", "noreply", "no-reply", "mailer", "www"}


def _initials(core: list[str]) -> str:
    return "".join(w if len(w) <= 3 else w[0] for w in core)


def name_phrase(company: str) -> str | None:
    """The words a company's name is written with: "accenture", "futures first", "icici lombard", "ey global"."""
    core = tokens(company)
    if not core:
        return None
    short = list(core)
    while len(short) > 1 and short[-1] in GENERIC:
        short.pop()
    if len(short) == 1 and (len(short[0]) < 5 or short[0] in COMMON_WORDS):
        short = core[:2]                                  # "pine" alone is a tree: "pine labs"
    if len(short) == 1 and (len(short[0]) < 4 or short[0] in COMMON_WORDS):
        return None
    return " ".join(short[:3])


class Names:
    def __init__(self, index: CompanyIndex):
        self.index = index
        self.labels: dict[str, str] = {}      # domain labels
        self.phrases: dict[str, str] = {}     # company -> its name's words
        self.together: dict[str, str] = {}    # "pinelabs" -> company
        for c in index.by_company:
            core = tokens(c)
            if not core:
                continue
            whole = compact(c)
            if len(whole) >= 4:
                self.labels.setdefault(whole, c)
                if len(whole) >= 6:
                    self.together.setdefault(whole, c)
            if len(core) > 1:
                ini = _initials(core)
                if len(ini) >= 3:
                    self.labels.setdefault(ini, c)
                for k in range(1, len(core)):
                    v = _initials(core[:k]) + "".join(core[k:])
                    if len(v) >= 6:
                        self.labels.setdefault(v, c)
            phrase = name_phrase(c)
            if phrase:
                self.phrases[c] = phrase
                self.labels.setdefault(phrase.replace(" ", ""), c)
            if 2 <= len(core[0]) <= 4 and core[0] not in COMMON_WORDS:
                self.labels.setdefault(core[0], c)          # "ey", "zs": only as a whole domain label

    def in_sender(self, name: str, domain: str) -> str | None:
        labels = [w for w in re.split(r"[.\-]", (domain or "").lower()) if w][:-1]    # never the ending
        for l in labels:
            if l not in NOT_A_NAME and l in self.labels:
                return self.labels[l]
        hits = self.in_text(name)
        return hits[0] if hits else None

    def in_text(self, text: str) -> list[str]:
        words = tokens(text or "", keep_stop=True)
        seq = " " + " ".join(words) + " "
        found = [c for c, p in self.phrases.items() if f" {p} " in seq]
        ws = set(words)
        found += [c for w, c in self.together.items() if w in ws and c not in found]
        return found
