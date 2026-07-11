"""
Real inference runner for AOI PCB defect detection.

Runs a trained YOLOv8 defect detector over PCB scans and emits ``InferenceEvent``s,
either for a single image or a whole folder, optionally POSTing them to the AOI API so
they flow through the same JSONL -> Promtail -> Loki -> Grafana pipeline the synthetic
scenarios use.

ultralytics is imported lazily so importing this module never requires the ML stack
until inference is actually invoked.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aoi.schema import InferenceEvent, InspectionResult

CONFIDENCE_THRESHOLD = 0.40
NO_DEFECT_TYPE = "NO_DEFECT"
BOARD_FAILURE_TYPE = "BOARD_FAILURE"
MODEL_VERSION = "yolov8s-dspcbsd-v1"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}

# Canonical schema defect_type for each known DsPCBSD+ class (full names + paper
# abbreviations). DsPCBSD+ is a pure-defect dataset, so every detected class is a defect.
DEFECT_LABELS = {
    "short": "SHORT",
    "sh": "SHORT",
    "spur": "SPUR",
    "sp": "SPUR",
    "spurious_copper": "SPURIOUS_COPPER",
    "sc": "SPURIOUS_COPPER",
    "open": "OPEN_CIRCUIT",
    "open_circuit": "OPEN_CIRCUIT",
    "op": "OPEN_CIRCUIT",
    "mouse_bite": "MOUSE_BITE",
    "mousebite": "MOUSE_BITE",
    "mb": "MOUSE_BITE",
    "hole_breakout": "HOLE_BREAKOUT",
    "hb": "HOLE_BREAKOUT",
    "conductor_scratch": "CONDUCTOR_SCRATCH",
    "cs": "CONDUCTOR_SCRATCH",
    "conductor_foreign_object": "CONDUCTOR_FOREIGN_OBJECT",
    "cfo": "CONDUCTOR_FOREIGN_OBJECT",
    "base_material_foreign_object": "BASE_MATERIAL_FOREIGN_OBJECT",
    "bmfo": "BASE_MATERIAL_FOREIGN_OBJECT",
}


def defect_type_for(class_name: str) -> str:
    """Map a model class name to a schema defect_type, tolerating unknown spellings."""
    key = class_name.strip().lower().replace(" ", "_").replace("-", "_")
    if key in DEFECT_LABELS:
        return DEFECT_LABELS[key]
    # Every class in a defect dataset is a defect; uppercase unknowns rather than crash.
    return key.upper() or "UNKNOWN_DEFECT"


def _load_model(weights_path: str | Path):
    from ultralytics import YOLO

    return YOLO(str(weights_path))


def load_defect_model(weights_path: str | Path | None = None):
    """Load the trained defect detector for API/UI-driven inspection.

    Public entry point so callers do not have to reach into private helpers. Raises
    ``FileNotFoundError`` when no trained weights are present and ``ImportError`` (via
    ``ModuleNotFoundError``) when the ultralytics runtime is not installed.
    """
    weights = Path(weights_path) if weights_path else _default_weights_path()
    return _load_model(weights)


def _default_weights_path() -> Path:
    candidates = [
        SRC_ROOT.parent / "ml" / "models" / "defect_detection" / "best.pt",
        SRC_ROOT.parent / "ml" / "models" / "best.pt",
        SRC_ROOT.parent / "ml" / "models" / "component_detection" / "best.pt",
        Path("ml/models/defect_detection/best.pt"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Trained model not found. Train one (see ml/notebooks/colab_train_dspcbsd.ipynb) "
        "and place it at ml/models/defect_detection/best.pt, or pass --weights."
    )


def _normalise_class_names(names: object) -> dict[int, str]:
    if isinstance(names, dict):
        return {int(key): str(value) for key, value in names.items()}
    if isinstance(names, list):
        return {index: str(value) for index, value in enumerate(names)}
    return {}


def _board_id(pcb_id: str | None, run_id: str | None, image_path: Path) -> str:
    if pcb_id:
        return pcb_id
    if run_id:
        return run_id[:8].upper()
    return image_path.stem.upper()[:24] or "BOARD"


def _pass_event(board_id: str, latency_ms: int, run_image_index: int | None) -> InferenceEvent:
    return InferenceEvent.create(
        pcb_id=board_id,
        component_id="BOARD",
        inspection_result=InspectionResult.PASS,
        defect_type=NO_DEFECT_TYPE,
        confidence_score=1.0,
        inference_latency_ms=latency_ms,
        run_image_index=run_image_index,
    )


def _board_failure_event(board_id: str, latency_ms: int, run_image_index: int | None) -> InferenceEvent:
    """A scan the model could not process (corrupt/unreadable) is a board-level FAIL."""
    return InferenceEvent.create(
        pcb_id=board_id,
        component_id="BOARD",
        inspection_result=InspectionResult.FAIL,
        defect_type=BOARD_FAILURE_TYPE,
        confidence_score=1.0,
        inference_latency_ms=latency_ms,
        run_image_index=run_image_index,
    )


def run_inference(
    image_path: str | Path,
    *,
    model=None,
    run_id: str | None = None,
    pcb_id: str | None = None,
    weights_path: str | Path | None = None,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
    run_image_index: int | None = None,
) -> list[InferenceEvent]:
    """Run defect inference on one PCB scan.

    Returns one PASS/NO_DEFECT event when nothing is detected above threshold, otherwise
    one FAIL event per detected defect with a normalized overlay box. Pass a preloaded
    ``model`` to avoid reloading weights per image when running over a folder.
    """
    image_path = Path(image_path)
    if model is None:
        weights = Path(weights_path) if weights_path else _default_weights_path()
        model = _load_model(weights)
    board_id = _board_id(pcb_id, run_id, image_path)

    t_start = time.perf_counter()
    try:
        results = model.predict(
            source=str(image_path),
            conf=confidence_threshold,
            imgsz=640,
            verbose=False,
            save=False,
        )
    except Exception:
        # Corrupt / unreadable scan: a real inspection outcome, not a crash. Emit a
        # board-level FAIL so the batch continues and the failure is monitored (S06).
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        return [_board_failure_event(board_id, latency_ms, run_image_index)]
    latency_ms = int((time.perf_counter() - t_start) * 1000)

    result = results[0]
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return [_pass_event(board_id, latency_ms, run_image_index)]

    class_names = _normalise_class_names(getattr(result, "names", getattr(model, "names", {})))
    events: list[InferenceEvent] = []
    for idx, (cls_tensor, conf_tensor, xyxyn_tensor) in enumerate(
        zip(boxes.cls, boxes.conf, boxes.xyxyn), start=1
    ):
        class_index = int(cls_tensor.item())
        label = class_names.get(class_index, f"class_{class_index}")
        confidence = float(conf_tensor.item())
        x1, y1, x2, y2 = (float(value) for value in xyxyn_tensor.tolist())
        events.append(
            InferenceEvent.create(
                pcb_id=board_id,
                component_id=f"DET-{idx:03d}",
                inspection_result=InspectionResult.FAIL,
                defect_type=defect_type_for(label),
                confidence_score=round(confidence, 4),
                inference_latency_ms=latency_ms,
                run_image_index=run_image_index,
                overlay_x=round(min(max(x1, 0.0), 1.0), 4),
                overlay_y=round(min(max(y1, 0.0), 1.0), 4),
                overlay_width=round(min(max(x2 - x1, 0.0), 1.0), 4),
                overlay_height=round(min(max(y2 - y1, 0.0), 1.0), 4),
                overlay_shape="rect",
            )
        )

    return events or [_pass_event(board_id, latency_ms, run_image_index)]


def _image_metadata(image_path: Path) -> dict[str, object]:
    from PIL import Image

    with Image.open(image_path) as image:
        width, height = image.size
    return {
        "image_path": image_path.name,
        "image_role": "scan",
        "image_width": int(width),
        "image_height": int(height),
    }


def post_events_to_api(
    events: list[InferenceEvent],
    api_url: str = "http://localhost:8000",
    *,
    model_version: str = MODEL_VERSION,
    image_path: str | Path | None = None,
    timeout: float = 10.0,
) -> dict[str, object]:
    """POST one run's events (and optional scan-image metadata) to the AOI API.

    Uses stdlib urllib (like the experiment scenarios) so the runner needs no extra deps.
    """
    from urllib import request as urllib_request

    payload: dict[str, object] = {
        "model_version": model_version,
        "events": [event.to_dict() for event in events],
    }
    if image_path is not None:
        payload["images"] = [_image_metadata(Path(image_path))]

    body = json.dumps(payload).encode("utf-8")
    http_request = urllib_request.Request(
        f"{api_url}/events",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(http_request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def iter_images(image_dir: str | Path) -> list[Path]:
    image_dir = Path(image_dir)
    return sorted(
        path
        for path in image_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def run_inference_dir(
    image_dir: str | Path,
    *,
    weights_path: str | Path | None = None,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
    api_url: str | None = None,
    model_version: str = MODEL_VERSION,
    pcb_prefix: str = "PCB",
    attach_images: bool = True,
    limit: int | None = None,
) -> dict[str, object]:
    """Run defect inference over every image in a folder.

    Each image is treated as one inspection run. When ``api_url`` is set, each run's
    events are POSTed (mirroring how the experiment scenarios feed the pipeline); when it
    is ``None`` this is a dry run that only returns the events for inspection.
    """
    images = iter_images(image_dir)
    if limit is not None:
        images = images[:limit]
    if not images:
        raise FileNotFoundError(f"No images found under {image_dir}")

    weights = Path(weights_path) if weights_path else _default_weights_path()
    model = _load_model(weights)

    runs: list[dict[str, object]] = []
    total_events = total_fail = total_pass = 0
    for index, image_path in enumerate(images, start=1):
        events = run_inference(
            image_path,
            model=model,
            pcb_id=f"{pcb_prefix}-{index:04d}",
            confidence_threshold=confidence_threshold,
            run_image_index=0 if attach_images else None,
        )
        fails = sum(1 for event in events if event.inspection_result == InspectionResult.FAIL)
        total_events += len(events)
        total_fail += fails
        total_pass += len(events) - fails

        record: dict[str, object] = {"image": str(image_path), "events": events, "fail_count": fails}
        if api_url:
            record["response"] = post_events_to_api(
                events,
                api_url=api_url,
                model_version=model_version,
                image_path=image_path if attach_images else None,
            )
        runs.append(record)

    return {
        "image_dir": str(image_dir),
        "weights": str(weights),
        "images": len(images),
        "events": total_events,
        "fail_events": total_fail,
        "pass_events": total_pass,
        "posted": bool(api_url),
        "runs": runs,
    }


def _print_events(image_path: Path, events: list[InferenceEvent]) -> None:
    print(f"\n{image_path.name}: {len(events)} event(s)")
    for event in events:
        print(
            f"  [{event.inspection_result}] {event.defect_type} conf={event.confidence_score} "
            f"xywh=({event.overlay_x},{event.overlay_y},{event.overlay_width},{event.overlay_height})"
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run AOI defect inference on a PCB image or folder")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", help="Path to a single PCB scan image")
    source.add_argument("--image-dir", help="Path to a folder of PCB scan images")
    parser.add_argument("--api-url", default="http://localhost:8000", help="AOI API base URL")
    parser.add_argument("--weights", default=None, help="Path to trained weights (default: ml/models/defect_detection/best.pt)")
    parser.add_argument("--threshold", type=float, default=CONFIDENCE_THRESHOLD)
    parser.add_argument("--model-version", default=MODEL_VERSION)
    parser.add_argument("--pcb-prefix", default="PCB", help="PCB id prefix for batch runs")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N images in a folder")
    parser.add_argument("--dry-run", action="store_true", help="Print events; do not POST to the API")
    args = parser.parse_args()

    if args.image_dir:
        summary = run_inference_dir(
            args.image_dir,
            weights_path=args.weights,
            confidence_threshold=args.threshold,
            api_url=None if args.dry_run else args.api_url,
            model_version=args.model_version,
            pcb_prefix=args.pcb_prefix,
            limit=args.limit,
        )
        for record in summary["runs"]:
            _print_events(Path(record["image"]), record["events"])
        print(
            f"\n{summary['images']} image(s) -> {summary['events']} event(s) "
            f"({summary['fail_events']} FAIL / {summary['pass_events']} PASS); "
            f"posted={summary['posted']}"
        )
        return

    events = run_inference(
        args.image,
        weights_path=args.weights,
        confidence_threshold=args.threshold,
        run_image_index=None if args.dry_run else 0,
    )
    _print_events(Path(args.image), events)
    if not args.dry_run:
        response = post_events_to_api(
            events,
            api_url=args.api_url,
            model_version=args.model_version,
            image_path=args.image,
        )
        print(f"\nAPI response: {response}")


if __name__ == "__main__":
    main()
