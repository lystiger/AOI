"""
Scenario 9 — Model Degradation / Drift (real model variants)
Runs the SAME defective boards through two trained model variants in sequence — baseline
then channel_attention — each tagged with its own model_version. The shift in the
monitored confidence / fail-rate between phases is a real model-version drift signal,
not a synthesized gradient. Point weights_b at an under-trained checkpoint for a starker
degradation.
"""
from __future__ import annotations

from experiments.scenarios.base import (
    MODELS_DIR,
    ScenarioResult,
    real_model_batches,
    send_batch_sequence,
)


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


def build_batches(limit: int = 10) -> list[list[dict]]:
    baseline = real_model_batches("defective", pcb_prefix="PCB-DRIFT", weights=_weights("best-baseline.pt"), limit=limit)
    variant = real_model_batches("defective", pcb_prefix="PCB-DRIFT", weights=_weights("best-channel_attention.pt"), limit=limit)
    return _relabel(baseline, 1) + _relabel(variant, len(baseline) + 1)


def run(endpoint: str = "http://localhost:8000/events", limit: int = 10) -> ScenarioResult:
    baseline = _relabel(
        real_model_batches("defective", pcb_prefix="PCB-DRIFT", weights=_weights("best-baseline.pt"), limit=limit),
        1,
    )
    variant = _relabel(
        real_model_batches("defective", pcb_prefix="PCB-DRIFT", weights=_weights("best-channel_attention.pt"), limit=limit),
        len(baseline) + 1,
    )

    phase_a = send_batch_sequence(
        "S09", "Model Drift — phase A (baseline)",
        batches=baseline, interval_seconds=5.0, endpoint=endpoint,
        model_version="yolov8s-dspcbsd-baseline",
    )
    phase_b = send_batch_sequence(
        "S09", "Model Drift — phase B (channel_attention)",
        batches=variant, interval_seconds=5.0, endpoint=endpoint,
        model_version="yolov8s-dspcbsd-channel_attention",
    )
    return ScenarioResult(
        scenario_id="S09",
        scenario_name="Model Degradation / Drift (baseline -> channel_attention)",
        events_sent=phase_a.events_sent + phase_b.events_sent,
        batches_sent=phase_a.batches_sent + phase_b.batches_sent,
        duration_seconds=phase_a.duration_seconds + phase_b.duration_seconds,
        errors=phase_a.errors + phase_b.errors,
    )


if __name__ == "__main__":
    run()
