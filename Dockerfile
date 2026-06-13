# Contenedor de captura supercarros -> Postgres (corrida semanal)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && patchright install --with-deps chromium

COPY sv_resolver.py capture_core.py db.py run_capture.py ./

# Corre una vez y termina (el scheduler de easypanel lo dispara semanalmente).
CMD ["python", "run_capture.py"]
