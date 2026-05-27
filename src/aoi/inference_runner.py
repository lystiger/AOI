"""
Real inference runner for AOI component/solder defect detection.

This module lazy-loads ultralytics so importing it does not require the ML
stack to be installed until inference is actually invoked.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aoi.schema import InferenceEvent, InspectionResult


DATASET_TO_SCHEMA_DEFECT = {
    "missing_component": "MISSING_COMPONENT",
    "misalignment": "MISALIGNMENT",
    "reversed_polarity": "REVERSED_POLARITY",
    "bent_lead": "BENT_LEAD",
    "lifted_lead": "LIFTED_LEAD",
    "insufficient_solder": "INSUFFICIENT_SOLDER",
    "solder_bridge": "SOLDER_BRIDGE",
    "solder_ball": "SOLDER_BALL",
}

CONFIDENCE_THRESHOLD = 0.40
NO_DEFECT_TYPE = "NO_DEFECT"
MODEL_VERSION = "yolov8s-component-solder-v1"


def _load_model(weights_path: str | Path):
    from ultralytics import YOLO

    return YOLO(str(weights_path))


def _default_weights_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2] / "ml" / "models" / "best.pt",
        Path("ml/models/best.pt"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Trained model not found. Run: python -m ml.pipeline.train\nExpected location: ml/models/best.pt"
    )


def _normalise_class_names(names: object) -> dict[int, str]:
    if isinstance(names, dict):
        return {int(key): str(value) for key, value in names.items()}
    if isinstance(names, list):
        return {index: str(value) for index, value in enumerate(names)}
    return {}


def run_inference(
    image_path: str | Path,
    run_id: str,
    pcb_id: str | None = None,
    weights_path: str | Path | None = None,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> list[InferenceEvent]:
    """
    Run model inference on a PCB scan image.

    Returns one PASS event when no supported defects are found above threshold.
    """
    weights = Path(weights_path) if weights_path else _default_weights_path()
    board_id = pcb_id or run_id[:8].upper()
    model = _load_model(weights)

    t_start = time.perf_counter()
    results = model.predict(
        source=str(image_path),
        conf=confidence_threshold,
        imgsz=640,
        verbose=False,
        save=False,
    )
    latency_ms = int((time.perf_counter() - t_start) * 1000)

    result = results[0]
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return [
            InferenceEvent.create(
                pcb_id=board_id,
                component_id="BOARD",
                inspection_result=InspectionResult.PASS,
                defect_type=NO_DEFECT_TYPE,
                confidence_score=1.0,
                inference_latency_ms=latency_ms,
            )
        ]

    class_names = _normalise_class_names(getattr(result, "names", getattr(model, "names", {})))
    events: list[InferenceEvent] = []
    unsupported_labels: set[str] = set()

    for idx, (cls_tensor, conf_tensor, xyxyn_tensor) in enumerate(zip(boxes.cls, boxes.conf, boxes.xyxyn), start=1):
        class_index = int(cls_tensor.item())
        dataset_label = class_names.get(class_index, f"class_{class_index}")
        schema_defect = DATASET_TO_SCHEMA_DEFECT.get(dataset_label)
        if schema_defect is None:
            unsupported_labels.add(dataset_label)
            continue

        confidence = float(conf_tensor.item())
        x1, y1, x2, y2 = [float(value) for value in xyxyn_tensor.tolist()]
        events.append(
            InferenceEvent.create(
                pcb_id=board_id,
                component_id=f"DET-{idx:03d}",
                inspection_result=InspectionResult.FAIL,
                defect_type=schema_defect,
                confidence_score=round(confidence, 4),
                inference_latency_ms=latency_ms,
                overlay_x=round(x1, 4),
                overlay_y=round(y1, 4),
                overlay_width=round(x2 - x1, 4),
                overlay_height=round(y2 - y1, 4),
                overlay_shape="rect",
            )
        )

    if unsupported_labels:
        unsupported_csv = ", ".join(sorted(unsupported_labels))
        raise ValueError(f"Model emitted unsupported dataset classes: {unsupported_csv}")

    if events:
        return events

    return [
        InferenceEvent.create(
            pcb_id=board_id,
            component_id="BOARD",
            inspection_result=InspectionResult.PASS,
            defect_type=NO_DEFECT_TYPE,
            confidence_score=1.0,
            inference_latency_ms=latency_ms,
        )
    ]


def post_events_to_api(
    events: list[InferenceEvent],
    api_url: str = "http://localhost:8000",
    image_path: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    """POST inference results to the AOI API."""
    import requests

    payload: dict[str, object] = {
        "model_version": MODEL_VERSION,
        "events": [event.to_dict() for event in events],
    }

    if image_path and run_id:
        from PIL import Image

        with Image.open(str(image_path)) as image:
            width, height = image.size
        payload["images"] = [
            {
                "image_path": f"/runs/{run_id}/images/scan.jpg",
                "image_role": "scan",
                "image_width": width,
                "image_height": height,
            }
        ]

    response = requests.post(f"{api_url}/events", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run AOI inference on a PCB image")
    parser.add_argument("--image", required=True, help="Path to PCB scan image")
    parser.add_argument("--run-id", required=True, help="Run UUID")
    parser.add_argument("--pcb-id", default=None, help="PCB identifier")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--weights", default=None, help="Path to best.pt")
    parser.add_argument("--threshold", type=float, default=CONFIDENCE_THRESHOLD)
    parser.add_argument("--dry-run", action="store_true", help="Print events, do not POST")
    args = parser.parse_args()

    events = run_inference(
        image_path=args.image,
        run_id=args.run_id,
        pcb_id=args.pcb_id,
        weights_path=args.weights,
        confidence_threshold=args.threshold,
    )

    print(f"\nDetected {len(events)} event(s):")
    for event in events:
        print(
            f"  [{event.inspection_result}] {event.defect_type} conf={event.confidence_score} "
            f"xy=({event.overlay_x},{event.overlay_y}) wh=({event.overlay_width},{event.overlay_height})"
        )

    if not args.dry_run:
        response = post_events_to_api(events, api_url=args.api_url, image_path=args.image, run_id=args.run_id)
        print(f"\nAPI response: {response}")
