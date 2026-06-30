"""
Shared utilities for all anomaly scenario scripts.
All scenarios import from here — no duplication of HTTP logic.
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request as urllib_request

DEFAULT_ENDPOINT = "http://localhost:8000/events"
DEFAULT_MODEL_VERSION = "yolov8s-dspcbsd-v1"
CORPUS_ROOT = Path(__file__).resolve().parents[2] / "ml" / "data" / "corpus"
MODELS_DIR = Path(__file__).resolve().parents[2] / "ml" / "models" / "defect_detection"


@dataclass
class ScenarioResult:
    scenario_id: str
    scenario_name: str
    events_sent: int
    batches_sent: int
    duration_seconds: float
    errors: list[str]

    def summary(self) -> str:
        status = "PASS" if not self.errors else "ERRORS"
        return (
            f"[{status}] {self.scenario_id} — {self.scenario_name}\n"
            f"  Events: {self.events_sent} | Batches: {self.batches_sent} "
            f"| Duration: {self.duration_seconds:.1f}s"
            + (f"\n  Errors: {self.errors}" if self.errors else "")
        )


def send_events(
    events: list[dict[str, Any]],
    endpoint: str = DEFAULT_ENDPOINT,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> dict[str, Any] | None:
    """POST a batch of events to the AOI API. Returns response dict or None on failure."""
    payload = json.dumps({"events": events, "model_version": model_version}).encode()
    req = urllib_request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except error.URLError as exc:
        print(f"  [SEND ERROR] {exc}")
        return None


def make_event(
    pcb_id: str,
    component_id: str,
    inspection_result: str,        # return "PASS" or "FAIL"
    defect_type: str,              # example: "NO_DEFECT", "SOLDER_BRIDGE"
    confidence_score: float,       # range from 0.0 to 1.0
    inference_latency_ms: int,     # miliseconds, non-negative
    overlay_x: float | None = None,
    overlay_y: float | None = None,
    overlay_width: float | None = None,
    overlay_height: float | None = None,
) -> dict[str, Any]:
    # Clamp to the API's accepted ranges so random jitter in scenario
    # generators can never produce confidence > 1.0 or negative latency.
    confidence_score = max(0.0, min(1.0, confidence_score))
    inference_latency_ms = max(0, inference_latency_ms)
    event: dict[str, Any] = {
        "pcb_id": pcb_id,
        "component_id": component_id,
        "inspection_result": inspection_result,
        "defect_type": defect_type,
        "confidence_score": confidence_score,
        "inference_latency_ms": inference_latency_ms,
        "overlay_shape": "rect" if inspection_result == "FAIL" else None,
        "overlay_x": overlay_x,
        "overlay_y": overlay_y,
        "overlay_width": overlay_width,
        "overlay_height": overlay_height,
    }
    return {k: v for k, v in event.items() if v is not None}


def real_model_batches(
    pool: str,
    *,
    weights: str | None = None,
    conf: float = 0.40,
    limit: int | None = None,
    shuffle: bool = False,
    seed: int = 42,
) -> list[list[dict[str, Any]]]:
    """Run the trained model over a corpus pool and return one event-dict batch per board.

    Each board (image) becomes a batch of real inference events (real defect type,
    confidence, latency, overlay), ready to feed ``send_batch_sequence``. ``pool`` is a
    name under ``ml/data/corpus`` (good/defective/degraded/corrupt) or an absolute path.
    """
    from aoi.inference_runner import run_inference_dir

    pool_path = Path(pool)
    pool_dir = pool_path if pool_path.is_absolute() else CORPUS_ROOT / pool
    summary = run_inference_dir(
        str(pool_dir),
        api_url=None,
        weights_path=weights,
        confidence_threshold=conf,
        limit=limit,
        attach_images=False,
    )
    batches = [[event.to_dict() for event in record["events"]] for record in summary["runs"]]
    if shuffle:
        random.Random(seed).shuffle(batches)
    return batches


def send_batch_sequence(
    scenario_id: str,
    scenario_name: str,
    batches: list[list[dict[str, Any]]],
    interval_seconds: float = 2.0,
    endpoint: str = DEFAULT_ENDPOINT,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> ScenarioResult:
    """Send a sequence of batches with a delay between each. Returns ScenarioResult."""
    print(f"\n▶ {scenario_id} — {scenario_name}")
    print(f"  {len(batches)} batches, {interval_seconds}s interval")

    t_start = time.perf_counter()
    total_events = 0
    errors: list[str] = []

    for i, batch in enumerate(batches, 1):
        result = send_events(batch, endpoint=endpoint, model_version=model_version)
        if result:
            total_events += len(batch)
            print(f"  Batch {i}/{len(batches)}: {len(batch)} events → run_id={str(result.get('run_id', '?'))[:8]}")
        else:
            errors.append(f"Batch {i} failed")
        if i < len(batches):
            time.sleep(interval_seconds)

    duration = time.perf_counter() - t_start
    result_obj = ScenarioResult(
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        events_sent=total_events,
        batches_sent=len(batches),
        duration_seconds=duration,
        errors=errors,
    )
    print(f"  ✓ Done in {duration:.1f}s — {total_events} events sent")
    return result_obj
