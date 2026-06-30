"""
Scenario 8 — Intermittent Faults (real model)
Mostly clean-board traffic with real defective-board bursts injected at a few positions.
Tests log-level anomaly detection vs aggregate-metric blindness, using real inference.
"""
from __future__ import annotations

from experiments.scenarios.base import ScenarioResult, real_model_batches, send_batch_sequence

FAULT_POSITIONS = (5, 11, 17)
BURST_BOARDS = 4  # defective boards merged into each burst so it stands out from FP noise


def build_batches() -> list[list[dict]]:
    batches = real_model_batches("good", pcb_prefix="PCB-INTERMIT", limit=20)
    # A single defective board yields only 1-2 detections — barely above the good-board
    # false-positive noise. Merge several defective boards into each burst so the fault
    # spikes clearly above the baseline.
    defective = real_model_batches("defective", pcb_prefix="PCB-INTERMIT", limit=len(FAULT_POSITIONS) * BURST_BOARDS)
    for slot, position in enumerate(FAULT_POSITIONS):
        index = position - 1
        if not 0 <= index < len(batches):
            continue
        chunk = defective[slot * BURST_BOARDS:(slot + 1) * BURST_BOARDS]
        board_id = f"PCB-INTERMIT-{position:04d}"
        burst = [event for board in chunk for event in board]
        for event in burst:
            event["pcb_id"] = board_id
        batches[index] = burst
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
