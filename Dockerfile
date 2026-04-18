FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "aoi.cli", "stream-mock-logs", "--batch-size", "5", "--interval-seconds", "5", "--output", "/var/log/aoi/inference.jsonl"]

