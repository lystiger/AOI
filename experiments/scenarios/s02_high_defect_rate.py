"""
Scenario 2 — High Defect Rate Spike
Simulates a production batch where >80% of components are defective.
This is the primary 'abnormal prediction pattern' test case.
Duration: ~50 seconds (10 batches × 5s interval)
"""
from __future__ import annotations

from experiments.scenarios.base import ScenarioResult, make_event, send_batch_sequence

HIGH_FAIL_EVENTS = [
    ("SOLDER_BRIDGE",       "FAIL", 0.91, 30),
    ("MISSING_COMPONENT",   "FAIL", 0.87, 32),
    ("SOLDER_BRIDGE",       "FAIL", 0.84, 28),
    ("BENT_LEAD",           "FAIL", 0.79, 35),
    ("INSUFFICIENT_SOLDER", "FAIL", 0.88, 31),
    ("MISALIGNMENT",        "FAIL", 0.82, 29),
    ("SOLDER_BRIDGE",       "FAIL", 0.90, 27),
    ("MISSING_COMPONENT",   "FAIL", 0.85, 34),
    ("NO_DEFECT",           "PASS", 0.93, 22),   # 1 in 10 pass
    ("BENT_LEAD",           "FAIL", 0.77, 36),
]


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []
    for board_idx in range(1, 11):  # 10 batches
        batch = [
            make_event(
                pcb_id=f"PCB-HIGHFAIL-{board_idx:03d}",
                component_id=f"U{i+1:02d}",
                inspection_result=evt[1],
                defect_type=evt[0],
                confidence_score=evt[2],
                inference_latency_ms=evt[3],
                overlay_x=round(0.1 + i * 0.08, 3) if evt[1] == "FAIL" else None,
                overlay_y=round(0.1 + i * 0.07, 3) if evt[1] == "FAIL" else None,
                overlay_width=0.07 if evt[1] == "FAIL" else None,
                overlay_height=0.06 if evt[1] == "FAIL" else None,
            )
            for i, evt in enumerate(HIGH_FAIL_EVENTS)
        ]
        batches.append(batch)

    return send_batch_sequence(
        "S02", "High Defect Rate Spike",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
