"""
Scenario 3 — Latency Spike
Simulates inference service under severe load or resource starvation.
Normal prediction results but drastically elevated latency.
Duration: ~70 seconds (14 batches × 5s interval)
"""
from __future__ import annotations

import random

from experiments.scenarios.base import ScenarioResult, make_event, send_batch_sequence


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []
    events_template = [
        ("NO_DEFECT",           "PASS", 0.94),
        ("SOLDER_BRIDGE",       "FAIL", 0.82),
        ("NO_DEFECT",           "PASS", 0.97),
        ("NO_DEFECT",           "PASS", 0.91),
        ("MISSING_COMPONENT",   "FAIL", 0.78),
    ]

    for board_idx in range(1, 15):  # 14 batches — latency builds then stays high
        # Latency escalates: 30ms → 800ms → 2000ms over first 7 batches, holds at 2000ms
        base_latency = min(30 + (board_idx - 1) * 280, 2000)
        batch = [
            make_event(
                pcb_id=f"PCB-LATENCY-{board_idx:03d}",
                component_id=f"U{i+1:02d}",
                inspection_result=evt[1],
                defect_type=evt[0],
                confidence_score=evt[2],
                inference_latency_ms=base_latency + random.randint(-50, 150),
                overlay_x=round(0.15 + i * 0.12, 3) if evt[1] == "FAIL" else None,
                overlay_y=round(0.2 + i * 0.1, 3) if evt[1] == "FAIL" else None,
                overlay_width=0.08 if evt[1] == "FAIL" else None,
                overlay_height=0.06 if evt[1] == "FAIL" else None,
            )
            for i, evt in enumerate(events_template)
        ]
        batches.append(batch)

    return send_batch_sequence(
        "S03", "Latency Spike",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
