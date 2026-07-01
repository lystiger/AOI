#!/usr/bin/env python3
"""Synthesize a controllable AOI event corpus for the label-design ablation.

The corpus mirrors the real run's label *shapes* (15 components, 7 defect types,
2 model versions, PASS/FAIL) so that cardinality is dominated by pcb_id exactly
as in the deployed system, but lets us dial the board count N to trace scaling.

Design invariants that make the ablation clean:
  * component_id / defect_type / model_version are drawn from small fixed sets,
    so the parsed-only arm (which does not promote pcb_id) has cardinality that
    is BOUNDED and independent of N.
  * A FIXED set of PCB-DEAD-* boards is always emitted, so the board-isolation
    query returns the same result set at every N; only the scanned corpus grows.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

COMPONENTS = [f"U{i:02d}" for i in range(1, 16)]        # 15 components
FAIL_DEFECTS = [
    "BENT_LEAD", "INSUFFICIENT_SOLDER", "MISALIGNMENT",
    "MISSING_COMPONENT", "SOLDER_BALL", "SOLDER_BRIDGE",
]                                                        # 6 FAIL classes + NO_DEFECT
MODEL_VERSIONS = ["yolov8s-baseline", "yolov8s-undertrained"]
N_DEAD_BOARDS = 5            # fixed board-isolation target set, constant across N
EVENTS_PER_DEAD = 10


def _event(pcb_id: str, component: str, defect: str, version: str, rng: random.Random) -> dict:
    result = "PASS" if defect == "NO_DEFECT" else "FAIL"
    conf = round(rng.uniform(0.90, 0.99) if result == "PASS" else rng.uniform(0.55, 0.85), 2)
    return {
        "timestamp": "",  # left empty on purpose: promtail stamps entries at ingest time
        "pcb_id": pcb_id,
        "component_id": component,
        "inspection_result": result,
        "defect_type": defect,
        "confidence_score": conf,
        "inference_latency_ms": rng.randint(20, 40),
        "model_version": version,
    }


def build(n_boards: int, out_path: Path, seed: int = 42) -> dict[str, int]:
    rng = random.Random(seed)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    events = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for b in range(1, n_boards + 1):
            pcb_id = f"PCB-{b:05d}"
            version = MODEL_VERSIONS[0] if rng.random() < 0.85 else MODEL_VERSIONS[1]
            k = rng.randint(6, 12)  # distinct components inspected on this board
            for component in rng.sample(COMPONENTS, k):
                defect = "NO_DEFECT" if rng.random() < 0.5 else rng.choice(FAIL_DEFECTS)
                fh.write(json.dumps(_event(pcb_id, component, defect, version, rng)) + "\n")
                events += 1
        # Fixed PCB-DEAD board-isolation target set (constant at every N).
        for d in range(1, N_DEAD_BOARDS + 1):
            pcb_id = f"PCB-DEAD-{d:04d}"
            for _ in range(EVENTS_PER_DEAD):
                component = rng.choice(COMPONENTS)
                fh.write(json.dumps(_event(pcb_id, component, "BOARD_FAILURE", MODEL_VERSIONS[0], rng)) + "\n")
                events += 1
    return {"boards": n_boards + N_DEAD_BOARDS, "events": events}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-boards", type=int, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "ablation_data" / "corpus.jsonl",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    counts = build(args.n_boards, args.out, args.seed)
    print(f"wrote {counts['events']} events for {counts['boards']} boards -> {args.out}")


if __name__ == "__main__":
    main()
