"""Sincronización con Google Sheets: solo agrega reseñas nuevas, nunca borra ni pisa filas existentes
(las columnas de categoría y sentimiento que se completan desde n8n quedan intactas)."""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import gspread

from core import playstore

ROOT = Path(__file__).resolve().parent.parent
CHUNK = 5000
HEADERS_CHECK = ["usuario", "calificación", "reseña", "fecha"]  # las 4 primeras columnas del Sheet


def is_configured() -> bool:
    return bool(os.getenv("SPREADSHEET_ID"))


def _client():
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return gspread.service_account_from_dict(json.loads(raw))
    path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if path:
        return gspread.service_account(filename=path)
    # Respaldo para desarrollo local: la autorización OAuth de tu usuario
    return gspread.oauth(
        credentials_filename=str(ROOT / "credentials.json"),
        authorized_user_filename=str(ROOT / "token.json"),
    )


def _worksheet():
    sh = _client().open_by_key(os.environ["SPREADSHEET_ID"])
    return sh.worksheet(os.getenv("WORKSHEET_NAME", "PlayStore"))


def _fmt(d) -> str:
    return d.strftime("%Y-%m-%d %H:%M") if d else ""


def _key(usuario, resena, fecha) -> tuple:
    return (str(usuario).strip(), str(resena).strip()[:80], str(fecha).strip()[:16])


def _to_row(r: dict) -> list:
    return [
        r.get("userName") or "",
        r.get("score") or "",
        r.get("content") or "",
        _fmt(r.get("at")),
        r.get("thumbsUpCount") or 0,
        r.get("replyContent") or "",
        _fmt(r.get("repliedAt")),
        r.get("reviewCreatedVersion") or "",
    ]


def append_new_reviews(rows: list[dict], dry_run: bool = False, ws=None) -> dict:
    """Agrega al final del Sheet las reseñas que no estén (comparando usuario, texto y fecha)."""
    ws = ws or _worksheet()
    values = ws.get_values("A:D")
    header = [h.strip().lower() for h in (values[0] if values else [])]
    if header[:4] != HEADERS_CHECK:
        raise RuntimeError(
            "La pestaña no tiene las columnas esperadas (usuario, calificación, reseña, fecha). No se escribió nada."
        )

    seen = set()
    for v in values[1:]:
        v = v + [""] * (4 - len(v))
        seen.add(_key(v[0], v[2], v[3]))

    new_rows = []
    for r in rows:
        row = _to_row(r)
        k = _key(row[0], row[2], row[3])
        if k in seen:
            continue
        seen.add(k)
        new_rows.append(row)

    result = {"read": len(rows), "added": len(new_rows), "skipped": len(rows) - len(new_rows), "dry_run": dry_run}
    if dry_run or not new_rows:
        return result

    start = len(values) + 1
    needed = start + len(new_rows) - 1
    if needed > ws.row_count:
        ws.add_rows(needed - ws.row_count)
    for i in range(0, len(new_rows), CHUNK):
        ws.update(values=new_rows[i:i + CHUNK], range_name=f"A{start + i}", value_input_option="RAW")
    return result


def run_sync(app_id: str, days: int = 14, country: str = "ar", dry_run: bool = False,
             on_progress=None, should_cancel=None) -> dict:
    """Descarga las reseñas de los últimos `days` días y las agrega al Sheet."""
    since: Optional[date] = date.today() - timedelta(days=days)
    rows, _ = playstore.fetch_reviews(
        app_id, country, since=since, on_progress=on_progress, should_cancel=should_cancel,
    )
    return append_new_reviews(rows, dry_run=dry_run)
