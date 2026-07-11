from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import shutil
import uuid
from typing import Annotated, Literal
from urllib import error as urllib_error, parse as urllib_parse, request as urllib_request

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from aoi.api.deps import (
    DatabaseManagerDep,
    LogManagerDep,
    SetupServiceDep,
    StoragePathDep,
    VisionServiceDep,
)
from aoi.api.models import (
    CreateRunRequest,
    ManualBarcodeRequest,
    ManualFiducialsRequest,
    ReviewDefectRequest,
    SaveModelFovsRequest,
    UpdateRunRequest,
    parse_post_events_payload,
)
from aoi.inference_runner import MODEL_VERSION, load_defect_model, run_inference
from aoi.schema import InferenceEvent, InspectionResult

router = APIRouter()


def _load_cached_defect_model(request: Request):
    """Load the defect detector once per process and reuse it across inspections.

    Caching on ``app.state`` avoids re-reading the weights (and re-importing the ML stack)
    on every button click, so only the first inspection pays the model-load cost.
    """
    model = getattr(request.app.state, "defect_model", None)
    if model is None:
        model = load_defect_model()
        request.app.state.defect_model = model
    return model


def _remote_inference(
    inference_url: str,
    scan_file: Path,
    *,
    pcb_id: str,
    run_id: str | None,
) -> tuple[list[InferenceEvent], str | None]:
    """Delegate inference to the standalone model service and rebuild domain events.

    Uses stdlib urllib (no extra API deps) and the same event schema ``/events`` accepts, so
    the response round-trips through the parsing the API already owns. Connection failures
    surface as 503 (service down / not started) rather than an opaque 500.
    """
    query = {"pcb_id": pcb_id}
    if run_id:
        query["run_id"] = run_id
    endpoint = f"{inference_url.rstrip('/')}/infer?{urllib_parse.urlencode(query)}"
    http_request = urllib_request.Request(
        endpoint,
        data=scan_file.read_bytes(),
        headers={"Content-Type": "application/octet-stream"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(http_request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise HTTPException(status_code=502, detail=f"inference service error: {detail}") from exc
    except (urllib_error.URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=503, detail="inference service is unavailable") from exc

    try:
        events_in, model_version, _images = parse_post_events_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"inference service returned an invalid response: {exc}") from exc
    return [event.to_domain() for event in events_in], model_version

RunStatusFilter = Literal["PASS", "FAIL"]
SeverityFilter = Literal["none", "minor", "major", "critical"]


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
    setup_service: SetupServiceDep,
) -> dict[str, object]:
    run = setup_service.create_run(pcb_id=payload.pcb_id)
    return {"status": "ok", "run": run}


@router.get("/runs")
def list_runs(
    database_manager: DatabaseManagerDep,
    limit: Annotated[int, Query(ge=1)] = 20,
    pcb_id: str | None = None,
    status: RunStatusFilter | None = None,
    model_version: str | None = None,
    defect_type: str | None = None,
) -> dict[str, object]:
    runs = database_manager.list_runs(
        limit=limit,
        pcb_id=pcb_id or None,
        status=status,
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
    severity: SeverityFilter | None = None,
    inspection_result: RunStatusFilter | None = None,
) -> dict[str, object]:
    run = database_manager.fetch_run_with_defects(
        run_id,
        component_id=component_id or None,
        defect_type=defect_type or None,
        severity=severity,
        inspection_result=inspection_result,
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
    severity: SeverityFilter | None = None,
    inspection_result: RunStatusFilter | None = None,
) -> dict[str, object]:
    run = database_manager.fetch_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    defect_logs = database_manager.fetch_defect_logs(
        run_id,
        component_id=component_id or None,
        defect_type=defect_type or None,
        severity=severity,
        inspection_result=inspection_result,
    )
    return {"status": "ok", "run_id": run_id, "count": len(defect_logs), "defect_logs": defect_logs}


@router.post("/runs/{run_id}/inspect")
def run_inspection(
    run_id: str,
    request: Request,
    database_manager: DatabaseManagerDep,
    log_manager: LogManagerDep,
    vision_service: VisionServiceDep,
) -> dict[str, object]:
    """Run the trained defect model on the run's scan and attach the results.

    Persists one PASS/FAIL defect per detection onto this run (replacing prior results so
    re-inspection is idempotent) and writes each event to the JSONL log so it flows through
    the Promtail -> Loki -> Grafana pipeline, exactly like the synthetic scenarios.
    """
    run = database_manager.fetch_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    images = database_manager.fetch_run_images(run_id)
    scan = next((image for image in images if image.get("image_role") == "full_board"), None)
    if scan is None:
        raise HTTPException(status_code=422, detail="upload a PCB scan before running inspection")

    try:
        scan_file = vision_service.resolve_run_image_file(run_id, scan)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    inference_url = getattr(request.app.state, "inference_url", None)
    if inference_url:
        events, model_version = _remote_inference(
            inference_url, scan_file, pcb_id=str(run["pcb_id"]), run_id=run_id
        )
    else:
        try:
            model = _load_cached_defect_model(request)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="defect inference runtime is unavailable; install ultralytics to enable AI inspection",
            ) from exc
        events = run_inference(scan_file, model=model, run_id=run_id, pcb_id=str(run["pcb_id"]))
        model_version = MODEL_VERSION

    model_version = model_version or MODEL_VERSION
    updated_run = database_manager.persist_run_inference(
        run_id,
        events=events,
        model_version=model_version,
        run_image_id=str(scan["id"]),
    )
    if updated_run is None:
        raise HTTPException(status_code=404, detail="run not found")

    for event in events:
        log_manager.write_json(event, model_version=model_version)

    hydrated_run = database_manager.fetch_run_with_defects(run_id)
    assert hydrated_run is not None
    fail_count = sum(1 for event in events if event.inspection_result == InspectionResult.FAIL)
    return {
        "status": "ok",
        "run": hydrated_run,
        "model_version": model_version,
        "event_count": len(events),
        "fail_count": fail_count,
    }


@router.patch("/runs/{run_id}")
def update_run(
    run_id: str,
    payload: UpdateRunRequest,
    setup_service: SetupServiceDep,
) -> dict[str, object]:
    run = setup_service.update_run(
        run_id,
        model_name=payload.model_name if "model_name" in payload.model_fields_set else None,
        requires_fovs=payload.requires_fovs if "requires_fovs" in payload.model_fields_set else None,
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
    setup_service: SetupServiceDep,
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
    updated_run = setup_service.add_run_image(
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
    database_manager: DatabaseManagerDep,
    storage_path: StoragePathDep,
) -> FileResponse:
    image = database_manager.fetch_run_image(run_id, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="image not found")

    image_path = str(image.get("image_path") or "").strip()
    candidate = storage_path / run_id / "scan.png"
    if image_path:
        path = Path(image_path)
        if image_path.startswith(f"/runs/{run_id}/images/"):
            for ext in ["png", "jpg", "jpeg"]:
                scan_candidate = storage_path / run_id / f"scan.{ext}"
                if scan_candidate.exists():
                    candidate = scan_candidate
                    break
        elif path.is_absolute():
            candidate = path
        elif path.exists():
            candidate = path.resolve()
        else:
            candidate = (storage_path.parent / image_path.lstrip("/")).resolve()

    if candidate.exists():
        media_type = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
        return FileResponse(candidate, media_type=media_type)
    raise HTTPException(status_code=404, detail="image not found")


@router.get("/models/{model_name}/fovs")
def get_model_fovs(
    model_name: str,
    database_manager: DatabaseManagerDep,
) -> dict[str, object]:
    fovs = database_manager.fetch_model_fovs(model_name)
    return {"status": "ok", "model_name": model_name, "count": len(fovs), "fovs": fovs}


@router.put("/models/{model_name}/fovs")
def save_model_fovs(
    model_name: str,
    payload: SaveModelFovsRequest,
    setup_service: SetupServiceDep,
) -> dict[str, object]:
    try:
        fovs = setup_service.save_model_fovs(
            model_name,
            [entry.model_dump(exclude_none=True) for entry in payload.fovs],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "model_name": model_name, "count": len(fovs), "fovs": fovs}


@router.post("/runs/{run_id}/fovs/generate")
def generate_run_fov_crops(
    run_id: str,
    setup_service: SetupServiceDep,
    database_manager: DatabaseManagerDep,
) -> dict[str, object]:
    try:
        run = setup_service.generate_run_fov_crops(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    hydrated_run = database_manager.fetch_run_with_defects(run_id)
    assert hydrated_run is not None
    return {"status": "ok", "run": hydrated_run}


@router.post("/runs/{run_id}/fiducials/detect")
def detect_fiducials(
    run_id: str,
    setup_service: SetupServiceDep,
) -> dict[str, object]:
    try:
        run = setup_service.detect_fiducials(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"status": "ok", "run": run}


@router.post("/runs/{run_id}/fiducials/confirm")
def confirm_fiducials(
    run_id: str,
    setup_service: SetupServiceDep,
) -> dict[str, object]:
    try:
        run = setup_service.confirm_fiducials(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"status": "ok", "run": run}


@router.post("/runs/{run_id}/fiducials/manual")
def save_manual_fiducials(
    run_id: str,
    payload: ManualFiducialsRequest,
    setup_service: SetupServiceDep,
) -> dict[str, object]:
    try:
        run = setup_service.save_manual_fiducials(
            run_id,
            [fiducial.model_dump(exclude_none=True) for fiducial in payload.fiducials],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"status": "ok", "run": run}


@router.post("/runs/{run_id}/barcode/detect")
def detect_barcode(
    run_id: str,
    setup_service: SetupServiceDep,
) -> dict[str, object]:
    try:
        run = setup_service.detect_barcode(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"status": "ok", "run": run}


@router.post("/runs/{run_id}/barcode/confirm")
def confirm_barcode(
    run_id: str,
    setup_service: SetupServiceDep,
) -> dict[str, object]:
    try:
        run = setup_service.confirm_barcode(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"status": "ok", "run": run}


@router.post("/runs/{run_id}/barcode/manual")
def save_manual_barcode(
    run_id: str,
    payload: ManualBarcodeRequest,
    setup_service: SetupServiceDep,
) -> dict[str, object]:
    try:
        run = setup_service.save_manual_barcode(run_id, payload.barcode.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"status": "ok", "run": run}


@router.patch("/runs/{run_id}/defects/{defect_id}/review")
def review_defect(
    run_id: str,
    defect_id: int,
    payload: ReviewDefectRequest,
    database_manager: DatabaseManagerDep,
) -> dict[str, object]:
    updated = database_manager.update_defect_review(
        run_id,
        defect_id,
        payload.status.value,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="defect not found for this run")
    return {"status": "ok", "run_id": run_id, "defect_id": defect_id, "operator_review": payload.status}
