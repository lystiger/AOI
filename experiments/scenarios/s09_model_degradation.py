"""
Scenario 9 — Gradual Model Degradation
Confidence and accuracy degrade linearly over 20 batches.
Simulates model drift / dataset shift in production.
Duration: ~100 seconds (20 batches × 5s interval)
"""
from __future__ import annotations

import random

from experiments.scenarios.base import ScenarioResult, make_event, send_batch_sequence


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []
    total_batches = 20

    for i in range(1, total_batches + 1):
        # Linear degradation
        progress = (i - 1) / (total_batches - 1)          # 0.0 → 1.0
        fail_probability = 0.20 + progress * 0.55          # 20% → 75%
        confidence_base = 0.95 - progress * 0.50           # 0.95 → 0.45

        batch = []
        for j in range(1, 8):
            is_fail = random.random() < fail_probability
            batch.append(make_event(
                pcb_id=f"PCB-DRIFT-{i:03d}",
                component_id=f"U{j:02d}",
                inspection_result="FAIL" if is_fail else "PASS",
                defect_type=random.choice([
                    "SOLDER_BRIDGE", "MISSING_COMPONENT", "BENT_LEAD"
                ]) if is_fail else "NO_DEFECT",
                confidence_score=round(
                    max(0.40, confidence_base + random.uniform(-0.05, 0.05)), 3
                ),
                inference_latency_ms=random.randint(20, 45),
                overlay_x=round(0.1 + j * 0.09, 3) if is_fail else None,
                overlay_y=round(0.15 + j * 0.07, 3) if is_fail else None,
                overlay_width=0.08 if is_fail else None,
                overlay_height=0.06 if is_fail else None,
            ))
        batches.append(batch)

    return send_batch_sequence(
        "S09", "Gradual Model Degradation",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
