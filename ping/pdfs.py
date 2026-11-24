"""Check a notice attachment (shortlist, room allocation, schedule) for YOU.

Only your own row and the table heading are kept. The rest of the file
(hundreds of other students' names) is never stored or sent anywhere.

A job description (one role or several) is not a list of students: it is classified first (classify()) and kept
whole (status "jd", the text in "context"), with any phone number or email address in it taken out. Anything with a
roll number in it, or that reads like a list of students, is never a JD.

Result status:
  yes      your roll number (or, as a fallback, your name) is in it
  no       the file was read in full, it lists students by roll number, and yours isn't there. Ping never says
           an absence ("not on it") for this: it says it couldn't find your roll number and asks you to check the list
  unknown  the file couldn't be read reliably: not opened, scanned (read by OCR), a page without text, or a list
           without roll numbers (names only). "reliability" says which
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import os
import zipfile
from datetime import datetime

ROLL_LIKE = re.compile(r"\b\d{2}[A-Z]{2}[A-Z0-9]{5}\b")
ROOM_HDR = re.compile(r"room|venue|lab|hall|class|location|centre|center", re.I)
DATE_HDR = re.compile(r"\bdate\b|\bday\b", re.I)
TIME_HDR = re.compile(r"time|reporting|timing", re.I)
SLOT_HDR = re.compile(r"slot|batch|session|panel|shift|group|round", re.I)


def _norm_cell(c) -> str:
    return re.sub(r"\s+", " ", str(c or "")).strip()


def roll_pattern(roll: str) -> re.Pattern:
    """Your roll number as lists write it: any case, with spaces, dashes, dots or a line break inside
    ("22XY10042", "22xy10042", "22 XY 10042", "22-XY-10042"), and inside a longer string ("22XY10042@kgpian...",
    "22XY10042_Name"), but never as part of a longer roll ("22XY100425", "122XY10042")."""
    body = r"[\s\-./]?".join(re.escape(c) for c in roll)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.I)


def _row_has(row: list[str], roll: str) -> bool:
    pat = roll_pattern(roll)
    return any(pat.search(c) for c in row) or bool(pat.search(" ".join(row)))


def _close(a: str, b: str) -> bool:
    """One typo (a letter wrong, missing, extra or two swapped) in a name part of 5+ letters."""
    if a == b:
        return True
    if min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1:
        return False
    d = [[i + j if not i * j else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1] <= 1


def _row_has_name(row: list[str], name: str, fuzzy: bool = False) -> bool:
    """Every part of your profile name is a word in the row (any order, any case). fuzzy: one typo allowed per
    part of 5+ letters; shorter parts must be exact."""
    parts = [p for p in re.split(r"\s+", name.lower()) if len(p) > 1]
    words = re.findall(r"[a-z]+", " ".join(row).lower())
    if not parts:
        return False
    if not fuzzy:
        return all(p in words for p in parts)
    return all(any(_close(p, w) for w in words) for p in parts)


ROOM_TOKEN = re.compile(r"\b(?:NC|NR|LH|CR|V|S|F|G)\s?-?\d{1,4}[A-Z]?\b")


def _details_from(header: list[str], row: list[str], needle: str = "") -> dict:
    """Read room/slot/date/time from the columns that belong to YOUR entry. Real room lists put two
    students side by side ("Roll No | Room No | | Roll No | Room No"), so take the columns nearest to
    your cell, to the right first, never just the first Room column."""
    out = {}
    pat = roll_pattern(needle) if needle else None
    mine = next((i for i, c in enumerate(row) if pat and pat.search(str(c))), None)
    order = list(range(len(row)))
    if mine is not None:
        order = sorted(order, key=lambda j: (j < mine, abs(j - mine)))
        h = header[mine] if mine < len(header) else ""
        if h and not re.search(r"roll|name|s\.?\s*no|sl\b|^no\.?$", h, re.I):
            out["column"] = h  # e.g. a shortlist with one column per role: "SDE-1"
    for j in order:
        h = header[j] if j < len(header) else ""
        v = row[j] if j < len(row) else ""
        if not v or j == mine:
            continue
        if ROOM_HDR.search(h) and "room" not in out:
            out["room"] = v
        elif SLOT_HDR.search(h) and "slot" not in out:
            out["slot"] = v
        elif DATE_HDR.search(h) and "date" not in out:
            out["date"] = v
        elif TIME_HDR.search(h) and "time" not in out:
            out["time"] = v
            if re.search(r"report", h, re.I):
                out["time_is"] = "reporting"     # "Reporting Time": when to be there, not when the test starts
    if "room" not in out:
        rest = " ".join(str(c) for k, c in enumerate(row) if k != mine or len(row) == 1)
        if needle:
            rest = roll_pattern(needle).sub(" ", rest)
        m = ROOM_TOKEN.search(rest)
        if m:
            out["room"] = m.group(0)
    return out


def _context_details(context: str) -> dict:
    out = {}
    m = re.search(r"(?:Room|Venue|Lab|Hall)\s*(?:No\.?)?\s*[:\-]\s*([A-Za-z0-9][\w\- /,]{0,40}\d[\w\-]*)", context)
    if m:
        out["room_or_venue_from_heading"] = m.group(1).strip()
    m = re.search(r"(Slot|Batch|Session|Panel)\s*[:\-]?\s*(\w{1,10})", context, re.I)
    if m:
        out["slot_from_heading"] = f"{m.group(1)} {m.group(2)}"
    m = re.search(r"\d{1,2}(?::\d{2})?\s*[AP]\.?M\.?(?:\s*(?:-|to|–)\s*\d{1,2}(?::\d{2})?\s*[AP]\.?M\.?)?", context, re.I)
    if m:
        out["time_from_heading"] = m.group(0)
    return out


def _looks_like_header(row: list[str]) -> bool:
    filled = [c for c in row if c]
    if len(filled) < 2:          # one cell across the table is a section ("Slot 2: 2:00 PM"), not the header
        return False
    alpha = sum(1 for c in filled if re.search(r"[A-Za-z]", c) and not ROLL_LIKE.search(c))
    return alpha == len(filled) and any(re.search(r"roll|name|s\.?\s*no|sl|room|venue|slot|dept|time", c, re.I)
                                        for c in filled)


# ---------------------------------------------------------------- readers

def _read_pdf(data: bytes) -> dict:
    import pdfplumber
    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for p in pdf.pages:
            text = p.extract_text() or ""
            try:
                raw = p.extract_tables()
            except Exception:
                raw = []
            tables = [[[_norm_cell(c) for c in row] for row in t] for t in raw]
            # None = a cell covered by a merged cell above it (pdfplumber); "" = a cell that is really empty
            merged = [[[c is None for c in row] for row in t] for t in raw]
            pages.append({"text": text, "tables": tables, "merged": merged, "images": len(p.images)})
    return {"format": "pdf", "pages": pages}


def _read_xlsx(data: bytes) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    pages = []
    for ws in wb.worksheets:
        rows = [[_norm_cell(c) for c in r] for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(r)]
        pages.append({"text": "\n".join(" ".join(r) for r in rows), "tables": [rows] if rows else [], "images": 0,
                      "sheet": ws.title})
    return {"format": "xlsx", "pages": pages}


def _ocr_available() -> bool:
    if shutil.which("tesseract"):
        return True
    if os.environ.get("CI") and shutil.which("sudo"):
        # GitHub's machines allow installing it on demand (~30s, only when a scanned file shows up)
        try:
            subprocess.run(["sudo", "apt-get", "install", "-y", "-qq", "tesseract-ocr"], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
        except Exception:
            return False
    return bool(shutil.which("tesseract"))


def _ocr_pdf(data: bytes) -> list[str]:
    import pypdfium2 as pdfium
    import pytesseract
    texts = []
    doc = pdfium.PdfDocument(data)
    for i in range(len(doc)):
        img = doc[i].render(scale=2.5).to_pil()
        texts.append(pytesseract.image_to_string(img))
    return texts


# ---------------------------------------------------------------- what kind of document

LIST_NOTICE_KINDS = ("test", "test_rooms", "shortlist", "result")
# a list of students: never a JD, whatever else it says
LISTY = re.compile(r"name of (the )?(student|candidate)s?|roll\s*(no|number)|room allocation|seating (plan|arrangement)|"
                   r"list of (the )?(shortlisted|selected|eligible)? ?(students|candidates)|following students|"
                   r"students? (are|have been) (shortlisted|selected)|s\.?\s?no\.?\s+name", re.I)
# what a job description says: at least three different ones
JD_CUES = [re.compile(p, re.I) for p in (
    r"job description|\bjd\b", r"responsibilit", r"requirements?|must[- ]have|what we('re| are) looking for",
    r"qualifications?|eligibility|who can apply", r"about (the )?(role|company|us|team)|role overview|the role",
    r"what you('ll| will) (do|work on)|day[- ]to[- ]day|you will", r"skills?( required| set)?|competenc",
    r"\bctc\b|compensation|stipend|salary|package", r"location|work mode|on[- ]?site|hybrid|remote",
    r"designation|job title|position|profile:", r"experience|years? of", r"selection process|interview rounds?|hiring process")]
PHONE_OR_MAIL = re.compile(r"(\+?91[\s\-]?)?(?<![\d\-./])\d(?:[\s\-.]?\d){9}(?![\s\-.]?\d)|[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def classify(text: str, roll_like_count: int) -> str:
    """'jd' (a job description: safe to keep whole), 'list' (lists students: only your row is kept) or 'other'."""
    if roll_like_count > 0 or LISTY.search(text or ""):
        return "list"
    cues = sum(1 for c in JD_CUES if c.search(text or ""))
    return "jd" if cues >= 3 and len((text or "").strip()) >= 200 else "other"


def jd_document(text: str) -> str:
    """A JD's text as kept: no phone numbers or email addresses (a recruiter's contact isn't needed), tidy."""
    from .jd import clean
    return clean(PHONE_OR_MAIL.sub("[contact removed]", text or ""))[:60000]


def sniff(data: bytes, content_type: str = "") -> str:
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:2] == b"PK":
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
            if any(n.startswith("xl/") for n in names):
                return "xlsx"
            if any(n.startswith("word/") for n in names):
                return "docx"
        except zipfile.BadZipFile:
            pass
    head = data[:400].lower()
    if b"<html" in head or b"<!doctype" in head:
        return "html"
    return content_type.split(";")[0] or "unknown"


# ---------------------------------------------------------------- check

def check_attachment(data: bytes, roll: str, name: str = "", content_type: str = "", also: list[str] | None = None,
                     notice_kind: str | None = None) -> dict:
    """also: other spellings of your roll to look for (your ERP login id when the profile has a roll of its own).
    notice_kind: the notice's kind; a list notice's file (shortlist, test, rooms, result) is never taken for a JD."""
    roll = (roll or "").strip().upper()
    others = [r.strip().upper() for r in (also or []) if r and r.strip().upper() != roll]
    fmt = sniff(data, content_type)
    result = {"status": "unknown", "matched_by": None, "format": fmt, "pages": 0, "text_chars": 0,
              "scanned": False, "ocr": False, "roll_like_count": 0, "header": None, "my_row": None,
              "context": None, "section": None, "details": {}, "error": None, "reliability": None}
    try:
        if fmt == "pdf":
            doc = _read_pdf(data)
        elif fmt == "xlsx":
            doc = _read_xlsx(data)
        elif fmt == "docx" and notice_kind not in LIST_NOTICE_KINDS:
            # a Word file on a notice is usually a JD: read it as one, never as a list
            from .jd import docx_text
            text = docx_text(data)
            result["text_chars"] = len(text.strip())
            result["roll_like_count"] = len(set(ROLL_LIKE.findall(text.upper())))
            if classify(text, result["roll_like_count"]) == "jd":
                result.update(status="jd", reliability="a job description: kept whole (no students listed)",
                              context=jd_document(text))
            else:
                result["error"] = "a Word file that isn't a job description"
            return result
        else:
            result["error"] = f"not a PDF or Excel file ({fmt})"
            return result
    except Exception as e:
        result["error"] = f"could not open file: {type(e).__name__}"
        return result

    pages = doc["pages"]
    result["pages"] = len(pages)
    all_text = "\n".join(p["text"] for p in pages)
    result["text_chars"] = len(all_text.strip())

    if fmt == "pdf" and result["text_chars"] < 30 * max(1, len(pages)) and any(p["images"] for p in pages):
        result["scanned"] = True
        if _ocr_available():
            try:
                texts = _ocr_pdf(data)
                for p, t in zip(pages, texts):
                    p["text"] = t
                all_text = "\n".join(texts)
                result["ocr"] = True
                result["text_chars"] = len(all_text.strip())
            except Exception as e:
                result["error"] = f"OCR failed: {type(e).__name__}"
        else:
            result["error"] = "scanned PDF and OCR is not available here"

    if result["text_chars"] < 10:
        result["error"] = result["error"] or "no readable text"
        return result

    result["roll_like_count"] = len(set(ROLL_LIKE.findall(all_text.upper())))
    # a job description (no student in it): kept whole, linked to the company's roles (ping/notice_jd.py)
    if notice_kind not in LIST_NOTICE_KINDS and classify(all_text, result["roll_like_count"]) == "jd":
        result.update(status="jd", reliability="a job description: kept whole (no students listed)", context=jd_document(all_text))
        return result

    found = None
    for r in [roll, *others]:
        if not r:
            continue
        found = _find_in_tables(pages, r, by="roll")
        if not found and roll_pattern(r).search(all_text):
            found = _find_in_text(pages, r, by="roll") or \
                {"matched_by": "roll", "header": None, "my_row": None, "context": "roll number found (split across lines)"}
        if found:
            if r != roll:
                roll = r                      # the room / slot next to it are read against this spelling
            break
    if not found and name:
        found = _find_in_tables(pages, name, by="name") or _find_in_text(pages, name, by="name")
    if not found and name:
        # one typo per name part (5+ letters): "Studnet" for "Student"; said so in the result
        found = _find_in_tables(pages, name, by="name", fuzzy=True) or _find_in_text(pages, name, by="name", fuzzy=True)

    if found:
        result.update({k: v for k, v in found.items() if k != "details"})
        result["status"] = "yes"
        det = {}
        if found.get("my_row"):
            needle = roll if found.get("matched_by") == "roll" else ""
            det.update(_details_from(found.get("header") or [], found["my_row"], needle))
        if found.get("context"):
            det.update({k: v for k, v in _context_details(found["context"]).items() if k not in det})
        if "room" not in det and "room_or_venue_from_heading" not in det and found.get("section"):
            m = ROOM_TOKEN.search(found["section"])          # "Beta Bank - Written Test, 2:00 PM, Room NR 422"
            if m:
                det["room_or_venue_from_heading"] = m.group(0)
        if found.get("section"):
            det["section"] = found["section"][:160]   # stored inside details (pdf_checks.details): the run re-reads it
        result["details"] = det
        result["reliability"] = "found"
    else:
        # not found: say so only for a file read in full that lists students by roll number
        blank = [i + 1 for i, p in enumerate(pages) if len((p["text"] or "").strip()) < 20 and not p["tables"]]
        if result["scanned"]:
            why = "scanned file (read by OCR, which can misread roll numbers)"
        elif blank:
            why = f"page {', '.join(map(str, blank))} had no readable text"
        elif result["roll_like_count"] == 0:
            why = "the list has no roll numbers (names only?)"
        else:
            why = None
        if why:
            result["status"] = "unknown"
            result["reliability"] = why
            result["error"] = result["error"] or why
        else:
            result["status"] = "no"
            result["reliability"] = "read in full"
    return result


def _is_section(row: list[str]) -> bool:
    """A row with one text across the table ("Slot 2: 2:00 PM - 3:00 PM"): a section of the list, not a student."""
    filled = [c for c in row if c]
    return bool(filled) and len(set(filled)) == 1 and not ROLL_LIKE.search(filled[0].upper()) and len(filled[0]) < 160


def _matcher(needle: str, by: str, fuzzy: bool):
    if by == "roll":
        pat = roll_pattern(needle)
        return lambda cells: any(pat.search(c) for c in cells) or bool(pat.search(" ".join(cells)))
    return lambda cells: _row_has_name(cells, needle, fuzzy)


def _found(by: str, fuzzy: bool) -> str:
    return "name (close spelling)" if by == "name" and fuzzy else by


def _find_in_tables(pages, needle: str, by: str, fuzzy: bool = False) -> dict | None:
    hit = _matcher(needle, by, fuzzy)
    header = None            # carried over: a table that breaks across pages keeps the header of its first page
    for p in pages:
        for ti, t in enumerate(p["tables"]):
            if header is not None and t and len(t[0]) != len(header):
                header = None    # a different table
            merged = (p.get("merged") or [])[ti] if ti < len(p.get("merged") or []) else None
            section = None
            for k, row in enumerate(t):
                if _looks_like_header(row) or (k == 0 and header is None and _column_titles(t)):
                    header, section = row, None
                    continue
                if _is_section(row):
                    section = next(c for c in row if c)
                    continue
                if hit(row):
                    mine = _fill_merged(t, merged, k, header)
                    key = lambda line: hit([line])  # noqa: E731
                    above = _headings_above(p["text"], key)
                    ctx = ([section] if section else []) + above
                    return {"matched_by": _found(by, fuzzy), "header": header, "my_row": mine,
                            "context": "\n".join(ctx)[:400] or None, "section": section or (above[0] if above else None)}
    return None


def _column_titles(t: list[list[str]]) -> bool:
    """A first row of titles without the usual words ("PA | SDE-1 | MLE": one column per role): no roll number
    in it, and roll numbers in the rows below. Never a row that could be a student."""
    first = t[0] if t else []
    return (len([c for c in first if c]) >= 2 and not any(ROLL_LIKE.search(c.upper()) for c in first)
            and any(ROLL_LIKE.search(" ".join(r).upper()) for r in t[1:]))


def _fill_merged(t: list[list[str]], merged, k: int, header) -> list[str]:
    """Your row, with a room / slot / time that the PDF shows once for several rows (a merged cell) filled in
    from the row that carries it. Only cells the PDF really merged; a cell that is just empty stays empty."""
    row = list(t[k])
    if not header or not merged or k >= len(merged):
        return row
    for j, v in enumerate(row):
        if v or j >= len(header) or j >= len(merged[k]) or not merged[k][j]:
            continue
        if not (ROOM_HDR.search(header[j]) or SLOT_HDR.search(header[j]) or TIME_HDR.search(header[j]) or DATE_HDR.search(header[j])):
            continue
        for up in range(k - 1, -1, -1):
            if _looks_like_header(t[up]) or _is_section(t[up]):
                break
            if j < len(t[up]) and t[up][j] and not (j < len(merged[up]) and merged[up][j]):
                row[j] = t[up][j]
                break
    return row


def _find_in_text(pages, needle: str, by: str, fuzzy: bool = False) -> dict | None:
    hit = _matcher(needle, by, fuzzy)
    for p in pages:
        lines = p["text"].splitlines()
        for i, line in enumerate(lines):
            if hit([line]):
                header = None
                for back in range(i - 1, -1, -1):
                    if re.search(r"roll|name", lines[back], re.I) and not ROLL_LIKE.search(lines[back].upper()):
                        header = [lines[back].strip()]
                        break
                above = [l.strip() for l in reversed(lines[max(0, i - 60):i]) if _is_heading(l)][:4]
                return {"matched_by": _found(by, fuzzy), "header": header, "my_row": [line.strip()],
                        "context": "\n".join(above)[:400] or None, "section": above[0] if above else None}
    return None


def _headings_above(page_text: str, is_mine) -> list[str]:
    """Heading lines above your row on the page (slot, room, test, company), nearest first; never a line that
    could be another student's entry."""
    lines = page_text.splitlines()
    for i, line in enumerate(lines):
        if is_mine(line):
            return [l.strip() for l in reversed(lines[max(0, i - 60):i]) if _is_heading(l)][:4]
    return []


HEADING_WORDS = re.compile(r"slot|room|venue|batch|session|time|date|test|shortlist|round|panel|lab|hall|"
                           r"floor|block|complex|assessment|interview|reporting", re.I)


def _is_heading(line: str) -> bool:
    """Only keep lines that look like headings, never lines that could be another student's entry."""
    line = line.strip()
    return bool(line) and not ROLL_LIKE.search(line.upper()) and bool(HEADING_WORDS.search(line)) and len(line) < 160


def refresh_details(check: dict, roll: str) -> dict:
    """Re-read room/slot/time from a saved check (your row + heading only) with today's rules, so a fix
    to the reading (e.g. which of two side-by-side room columns is yours) also corrects older files."""
    if not check or check.get("status") != "yes" or not (check.get("my_row") or check.get("context")):
        return check
    det = {}
    if check.get("my_row"):
        needle = (roll or "").strip().upper() if check.get("matched_by") == "roll" else ""
        det.update(_details_from(check.get("header") or [], check["my_row"], needle))
    if check.get("context"):
        det.update({k: v for k, v in _context_details(check["context"]).items() if k not in det})
    if (check.get("details") or {}).get("section"):
        det["section"] = check["details"]["section"]      # which section of the file lists you: kept as read
    check["details"] = det
    return check


# ---------------------------------------------------------------- inspection (diagnosis; structure only)

def _shape(tok: str) -> str:
    """"22XY10042" -> "DDLLDDDDD": how a roll number is written, never the roll itself."""
    return re.sub(r"\d", "D", re.sub(r"[A-Z]", "L", tok.upper()))


def _dist(a: str, b: str) -> int:
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev, d[j] = d[j], cur
    return d[-1]


def inspect(data: bytes, roll: str, name: str = "", content_type: str = "", ocr: bool = True) -> dict:
    """What a list file is made of and how your roll appears in it, for a diagnosis. Counts and shapes only:
    nothing about any other student (no rolls, no names, no rows) is returned."""
    roll = (roll or "").strip().upper()
    fmt = sniff(data, content_type)
    out = {"format": fmt, "bytes": len(data), "pages": [], "roll_shapes": {}, "my_roll_shape": _shape(roll),
           "found": {}, "nearest_roll_distance": None, "error": None}
    try:
        doc = _read_pdf(data) if fmt == "pdf" else _read_xlsx(data) if fmt == "xlsx" else None
    except Exception as e:
        out["error"] = f"could not open: {type(e).__name__}"
        return out
    if doc is None:
        out["error"] = f"not a PDF or Excel file ({fmt})"
        return out
    texts = []
    for i, p in enumerate(doc["pages"]):
        t = p["text"]
        rows = sum(len(tb) for tb in p["tables"])
        cells = " ".join(" ".join(r) for tb in p["tables"] for r in tb)
        out["pages"].append({"page": i + 1, "text_chars": len(t.strip()), "images": p.get("images", 0),
                             "tables": len(p["tables"]), "table_rows": rows,
                             "roll_like_text": len(set(ROLL_LIKE.findall(t.upper()))),
                             "roll_like_tables": len(set(ROLL_LIKE.findall(cells.upper())))})
        texts.append(t + "\n" + cells)
    if ocr and fmt == "pdf" and any(p["images"] for p in out["pages"]) and _ocr_available():
        try:
            o = _ocr_pdf(data)
            for pg, t in zip(out["pages"], o):
                pg["ocr_chars"] = len(t.strip())
                pg["roll_like_ocr"] = len(set(ROLL_LIKE.findall(t.upper())))
            texts += o
            out["ocr"] = True
        except Exception as e:
            out["ocr_error"] = type(e).__name__
    allt = "\n".join(texts)
    up = allt.upper()
    toks = set(re.findall(r"\b[0-9]{2}[A-Z0-9]{2,3}[A-Z0-9]{4,6}\b", up))
    shapes: dict[str, int] = {}
    for tk in toks:
        shapes[_shape(tk)] = shapes.get(_shape(tk), 0) + 1
    out["roll_shapes"] = dict(sorted(shapes.items(), key=lambda kv: -kv[1])[:6])
    if roll:
        compact_text = re.sub(r"[\s\-./_]", "", up)
        out["found"] = {
            "roll_pattern": bool(roll_pattern(roll).search(allt)),
            "roll_ignoring_spaces": roll in compact_text,
            "roll_digits_only": bool(re.search(rf"(?<!\d){re.escape(re.sub(r'[^0-9]', '', roll))}(?!\d)", compact_text)),
            "roll_last5": bool(re.search(rf"(?<!\d){re.escape(roll[-5:])}(?!\d)", up)),
        }
        cand = [t for t in toks if len(t) == len(roll)]
        out["nearest_roll_distance"] = min((_dist(roll, t) for t in cand), default=None)
        # tokens that end in your roll's last five digits: how they differ from yours, position by position
        # ("=" same, "x" different), never the token itself
        tail = [t for t in toks if t.endswith(roll[-5:])]
        out["same_last5"] = [{"shape": _shape(t), "diff": "".join("=" if i < len(roll) and roll[i] == c else "x" for i, c in enumerate(t)),
                              "edits": _dist(roll, t)} for t in tail][:3]
    if name:
        words = set(re.findall(r"[a-z]+", allt.lower()))
        parts = [p for p in re.split(r"\s+", name.lower()) if len(p) > 1]
        out["found"]["name_parts"] = f"{sum(p in words for p in parts)}/{len(parts)}"
    out["roll_like_total"] = len(set(ROLL_LIKE.findall(up)))
    return out
