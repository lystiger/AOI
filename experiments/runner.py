"""
Run all anomaly detection scenarios in sequence.
Usage:
    python -m experiments.runner                      # run all
    python -m experiments.runner --scenarios S01 S02  # run specific
    python -m experiments.runner --endpoint http://localhost:8000/events
"""
from __future__ import annotations

import argparse
import time

from experiments.scenarios import (
    s01_normal_baseline,
    s02_high_defect_rate,
    s03_latency_spike,
    s04_confidence_drop,
    s05_missing_component,
    s06_board_failure,
    s07_recovery,
    s08_intermittent_fault,
    s09_model_degradation,
)
from experiments.scenarios.base import ScenarioResult

ALL_SCENARIOS = {
    "S01": s01_normal_baseline,
    "S02": s02_high_defect_rate,
    "S03": s03_latency_spike,
    "S04": s04_confidence_drop,
    "S05": s05_missing_component,
    "S06": s06_board_failure,
    "S07": s07_recovery,
    "S08": s08_intermittent_fault,
    "S09": s09_model_degradation,
}

# Gap between scenarios so Grafana timeseries separates them visually
INTER_SCENARIO_PAUSE_SECONDS = 15


def run_all(
    scenario_ids: list[str] | None = None,
    endpoint: str = "http://localhost:8000/events",
) -> list[ScenarioResult]:
    targets = scenario_ids or list(ALL_SCENARIOS.keys())
    results: list[ScenarioResult] = []

    print(f"\n{'='*60}")
    print("AOI Anomaly Detection Experiment Suite")
    print(f"Endpoint: {endpoint}")
    print(f"Scenarios: {', '.join(targets)}")
    print(f"{'='*60}")

    for idx, scenario_id in enumerate(targets):
        if scenario_id not in ALL_SCENARIOS:
            print(f"[SKIP] Unknown scenario: {scenario_id}")
            continue

        module = ALL_SCENARIOS[scenario_id]
        result = module.run(endpoint=endpoint)
        results.append(result)

        if idx < len(targets) - 1:
            print(f"\n  ⏸  Pausing {INTER_SCENARIO_PAUSE_SECONDS}s before next scenario...")
            time.sleep(INTER_SCENARIO_PAUSE_SECONDS)

    print(f"\n{'='*60}")
    print("EXPERIMENT SUITE COMPLETE")
    print(f"{'='*60}")
    for r in results:
        print(r.summary())

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios", nargs="+",
        help="Scenario IDs to run (e.g. S01 S02 S03). Default: all.",
    )
    parser.add_argument(
        "--endpoint", default="http://localhost:8000/events",
        help="AOI API events endpoint",
    )
    args = parser.parse_args()
    run_all(scenario_ids=args.scenarios, endpoint=args.endpoint)
