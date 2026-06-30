"""
Scenario 7 — System Recovery (real model)
A fault phase (real defective boards -> high fail rate) followed by a recovery phase
(clean boards -> back to PASS). Shows the monitoring system captures the full fault
lifecycle from real inference.
"""
from __future__ import annotations

from experiments.scenarios.base import ScenarioResult, real_model_batches, send_batch_sequence


def build_batches() -> list[list[dict]]:
    fault = real_model_batches("defective", pcb_prefix="PCB-FAULT", limit=5)
    recovery = real_model_batches("good", pcb_prefix="PCB-RECOVERED", limit=10)
    return fault + recovery


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    return send_batch_sequence(
        "S07", "System Recovery (real model)",
        batches=build_batches(),
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
