#!/usr/bin/env python3
"""Count active Loki series and distinct label values over a real time window."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from _measurement_common import request_json, write_measurement


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loki-url", default="http://localhost:3100")
    parser.add_argument("--lookback-minutes", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.lookback_minutes < 1:
        raise SystemExit("--lookback-minutes must be positive")
    captured_at = datetime.now(timezone.utc)
    start_ns = int((captured_at - timedelta(minutes=args.lookback_minutes)).timestamp() * 1e9)
    end_ns = int(captured_at.timestamp() * 1e9)
    response = request_json(
        f"{args.loki_url}/loki/api/v1/series",
        params={
            "match[]": '{job="aoi-inference"}',
            "start": str(start_ns),
            "end": str(end_ns),
        },
    )
    data = response.get("data")
    if not isinstance(data, list):
        raise RuntimeError("Loki series endpoint did not return a series list")
    value_sets: dict[str, set[str]] = {}
    for series in data:
        if not isinstance(series, dict):
            continue
        for label, value in series.items():
            value_sets.setdefault(str(label), set()).add(str(value))
    write_measurement(
        "label_cardinality.json",
        {
            "captured_at": captured_at.isoformat(),
            "lookback_minutes": args.lookback_minutes,
            "selector": '{job="aoi-inference"}',
            "active_series_count": len(data),
            "labels": {
                label: {"distinct_count": len(values), "values": sorted(values)}
                for label, values in sorted(value_sets.items())
            },
        },
    )


if __name__ == "__main__":
    main()
