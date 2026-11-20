"""Turn ERP pages into plain data. Formats taken from the real captured pages."""

from __future__ import annotations

import html as htmllib
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from bs4 import BeautifulSoup

from .config import IST

# ---------------------------------------------------------------- helpers

def _text(fragment: str) -> str:
    t = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", htmllib.unescape(t)).strip()


def _title(fragment: str) -> str:
    m = re.search(r"title='(.*?)'\s+href", fragment or "", re.S) or re.search(r'title="(.*?)"\s+href', fragment or "", re.S)
    return htmllib.unescape(m.group(1)).strip() if m else ""


def _call_args(fragment: str, fn: str) -> list[str]:
    m = re.search(fn + r"\(([^)]*)\)", fragment or "")
    if not m:
        return []
    return [a or b for a, b in re.findall(r'"([^"]*)"|\'([^\']*)\'', m.group(1))]


def parse_dt(value: str, day_first: bool) -> str | None:
    """'2026-10-21 15:30' (companies) or '21-11-2026 00:07' (notices) -> ISO in IST."""
    value = (value or "").strip()
    if not value:
        return None
    fmts = ["%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M", "%Y-%m-%d", "%d-%m-%Y"]
    if day_first:
        fmts = ["%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M", "%d-%m-%Y", "%Y-%m-%d"]
    for f in fmts:
        try:
            return datetime.strptime(value, f).replace(tzinfo=IST).isoformat()
        except ValueError:
            continue
    return None


def _grid_rows(xml_text: str) -> list[list[str]]:
    body = xml_text[xml_text.find("<rows"):] if "<rows" in xml_text else xml_text
    root = ET.fromstring(body.encode("utf-8"))
    return [[(c.text or "") for c in row.findall("cell")] for row in root.findall("row")]


# ------------------------------------------------------------ companies list
# Cells, left to right (13): companyname, view2 (Additional), view3 (PPT),
# designation (role link), description (hidden Apply link), ctc, Currency,
# view1 (Additional Details), apply (Application Status = Y), resume start,
# resume end (= apply deadline), interview/selection, contract.

def parse_companies(xml_text: str) -> list[dict]:
    roles = []
    for cells in _grid_rows(xml_text):
        if len(cells) < 13:
            continue
        com = _call_args(cells[0], "TPComView")
        jnf = _call_args(cells[3], "TPJNFView") or _call_args(cells[4], "TPJNFView")
        if len(jnf) < 3:
            continue
        jnf_id, com_id, yop = jnf[0], jnf[1], jnf[2]
        ctc_raw = _text(cells[5])
        try:
            ctc = float(ctc_raw.replace(",", "")) if ctc_raw else None
        except ValueError:
            ctc = None
        roles.append({
            "id": f"{yop}:{com_id}:{jnf_id}",
            "yop": yop, "com_id": com_id, "jnf_id": jnf_id,
            "company": _text(cells[0]) or (com[0] if com else ""),
            "designation": _text(cells[3]),
            "ctc": ctc, "ctc_text": ctc_raw,
            "currency": _text(cells[6]) or None,
            "has_company_doc": bool(_text(cells[1])),
            "has_ppt_doc": bool(_text(cells[2])),
            "has_form_doc": bool(_text(cells[7])),
            "applied": _text(cells[8]).upper() == "Y",
            "apply_start": parse_dt(_text(cells[9]), day_first=False),
            "apply_end": parse_dt(_text(cells[10]), day_first=False),
            "apply_end_text": _text(cells[10]),
            "interview_date": _text(cells[11]) or None,
            "contract": _text(cells[12]) or None,
        })
    return roles


# ------------------------------------------------------- role details popup

def parse_role_popup(html: str) -> dict:
    """TPJNFView.jsp. Its HTML nests <tr> inside <tr>, so read it in document
    order with patterns instead of a tree."""
    i = html.find('id="printableArea"')
    area = html[i:] if i >= 0 else html
    area = re.sub(r"(?is)<!--.*?-->", "", area)
    out: dict = {"erp_messages": [], "allowed": [], "has_more_details_link": "jnfMoreDet(" in area,
                 "applied_resume_link": "View applied Resume" in area}
    m = re.search(r'(?is)<td class="header"[^>]*>\s*Company\s*:\s*(.*?)</td>', area)
    if m:
        out["company"] = _text(m.group(1))
        # plain messages the ERP shows above the company name (e.g. CGPA warning)
        for cell in re.findall(r"(?is)<td[^>]*>(.*?)</td>", area[: m.start()]):
            if "<a" in cell.lower():
                continue
            t = _text(cell)
            if t:
                out["erp_messages"].append(t)
    hm = re.search(r"(?is)<tr>\s*(<th>.*?)</tr>\s*<tr>(.*?)</tr>", area)
    if hm:
        ths = [_text(x) for x in re.findall(r"(?is)<th[^>]*>(.*?)</th>", hm.group(1))]
        tds = [_text(x) for x in re.findall(r"(?is)<td[^>]*>(.*?)</td>", hm.group(2))]
        info = dict(zip(ths, tds))
        out["form_type"] = info.get("Form Type")
        out["designation"] = info.get("Designation")
        out["ctc_text"] = info.get("Cost to Company per year")
        out["bond"] = info.get("Bond / Service Contract") or None
        out["additional_criteria"] = info.get("Additional Criteria") or None
        cut = info.get("CGPA Cut-off", "") or ""
        try:
            cut_v = float(cut) if cut else None
        except ValueError:
            cut_v = None
        out["cgpa_cutoff"] = cut_v if cut_v else None  # 0.0 means no cut-off
        out["cgpa_cutoff_text"] = cut
    section = None
    dept = ""
    seen = set()
    for attrs, cell in re.findall(r'(?is)<td colspan="6"([^>]*)>(.*?)</td>', area):
        t = _text(cell)
        if 'class="header"' in attrs:
            low = t.lower()
            section = "jd" if low.startswith("job description") else \
                "allowed" if low.startswith("allowed departments") else "other"
            continue
        if section == "jd" and t and "job_description" not in out:
            out["job_description"] = t
        elif section == "allowed" and t:
            if "lightgrey" in attrs.lower() or "---" not in t:
                dept = t
            else:
                degree, _, programme = t.partition("---")
                key = (dept, degree.strip(), programme.strip())
                if key not in seen:
                    seen.add(key)
                    out["allowed"].append({"department": dept, "degree": key[1], "programme": key[2]})
    return out


# ------------------------------------------------------ "more details" popup
# JnfMoreDet.jsp (seen on the real ERP): <h4> section headings ("Job Profile",
# "Job Description", "Other Details", "Selection Details"); under them rows of
# <div class="col-xs-3 text-left"><div>Label :</div></div>
# <div class="col-xs-3"><div><b>value</b></div></div>

def parse_more_details(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    fields: dict[str, str] = {}
    sections: dict[str, dict] = {}
    for label_div in soup.select("div.text-left"):
        label = label_div.get_text(" ", strip=True).rstrip(":").strip()
        if not label:
            continue
        value_div = label_div.find_next_sibling("div")
        value = value_div.get_text(" ", strip=True) if value_div else ""
        heading = label_div.find_previous("h4")
        section = heading.get_text(" ", strip=True) if heading else "Other Details"
        sections.setdefault(section, {})[label] = value
        fields.setdefault(label, value)
    if not fields:  # older/other layout: two-cell table rows
        for tr in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"], recursive=False)]
            if len(cells) == 2 and cells[0] and len(cells[0]) < 120:
                fields.setdefault(cells[0].rstrip(": "), cells[1])
    raw = "\n".join(f"{k}: {v}" for k, v in fields.items())
    selection = next((sec for name, sec in sections.items() if "selection" in name.lower()), None)
    if selection is None:
        selection = {k: v for k, v in fields.items() if re.search(
            r"shortlist|written|test|interview|group discussion|\bgd\b|round|mode", k, re.I)}

    def find(pattern):
        for k, v in fields.items():
            if re.search(pattern, k, re.I):
                return v or None
        return None

    min_cgpa = find(r"minimum cgpa")
    return {
        "fields": fields,
        "sections": sections,
        "selection_details": selection,
        "backlog_rule": find(r"backlog"),
        "cgpa_criteria": " / ".join(x for x in (find(r"is there a cgpa"), min_cgpa) if x) or None,
        "min_cgpa": min_cgpa,
        "has_written_test": has_written_test(selection, raw),
        "raw_text": raw[:20000],
    }


def has_written_test(selection: dict, raw: str = "") -> bool | None:
    for k, v in selection.items():
        if re.search(r"written|online test|aptitude|coding test|\btest\b|assessment", k, re.I):
            return not re.match(r"\s*(no|n|nil|none|false|-|na|n/a)\s*$", v or "", re.I)
    text = " ".join(f"{k} {v}" for k, v in selection.items()) or raw
    if not text:
        return None
    if re.search(r"(written|online|aptitude|coding)\s+(test|assessment|round)", text, re.I):
        return True
    return None


# ------------------------------------------------------------- notice board
# Cells: id, type, subject, company, notice (link, full text in title),
# notice by, notice time (DD-MM-YYYY HH:MM), download, upload, deactivate.
# Upload / Deactivate are links Ping must never touch (the gate blocks them).

def parse_notices(xml_text: str) -> list[dict]:
    out = []
    for cells in _grid_rows(xml_text):
        if len(cells) < 8:
            continue
        args = _call_args(cells[4], "ViewNotice") or _call_args(cells[7], "TPNotice")
        year = args[0] if args else ""
        nid = _text(cells[0]) or (args[1] if len(args) > 1 else "")
        out.append({
            "id": f"{year}:{nid}",
            "year": year,
            "notice_id": int(nid) if nid.isdigit() else nid,
            "type": _text(cells[1]),
            "subject": _text(cells[2]),
            "company": _text(cells[3]),
            "preview": _title(cells[4]) or _text(cells[4]),
            "notice_time": parse_dt(_text(cells[6]), day_first=True),
            "notice_time_text": _text(cells[6]),
            "has_attachment": _text(cells[7]).lower() == "download",
        })
    return out


def parse_notice_page(html: str) -> dict:
    """ShowContent.jsp: '<b>Type</b> : X<br><b>Subject</b> : Y<br><b>Company</b> : Z<br><br>text...'"""
    m = re.search(r'(?is)<div id="printableArea">(.*?)</div>', html)
    body = m.group(1) if m else html
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)
    text = htmllib.unescape(re.sub(r"<[^>]+>", "", body))
    lines = [l.strip() for l in text.splitlines()]
    head = {}
    rest = []
    for l in lines:
        hm = re.match(r"^(Type|Subject|Company)\s*:\s*(.*)$", l)
        if not l and not rest:
            continue
        if hm and not rest:
            head[hm.group(1).lower()] = hm.group(2).strip()
        else:
            rest.append(l)
    body_text = "\n".join(rest).strip()
    body_text = re.sub(r"\n{3,}", "\n\n", body_text)
    return {"header": head, "text": body_text}
