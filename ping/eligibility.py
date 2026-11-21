"""Are you eligible for a role?

eligible = CGPA at or above the cut-off (no cut-off = yes)
         + your degree and department in the allowed list (empty list = yes, flagged)
         + the backlog rule doesn't rule you out
The ERP also prints its own warning in the role popup ("Company requirement has
CGPA cut off greater than yours."); that counts as a definite no.
"""

from __future__ import annotations

import re


def _norm_dept(s: str) -> str:
    s = (s or "").upper().replace("&", " AND ")
    s = re.sub(r"\bENGG\b\.?", "ENGINEERING", s)
    s = re.sub(r"\(.*?\)", " ", s)
    return re.sub(r"[^A-Z]", "", s)


def _norm_degree(s: str) -> str:
    s = re.sub(r"[^A-Z0-9]", "", (s or "").upper())
    return {"DUAL": "DUALDEGREE", "DD": "DUALDEGREE", "BTECH4Y": "BTECH", "BS": "4YRSBS"}.get(s, s)


def backlog_allows(rule: str | None) -> bool | None:
    if not rule:
        return None
    r = rule.lower()
    if re.search(r"\b(no|not|without|zero|nil|0)\b.{0,30}backlog|backlogs?\s*(are\s*)?not\s*allowed|^\s*no\b|"
                 r"not\s+eligible|should not have", r):
        return False
    if re.search(r"\b(yes|allowed|eligible|any)\b", r):
        return True
    return None


def evaluate(role: dict, profile: dict) -> dict:
    reasons, flags = [], []
    verdict: bool | None = True

    for msg in role.get("erp_messages") or []:
        if re.search(r"cut ?off greater than yours|not eligible", msg, re.I):
            return {"eligible": False, "reasons": [f"ERP says: {msg}"], "flags": []}

    cut = role.get("cgpa_cutoff")
    cg = profile.get("cgpa")
    if cut:
        if cg is None:
            verdict = None
            flags.append("add your CGPA in Profile")
        elif float(cg) + 1e-9 < float(cut):
            return {"eligible": False, "reasons": [f"CGPA cut-off {cut} is above your {cg}"], "flags": []}
        else:
            reasons.append(f"CG {cut:g}+")
    else:
        reasons.append("no CG cut-off")

    allowed = role.get("allowed") or []
    if role.get("details_fetched") and not allowed:
        flags.append("no department list on this role")
        reasons.append("all depts")
    elif allowed:
        dept, deg = _norm_dept(profile.get("department", "")), _norm_degree(profile.get("degree", ""))
        if not dept or not deg:
            verdict = None if verdict else verdict
            flags.append("add your degree and department in Profile")
        else:
            ok = any((_norm_dept(a["department"]) == dept or (dept and dept in _norm_dept(a["department"] + a["programme"])))
                     and (_norm_degree(a["degree"]) == deg or deg in _norm_degree(a["degree"]))
                     for a in allowed)
            if not ok:
                return {"eligible": False, "reasons": ["your degree/department is not in the allowed list"],
                        "flags": flags}
            n_depts = len({a["department"] for a in allowed})
            reasons.append("all depts" if n_depts >= 15 else "your dept allowed")
    elif not role.get("details_fetched"):
        verdict = None if verdict else verdict
        flags.append("role details not read yet")

    rule = role.get("backlog_rule")
    if profile.get("active_backlogs"):
        allows = backlog_allows(rule)
        if allows is False:
            return {"eligible": False, "reasons": [f"backlog rule: {rule}"], "flags": flags}
        if allows is None:
            flags.append("backlog rule unclear" if rule else "backlog rule not stated")

    return {"eligible": verdict, "reasons": reasons, "flags": flags}
