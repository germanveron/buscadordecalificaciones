FROM python:3.12-slim

# Las fechas del Sheet están en hora de Europa central; el contenedor usa la misma.
ENV TZ=Europe/Berlin \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY core ./core
COPY tools ./tools

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Un solo worker: la sincronización semanal corre dentro del proceso y no debe duplicarse.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
