# Backend FastAPI Migration Plan

## 1. Purpose

This document describes how to migrate the current backend from the custom `http.server` implementation in [src/aoi/service.py](/home/lystiger/projects/AOI/src/aoi/service.py) to FastAPI without rewriting the working domain logic.

The goal is not "adopt FastAPI" in the abstract. The goal is:

- preserve current behavior
- reduce HTTP-layer complexity
- improve request validation and error handling
- make deployment into internal IT environments easier
- create a cleaner path to production hardening later

## 2. Current Backend Baseline

The current backend is centered around:

- [src/aoi/service.py](/home/lystiger/projects/AOI/src/aoi/service.py)
- [src/aoi/database.py](/home/lystiger/projects/AOI/src/aoi/database.py)
- [src/aoi/schema.py](/home/lystiger/projects/AOI/src/aoi/schema.py)
- [src/aoi/log_manager.py](/home/lystiger/projects/AOI/src/aoi/log_manager.py)
- [src/aoi/cli.py](/home/lystiger/projects/AOI/src/aoi/cli.py)

The current HTTP layer already supports:

- `GET /health`
- `GET /runs`
- `GET /runs/<run_id>`
- `GET /runs/<run_id>/images/<image_id>`
- `POST /runs`
- `PATCH /runs/<run_id>`
- `DELETE /runs/<run_id>`
- `POST /runs/<run_id>/images`
- `POST /events`
- `POST /runs/<run_id>/fiducials/detect`
- `POST /runs/<run_id>/fiducials/confirm`
- `POST /runs/<run_id>/fiducials/manual`
- `POST /runs/<run_id>/barcode/detect`
- `POST /runs/<run_id>/barcode/confirm`
- `POST /runs/<run_id>/barcode/manual`

The business logic is already mostly outside the HTTP parser:

- persistence and state transitions live in `DatabaseManager`
- event validation lives in `InferenceEvent` and `RunImageInput`
- log writing lives in `LogManager`

This is good. It means the migration should focus on replacing the transport layer, not rewriting core behavior.

## 3. Migration Goal

After migration, the backend should:

- expose the same API behavior through FastAPI
- keep existing database behavior and setup-flow behavior
- validate payloads with Pydantic models at the API boundary
- serve image files and JSON responses more cleanly
- support local dev and IT deployment through ASGI servers such as `uvicorn`

The migration should be low-risk and incremental.

## 4. Non-Goals

This migration should not, in the first pass:

- redesign the database schema
- replace SQLite
- redesign the frontend API contract
- rewrite `DatabaseManager` into an ORM
- combine backend and frontend deployment into one process

Those are separate decisions and would increase migration risk.

## 5. Recommended Strategy

Use a staged migration.

Do not delete the current HTTP server immediately.

Keep the custom server running until the FastAPI version can:

- pass the existing backend test suite
- match current endpoint behavior
- serve the React frontend without breaking the setup flow

Recommended rollout:

1. Extract backend service dependencies and response contracts.
2. Introduce FastAPI app files alongside the current server.
3. Reimplement endpoints in FastAPI using the same `DatabaseManager` and `LogManager`.
4. Port tests to run against the FastAPI app.
5. Switch the CLI entrypoint to FastAPI only after parity is proven.
6. Remove the legacy server after stabilization.

## 6. Target Backend Structure

Recommended target structure under `src/aoi/`:

```text
src/aoi/
  api/
    app.py
    deps.py
    routes/
      health.py
      runs.py
      events.py
      setup.py
  services/
    run_service.py
    event_service.py
    image_service.py
  database.py
  schema.py
  log_manager.py
  cli.py
```

Notes:

- `database.py` can remain in place initially.
- `services/` should be thin orchestration around the existing `DatabaseManager`.
- `api/routes/` should contain FastAPI endpoint definitions only.
- `deps.py` should provide shared app dependencies such as `DatabaseManager`, `LogManager`, and storage paths.

## 7. FastAPI App Design

### 7.1 App Factory

Create an app factory instead of a module-global app.

Recommended shape:

```python
def create_app(*, db_path: Path, log_path: Path, storage_path: Path) -> FastAPI:
    ...
```

Why:

- better testability
- explicit dependency wiring
- easier IT deployment with environment-based settings

### 7.2 Shared State

The current server stores these on the HTTP server instance:

- `log_manager`
- `database_manager`
- `storage_path`

In FastAPI, store these either in:

- `app.state`, or
- dependency providers in `deps.py`

Recommended approach:

- initialize them once in `create_app()`
- expose them via dependency functions

### 7.3 Error Handling

The current server manually maps errors to JSON responses.

In FastAPI, standardize:

- `404` for missing runs/images
- `400` for bad client payloads
- `422` for schema validation failures from Pydantic
- `500` for unexpected internal failures

Add a small exception-mapping layer so `ValueError` from domain logic becomes consistent HTTP responses instead of leaking as generic `500`s.

## 8. API Contract Mapping

### 8.1 Health

Current:

- `GET /health`

FastAPI target:

- `GET /health`

Response should preserve:

- `status`
- `log_path`
- `db_path`

### 8.2 Runs

Current:

- `GET /runs`
- `GET /runs/{run_id}`
- `POST /runs`
- `PATCH /runs/{run_id}`
- `DELETE /runs/{run_id}`

FastAPI target:

- same routes
- same response shapes where possible

Use query parameter models or explicit query params for:

- `limit`
- `pcb_id`
- `status`
- `model_version`
- `defect_type`
- defect-detail filters on run detail requests

### 8.3 Event Ingestion

Current:

- `POST /events`

FastAPI target:

- same route
- request body parsed with Pydantic
- keep log writing and database persistence behavior unchanged

Important:

- the event ingestion path is operationally sensitive
- preserve accepted status code and payload semantics unless the frontend or clients are updated deliberately

### 8.4 Run Images

Current:

- `POST /runs/{run_id}/images`
- `GET /runs/{run_id}/images/{image_id}`

FastAPI target:

- same routes
- file upload implemented using FastAPI upload handling
- image response served with `FileResponse`

Important difference:

- current code accepts raw body bytes with `Content-Type`
- FastAPI will be simpler if the frontend uploads via multipart form data

Recommendation:

- Phase 1: preserve current raw upload contract if possible to avoid frontend churn
- Phase 2: optionally move to multipart after backend parity is complete

### 8.5 Setup Actions

Current:

- `POST /runs/{run_id}/fiducials/detect`
- `POST /runs/{run_id}/fiducials/confirm`
- `POST /runs/{run_id}/fiducials/manual`
- `POST /runs/{run_id}/barcode/detect`
- `POST /runs/{run_id}/barcode/confirm`
- `POST /runs/{run_id}/barcode/manual`

FastAPI target:

- same routes and status semantics

Recommendation:

- group these into `setup.py` or `runs.py`
- keep payload shapes unchanged in the first pass

## 9. Pydantic Model Plan

The current backend uses dataclasses and manual validation.

Do not replace the internal domain dataclasses immediately.

Instead:

- add Pydantic request/response models at the API boundary
- transform request models into existing domain objects

Recommended initial model groups:

- `CreateRunRequest`
- `UpdateRunRequest`
- `PostEventsRequest`
- `ManualFiducialsRequest`
- `ManualBarcodeRequest`
- `RunResponse`
- `RunListResponse`
- `RunDetailResponse`
- `HealthResponse`
- `ErrorResponse`

This keeps FastAPI-specific logic at the edge while preserving current internals.

## 10. Service Layer Extraction Plan

This is the most useful backend refactor to do during migration.

Right now `service.py` mixes:

- route matching
- body parsing
- validation
- orchestration
- response writing
- filesystem operations

Split this into thin services before or during endpoint migration.

Recommended service responsibilities:

### 10.1 Event Service

Responsibilities:

- validate `POST /events` payload at the application layer
- convert API models into `InferenceEvent` and `RunImageInput`
- call `LogManager.write_json`
- call `DatabaseManager.persist_events`

### 10.2 Run Service

Responsibilities:

- create, update, delete, fetch runs
- centralize `not found` handling for run-level operations

### 10.3 Image Service

Responsibilities:

- store uploaded image bytes
- validate image readability
- compute width/height
- persist image metadata
- map run/image ids to file paths

### 10.4 Setup Service

Responsibilities:

- detect/confirm/manual-save fiducials
- detect/confirm/manual-save barcode
- keep setup-state transitions in one place

This does not need to be large. Even a thin wrapper over `DatabaseManager` is enough if it removes HTTP concerns from business flow.

## 11. File-by-File Migration Plan

### 11.1 `src/aoi/service.py`

Status:

- currently the legacy HTTP transport layer

Action:

- stop adding new behavior here
- use it as the source of truth for endpoint parity during migration
- later replace it with either:
  - a tiny compatibility wrapper around FastAPI startup, or
  - full removal

### 11.2 `src/aoi/cli.py`

Action:

- add a FastAPI-based serve command
- support:
  - host
  - port
  - db path
  - log path
  - storage path
- optionally keep the old command behind a legacy flag during transition

### 11.3 `src/aoi/database.py`

Action:

- do not rewrite during initial migration
- add only small changes needed for cleaner service consumption
- possible future extraction:
  - run repository behavior
  - setup workflow behavior
  - image metadata behavior

### 11.4 `src/aoi/schema.py`

Action:

- keep domain dataclasses
- optionally add clearer conversion helpers if the FastAPI layer needs them

## 12. Testing Plan

### 12.1 Existing Tests

The current suite already covers a meaningful amount of business behavior:

- schema
- database
- service behavior

Preserve those tests.

### 12.2 New API Tests

Add FastAPI HTTP-level tests with `TestClient` or `httpx`.

Recommended coverage:

- `GET /health`
- `POST /runs`
- `PATCH /runs/{run_id}`
- `POST /runs/{run_id}/images`
- `POST /runs/{run_id}/fiducials/detect`
- `POST /runs/{run_id}/fiducials/manual`
- `POST /runs/{run_id}/barcode/manual`
- `POST /events`
- error cases for malformed payloads and missing runs

### 12.3 Migration Test Strategy

Best practical strategy:

1. Keep existing database tests unchanged.
2. Port service tests from the custom handler to FastAPI route tests.
3. During transition, keep a small parity checklist between old and new responses.

## 13. Configuration Plan

FastAPI deployment will be cleaner if configuration is explicit.

Move these into a settings object or environment-driven config:

- `AOI_HOST`
- `AOI_PORT`
- `AOI_DB_PATH`
- `AOI_LOG_PATH`
- `AOI_STORAGE_PATH`
- `AOI_CORS_ORIGINS`

Recommended implementation:

- small settings dataclass first
- Pydantic settings later if needed

## 14. Dependency Plan

If FastAPI is adopted, add at minimum:

- `fastapi`
- `uvicorn`

Likely test dependency additions:

- `httpx`

Recommendation:

- keep `pillow` as-is
- keep `pytest`
- decide on one primary environment workflow:
  - `uv` with `pyproject.toml` and `uv.lock`, or
  - `pip` with `requirements*.txt`

Do not let both drift for long.

## 15. Deployment Plan For IT Environments

For internal IT-managed environments, target a simple ASGI deployment:

- app process: `uvicorn`
- reverse proxy: Nginx or existing internal gateway
- persistent paths mounted for:
  - SQLite database
  - run assets
  - logs

Minimum deployment requirements:

- startup validation that required directories are writable
- health endpoint enabled
- explicit CORS configuration for the frontend origin
- documented backup handling for the SQLite file and run-assets directory

Recommended first deployment shape:

- one backend container
- one frontend container
- mounted volume for DB and assets

## 16. Risks

### 16.1 Hidden HTTP Contract Differences

Risk:

- frontend may depend on exact response JSON or status codes

Mitigation:

- preserve payloads exactly at first
- add route tests against current known behavior

### 16.2 Upload Contract Drift

Risk:

- image upload behavior may change when moving to FastAPI file handling

Mitigation:

- preserve current raw upload path first
- postpone multipart redesign

### 16.3 Over-Refactoring During Migration

Risk:

- backend migration gets blocked by unrelated cleanup

Mitigation:

- keep `DatabaseManager` stable during phase one
- avoid ORM migration
- avoid schema redesign

### 16.4 SQLite Operational Limits

Risk:

- internal production expectations may outgrow SQLite concurrency limits

Mitigation:

- accept SQLite for internal pilot
- document scaling constraints
- defer database replacement until usage justifies it

## 17. Recommended Delivery Phases

### Phase 1: App Skeleton

Deliver:

- `create_app()`
- FastAPI dependency wiring
- `GET /health`
- `GET /runs`
- `GET /runs/{run_id}`

Exit criteria:

- read-only API works in FastAPI

### Phase 2: Run Mutation

Deliver:

- `POST /runs`
- `PATCH /runs/{run_id}`
- `DELETE /runs/{run_id}`

Exit criteria:

- setup-flow run lifecycle works through FastAPI

### Phase 3: Image Upload and Serving

Deliver:

- `POST /runs/{run_id}/images`
- `GET /runs/{run_id}/images/{image_id}`

Exit criteria:

- frontend can upload and load run images without the legacy server

### Phase 4: Setup Endpoints

Deliver:

- fiducial detect/confirm/manual routes
- barcode detect/confirm/manual routes

Exit criteria:

- full setup mode works through FastAPI

### Phase 5: Event Ingestion

Deliver:

- `POST /events`

Exit criteria:

- event ingest path works with parity and persistence

### Phase 6: Cutover

Deliver:

- CLI serves FastAPI by default
- legacy server removed or explicitly deprecated
- docs updated

Exit criteria:

- no production or dev workflow depends on `BaseHTTPRequestHandler`

## 18. Acceptance Criteria

The migration is complete when:

- all current backend features are available through FastAPI
- `pytest` passes with FastAPI route coverage included
- the React frontend works against the FastAPI backend without route changes
- image upload and image retrieval still work
- setup flow state transitions still work
- event ingestion still persists runs and defect logs correctly
- local startup and IT deployment steps are documented clearly

## 19. Recommended Immediate Next Steps

In order:

1. Create `src/aoi/api/app.py` with an app factory and dependency wiring.
2. Implement `GET /health`, `GET /runs`, and `GET /runs/{run_id}` first.
3. Add FastAPI route tests for those read endpoints.
4. Migrate run mutation endpoints next.
5. Leave `POST /events` for later in the sequence, because it has the most operational sensitivity.

This order keeps momentum high and migration risk low.
