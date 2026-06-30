"""
Scenario 3 — Latency Spike (real predictions, injected latency)
The model's predictions are real (run over defective boards), but the inference latency
is overridden with an escalating profile to simulate the service under load. Latency is
the one signal we inject rather than observe, since a real spike can't be summoned on cue.
"""
from __future__ import annotations

import random

from experiments.scenarios.base import ScenarioResult, real_model_batches, send_batch_sequence


def build_batches(limit: int = 24) -> list[list[dict]]:
    batches = real_model_batches("defective", pcb_prefix="PCB-LATENCY", limit=limit)
    for index, batch in enumerate(batches):
        # 30ms -> 2000ms over the first ~7 boards, then hold high
        base_latency = min(30 + index * 280, 2000)
        for event in batch:
            event["inference_latency_ms"] = max(0, base_latency + random.randint(-50, 150))
    return batches


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    return send_batch_sequence(
        "S03", "Latency Spike (real predictions, injected latency)",
        batches=build_batches(),
        interval_seconds=2.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
