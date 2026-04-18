from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from aoi.schema import InferenceEvent, InspectionResult


@dataclass(slots=True)
class PersistedRun:
    run_id: str
    pcb_id: str
    status: str
    event_count: int


class DatabaseManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS inspection_runs (
                    id TEXT PRIMARY KEY,
                    pcb_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    model_version TEXT,
                    status TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS defect_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    defect_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    inference_latency_ms INTEGER NOT NULL,
                    inspection_result TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES inspection_runs(id)
                );
                """
            )

    def persist_events(
        self,
        *,
        events: list[InferenceEvent],
        model_version: str | None = None,
    ) -> PersistedRun:
        if not events:
            raise ValueError("cannot persist an empty event list")

        run_id = str(uuid.uuid4())
        status = self._derive_run_status(events)
        pcb_id = events[0].pcb_id
        run_timestamp = events[0].timestamp

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO inspection_runs (id, pcb_id, timestamp, model_version, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, pcb_id, run_timestamp, model_version, status),
            )
            connection.executemany(
                """
                INSERT INTO defect_logs (
                    run_id,
                    component_id,
                    defect_type,
                    severity,
                    confidence_score,
                    inference_latency_ms,
                    inspection_result,
                    timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        event.component_id,
                        event.defect_type,
                        self._derive_severity(event),
                        event.confidence_score,
                        event.inference_latency_ms,
                        event.inspection_result.value,
                        event.timestamp,
                    )
                    for event in events
                ],
            )

        return PersistedRun(run_id=run_id, pcb_id=pcb_id, status=status, event_count=len(events))

    def fetch_run(self, run_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, pcb_id, timestamp, model_version, status FROM inspection_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def fetch_defect_logs(self, run_id: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, run_id, component_id, defect_type, severity, confidence_score,
                       inference_latency_ms, inspection_result, timestamp
                FROM defect_logs
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _derive_run_status(events: list[InferenceEvent]) -> str:
        if any(event.inspection_result == InspectionResult.FAIL for event in events):
            return InspectionResult.FAIL.value
        return InspectionResult.PASS.value

    @staticmethod
    def _derive_severity(event: InferenceEvent) -> str:
        if event.inspection_result == InspectionResult.PASS:
            return "none"
        if event.confidence_score >= 0.9:
            return "critical"
        if event.confidence_score >= 0.75:
            return "major"
        return "minor"
