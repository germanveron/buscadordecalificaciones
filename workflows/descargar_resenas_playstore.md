# Descargar y sincronizar reseñas de Play Store

## Objetivo
Tener las reseñas de una app de Google Play en un Excel (uso público) y mantener actualizado un Google Sheet con las de Personal Pay (`ar.com.personalpay`), que alimenta el flujo de n8n de clasificación e informe semanal.

## Piezas
| Pieza | Dónde | Qué hace |
|---|---|---|
| Web pública | `app/`, `core/playstore.py`, `core/excel.py` | Busca apps, descarga reseñas (todas o por período) y entrega un `.xlsx` |
| Sincronización semanal | `app/scheduler.py`, `core/sheets.py` | Domingo 22:00 agrega al Sheet las reseñas nuevas de los últimos 14 días |
| Comando manual | `tools/weekly_sync.py [--days N] [--dry-run]` | Hace lo mismo que la sincronización semanal desde la terminal |
| Flujo n8n | Workflow "Análisis de Reseña Personal Pay" | Lunes 9:00: clasifica la última semana, arma el informe y lo envía por mail |

## Entradas
- **Web:** nombre de la app, país y período (opcional).
- **Sincronización:** variables de entorno `SPREADSHEET_ID`, `WORKSHEET_NAME`, `GOOGLE_SERVICE_ACCOUNT_JSON` (JSON en una línea o en base64), `WEEKLY_SYNC=1` y `TZ=Europe/Berlin`.

## Salidas
- Excel con: usuario, calificación, reseña, fecha, útiles, respuesta del desarrollador, fecha de respuesta y versión de la app.
- Google Sheet (pestaña `PlayStore`): las mismas columnas A-H, más `categoría` y `sentimiento`, que completa n8n.

## Cómo operar
- **Probar sin escribir:** `python tools/weekly_sync.py --dry-run` (en Easypanel, desde la Console de la app).
- **Cargar reseñas pendientes ya:** `python tools/weekly_sync.py`. Una segunda corrida debe dar `nuevas: 0`.
- **Ver el resultado de la sincronización automática:** logs de la app en Easypanel (`[sync semanal ...] leídas X, nuevas Y, ya existían Z`).
- **Despliegue:** `Dockerfile` en la raíz, puerto 8000, **una sola instancia** y sin "zero downtime" (si hay dos procesos, la sincronización corre repetida).

## Reglas y límites
- Solo reseñas desde el 1 de enero de 2025, tope de 50.000 por descarga y 3 descargas simultáneas.
- Los Excel generados se borran a los 30 minutos.
- La sincronización **nunca borra ni modifica** filas existentes. Duplicados: se detectan por usuario + primeros 80 caracteres de la reseña + fecha (hasta el minuto).
- `tools/write_reviews_to_sheet.py` **borra toda la pestaña** y exige `--replace`. Usarlo solo para reconstruir el Sheet desde cero (se pierden las columnas de categoría y sentimiento).

## Lo que aprendimos (casos borde)
- **Fuente no oficial:** `google-play-scraper` usa el servicio interno de Google Play. Si Google lo cambia, hay que actualizar la librería. La API oficial solo da reseñas de apps propias.
- **Rango real:** Google devuelve reseñas hasta unos pocos años atrás (en Personal Pay, desde abril de 2024).
- **Zona horaria:** las fechas del Sheet están en hora de Europa central, no argentina. El servidor debe correr con `TZ=Europe/Berlin`; con otra zona, ninguna reseña coincide y se duplican todas.
- **Por qué 14 días y no 7:** es un margen para cubrir una semana en que la sincronización falle o una reseña aparezca con retraso. Los duplicados no se agregan.
- **Logos:** la CDN de Google devuelve 429 si el navegador pide varios a la vez. Los sirve el servidor (`/api/icon`) y guarda en memoria.
- **Cuenta de servicio:** la autorización OAuth de usuario caduca a los 7 días si la app está en modo "Prueba". Para el servidor se usa cuenta de servicio, con el Sheet compartido como editor.

## Flujo de n8n: configuración que importa
- **Nodo "Code" (filtro):** deja las reseñas de los últimos 7 días con `categoría` y `sentimiento` vacíos. Si no queda ninguna, el flujo termina sin mandar mail.
- **Loop Over Items → Basic LLM Chain (con Structured Output Parser) → Code que une la reseña original con la clasificación → Google Sheets Update Row** (match por `row_number`, *Map Automatically*).
- **No usar un AI Agent** con el Sheet como herramienta: mete las 25.000 filas en el contexto y falla por exceso de tokens.
- **Rama `done`:** Code que agrupa por categoría y sentimiento → Basic LLM Chain que redacta el informe en HTML → Gmail (*Email Type: HTML*, mensaje `{{ $json.text }}`).
- **Ejecuciones manuales largas** pueden cortarse con un 502 del editor. El filtro retoma lo que falta, así que se puede volver a ejecutar sin duplicar.
- **Prueba parcial:** si todo ya está clasificado, el Loop no recibe nada. Para probar solo el mail, usar *Copy to editor* desde Executions y ejecutar desde el nodo que agrupa.
