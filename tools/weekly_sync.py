"""Agrega al Google Sheet las reseñas nuevas de los últimos N días (sin borrar nada).
Uso: python tools/weekly_sync.py [--days 14] [--dry-run]"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ.setdefault("TZ", "Europe/Berlin")
if hasattr(time, "tzset"):
    time.tzset()

from core import sheets  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--app-id", default=os.getenv("PRIVATE_APP_ID", "ar.com.personalpay"))
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--dry-run", action="store_true", help="Cuenta lo que agregaría sin escribir")
    a = p.parse_args()
    r = sheets.run_sync(a.app_id, days=a.days, dry_run=a.dry_run)
    modo = "SIMULACIÓN, no se escribió nada" if r["dry_run"] else "escrito"
    print(f"Leídas: {r['read']} · nuevas: {r['added']} · ya existían: {r['skipped']} ({modo})")


if __name__ == "__main__":
    main()
