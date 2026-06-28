#!/usr/bin/env python3
"""Measure POST /events to first visibility in Loki."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import statistics
import time
import uuid

from _measurement_common import loki_stream_count, request_json, write_measurement


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--loki-url", default="http://localhost:3100")
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--poll-interval", type=float, default=0.1)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.trials < 1:
        raise SystemExit("--trials must be at least 1")
    trials: list[dict[str, object]] = []
    for trial_number in range(1, args.trials + 1):
        unique_id = uuid.uuid4().hex
        pcb_id = f"MEASURE-FRESHNESS-{unique_id}"
        injected_at = datetime.now(timezone.utc)
        event = {
            "timestamp": injected_at.isoformat(),
            "pcb_id": pcb_id,
            "component_id": f"MEASURE-{trial_number}",
            "inspection_result": "PASS",
            "defect_type": "NO_DEFECT",
            "confidence_score": 1.0,
            "inference_latency_ms": 0,
        }
        started = time.perf_counter_ns()
        accepted = request_json(f"{args.api_url}/events", payload=event)
        deadline = time.monotonic() + args.timeout
        query_response: dict[str, object] | None = None
        while time.monotonic() < deadline:
            now = datetime.now(timezone.utc)
            query_response = request_json(
                f"{args.loki_url}/loki/api/v1/query_range",
                params={
                    "query": f'{{job="aoi-inference",pcb_id="{pcb_id}"}}',
                    "start": str(int((injected_at - timedelta(seconds=5)).timestamp() * 1e9)),
                    "end": str(int(now.timestamp() * 1e9)),
                    "limit": 10,
                },
            )
            if loki_stream_count(query_response) > 0:
                elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
                trials.append(
                    {
                        "trial": trial_number,
                        "pcb_id": pcb_id,
                        "injected_at": injected_at.isoformat(),
                        "visible_at": now.isoformat(),
                        "freshness_ms": elapsed_ms,
                        "api_response": accepted,
                    }
                )
                break
            time.sleep(args.poll_interval)
        else:
            raise TimeoutError(
                f"event {pcb_id} was not visible in Loki within {args.timeout} seconds"
            )

    values = [float(trial["freshness_ms"]) for trial in trials]
    write_measurement(
        "freshness.json",
        {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "trial_count": len(trials),
            "trials": trials,
            "summary_ms": {
                "minimum": min(values),
                "maximum": max(values),
                "mean": statistics.fmean(values),
                "median": statistics.median(values),
            },
        },
    )


if __name__ == "__main__":
    main()
