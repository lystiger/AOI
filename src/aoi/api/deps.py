from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request

from aoi.database import DatabaseManager
from aoi.log_manager import LogManager
from aoi.setup_service import SetupService


def get_database_manager(request: Request) -> DatabaseManager:
    return request.app.state.database_manager


def get_log_manager(request: Request) -> LogManager:
    return request.app.state.log_manager


def get_setup_service(request: Request) -> SetupService:
    return request.app.state.setup_service


def get_storage_path(request: Request) -> Path:
    return request.app.state.storage_path


DatabaseManagerDep = Annotated[DatabaseManager, Depends(get_database_manager)]
LogManagerDep = Annotated[LogManager, Depends(get_log_manager)]
SetupServiceDep = Annotated[SetupService, Depends(get_setup_service)]
StoragePathDep = Annotated[Path, Depends(get_storage_path)]
