# Образ застосунку. Контекст збірки — корінь репозиторію:
#   docker compose -f deploy/docker-compose.yml build
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Залежності окремим шаром: зміна коду не змушує pip ставити пакети знову.
COPY pyproject.toml /app/pyproject.toml
COPY app/__init__.py /app/app/__init__.py
RUN pip install .

COPY app /app/app
COPY migrations /app/migrations
COPY alembic.ini /app/alembic.ini
COPY scripts /app/scripts
COPY deploy/entrypoint.py /app/entrypoint.py

EXPOSE 8000

# liveness без бази: той самий маршрут, який потім опитуватиме балансувальник.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

ENTRYPOINT ["python", "/app/entrypoint.py"]
