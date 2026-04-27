from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from aoi.database import DatabaseManager
from aoi.log_manager import LogManager


def get_database_manager(request: Request) -> DatabaseManager:
    return request.app.state.database_manager


def get_log_manager(request: Request) -> LogManager:
    return request.app.state.log_manager


def get_storage_path(request: Request):
    return request.app.state.storage_path


DatabaseManagerDep = Annotated[DatabaseManager, Depends(get_database_manager)]
LogManagerDep = Annotated[LogManager, Depends(get_log_manager)]
StoragePathDep = Annotated[object, Depends(get_storage_path)]
