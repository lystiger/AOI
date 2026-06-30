"""
Scenario 2 — High Defect Rate Spike (real model)
Runs the trained model over real defective boards (DsPCBSD+ defects), producing a
FAIL-dominated stream. This is the primary 'abnormal prediction pattern' test case.
"""
from __future__ import annotations

from experiments.scenarios.base import ScenarioResult, real_model_batches, send_batch_sequence


def build_batches(limit: int = 12) -> list[list[dict]]:
    return real_model_batches("defective", pcb_prefix="PCB-HIGHFAIL", limit=limit)


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    return send_batch_sequence(
        "S02", "High Defect Rate Spike (real model, defective boards)",
        batches=build_batches(),
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
