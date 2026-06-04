"""
Scenario 5 — Single Defect Type Flood
One defect type dominates — simulates a systematic equipment fault
(e.g. bad solder paste causing bridges across all boards).
Duration: ~55 seconds (11 batches × 5s interval)
"""
from __future__ import annotations

import random

from experiments.scenarios.base import ScenarioResult, make_event, send_batch_sequence


def run(
    dominant_defect: str = "SOLDER_BRIDGE",
    endpoint: str = "http://localhost:8000/events",
) -> ScenarioResult:
    batches = []
    for board_idx in range(1, 12):
        batch = []
        for comp_idx in range(1, 9):
            # 85% FAIL, all the same defect type
            is_fail = random.random() < 0.85
            batch.append(make_event(
                pcb_id=f"PCB-FLOOD-{board_idx:03d}",
                component_id=f"U{comp_idx:02d}",
                inspection_result="FAIL" if is_fail else "PASS",
                defect_type=dominant_defect if is_fail else "NO_DEFECT",
                confidence_score=round(random.uniform(0.78, 0.94), 3),
                inference_latency_ms=random.randint(22, 40),
                overlay_x=round(0.1 + comp_idx * 0.09, 3) if is_fail else None,
                overlay_y=round(0.15 + comp_idx * 0.07, 3) if is_fail else None,
                overlay_width=0.08 if is_fail else None,
                overlay_height=0.06 if is_fail else None,
            ))
        batches.append(batch)

    return send_batch_sequence(
        "S05", f"Single Defect Type Flood ({dominant_defect})",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
