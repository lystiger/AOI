#!/usr/bin/env python3
"""Measure HTTP response latency for the thesis's representative LogQL queries."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import statistics
import time

from _measurement_common import loki_stream_count, request_json, write_measurement


QUERIES = {
    "all_recent_events": '{job="aoi-inference"} | json',
    "recent_failures": '{job="aoi-inference", inspection_result="FAIL"} | json',
    "latency_anomaly": '{job="aoi-inference"} | json | inference_latency_ms > 500',
    "low_confidence": '{job="aoi-inference"} | json | confidence_score < 0.56',
    "board_isolation": '{job="aoi-inference", pcb_id=~"PCB-DEAD-.*"} | json',
    "defect_concentration": '{job="aoi-inference", defect_type="SOLDER_BRIDGE"}',
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loki-url", default="http://localhost:3100")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--lookback-minutes", type=int, default=120)
    parser.add_argument("--limit", type=int, default=1000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.repeats < 1 or args.lookback_minutes < 1 or args.limit < 1:
        raise SystemExit("repeats, lookback minutes, and limit must be positive")
    captured_at = datetime.now(timezone.utc)
    start_ns = int((captured_at - timedelta(minutes=args.lookback_minutes)).timestamp() * 1e9)
    end_ns = int(captured_at.timestamp() * 1e9)
    results: dict[str, object] = {}
    for name, query in QUERIES.items():
        samples: list[dict[str, object]] = []
        for _ in range(args.repeats):
            started = time.perf_counter_ns()
            response = request_json(
                f"{args.loki_url}/loki/api/v1/query_range",
                params={
                    "query": query,
                    "start": str(start_ns),
                    "end": str(end_ns),
                    "limit": args.limit,
                },
            )
            latency_ms = (time.perf_counter_ns() - started) / 1_000_000
            samples.append(
                {"latency_ms": latency_ms, "returned_entries": loki_stream_count(response)}
            )
        latencies = [float(sample["latency_ms"]) for sample in samples]
        results[name] = {
            "query": query,
            "samples": samples,
            "summary_ms": {
                "minimum": min(latencies),
                "maximum": max(latencies),
                "mean": statistics.fmean(latencies),
                "median": statistics.median(latencies),
            },
        }
    write_measurement(
        "logql_latency.json",
        {
            "captured_at": captured_at.isoformat(),
            "lookback_minutes": args.lookback_minutes,
            "limit": args.limit,
            "repeats": args.repeats,
            "queries": results,
        },
    )


if __name__ == "__main__":
    main()
