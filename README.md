# Buscador de reseñas en Play Store

Dos piezas que comparten el código de `core/`:

1. **Web pública** (`app/`): se busca una app, se elige "todas" o un período y se baja un Excel con sus reseñas. Solo trae reseñas desde el 1 de enero de 2025, con un máximo de 50.000 por descarga y 3 descargas simultáneas. Los archivos se borran a los 30 minutos.
2. **Sincronización semanal** (`app/scheduler.py`, `core/sheets.py`): los domingos a las 22:00 agrega a un Google Sheet las reseñas nuevas de Personal Pay de los últimos 14 días. No borra ni modifica filas existentes (las columnas de categoría y sentimiento que completa el flujo de n8n quedan intactas). Sin interfaz.

Las reseñas se obtienen con [`google-play-scraper`](https://github.com/JoMingyu/google-play-scraper), que usa el servicio interno de Google Play. No es una API oficial.

## Correr en local

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --port 8001
```

Abrir http://localhost:8001. Para probar la sincronización sin escribir: `python tools/weekly_sync.py --dry-run`.

## Desplegar en Easypanel

1. **Cuenta de servicio de Google** (una sola vez): en Google Cloud, habilitar *Google Sheets API*, crear una cuenta de servicio, generar una clave JSON y compartir el Sheet con el email de esa cuenta como **editor**.
2. En Easypanel, crear una app desde este repositorio de GitHub (build con el `Dockerfile`).
3. Puerto de la app: **8000**.
4. Variables de entorno (ver `.env.example`):

   | Variable | Valor |
   |---|---|
   | `TZ` | `Europe/Berlin` |
   | `WEEKLY_SYNC` | `1` |
   | `SPREADSHEET_ID` | ID del Sheet (la parte larga de la URL) |
   | `WORKSHEET_NAME` | `PlayStore` |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | contenido del JSON de la cuenta de servicio, en una línea |

   Sin `WEEKLY_SYNC` y `SPREADSHEET_ID` la web funciona igual, pero no hay sincronización.
5. Dominio: asignar uno desde la pestaña *Domains*.
6. Instancias: **una sola**. La sincronización semanal corre dentro del proceso, y con más réplicas se ejecutaría varias veces.

El resultado de cada sincronización queda en los logs de la app (`[sync semanal ...] leídas X, nuevas Y, ya existían Z`).

## Estructura

```
app/        servidor web (FastAPI), interfaz y sincronización semanal
core/       búsqueda y descarga de reseñas, Excel y Google Sheets
tools/      scripts de línea de comandos
```
