# Backend FastAPI Migration Plan

## 1. Status: COMPLETED (Phase 1)
The legacy `http.server` implementation (`service.py`) has been removed. The backend now runs exclusively on FastAPI.

## 2. Completed Steps
- [x] Introduce FastAPI app files (`api/app.py`).
- [x] Port all endpoints to FastAPI routes.
- [x] Update CLI to use `uvicorn` and FastAPI factory.
- [x] Remove legacy `service.py`.

## 3. Remaining Debt (Post-Migration)
While the transport layer is now modernized, the "God Object" in `database.py` remains. The following services still need to be extracted to fulfill the architectural vision:

- **VisionService:** Extract image processing (BFS, HSV masking) from `DatabaseManager`.
- **SetupService:** Extract run-state machine logic (fiducial/barcode state) from `DatabaseManager`.

## 4. Target Structure (Current)
```text
src/aoi/
  api/
    app.py
    deps.py
    models/      <-- Pydantic models
    routes/
      health.py
      runs.py
      events.py
  database.py    <-- STILL CONTAINS BUSINESS/VISION LOGIC (NEXT REFACTOR)
  schema.py
  log_manager.py
  cli.py
```
