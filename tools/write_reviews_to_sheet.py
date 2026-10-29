"""Vuelca .tmp/reviews_<app_id>.json en la pestaña indicada de un Google Sheet (reemplaza el contenido)."""
import argparse
import json
import os
from pathlib import Path

import gspread
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CHUNK = 5000
HEADERS = [
    "usuario", "calificación", "reseña", "fecha",
    "útiles", "respuesta de Personal Pay", "fecha de respuesta", "versión de la app",
]


def row(r):
    return [
        r.get("userName") or "",
        r.get("score") or "",
        r.get("content") or "",
        (r.get("at") or "")[:16],
        r.get("thumbsUpCount") or 0,
        r.get("replyContent") or "",
        (r.get("repliedAt") or "")[:16],
        r.get("reviewCreatedVersion") or "",
    ]


def main():
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("--app-id", default=os.getenv("APP_ID"))
    p.add_argument("--spreadsheet-id", default=os.getenv("SPREADSHEET_ID"))
    p.add_argument("--worksheet", default=None, help="Nombre de la pestaña (por defecto la primera)")
    p.add_argument("--replace", action="store_true", help="BORRA toda la pestaña antes de escribir")
    a = p.parse_args()
    if not a.replace:
        raise SystemExit(
            "Este script borra toda la pestaña, incluidas las columnas de categoría y sentimiento. "
            "Para agregar solo reseñas nuevas usá core/sheets.py (modo privado de la web o tools/weekly_sync.py). "
            "Si de verdad querés reemplazar todo, agregá --replace."
        )

    data = json.loads((ROOT / ".tmp" / f"reviews_{a.app_id}.json").read_text(encoding="utf-8"))
    rows = [HEADERS] + [row(r) for r in data]

    gc = gspread.oauth(
        credentials_filename=str(ROOT / "credentials.json"),
        authorized_user_filename=str(ROOT / "token.json"),
    )
    sh = gc.open_by_key(a.spreadsheet_id)
    ws = sh.worksheet(a.worksheet) if a.worksheet else sh.sheet1

    ws.clear()
    if ws.row_count < len(rows):
        ws.resize(rows=len(rows))
    for i in range(0, len(rows), CHUNK):
        ws.update(values=rows[i:i + CHUNK], range_name=f"A{i + 1}", value_input_option="RAW")
    ws.freeze(rows=1)
    print(f"Escritas {len(rows) - 1} reseñas en '{ws.title}'")


if __name__ == "__main__":
    main()
