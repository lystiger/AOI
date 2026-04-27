from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def get_health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "log_path": str(request.app.state.log_manager.log_path),
        "db_path": str(request.app.state.database_manager.db_path),
    }
