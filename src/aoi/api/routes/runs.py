from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from aoi.api.deps import DatabaseManagerDep

router = APIRouter()


def _validate_optional_choice(value: str | None, key: str, allowed: set[str]) -> str | None:
    if value is None:
        return None
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise HTTPException(status_code=400, detail=f"{key} must be one of: {allowed_values}")
    return value


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
