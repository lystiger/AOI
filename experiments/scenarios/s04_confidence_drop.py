"""
Scenario 4 — Low Confidence Storm (real model on degraded boards)
Runs the model over degraded copies of defective boards (blur / noise / downscale). The
model still fires on the defects but at genuinely lower confidence, and misses some — a
real confidence drop, not a synthesized one.
"""
from __future__ import annotations

from experiments.scenarios.base import ScenarioResult, real_model_batches, send_batch_sequence


def build_batches(limit: int = 40) -> list[list[dict]]:
    return real_model_batches("degraded", pcb_prefix="PCB-LOWCONF", limit=limit)


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    return send_batch_sequence(
        "S04", "Low Confidence Storm (real model, degraded boards)",
        batches=build_batches(),
        interval_seconds=2.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
