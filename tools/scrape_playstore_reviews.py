"""Descarga todas las reseñas de una app de Google Play y las guarda en .tmp/reviews_<app_id>.json"""
import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google_play_scraper import Sort, reviews

ROOT = Path(__file__).resolve().parent.parent
BATCH = 200
RETRIES = 5


def fetch_all(app_id, lang, country):
    seen, out, token = set(), [], None
    while True:
        for attempt in range(RETRIES):
            try:
                batch, token = reviews(
                    app_id, lang=lang, country=country, sort=Sort.NEWEST,
                    count=BATCH, continuation_token=token,
                )
                break
            except Exception as e:
                wait = 2 ** attempt
                print(f"Error ({e}); reintento en {wait}s")
                time.sleep(wait)
        else:
            raise RuntimeError("Demasiados errores consecutivos")
        for r in batch:
            if r["reviewId"] not in seen:
                seen.add(r["reviewId"])
                out.append(r)
        print(f"{len(out)} reseñas descargadas")
        if not batch or token is None:
            return out
        time.sleep(1)


def main():
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("--app-id", default=os.getenv("APP_ID"))
    p.add_argument("--lang", default="es")
    p.add_argument("--country", default="ar")
    a = p.parse_args()

    data = fetch_all(a.app_id, a.lang, a.country)
    dest = ROOT / ".tmp" / f"reviews_{a.app_id}.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, default=str, indent=1), encoding="utf-8")
    print(f"Guardadas {len(data)} reseñas en {dest}")


if __name__ == "__main__":
    main()
