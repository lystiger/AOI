# AOI

Initial scaffold for the AOI logging and monitoring pipeline.

## Current Scope

This repository currently implements the first milestone from `docs/priority.md`:

- structured inference event schema
- JSONL log writer
- HTTP ingestion service for inference events
- SQLite persistence for `inspection_runs` and `defect_logs`
- dedicated Vite + React frontend in `web/`
- optional mock event sender for development traffic
- local file-backed logging flow behind the ingestion API
- basic tests for schema and log writing

## Project Layout

```text
src/aoi/
  schema.py
  log_manager.py
  mock_inference.py
  cli.py
  service.py
web/
  src/
tests/
```

## Run Local HTTP Service

Use the local package path when running without installation:

```bash
PYTHONPATH=src python3 -m aoi.cli serve-http --host 127.0.0.1 --port 8000 --output logs/inference.jsonl
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Send one event:

```bash
curl -X POST http://127.0.0.1:8000/events \
  -H 'Content-Type: application/json' \
  -d '{"events":[{"pcb_id":"PCB-0001","component_id":"R101","inspection_result":"FAIL","defect_type":"MISALIGNMENT","confidence_score":0.88,"inference_latency_ms":31}]}'
```

Accepted events are written as newline-delimited JSON to `logs/inference.jsonl`.
Accepted event batches are also persisted into a SQLite database as one `inspection_run`
plus related `defect_logs`.

Read recent runs:

```bash
curl http://127.0.0.1:8000/runs?limit=5
```

Supported run filters:

- `limit`
- `pcb_id`
- `status`
- `model_version`
- `defect_type`

Read one run with embedded defect logs:

```bash
curl http://127.0.0.1:8000/runs/<run_id>
```

Supported embedded defect filters:

- `component_id`
- `defect_type`
- `severity`
- `inspection_result`

Read defect logs for one run:

```bash
curl http://127.0.0.1:8000/runs/<run_id>/defects
```

Example filtered queries:

```bash
curl 'http://127.0.0.1:8000/runs?status=FAIL&defect_type=MISALIGNMENT&limit=10'
curl 'http://127.0.0.1:8000/runs/<run_id>?component_id=U002'
curl 'http://127.0.0.1:8000/runs/<run_id>/defects?inspection_result=FAIL&severity=major'
```

## Run Dedicated Frontend

The repo also contains a separate React app in `web/`.

This environment uses Node `22`.

Load Node:

```bash
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use
```

Install dependencies:

```bash
cd web
npm install
```

Run the Vite dev server:

```bash
npm run dev
```

Frontend URL:

```text
http://127.0.0.1:5173
```

The Vite dev server proxies `/health`, `/runs`, and `/events` to the AOI backend on port `8000`.
When the frontend runs inside Docker, the proxy target is injected with `VITE_PROXY_TARGET=http://aoi-app:8000`.

## Run Mock Event Sender

To continuously generate synthetic traffic against the HTTP service:

```bash
PYTHONPATH=src python3 -m aoi.cli send-mock-events --endpoint http://127.0.0.1:8000/events
```

## Docker Stack

The repository includes a local stack for:

- `aoi-app`: exposes the HTTP ingestion API and writes validated events to JSONL
- `aoi-app`: also persists accepted batches to `/var/lib/aoi/aoi.db`
- `aoi-web`: runs the dedicated frontend from `web/`
- `aoi-mock-sender`: continuously sends mock events to the API
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

- AOI ingestion API: `http://localhost:8000`
- AOI frontend: `http://localhost:5173`
- Grafana: `http://localhost:3000`
- Loki: `http://localhost:3100`

Grafana default credentials:

- username: `admin`
- password: `admin`

### Provisioned Dashboard

Grafana provisions an `AOI Overview` dashboard automatically in the `AOI` folder.

Direct URL:

```text
http://localhost:3000/d/aoi-overview/aoi-overview
```

The dashboard includes:

- event count in the last 5 minutes
- fail count in the last 5 minutes
- boards seen in the last 15 minutes
- average inference latency
- inspection result rate over time
- failure type breakdown
- raw AOI event logs

### Inspect logs

To inspect container status:

```bash
docker compose ps
```

To inspect app logs:

```bash
docker compose logs aoi-app
```

To inspect the persisted SQLite database inside the app container:

```bash
docker exec aoi-app python -c "import sqlite3; conn=sqlite3.connect('/var/lib/aoi/aoi.db'); print(conn.execute('select pcb_id, model_version, status from inspection_runs order by rowid desc limit 5').fetchall())"
```

To inspect mock sender logs:

```bash
docker compose logs aoi-mock-sender
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
