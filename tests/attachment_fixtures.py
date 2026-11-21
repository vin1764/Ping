"""Made-up attachment files in the messy layouts real CDC lists use (no real student appears anywhere).

Built with reportlab so the PDFs have what pdfplumber sees in real files: merged cells, two students side by
side, a table that breaks across pages without repeating its header, section rows inside the table, and
schedules that list several companies' tests on one day.
"""

from __future__ import annotations

import io
import random

ME = "22XY10042"


def others(n: int, seed: int = 7) -> list[str]:
    rnd = random.Random(seed)
    out = []
    while len(out) < n:
        r = f"{rnd.randint(19, 24)}{rnd.choice(['CS', 'EE', 'ME', 'CH', 'MA', 'AE'])}{rnd.randint(10000, 39999)}"
        if r != ME and r not in out:
            out.append(r)
    return out


def table_pdf(rows: list[list[str]], *, title: str = "Assessment room allocation", spans: list = (),
              header_rows: int = 1, repeat_header: bool = False, sections: list[int] = ()) -> bytes:
    """One table that may run over several pages. spans: reportlab SPAN commands ((c0, r0), (c1, r1)).
    sections: row numbers that are full-width section rows ("Slot 2: 2:00 PM")."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=36, bottomMargin=36)
    style = [("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 9),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    style += [("SPAN", a, b) for a, b in spans]
    style += [("SPAN", (0, r), (-1, r)) for r in sections]
    t = LongTable(rows, repeatRows=header_rows if repeat_header else 0)
    t.setStyle(TableStyle(style))
    doc.build([Paragraph(title, getSampleStyleSheet()["Heading2"]), Spacer(1, 8), t])
    return buf.getvalue()


def text_pdf(lines: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in lines:
        if y < 50:
            c.showPage()
            y = 800
        c.setFont("Helvetica-Bold" if not line[:2].isdigit() else "Helvetica", 10)
        c.drawString(50, y, line)
        y -= 16
    c.save()
    return buf.getvalue()


def roster_rows(n: int, me_at: int | None, me_cell: str = ME, room_of=lambda i: f"NC {231 + i % 4}") -> list[list[str]]:
    rolls = others(n)
    rows = [["S.No", "Roll No", "Name", "Room", "Reporting Time"]]
    for i, r in enumerate(rolls, 1):
        rows.append([str(i), r, f"Student {i}", room_of(i), "09:30 AM"])
    if me_at is not None:
        rows.insert(me_at, [str(me_at), me_cell, "DEMO STUDENT", "NR 422", "01:30 PM"])
    return rows


def scanned_pdf(pdf: bytes, scale: float = 2.0) -> bytes:
    """The same pages as images only (no text layer), like a printed list that was scanned."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    images = [doc[i].render(scale=scale).to_pil().convert("RGB") for i in range(len(doc))]
    buf = io.BytesIO()
    images[0].save(buf, "PDF", save_all=True, append_images=images[1:], resolution=72 * scale)
    return buf.getvalue()
