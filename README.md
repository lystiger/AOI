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

## Run Tests

If `pytest` is available in the environment:

```bash
PYTHONPATH=src python3 -m pytest -q
```
