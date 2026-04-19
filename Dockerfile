FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "aoi.cli", "serve-http", "--host", "0.0.0.0", "--port", "8000", "--output", "/var/log/aoi/inference.jsonl", "--db-path", "/var/lib/aoi/aoi.db", "--storage-path", "/var/lib/aoi/storage"]
