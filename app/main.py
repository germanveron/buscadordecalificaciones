"""API web: buscar apps, descargar reseñas como tarea en segundo plano y entregar el Excel."""
from __future__ import annotations

import os
import re
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

STATIC = Path(__file__).resolve().parent / "static"
load_dotenv(STATIC.parent.parent / ".env")
# Las fechas del Sheet existente están en hora de Europa central (la de tu compu); el servidor usa la misma para no duplicar
os.environ.setdefault("TZ", "Europe/Berlin")
if hasattr(time, "tzset"):
    time.tzset()

from app import scheduler  # noqa: E402
from core import excel, playstore  # noqa: E402

TMP = Path(tempfile.gettempdir()) / "resenas-playstore"
TMP.mkdir(exist_ok=True)

MAX_CONCURRENT = 3
FILE_TTL = 30 * 60  # los Excel se borran a los 30 minutos
APP_ID_RE = re.compile(r"^[A-Za-z0-9_.]{3,150}$")

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


@asynccontextmanager
async def lifespan(_app):
    scheduler.start_if_enabled()
    yield


app = FastAPI(title="Reseñas de Play Store", lifespan=lifespan)



class JobRequest(BaseModel):
    app_id: str
    country: str = "ar"
    since: Optional[date] = None
    until: Optional[date] = None


def _cleanup() -> None:
    now = time.time()
    with LOCK:
        for jid in [j for j, v in JOBS.items() if now - v["created"] > FILE_TTL]:
            (TMP / f"{jid}.xlsx").unlink(missing_ok=True)
            del JOBS[jid]


def _run(jid: str, req: JobRequest) -> None:
    job = JOBS[jid]
    try:
        rows, truncated = playstore.fetch_reviews(
            req.app_id, req.country, req.since, req.until,
            on_progress=lambda n: job.update(count=n),
            should_cancel=lambda: job["status"] == "cancelled",
        )
        job.update(message="Armando el Excel…")
        excel.build_xlsx(TMP / f"{jid}.xlsx", rows)
        if job["status"] != "cancelled":
            job.update(status="done", count=len(rows), truncated=truncated, message="")
    except playstore.Cancelled:
        pass
    except Exception as e:
        if job["status"] == "cancelled":
            return
        msg = "No se encontró la app en ese país." if e.__class__.__name__ == "NotFoundError" else \
            "Google Play no respondió. Probá de nuevo en un momento."
        job.update(status="error", message=msg)


@app.get("/api/config")
def config():
    return {
        "min_date": playstore.MIN_DATE.isoformat(),
        "max_reviews": playstore.MAX_REVIEWS,
        "countries": [{"code": c, "name": n} for c, (n, _) in playstore.COUNTRIES.items()],
    }


@app.get("/api/search")
def search(q: str, country: str = "ar"):
    q = q.strip()
    if len(q) < 2:
        return []
    if country not in playstore.COUNTRIES:
        raise HTTPException(400, "País no soportado")
    try:
        return playstore.search_apps(q, country)
    except Exception:
        raise HTTPException(502, "No se pudo buscar en Google Play")


@app.post("/api/jobs")
def create_job(req: JobRequest):
    if not APP_ID_RE.match(req.app_id):
        raise HTTPException(400, "ID de app inválido")
    if req.country not in playstore.COUNTRIES:
        raise HTTPException(400, "País no soportado")
    if req.since and req.until and req.since > req.until:
        raise HTTPException(400, "La fecha 'desde' es posterior a 'hasta'")
    _cleanup()
    with LOCK:
        if sum(1 for j in JOBS.values() if j["status"] == "running") >= MAX_CONCURRENT:
            raise HTTPException(429, "Hay varias descargas en curso. Probá en un minuto.")
        jid = uuid.uuid4().hex
        JOBS[jid] = {
            "status": "running", "count": 0, "message": "Descargando…",
            "truncated": False, "created": time.time(), "app_id": req.app_id,
            "since": (max(req.since or playstore.MIN_DATE, playstore.MIN_DATE)).isoformat(),
            "until": req.until.isoformat() if req.until else date.today().isoformat(),
        }
    threading.Thread(target=_run, args=(jid, req), daemon=True).start()
    return {"id": jid}


@app.get("/api/jobs/{jid}")
def job_status(jid: str):
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(404, "La descarga expiró. Iniciá una nueva.")
    return {k: v for k, v in job.items() if k != "created"}


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str):
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(404, "La descarga expiró.")
    if job["status"] == "running":
        job.update(status="cancelled", message="Descarga detenida.")
    return {"status": job["status"]}


_ICON_HOST = "play-lh.googleusercontent.com"
_ICONS: dict[str, tuple[bytes, str]] = {}


@app.get("/api/icon")
def icon(url: str):
    """Sirve los logos desde el servidor: la CDN de Google bloquea (429) cuando el navegador pide muchos juntos."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != _ICON_HOST:
        raise HTTPException(400, "URL de icono no permitida")
    if url not in _ICONS:
        try:
            req = Request(url + "=s96" if "=" not in url else url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=8) as r:
                _ICONS[url] = (r.read(), r.headers.get("Content-Type", "image/png"))
        except Exception:
            raise HTTPException(404, "Icono no disponible")
        if len(_ICONS) > 300:
            _ICONS.pop(next(iter(_ICONS)))
    data, ctype = _ICONS[url]
    return Response(data, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/jobs/{jid}/download")
def download(jid: str):
    job = JOBS.get(jid)
    path = TMP / f"{jid}.xlsx"
    if not job or job["status"] != "done" or not path.exists():
        raise HTTPException(404, "El archivo ya no está disponible. Iniciá una nueva descarga.")
    name = f"resenas_{job['app_id']}_{job['since']}_{job['until']}.xlsx"
    return FileResponse(
        path, filename=name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
