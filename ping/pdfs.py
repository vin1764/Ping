"""Check a notice attachment (shortlist, room allocation, schedule) for YOU.

Only your own row and the table heading are kept. The rest of the file
(hundreds of other students' names) is never stored or sent anywhere.

Result status:
  yes      your roll number (or, as a fallback, your name) is in it
  no       the file was read and you are not in it
  unknown  the file could not be read at all
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


def _row_has(row: list[str], roll: str) -> bool:
    return any(re.search(rf"\b{re.escape(roll)}\b", c, re.I) for c in row) or \
        roll.lower() in "".join(row).replace(" ", "").lower()


def _row_has_name(row: list[str], name: str) -> bool:
    parts = [p for p in re.split(r"\s+", name.lower()) if len(p) > 1]
    joined = " ".join(row).lower()
    return bool(parts) and all(re.search(rf"\b{re.escape(p)}\b", joined) for p in parts)


ROOM_TOKEN = re.compile(r"\b(?:NC|NR|LH|CR|V|S|F|G)\s?-?\d{1,4}[A-Z]?\b")


def _details_from(header: list[str], row: list[str], needle: str = "") -> dict:
    """Read room/slot/date/time from the columns that belong to YOUR entry. Real room lists put two
    students side by side ("Roll No | Room No | | Roll No | Room No"), so take the columns nearest to
    your cell, to the right first, never just the first Room column."""
    out = {}
    mine = next((i for i, c in enumerate(row) if needle and needle.lower() in str(c).replace(" ", "").lower()), None)
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
    if "room" not in out:
        rest = " ".join(str(c) for k, c in enumerate(row) if k != mine or len(row) == 1)
        if needle:
            rest = re.sub(re.escape(needle), " ", rest, flags=re.I)
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
    if not filled:
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
                tables = [[[_norm_cell(c) for c in row] for row in t] for t in p.extract_tables()]
            except Exception:
                tables = []
            pages.append({"text": text, "tables": tables, "images": len(p.images)})
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

def check_attachment(data: bytes, roll: str, name: str = "", content_type: str = "") -> dict:
    roll = (roll or "").strip().upper()
    fmt = sniff(data, content_type)
    result = {"status": "unknown", "matched_by": None, "format": fmt, "pages": 0, "text_chars": 0,
              "scanned": False, "ocr": False, "roll_like_count": 0, "header": None, "my_row": None,
              "context": None, "details": {}, "error": None}
    try:
        if fmt == "pdf":
            doc = _read_pdf(data)
        elif fmt == "xlsx":
            doc = _read_xlsx(data)
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

    found = _find_in_tables(pages, roll, by="roll")
    if not found and roll and re.search(rf"\b{re.escape(roll)}\b", all_text, re.I):
        found = _find_in_text(pages, roll, by="roll")
    if not found and roll and roll.lower() in re.sub(r"\s+", "", all_text).lower():
        found = {"matched_by": "roll", "header": None, "my_row": None, "context": "roll number found (split across lines)"}
    if not found and name:
        found = _find_in_tables(pages, name, by="name") or _find_in_text(pages, name, by="name")

    if found:
        result.update({k: v for k, v in found.items() if k != "details"})
        result["status"] = "yes"
        det = {}
        if found.get("my_row"):
            needle = roll if found.get("matched_by") == "roll" else ""
            det.update(_details_from(found.get("header") or [], found["my_row"], needle))
        if found.get("context"):
            det.update({k: v for k, v in _context_details(found["context"]).items() if k not in det})
        result["details"] = det
    else:
        result["status"] = "no"
    return result


def _find_in_tables(pages, needle: str, by: str) -> dict | None:
    for p in pages:
        for t in p["tables"]:
            header = None
            for row in t:
                if _looks_like_header(row):
                    header = row
                    continue
                hit = _row_has(row, needle) if by == "roll" else _row_has_name(row, needle)
                if hit:
                    ctx = _heading_above(p["text"], row)
                    return {"matched_by": by, "header": header or (t[0] if t and t[0] is not row else None),
                            "my_row": row, "context": ctx}
    return None


def _find_in_text(pages, needle: str, by: str) -> dict | None:
    for p in pages:
        lines = p["text"].splitlines()
        for i, line in enumerate(lines):
            hit = re.search(rf"\b{re.escape(needle)}\b", line, re.I) if by == "roll" else _row_has_name([line], needle)
            if hit:
                header = None
                for back in range(i - 1, -1, -1):
                    if re.search(r"roll|name", lines[back], re.I):
                        header = [lines[back].strip()]
                        break
                ctx = "\n".join(l for l in lines[max(0, i - 40):i] if _is_heading(l))
                return {"matched_by": by, "header": header, "my_row": [line.strip()], "context": ctx[-400:] or None}
    return None


def _heading_above(page_text: str, row: list[str]) -> str | None:
    """Text lines above your row that are not other students' rows (slot / room headings)."""
    lines = page_text.splitlines()
    key = next((c for c in row if c), "")
    for i, line in enumerate(lines):
        if key and key in line:
            above = [l for l in lines[max(0, i - 40):i] if _is_heading(l)]
            return "\n".join(above[-4:])[-400:] or None
    return None


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
    check["details"] = det
    return check
