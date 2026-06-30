from __future__ import annotations

import json
from pathlib import Path

from aoi.schema import InferenceEvent


class LogManager:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write_json(self, event: InferenceEvent, model_version: str | None = None) -> None:
        payload = event.to_dict()
        if model_version is not None:
            payload["model_version"] = model_version
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")))
            handle.write("\n")

    def read_all(self) -> list[dict[str, object]]:
        if not self.log_path.exists():
            return []
        with self.log_path.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

