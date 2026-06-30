"""
Scenario 9 — Model Degradation / Drift (real models)
Runs the SAME defective boards through two real model checkpoints in sequence — the
fully-trained baseline (phase A) then a deliberately under-trained checkpoint (phase B,
epoch 0) — each tagged with its own model_version. On identical defective input the
degraded model misses most defects and reports lower confidence, so the monitored
fail-rate / confidence drops sharply at the phase boundary. This is a real drift signal,
not a synthesized gradient.
"""
from __future__ import annotations

from experiments.scenarios.base import (
    MODELS_DIR,
    ScenarioResult,
    real_model_batches,
    send_batch_sequence,
)

BASELINE_WEIGHTS = "best-baseline.pt"
DEGRADED_WEIGHTS = "epoch0-degraded.pt"
INTERVAL = 2.0


def _weights(name: str) -> str | None:
    path = MODELS_DIR / name
    return str(path) if path.exists() else None


def _relabel(batches: list[list[dict]], start: int) -> list[list[dict]]:
    """Renumber boards from PCB-DRIFT-{start} so phase A and B ids never collide."""
    for offset, batch in enumerate(batches):
        board_id = f"PCB-DRIFT-{start + offset:04d}"
        for event in batch:
            event["pcb_id"] = board_id
    return batches


def _phase(weights: str, limit: int, start: int) -> list[list[dict]]:
    batches = real_model_batches("defective", pcb_prefix="PCB-DRIFT", weights=_weights(weights), limit=limit)
    return _relabel(batches, start)


def build_batches(limit: int = 20) -> list[list[dict]]:
    baseline = _phase(BASELINE_WEIGHTS, limit, 1)
    degraded = _phase(DEGRADED_WEIGHTS, limit, len(baseline) + 1)
    return baseline + degraded


def run(endpoint: str = "http://localhost:8000/events", limit: int = 20) -> ScenarioResult:
    baseline = _phase(BASELINE_WEIGHTS, limit, 1)
    degraded = _phase(DEGRADED_WEIGHTS, limit, len(baseline) + 1)

    phase_a = send_batch_sequence(
        "S09", "Model Drift — phase A (trained baseline)",
        batches=baseline, interval_seconds=INTERVAL, endpoint=endpoint,
        model_version="yolov8s-dspcbsd-baseline",
    )
    phase_b = send_batch_sequence(
        "S09", "Model Drift — phase B (under-trained epoch0)",
        batches=degraded, interval_seconds=INTERVAL, endpoint=endpoint,
        model_version="yolov8s-dspcbsd-epoch0",
    )
    return ScenarioResult(
        scenario_id="S09",
        scenario_name="Model Degradation / Drift (baseline -> under-trained)",
        events_sent=phase_a.events_sent + phase_b.events_sent,
        batches_sent=phase_a.batches_sent + phase_b.batches_sent,
        duration_seconds=phase_a.duration_seconds + phase_b.duration_seconds,
        errors=phase_a.errors + phase_b.errors,
    )


if __name__ == "__main__":
    run()
