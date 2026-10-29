"""Sincronización semanal automática (domingo 22:00, hora de TZ) dentro del mismo servidor."""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from core import sheets

STATE: dict = {"enabled": False, "next_run": None, "last": None}


def next_run(now: datetime) -> datetime:
    target = now.replace(hour=22, minute=0, second=0, microsecond=0)
    target += timedelta(days=(6 - now.weekday()) % 7)  # domingo
    if target <= now:
        target += timedelta(days=7)
    return target


def _loop(app_id: str) -> None:
    while True:
        STATE["next_run"] = next_run(datetime.now()).isoformat(timespec="minutes")
        while datetime.now().isoformat(timespec="minutes") < STATE["next_run"]:
            time.sleep(30)
        started = datetime.now().isoformat(timespec="minutes")
        try:
            result = sheets.run_sync(app_id, days=14)
            STATE["last"] = {"at": started, "ok": True, **result}
            print(f"[sync semanal {started}] leídas {result['read']}, nuevas {result['added']}, ya existían {result['skipped']}", flush=True)
        except Exception as e:  # el próximo domingo reintenta
            STATE["last"] = {"at": started, "ok": False, "error": str(e)[:200]}
            print(f"[sync semanal {started}] ERROR: {e}", flush=True)
        time.sleep(61)


def start_if_enabled() -> Optional[threading.Thread]:
    app_id = os.getenv("PRIVATE_APP_ID", "ar.com.personalpay")
    if os.getenv("WEEKLY_SYNC") != "1" or not sheets.is_configured():
        return None
    STATE["enabled"] = True
    t = threading.Thread(target=_loop, args=(app_id,), daemon=True)
    t.start()
    return t
