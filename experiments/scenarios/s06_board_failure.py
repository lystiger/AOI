"""
Scenario 6 — Entire Board Failure
3 specific PCBs fail completely (100% component failure).
Surrounded by normal traffic to test isolation capability.
Duration: ~75 seconds (15 batches × 5s interval)
"""
from __future__ import annotations

import random

from experiments.scenarios.base import ScenarioResult, make_event, send_batch_sequence

DEFECT_POOL = [
    "SOLDER_BRIDGE", "MISSING_COMPONENT", "BENT_LEAD",
    "INSUFFICIENT_SOLDER", "MISALIGNMENT", "SOLDER_BALL",
]


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []

    # 5 normal boards first
    for board_idx in range(1, 6):
        batch = [
            make_event(
                pcb_id=f"PCB-NORMAL-{board_idx:03d}",
                component_id=f"U{i:02d}",
                inspection_result="PASS",
                defect_type="NO_DEFECT",
                confidence_score=round(random.uniform(0.88, 0.99), 3),
                inference_latency_ms=random.randint(20, 38),
            )
            for i in range(1, 9)
        ]
        batches.append(batch)

    # 3 completely failed boards
    for dead_idx in range(1, 4):
        batch = [
            make_event(
                pcb_id=f"PCB-DEAD-{dead_idx:03d}",
                component_id=f"U{i:02d}",
                inspection_result="FAIL",
                defect_type=random.choice(DEFECT_POOL),
                confidence_score=round(random.uniform(0.75, 0.92), 3),
                inference_latency_ms=random.randint(28, 50),
                overlay_x=round(0.05 + i * 0.1, 3),
                overlay_y=round(0.1 + i * 0.08, 3),
                overlay_width=0.08,
                overlay_height=0.06,
            )
            for i in range(1, 9)
        ]
        batches.append(batch)

    # 7 normal boards after — recovery context
    for board_idx in range(6, 13):
        batch = [
            make_event(
                pcb_id=f"PCB-NORMAL-{board_idx:03d}",
                component_id=f"U{i:02d}",
                inspection_result="PASS",
                defect_type="NO_DEFECT",
                confidence_score=round(random.uniform(0.89, 0.99), 3),
                inference_latency_ms=random.randint(20, 36),
            )
            for i in range(1, 9)
        ]
        batches.append(batch)

    return send_batch_sequence(
        "S06", "Entire Board Failure",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
