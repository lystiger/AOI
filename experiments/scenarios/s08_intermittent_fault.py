"""
Scenario 8 — Intermittent Faults
Mostly normal traffic with 3 random high-fail bursts injected.
Tests log-level anomaly detection vs aggregate-metric blindness.
Duration: ~100 seconds (20 batches × 5s interval)
"""
from __future__ import annotations

import random

from experiments.scenarios.base import ScenarioResult, make_event, send_batch_sequence


def _normal_batch(board_id: str) -> list[dict]:
    return [
        make_event(
            pcb_id=board_id,
            component_id=f"U{j:02d}",
            inspection_result="PASS" if random.random() < 0.72 else "FAIL",
            defect_type="NO_DEFECT" if random.random() < 0.72 else "INSUFFICIENT_SOLDER",
            confidence_score=round(random.uniform(0.86, 0.98), 3),
            inference_latency_ms=random.randint(20, 40),
        )
        for j in range(1, 7)
    ]


def _fault_burst(board_id: str) -> list[dict]:
    return [
        make_event(
            pcb_id=board_id,
            component_id=f"U{j:02d}",
            inspection_result="FAIL",
            defect_type=random.choice(["SOLDER_BRIDGE", "BENT_LEAD", "MISSING_COMPONENT"]),
            confidence_score=round(random.uniform(0.79, 0.93), 3),
            inference_latency_ms=random.randint(25, 50),
            overlay_x=round(0.1 + j * 0.1, 3),
            overlay_y=round(0.15 + j * 0.08, 3),
            overlay_width=0.08,
            overlay_height=0.06,
        )
        for j in range(1, 7)
    ]


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    # 20 batches — inject 3 fault bursts at positions 5, 11, 17
    fault_positions = {5, 11, 17}
    batches = []
    for i in range(1, 21):
        board_id = f"PCB-INTERMIT-{i:03d}"
        if i in fault_positions:
            batches.append(_fault_burst(board_id))
        else:
            batches.append(_normal_batch(board_id))

    return send_batch_sequence(
        "S08", "Intermittent Faults",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
