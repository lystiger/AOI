from __future__ import annotations

import shutil
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from aoi.api.deps import DatabaseManagerDep, StoragePathDep

router = APIRouter()


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pcb_id: str | None = None


class UpdateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str | None = None
    requires_fiducials: bool | None = None
    requires_barcode: bool | None = None


def _validate_optional_choice(value: str | None, key: str, allowed: set[str]) -> str | None:
    if value is None:
        return None
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise HTTPException(status_code=400, detail=f"{key} must be one of: {allowed_values}")
    return value


def _normalize_optional_string(value: str | None, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=400, detail=f"{key} must be a non-empty string")
    return value


@router.post("/runs", status_code=201)
def create_run(
    payload: CreateRunRequest,
    database_manager: DatabaseManagerDep,
) -> dict[str, object]:
    pcb_id = _normalize_optional_string(payload.pcb_id, "pcb_id")
    run = database_manager.create_run(pcb_id=pcb_id)
    return {"status": "ok", "run": run}


@router.get("/runs")
def list_runs(
    database_manager: DatabaseManagerDep,
    limit: Annotated[int, Query(ge=1)] = 20,
    pcb_id: str | None = None,
    status: str | None = None,
    model_version: str | None = None,
    defect_type: str | None = None,
) -> dict[str, object]:
    validated_status = _validate_optional_choice(status, "status", {"PASS", "FAIL"})
    runs = database_manager.list_runs(
        limit=limit,
        pcb_id=pcb_id or None,
        status=validated_status,
        model_version=model_version or None,
        defect_type=defect_type or None,
    )
    return {"status": "ok", "count": len(runs), "runs": runs}


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    database_manager: DatabaseManagerDep,
    component_id: str | None = None,
    defect_type: str | None = None,
    severity: str | None = None,
    inspection_result: str | None = None,
) -> dict[str, object]:
    validated_severity = _validate_optional_choice(severity, "severity", {"none", "minor", "major", "critical"})
    validated_result = _validate_optional_choice(inspection_result, "inspection_result", {"PASS", "FAIL"})
    run = database_manager.fetch_run_with_defects(
        run_id,
        component_id=component_id or None,
        defect_type=defect_type or None,
        severity=validated_severity,
        inspection_result=validated_result,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"status": "ok", "run": run}


@router.get("/runs/{run_id}/defects")
def get_run_defects(
    run_id: str,
    database_manager: DatabaseManagerDep,
    component_id: str | None = None,
    defect_type: str | None = None,
    severity: str | None = None,
    inspection_result: str | None = None,
) -> dict[str, object]:
    validated_severity = _validate_optional_choice(severity, "severity", {"none", "minor", "major", "critical"})
    validated_result = _validate_optional_choice(inspection_result, "inspection_result", {"PASS", "FAIL"})
    run = database_manager.fetch_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    defect_logs = database_manager.fetch_defect_logs(
        run_id,
        component_id=component_id or None,
        defect_type=defect_type or None,
        severity=validated_severity,
        inspection_result=validated_result,
    )
    return {"status": "ok", "run_id": run_id, "count": len(defect_logs), "defect_logs": defect_logs}


@router.patch("/runs/{run_id}")
def update_run(
    run_id: str,
    payload: UpdateRunRequest,
    database_manager: DatabaseManagerDep,
) -> dict[str, object]:
    model_name = payload.model_name if "model_name" in payload.model_fields_set else None
    if "model_name" in payload.model_fields_set:
        model_name = _normalize_optional_string(model_name, "model_name")

    run = database_manager.update_run(
        run_id,
        model_name=model_name,
        requires_fiducials=payload.requires_fiducials if "requires_fiducials" in payload.model_fields_set else None,
        requires_barcode=payload.requires_barcode if "requires_barcode" in payload.model_fields_set else None,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"status": "ok", "run": run}


@router.delete("/runs/{run_id}")
def delete_run(
    run_id: str,
    database_manager: DatabaseManagerDep,
    storage_path: StoragePathDep,
) -> dict[str, object]:
    deleted = database_manager.delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="run not found")

    run_dir = storage_path / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)

    return {"status": "ok", "run_id": run_id}
