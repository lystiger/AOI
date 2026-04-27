from __future__ import annotations

from io import BytesIO
import shutil
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
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


def _read_image_size(image_data: bytes) -> tuple[int, int]:
    try:
        with Image.open(BytesIO(image_data)) as image:
            width, height = image.size
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="unsupported image format; upload a valid image file") from exc

    if width < 1 or height < 1:
        raise HTTPException(status_code=400, detail="invalid image dimensions")
    return width, height


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


@router.post("/runs/{run_id}/images", status_code=201)
async def upload_run_image(
    run_id: str,
    request: Request,
    database_manager: DatabaseManagerDep,
    storage_path: StoragePathDep,
) -> dict[str, object]:
    run = database_manager.fetch_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    content_length_str = request.headers.get("content-length", "0")
    try:
        content_length = int(content_length_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid content length") from exc

    if content_length == 0:
        raise HTTPException(status_code=400, detail="empty image body")

    image_data = await request.body()
    if not image_data:
        raise HTTPException(status_code=400, detail="empty image body")

    image_width, image_height = _read_image_size(image_data)
    ext = "png"
    content_type = request.headers.get("content-type", "image/png")
    if "jpeg" in content_type:
        ext = "jpg"

    image_filename = f"scan.{ext}"
    run_dir = storage_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    file_path = run_dir / image_filename
    file_path.write_bytes(image_data)

    image_id = str(uuid.uuid4())
    updated_run = database_manager.add_run_image(
        run_id,
        image_id=image_id,
        image_path=f"/runs/{run_id}/images/{image_id}",
        image_role="full_board",
        image_width=image_width,
        image_height=image_height,
        created_at=str(run["timestamp"]),
    )
    if updated_run is None:
        raise HTTPException(status_code=404, detail="run not found")

    return {"status": "ok", "image_id": image_id, "run": updated_run}


@router.get("/runs/{run_id}/images/{image_id}")
def get_run_image(
    run_id: str,
    image_id: str,
    storage_path: StoragePathDep,
) -> FileResponse:
    _ = image_id
    run_dir = storage_path / run_id
    for ext in ["png", "jpg", "jpeg"]:
        candidate = run_dir / f"scan.{ext}"
        if candidate.exists():
            media_type = "image/png" if candidate.suffix == ".png" else "image/jpeg"
            return FileResponse(candidate, media_type=media_type)
    raise HTTPException(status_code=404, detail="image not found")
