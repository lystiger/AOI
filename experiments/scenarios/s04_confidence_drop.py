"""
Scenario 4 — Low Confidence Storm
Model outputs predictions but with low confidence on all components.
Indicates the model is encountering board types outside its training distribution.
Duration: ~60 seconds (12 batches × 5s interval)
"""
from __future__ import annotations

import random

from experiments.scenarios.base import ScenarioResult, make_event, send_batch_sequence


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []
    defect_pool = [
        ("NO_DEFECT",           "PASS"),
        ("SOLDER_BRIDGE",       "FAIL"),
        ("NO_DEFECT",           "PASS"),
        ("MISSING_COMPONENT",   "FAIL"),
        ("NO_DEFECT",           "PASS"),
        ("INSUFFICIENT_SOLDER", "FAIL"),
    ]

    for board_idx in range(1, 13):
        batch = [
            make_event(
                pcb_id=f"PCB-LOWCONF-{board_idx:03d}",
                component_id=f"U{i+1:02d}",
                inspection_result=evt[1],
                defect_type=evt[0],
                # Low confidence — model is uncertain
                confidence_score=round(random.uniform(0.40, 0.55), 3),
                inference_latency_ms=random.randint(25, 45),
                overlay_x=round(0.1 + i * 0.1, 3) if evt[1] == "FAIL" else None,
                overlay_y=round(0.15 + i * 0.08, 3) if evt[1] == "FAIL" else None,
                overlay_width=0.08 if evt[1] == "FAIL" else None,
                overlay_height=0.06 if evt[1] == "FAIL" else None,
            )
            for i, evt in enumerate(defect_pool)
        ]
        batches.append(batch)

    return send_batch_sequence(
        "S04", "Low Confidence Storm",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
