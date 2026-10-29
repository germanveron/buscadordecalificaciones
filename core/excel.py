"""Genera el archivo Excel con las reseñas."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

HEADERS = [
    ("usuario", 22), ("calificación", 12), ("reseña", 70), ("fecha", 18),
    ("útiles", 9), ("respuesta del desarrollador", 50), ("fecha de respuesta", 18),
    ("versión de la app", 16),
]


def build_xlsx(path: Path, rows: list[dict]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Reseñas"
    ws.append([h for h, _ in HEADERS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F6B4F")
    for i, (_, width) in enumerate(HEADERS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

    for r in rows:
        ws.append([
            r.get("userName") or "",
            r.get("score"),
            r.get("content") or "",
            r.get("at"),
            r.get("thumbsUpCount") or 0,
            r.get("replyContent") or "",
            r.get("repliedAt"),
            r.get("reviewCreatedVersion") or "",
        ])
    for row in ws.iter_rows(min_row=2):
        row[2].alignment = Alignment(wrap_text=True, vertical="top")
        row[5].alignment = Alignment(wrap_text=True, vertical="top")
        row[3].number_format = "yyyy-mm-dd hh:mm"
        row[6].number_format = "yyyy-mm-dd hh:mm"

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)
