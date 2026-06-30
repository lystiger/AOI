"""
Scenario 6 — Entire Board Failure (real model)
Unreadable/corrupt scans (the model cannot process them) produce real BOARD_FAILURE
events, surrounded by normal clean-board traffic to test isolation. Exercises the runner's
board-failure path on genuinely corrupt image files.
"""
from __future__ import annotations

from experiments.scenarios.base import ScenarioResult, real_model_batches, send_batch_sequence


def build_batches() -> list[list[dict]]:
    good = real_model_batches("good", limit=10)
    corrupt = real_model_batches("corrupt")  # each -> one BOARD_FAILURE event
    # normal traffic, the failed boards in the middle, then recovery traffic
    return good[:5] + corrupt + good[5:10]


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    return send_batch_sequence(
        "S06", "Entire Board Failure (real model, corrupt scans)",
        batches=build_batches(),
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
