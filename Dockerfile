# Práctica 14 · Titicaca Vivo en Render (plan gratis): la app y su MariaDB en el mismo contenedor.
# El arranque está en scripts/nube_arrancar.sh. Lo que no dura (la base) está en render.yaml.
FROM python:3.13-slim-bookworm

# MariaDB 10.11 (Debian 12) y las zonas horarias del sistema
RUN apt-get update \
    && apt-get install -y --no-install-recommends mariadb-server mariadb-client tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Lima \
    FLASK_APP=app:crear_app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN sed -i 's/\r$//' scripts/nube_arrancar.sh

CMD ["sh", "scripts/nube_arrancar.sh"]
