#!/usr/bin/env python3
"""Measure actual JSONL and Loki filesystem growth caused by N accepted events."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import time
import uuid

from _measurement_common import loki_scalar_value, request_json, run_command, write_measurement


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--loki-url", default="http://localhost:3100")
    parser.add_argument("--events", type=int, default=1000)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--settle-seconds", type=float, default=5.0)
    return parser.parse_args()


def directory_kib(container: str, path: str) -> int:
    output = run_command(["docker", "exec", container, "du", "-sk", path])
    return int(output.split()[0])


def main() -> None:
    args = parse_args()
    if args.events < 1:
        raise SystemExit("--events must be at least 1")
    unique_id = uuid.uuid4().hex
    pcb_id = f"MEASURE-STORAGE-{unique_id}"
    before = {
        "jsonl_kib": directory_kib("aoi-app", "/var/log/aoi"),
        "loki_kib": directory_kib("aoi-loki", "/tmp/loki"),
    }
    payload = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pcb_id": pcb_id,
            "component_id": "MEASURE-STORAGE",
            "inspection_result": "PASS",
            "defect_type": "NO_DEFECT",
            "confidence_score": 1.0,
            "inference_latency_ms": 0,
        }
        for _ in range(args.events)
    ]
    accepted = request_json(f"{args.api_url}/events", payload=payload, timeout=args.timeout)
    deadline = time.monotonic() + args.timeout
    visible_count = 0
    while time.monotonic() < deadline:
        now = datetime.now(timezone.utc)
        response = request_json(
            f"{args.loki_url}/loki/api/v1/query",
            params={
                "query": f'sum(count_over_time({{job="aoi-inference",pcb_id="{pcb_id}"}}[1h]))',
                "time": str(now.timestamp()),
            },
            timeout=args.timeout,
        )
        visible_count = int(loki_scalar_value(response))
        if visible_count >= args.events:
            break
        time.sleep(0.25)
    else:
        raise TimeoutError(
            f"only {visible_count}/{args.events} measurement events became visible in Loki"
        )
    time.sleep(args.settle_seconds)
    after = {
        "jsonl_kib": directory_kib("aoi-app", "/var/log/aoi"),
        "loki_kib": directory_kib("aoi-loki", "/tmp/loki"),
    }
    write_measurement(
        "storage_growth.json",
        {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "event_count": args.events,
            "pcb_id": pcb_id,
            "api_response": accepted,
            "loki_visible_count": visible_count,
            "measurement_resolution": "KiB reported by du -sk inside each container",
            "before_kib": before,
            "after_kib": after,
            "growth_kib": {key: after[key] - before[key] for key in before},
            "settle_seconds": args.settle_seconds,
        },
    )


if __name__ == "__main__":
    main()
