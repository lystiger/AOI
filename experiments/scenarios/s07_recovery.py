"""
Scenario 7 — System Recovery
Simulates anomaly followed by resolution.
Shows the monitoring system captures the full fault lifecycle.
Duration: ~75 seconds (5 bad + 10 good batches × 5s interval)
"""
from __future__ import annotations

import random

from experiments.scenarios.base import ScenarioResult, make_event, send_batch_sequence


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []

    # Phase 1 — fault active (5 batches, 90% fail, high latency)
    for i in range(1, 6):
        batch = [
            make_event(
                pcb_id=f"PCB-FAULT-{i:03d}",
                component_id=f"U{j:02d}",
                inspection_result="FAIL" if random.random() < 0.9 else "PASS",
                defect_type=random.choice(["SOLDER_BRIDGE", "MISSING_COMPONENT", "BENT_LEAD"]),
                confidence_score=round(random.uniform(0.75, 0.89), 3),
                inference_latency_ms=random.randint(800, 1800),
                overlay_x=round(0.1 + j * 0.08, 3),
                overlay_y=round(0.1 + j * 0.07, 3),
                overlay_width=0.08,
                overlay_height=0.06,
            )
            for j in range(1, 7)
        ]
        batches.append(batch)

    # Phase 2 — recovery (10 batches, healthy)
    for i in range(1, 11):
        batch = [
            make_event(
                pcb_id=f"PCB-RECOVERED-{i:03d}",
                component_id=f"U{j:02d}",
                inspection_result="PASS" if random.random() < 0.75 else "FAIL",
                defect_type="NO_DEFECT" if random.random() < 0.75 else "INSUFFICIENT_SOLDER",
                confidence_score=round(random.uniform(0.88, 0.98), 3),
                inference_latency_ms=random.randint(20, 42),
                overlay_x=round(0.1 + j * 0.09, 3) if random.random() < 0.25 else None,
                overlay_y=round(0.1 + j * 0.07, 3) if random.random() < 0.25 else None,
                overlay_width=0.08 if random.random() < 0.25 else None,
                overlay_height=0.06 if random.random() < 0.25 else None,
            )
            for j in range(1, 7)
        ]
        batches.append(batch)

    return send_batch_sequence(
        "S07", "System Recovery",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
