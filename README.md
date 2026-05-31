# AOI Review Workstation

An Automatic Optical Inspection (AOI) workstation for PCB review, setup validation, and event logging. This repository combines a FastAPI backend, a React review interface, SQLite persistence, and an observability stack for inspecting runs from image upload through defect review.

![Python](https://img.shields.io/badge/Python-3.11%2B-1f6feb?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square)
![React](https://img.shields.io/badge/React-19-20232a?style=flat-square)
![Vite](https://img.shields.io/badge/Vite-Frontend-646cff?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-Persistence-0f6ab4?style=flat-square)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=flat-square)

## Overview

The current project state includes:

- A FastAPI service for run creation, image upload, event ingestion, and run review APIs
- A React-based AOI review workstation with run history, defect filters, image viewer controls, and settings
- Setup-stage workflow support for model selection, fiducial detection, barcode handling, and review readiness
- Automatic component-candidate detection on uploaded PCB scans, with persisted overlays in setup and review
- SQLite-backed storage for `inspection_runs`, `defect_logs`, and uploaded scan assets
- JSONL event logging for downstream observability pipelines
- A local Docker stack with Grafana, Loki, and Promtail

## Project Progress

The workstation and backend are already functional, and the ML work has now advanced to a first component-detection baseline.

### Latest ML Status

| Item | Current Value |
| --- | --- |
| Task | `component_detection` |
| Dataset profile | `reduced` |
| Active classes | `resistor`, `capacitor`, `connector`, `ic`, `led`, `other` |
| Dataset split | `470 train / 102 val / 100 test` |
| Latest test `mAP@50` | `0.1346` |
| Latest test `mAP@50-95` | `0.0687` |
| Latest test precision | `0.1602` |
| Latest test recall | `0.2452` |
| Best current class | `ic` (`AP50 = 0.461`) |
| Latest ablation result | `E2 channel_attention` collapsed to `0.0000 mAP@50` on the small seed |
| Current limitation | dense small parts still suppress `resistor` and `led` performance |

Quick links:

- [Progress report](docs/project_progress.md)
- [Larger-seed dataset report](ml/reports/component_detection/20260531-164255Z-dataset.md)
- [Larger-seed train report](ml/reports/component_detection/20260531-170538Z-train.md)
- [Larger-seed evaluation report](ml/reports/component_detection/20260531-170800Z-evaluate.md)
- [Small-seed baseline train report](ml/reports/component_detection/20260531-162633Z-train.md)
- [Small-seed baseline evaluation report](ml/reports/component_detection/20260531-162656Z-evaluate.md)
- [E2 channel-attention train report](ml/reports/component_detection/20260531-163332Z-train.md)
- [E2 channel-attention evaluation report](ml/reports/component_detection/20260531-163349Z-evaluate.md)

Current ML status:

- A component-detection-first pipeline now exists beside the original defect-first path
- The WACV 2019 reference dataset was converted into a YOLOv8 board-level dataset
- The initial 20-class setup was collapsed into a reduced 6-class profile:
  - `resistor`
  - `capacitor`
  - `connector`
  - `ic`
  - `led`
  - `other`
- Automatic Markdown run reports are generated for dataset build, training, and evaluation

Latest larger-seed test metrics:

- `mAP@50`: `0.1346`
- `mAP@50-95`: `0.0687`
- `precision`: `0.1602`
- `recall`: `0.2452`

That result is still far from production quality, but it is materially better than both the earlier 20-class baseline (`mAP@50 = 0.0044`) and the tiny reduced small-seed baseline (`mAP@50 = 0.0953`). The larger cleaned Roboflow-derived seed is already helping before any longer training schedule or real AOI images are added.

Latest controlled ablation on the reduced 6-class task:

| Experiment | Dataset | Variant | Test `mAP@50` | Test `mAP@50-95` | Precision | Recall | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `E1` | `small seed` | `baseline` | `0.0953` | `0.0617` | `0.2057` | `0.1581` | `183.4 ms` |
| `E1b` | `larger seed` | `baseline` | `0.1346` | `0.0687` | `0.1602` | `0.2452` | `102.6 ms` |
| `E2` | `small seed` | `channel_attention` | `0.0000` | `0.0000` | `0.0000` | `0.0000` | `253.4 ms` |

Interpretation:

- `E1` confirms the new variant-aware training path reproduces the earlier reduced baseline.
- `E1b` shows that better data is already more valuable than architectural experimentation in this project stage.
- `E2` is currently a negative result: channel attention increases inference cost and fails to learn a usable detector on the small seed dataset under the same 5-epoch CPU budget.
- This means the thesis ablation is already informative: attention is not automatically beneficial, and the dataset/training regime matters.

Benchmarking note:

- the current `0.1346 mAP@50` result is an internal engineering baseline for the reduced 6-class taxonomy
- it should be compared to our earlier internal runs, not directly to published SOTA numbers on `pcb_wacv_2019`
- a fair literature comparison would require matching the original benchmark task definition, label space, and evaluation protocol

Latest chart:

<p align="center">
  <img src="docs/chart/component-detection-reduced-f1-20260531.png" alt="Per-class F1 chart for the reduced 6-class component detection baseline" width="78%" />
</p>

Tracked reports:

- [Project progress](docs/project_progress.md)
- [Larger-seed dataset report](ml/reports/component_detection/20260531-164255Z-dataset.md)
- [Larger-seed train report](ml/reports/component_detection/20260531-170538Z-train.md)
- [Larger-seed evaluation report](ml/reports/component_detection/20260531-170800Z-evaluate.md)
- [Small-seed baseline train report](ml/reports/component_detection/20260531-162633Z-train.md)
- [Small-seed baseline evaluation report](ml/reports/component_detection/20260531-162656Z-evaluate.md)
- [E2 channel-attention train report](ml/reports/component_detection/20260531-163332Z-train.md)
- [E2 channel-attention evaluation report](ml/reports/component_detection/20260531-163349Z-evaluate.md)

## Current UI

<p align="center">
  <img src="assets/readme/review-workspace.png" alt="AOI review workspace captured from the running application" width="48%" />
  <img src="assets/readme/setup-workflow.png" alt="AOI setup workflow captured from the running application" width="48%" />
</p>

<p align="center">
  <em>Fresh captures from the live application: defect review and pre-program setup workflow.</em>
</p>

The operator-facing flow in the repo today is:

1. Create a run
2. Upload a PCB scan
3. Configure setup requirements such as fiducials and barcode validation
4. Review generated or ingested defects in the workstation
5. Persist events and review history for traceability

## Architecture

### Backend

- `src/aoi/api/`: FastAPI routes for runs, events, health, setup, and image access
- `src/aoi/setup_service.py`: run setup state transitions and review-readiness logic
- `src/aoi/vision_service.py`: component detection, fiducial detection, normalization, and barcode helpers
- `src/aoi/database.py`: SQLite schema and persistence operations
- `src/aoi/log_manager.py`: JSONL event logging

### Frontend

- `web/src/components/`: review workspace, run rail, PCB viewer, setup flow, and settings
- `web/src/hooks/`: workspace state, run data fetching, and setup actions
- `web/src/styles/`: layout, viewer, control, and theme styling

### Supporting Stack

- `docker-compose.yml`: local multi-service stack
- `aoi-mock-sender`: synthetic event generator for development traffic
- `Grafana + Loki + Promtail`: log aggregation and dashboards

## Repository Layout

```text
src/aoi/               Python application
web/                   React frontend
tests/                 Backend test suite
docs/                  Architecture notes, UI references, and screenshots
ml/                    ML-related placeholders and requirements
docker-compose.yml     Local full-stack environment
```

## Quick Start

### 1. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=src python3 -m aoi.cli serve-http \
  --host 127.0.0.1 \
  --port 8000 \
  --output logs/inference.jsonl
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

### 2. Frontend

This project uses Node `22`.

```bash
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use
cd web
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

### 3. Tests

```bash
pytest
```

## API Highlights

### Runs

- `POST /runs` creates a new inspection run
- `GET /runs` lists runs with filters such as `status`, `pcb_id`, and `defect_type`
- `GET /runs/{run_id}` returns one run with embedded defect data
- `PATCH /runs/{run_id}` updates setup-related run fields
- `DELETE /runs/{run_id}` removes a run and its stored scan assets

### Images and Setup

- `POST /runs/{run_id}/images` uploads the active PCB scan
- `GET /runs/{run_id}/images/{image_id}` serves the stored scan image
- `POST /runs/{run_id}/fiducials/detect` runs fiducial detection
- `POST /runs/{run_id}/fiducials/confirm` confirms detected fiducials
- `POST /runs/{run_id}/fiducials/manual` stores manually defined fiducials
- `POST /runs/{run_id}/barcode/detect` and related setup routes support barcode validation

### Events

- `POST /events` ingests inference events
- accepted payloads are written to `logs/inference.jsonl`
- accepted batches are also persisted into SQLite for run and defect review

Example event ingestion:

```bash
curl -X POST http://127.0.0.1:8000/events \
  -H 'Content-Type: application/json' \
  -d '{"events":[{"pcb_id":"PCB-0001","component_id":"R101","inspection_result":"FAIL","defect_type":"MISALIGNMENT","confidence_score":0.88,"inference_latency_ms":31}]}'
```

## Docker Stack

Run the full local environment:

```bash
docker compose up -d --build
```

Service URLs:

- API: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- Grafana: `http://localhost:3000`
- Loki: `http://localhost:3100`

Grafana default credentials:

- Username: `admin`
- Password: `admin`

To stop the stack:

```bash
docker compose down
```

## Development Notes

- Python requirement: `3.11+`
- Frontend runtime: Node `22`
- Uploaded images are stored under the configured storage path, defaulting to `data/storage`
- Local SQLite data defaults to `data/aoi.db`
- Mock traffic can be generated with `PYTHONPATH=src python3 -m aoi.cli send-mock-events`
- Fresh README screenshots can be regenerated with `cd web && npm run capture:readme`

## Documentation

- [System architecture](docs/architecture.md)
- [API contract](docs/api_spec.md)
- [Database notes](docs/database.md)
- [Testing notes](docs/testing.md)
- [Troubleshooting manual](docs/troubleshooting_manual.md)
