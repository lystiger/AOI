"""
Scenario 8 — Intermittent Faults (real model)
Mostly clean-board traffic with real defective-board bursts injected at a few positions.
Tests log-level anomaly detection vs aggregate-metric blindness, using real inference.
"""
from __future__ import annotations

from experiments.scenarios.base import ScenarioResult, real_model_batches, send_batch_sequence

FAULT_POSITIONS = (5, 11, 17)


def build_batches() -> list[list[dict]]:
    batches = real_model_batches("good", limit=20)
    bursts = real_model_batches("defective", limit=len(FAULT_POSITIONS))
    for position, burst in zip(FAULT_POSITIONS, bursts):
        if 0 <= position - 1 < len(batches):
            batches[position - 1] = burst
    return batches


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    return send_batch_sequence(
        "S08", "Intermittent Faults (real model)",
        batches=build_batches(),
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
