#!/usr/bin/env python3
"""Run the label-design ablation sweep.

For each board count N it: synthesizes a corpus, brings up one Loki with two
Promtail arms (pcb_id-as-label vs pcb_id-parsed) reading the SAME corpus, waits
for both arms to finish ingesting, then measures for each arm:

  * active Loki series and the distinct pcb_id count (the cardinality cost), and
  * board-isolation query latency in its label form vs its parsed-filter form
    (the query cost), plus a full-scan control.

Everything but pcb_id's label status is held constant, so differences between
the arms isolate the labeling decision. Results -> docs/experiments/label_ablation.json.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from ablation_corpus import build as build_corpus

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.ablation.yml"
CORPUS = ROOT / "experiments" / "ablation_data" / "corpus.jsonl"
OUT = ROOT / "docs" / "experiments" / "label_ablation.json"
LOKI = "http://localhost:3100"


def _get(url: str, params: dict | None = None, timeout: float = 30.0) -> dict:
    if params:
        url = f"{url}?{urlencode(params)}"
    with urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _compose(*args: str) -> None:
    subprocess.run(["docker", "compose", "-f", str(COMPOSE), *args], cwd=ROOT, check=True)


def _wait_loki_ready(timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(f"{LOKI}/ready", timeout=5) as resp:
                if resp.status == 200 and b"ready" in resp.read():
                    return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Loki did not become ready")


def _job_count(job: str) -> int:
    """Total ingested lines for a job (0 if none yet)."""
    try:
        resp = _get(f"{LOKI}/loki/api/v1/query",
                    {"query": f'sum(count_over_time({{job="{job}"}}[6h]))'})
    except Exception:
        return 0
    result = resp.get("data", {}).get("result", [])
    if not result:
        return 0
    return int(float(result[0]["value"][1]))


def _wait_ingest(expected: int, timeout: float = 180.0) -> dict[str, int]:
    """Wait until both arms have ingested `expected` lines (or counts go stable)."""
    deadline = time.time() + timeout
    last = (-1, -1)
    stable = 0
    while time.time() < deadline:
        cur = (_job_count("aoi-label"), _job_count("aoi-parsed"))
        if cur[0] >= expected and cur[1] >= expected:
            return {"aoi-label": cur[0], "aoi-parsed": cur[1]}
        stable = stable + 1 if cur == last and cur[0] > 0 else 0
        if stable >= 3:  # counts unchanged over ~9s and non-zero -> done
            return {"aoi-label": cur[0], "aoi-parsed": cur[1]}
        last = cur
        time.sleep(3)
    return {"aoi-label": last[0], "aoi-parsed": last[1]}


def _cardinality(job: str) -> dict:
    now = datetime.now(timezone.utc)
    start_ns = int((now.timestamp() - 6 * 3600) * 1e9)
    end_ns = int(now.timestamp() * 1e9)
    resp = _get(f"{LOKI}/loki/api/v1/series",
                {"match[]": f'{{job="{job}"}}', "start": str(start_ns), "end": str(end_ns)})
    data = resp.get("data", [])
    values: dict[str, set] = {}
    for series in data:
        for label, value in series.items():
            values.setdefault(label, set()).add(value)
    return {
        "active_series": len(data),
        "distinct": {k: len(v) for k, v in sorted(values.items())},
    }


def _entries(resp: dict) -> int:
    total = 0
    for stream in resp.get("data", {}).get("result", []):
        total += len(stream.get("values", []))
    return total


def _latency(query: str, repeats: int, limit: int = 5000) -> dict:
    now = datetime.now(timezone.utc)
    start_ns = int((now.timestamp() - 6 * 3600) * 1e9)
    end_ns = int(now.timestamp() * 1e9)
    times, returned = [], 0
    for _ in range(repeats):
        t0 = time.perf_counter_ns()
        resp = _get(f"{LOKI}/loki/api/v1/query_range",
                    {"query": query, "start": str(start_ns), "end": str(end_ns), "limit": limit})
        times.append((time.perf_counter_ns() - t0) / 1e6)
        returned = _entries(resp)
    return {
        "query": query,
        "returned_entries": returned,
        "ms": {"mean": statistics.fmean(times), "median": statistics.median(times),
               "min": min(times), "max": max(times)},
    }


def run_point(n: int, repeats: int) -> dict:
    print(f"\n=== N={n} boards ===", flush=True)
    counts = build_corpus(n, CORPUS)
    expected = counts["events"]
    print(f"corpus: {expected} events / {counts['boards']} boards", flush=True)
    _compose("up", "-d", "--force-recreate", "--remove-orphans")
    try:
        _wait_loki_ready()
        ingested = _wait_ingest(expected)
        print(f"ingested: {ingested}", flush=True)
        # warm the caches once, then measure
        _latency('{job="aoi-label"} | json', 1)
        row = {
            "n_boards": counts["boards"],
            "events": expected,
            "ingested": ingested,
            "label_arm": {
                "cardinality": _cardinality("aoi-label"),
                "board_query": _latency('{job="aoi-label", pcb_id=~"PCB-DEAD-.*"} | json', repeats),
                "full_scan": _latency('{job="aoi-label"} | json', repeats),
            },
            "parsed_arm": {
                "cardinality": _cardinality("aoi-parsed"),
                "board_query": _latency('{job="aoi-parsed"} | json | pcb_id=~"PCB-DEAD-.*"', repeats),
                "full_scan": _latency('{job="aoi-parsed"} | json', repeats),
            },
        }
        return row
    finally:
        _compose("down", "-t", "2")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[131, 500, 1000, 2000])
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()

    result = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "repeats": args.repeats,
        "sizes": args.sizes,
        "points": [],
    }
    for n in args.sizes:
        result["points"].append(run_point(n, args.repeats))
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")  # incremental save
        print(f"saved partial -> {OUT}", flush=True)
    print("\nsweep complete.")


if __name__ == "__main__":
    main()
