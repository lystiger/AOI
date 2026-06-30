"""Lightweight, CI-safe checks that every scenario exposes its entrypoints and imports.

Does not invoke the model (that needs ultralytics + the corpus); it guards against import
errors and signature drift in the re-pointed scenarios.
"""
from __future__ import annotations

import importlib

import pytest

SCENARIOS = [
    "s01_normal_baseline",
    "s02_high_defect_rate",
    "s03_latency_spike",
    "s04_confidence_drop",
    "s05_missing_component",
    "s06_board_failure",
    "s07_recovery",
    "s08_intermittent_fault",
    "s09_model_degradation",
]


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_exposes_run_and_build_batches(name):
    module = importlib.import_module(f"experiments.scenarios.{name}")
    assert callable(module.run)
    assert callable(module.build_batches)


def test_runner_registers_all_scenarios():
    from experiments.runner import ALL_SCENARIOS

    assert set(ALL_SCENARIOS) == {f"S0{i}" for i in range(1, 10)}
