"""
Scenario 5 — Single Defect Type Flood (real model)
One defect type dominates — simulates a systematic process fault. Built from real model
detections on defective boards, filtered to a single dominant defect class (by default the
most frequently detected one), so the flood is made of genuine detections of that type.
"""
from __future__ import annotations

from collections import Counter

from experiments.scenarios.base import ScenarioResult, real_model_batches, send_batch_sequence


def build_batches(limit: int = 45, dominant: str | None = None) -> tuple[list[list[dict]], str]:
    raw = real_model_batches("defective", pcb_prefix="PCB-FLOOD", limit=limit)
    counts = Counter(
        event["defect_type"]
        for batch in raw
        for event in batch
        if event["inspection_result"] == "FAIL"
    )
    chosen = dominant or (counts.most_common(1)[0][0] if counts else "SPUR")
    batches = [[event for event in batch if event["defect_type"] == chosen] for batch in raw]
    batches = [batch for batch in batches if batch]
    return batches, chosen


def run(
    dominant_defect: str | None = None,
    endpoint: str = "http://localhost:8000/events",
) -> ScenarioResult:
    batches, chosen = build_batches(dominant=dominant_defect)
    return send_batch_sequence(
        "S05", f"Single Defect Type Flood (real model, {chosen})",
        batches=batches,
        interval_seconds=2.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
