"""Búsqueda de apps y descarga de reseñas de Google Play, reutilizable por la web y por los scripts."""
from __future__ import annotations

import time
from datetime import date, datetime
from typing import Callable, Optional

from google_play_scraper import Sort, reviews, search

MIN_DATE = date(2025, 1, 1)  # no se buscan reseñas anteriores
MAX_REVIEWS = 50_000
BATCH = 200
RETRIES = 5

# código de país -> (nombre, idioma de las reseñas)
COUNTRIES = {
    "ar": ("Argentina", "es"),
    "mx": ("México", "es"),
    "cl": ("Chile", "es"),
    "co": ("Colombia", "es"),
    "uy": ("Uruguay", "es"),
    "es": ("España", "es"),
    "br": ("Brasil", "pt"),
    "us": ("Estados Unidos", "en"),
}


class Cancelled(Exception):
    """La descarga fue detenida por el usuario."""


def search_apps(query: str, country: str = "ar", limit: int = 6) -> list[dict]:
    lang = COUNTRIES.get(country, ("", "es"))[1]
    hits = search(query, lang=lang, country=country, n_hits=limit)
    return [
        {
            "app_id": h.get("appId"),
            "title": h.get("title"),
            "developer": h.get("developer"),
            "icon": h.get("icon"),
            "score": round(h["score"], 1) if h.get("score") else None,
        }
        for h in hits
        if h.get("appId")
    ]


def _page(app_id: str, lang: str, country: str, token):
    for attempt in range(RETRIES):
        try:
            return reviews(
                app_id, lang=lang, country=country, sort=Sort.NEWEST,
                count=BATCH, continuation_token=token,
            )
        except Exception as e:
            if attempt == RETRIES - 1 or e.__class__.__name__ == "NotFoundError":
                raise
            time.sleep(2 ** attempt)


def fetch_reviews(
    app_id: str,
    country: str = "ar",
    since: Optional[date] = None,
    until: Optional[date] = None,
    max_reviews: int = MAX_REVIEWS,
    on_progress: Optional[Callable[[int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> tuple[list[dict], bool]:
    """Devuelve (reseñas, truncado). Las reseñas llegan de la más nueva a la más vieja,
    así que la descarga se corta al pasar la fecha 'since'."""
    lang = COUNTRIES.get(country, ("", "es"))[1]
    since_dt = datetime.combine(max(since or MIN_DATE, MIN_DATE), datetime.min.time())
    until_dt = datetime.combine(until, datetime.max.time()) if until else None

    out, seen, token, truncated = [], set(), None, False
    while True:
        if should_cancel and should_cancel():
            raise Cancelled()
        batch, token = _page(app_id, lang, country, token)
        reached_start = False
        for r in batch:
            if r["at"] < since_dt:
                reached_start = True
                continue
            if until_dt and r["at"] > until_dt:
                continue
            if r["reviewId"] in seen:
                continue
            seen.add(r["reviewId"])
            out.append(r)
        if on_progress:
            on_progress(len(out))
        if len(out) >= max_reviews:
            out, truncated = out[:max_reviews], True
            break
        if reached_start or not batch or token is None:
            break
        time.sleep(0.5)
    return out, truncated
