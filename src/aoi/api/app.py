from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from aoi.api.routes import health_router, runs_router
from aoi.database import DatabaseManager
from aoi.log_manager import LogManager


def create_app(*, db_path: Path, log_path: Path, storage_path: Path) -> FastAPI:
    app = FastAPI(title="AOI API", version="0.1.0")
    app.state.database_manager = DatabaseManager(db_path)
    app.state.log_manager = LogManager(log_path)
    app.state.storage_path = storage_path
    app.state.storage_path.mkdir(parents=True, exist_ok=True)
    app.state.database_manager.storage_path = app.state.storage_path

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "request failed"
        return JSONResponse(status_code=exc.status_code, content={"status": "error", "message": message})

    app.include_router(health_router)
    app.include_router(runs_router)
    return app
