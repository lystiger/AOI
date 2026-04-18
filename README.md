# AOI

Initial scaffold for the AOI logging and monitoring pipeline.

## Current Scope

This repository currently implements the first milestone from `docs/priority.md`:

- structured inference event schema
- JSONL log writer
- mock inference event generation
- local file-backed logging flow for development
- basic tests for schema and log writing

## Project Layout

```text
src/aoi/
  schema.py
  log_manager.py
  mock_inference.py
  cli.py
tests/
```

## Run Mock Log Generation

Use the local package path when running without installation:

```bash
PYTHONPATH=src python3 -m aoi.cli generate-mock-logs --count 5 --output logs/inference.jsonl
```

This writes newline-delimited JSON records to `logs/inference.jsonl`.

## Docker Stack

The repository includes a local stack for:

- `aoi-app`: continuously emits mock inference logs
- `promtail`: scrapes JSONL logs from the shared volume
- `loki`: stores and indexes logs
- `grafana`: queries and visualizes Loki data

### Start the stack

```bash
docker compose up -d --build
```

### Stop the stack

```bash
docker compose down
```

### Service URLs

- Grafana: `http://localhost:3000`
- Loki: `http://localhost:3100`

Grafana default credentials:

- username: `admin`
- password: `admin`

### Inspect logs

To inspect container status:

```bash
docker compose ps
```

To inspect app logs:

```bash
docker compose logs aoi-app
```

To inspect Promtail logs:

```bash
docker compose logs promtail
```

## Run Tests

If `pytest` is available in the environment:

```bash
PYTHONPATH=src python3 -m pytest -q
```
