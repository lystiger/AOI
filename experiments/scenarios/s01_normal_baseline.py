"""
Scenario 1 — Normal Baseline (real model)
Runs the trained defect model over defect-free board crops to establish a healthy,
PASS-dominated baseline in Loki/Grafana. Run this FIRST before any anomaly scenarios.
"""
from __future__ import annotations

from experiments.scenarios.base import ScenarioResult, real_model_batches, send_batch_sequence


def build_batches(limit: int = 30) -> list[list[dict]]:
    return real_model_batches("good", pcb_prefix="PCB-BASELINE", limit=limit)


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    return send_batch_sequence(
        "S01", "Normal Baseline (real model, clean boards)",
        batches=build_batches(),
        interval_seconds=2.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
