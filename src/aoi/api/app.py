from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from aoi.api.routes import events_router, health_router, runs_router
from aoi.database import DatabaseManager
from aoi.log_manager import LogManager
from aoi.setup_service import SetupService
from aoi.vision_service import VisionService


def create_app(*, db_path: Path, log_path: Path, storage_path: Path) -> FastAPI:
    app = FastAPI(title="AOI API", version="0.1.0")
    app.state.database_manager = DatabaseManager(db_path)
    app.state.log_manager = LogManager(log_path)
    app.state.storage_path = storage_path
    app.state.storage_path.mkdir(parents=True, exist_ok=True)
    app.state.database_manager.storage_path = app.state.storage_path
    app.state.vision_service = VisionService(db_path=db_path, storage_path=app.state.storage_path)
    app.state.setup_service = SetupService(app.state.database_manager, app.state.vision_service)

    def _validation_message(exc: RequestValidationError) -> str:
        first_error = exc.errors()[0] if exc.errors() else {}
        return str(first_error.get("msg") or "validation error")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "request failed"
        return JSONResponse(status_code=exc.status_code, content={"status": "error", "message": message})

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"status": "error", "message": _validation_message(exc)})

    app.include_router(health_router)
    app.include_router(events_router)
    app.include_router(runs_router)
    return app
