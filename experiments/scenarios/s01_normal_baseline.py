"""
Scenario 1 — Normal Baseline
Establishes healthy system state in Loki/Grafana.
Run this FIRST before any anomaly scenarios.
Duration: ~60 seconds (12 batches × 5s interval)
"""
from __future__ import annotations

import random

from experiments.scenarios.base import ScenarioResult, make_event, send_batch_sequence

HEALTHY_EVENTS = [
    ("NO_DEFECT",           "PASS", 0.97, 22),
    ("NO_DEFECT",           "PASS", 0.94, 28),
    ("NO_DEFECT",           "PASS", 0.99, 21),
    ("SOLDER_BRIDGE",       "FAIL", 0.83, 35),
    ("NO_DEFECT",           "PASS", 0.96, 24),
    ("NO_DEFECT",           "PASS", 0.91, 30),
    ("MISSING_COMPONENT",   "FAIL", 0.78, 38),
    ("NO_DEFECT",           "PASS", 0.95, 26),
    ("NO_DEFECT",           "PASS", 0.93, 29),
    ("INSUFFICIENT_SOLDER", "FAIL", 0.81, 33),
]


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []
    for board_idx in range(1, 13):  # 12 batches
        batch = []
        for comp_idx, (defect_type, result, conf, latency) in enumerate(HEALTHY_EVENTS, 1):
            batch.append(make_event(
                pcb_id=f"PCB-BASELINE-{board_idx:03d}",
                component_id=f"U{comp_idx:02d}",
                inspection_result=result,
                defect_type=defect_type,
                confidence_score=conf + random.uniform(-0.02, 0.02),
                inference_latency_ms=latency + random.randint(-3, 5),
                overlay_x=round(0.1 + comp_idx * 0.07, 3) if result == "FAIL" else None,
                overlay_y=round(0.15 + comp_idx * 0.05, 3) if result == "FAIL" else None,
                overlay_width=0.08 if result == "FAIL" else None,
                overlay_height=0.06 if result == "FAIL" else None,
            ))
        batches.append(batch)

    return send_batch_sequence(
        "S01", "Normal Baseline",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
