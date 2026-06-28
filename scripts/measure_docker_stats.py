#!/usr/bin/env python3
"""Capture a real one-shot CPU/memory snapshot for Compose containers."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from _measurement_common import run_command, write_measurement


def main() -> None:
    container_ids = run_command(["docker", "compose", "ps", "-q"]).splitlines()
    if not container_ids:
        raise SystemExit("no running Docker Compose containers found")
    raw = run_command(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}", *container_ids]
    )
    snapshots = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not snapshots:
        raise SystemExit("docker stats returned no container snapshots")
    write_measurement(
        "docker_stats.json",
        {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "command": "docker stats --no-stream",
            "containers": snapshots,
        },
    )


if __name__ == "__main__":
    main()
