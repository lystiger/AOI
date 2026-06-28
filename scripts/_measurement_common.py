"""Shared helpers for observability measurements.

The measurement scripts intentionally use only the Python standard library and
write observations returned by the running stack. They do not supply fallback
or example measurements.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "experiments"


def run_command(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def request_json(
    url: str,
    *,
    params: dict[str, object] | None = None,
    payload: object | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    if params:
        url = f"{url}?{urlencode(params)}"
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise RuntimeError(f"expected a JSON object from {url}")
    return decoded


def write_measurement(filename: str, measurement: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename
    output_path.write_text(
        json.dumps(measurement, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(measurement, indent=2, sort_keys=True))
    print(f"saved: {output_path}")
    return output_path


def loki_stream_count(response: dict[str, Any]) -> int:
    data = response.get("data")
    if not isinstance(data, dict):
        return 0
    result = data.get("result")
    if not isinstance(result, list):
        return 0
    total = 0
    for stream in result:
        if isinstance(stream, dict) and isinstance(stream.get("values"), list):
            total += len(stream["values"])
    return total


def loki_scalar_value(response: dict[str, Any]) -> float:
    data = response.get("data")
    if not isinstance(data, dict):
        return 0.0
    result = data.get("result")
    if not isinstance(result, list) or not result:
        return 0.0
    first = result[0]
    if not isinstance(first, dict):
        return 0.0
    value = first.get("value")
    if not isinstance(value, list) or len(value) < 2:
        return 0.0
    return float(value[1])
