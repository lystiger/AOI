from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aoi.schema import InferenceEvent, InspectionResult, RunImageInput


@dataclass(slots=True)
class PersistedRun:
    run_id: str
    pcb_id: str
    status: str
    event_count: int


DEMO_RUN_IMAGE_PATH = "/mock/pcb-example-2nd.png"
DEMO_RUN_IMAGE_ROLE = "demo_full_board"
DEMO_RUN_IMAGE_WIDTH = 1464
DEMO_RUN_IMAGE_HEIGHT = 1013


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

                CREATE TABLE IF NOT EXISTS run_images (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    image_role TEXT NOT NULL,
                    image_width INTEGER NOT NULL,
                    image_height INTEGER NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES inspection_runs(id)
                );
                """
            )
            self._ensure_column(
                connection,
                table_name="inspection_runs",
                column_name="model_name",
                definition="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="inspection_runs",
                column_name="setup_status",
                definition="TEXT NOT NULL DEFAULT 'not_ready'",
            )
            self._ensure_column(
                connection,
                table_name="inspection_runs",
                column_name="requires_fiducials",
                definition="INTEGER NOT NULL DEFAULT 0",
            )
            self._ensure_column(
                connection,
                table_name="inspection_runs",
                column_name="fiducial_status",
                definition="TEXT NOT NULL DEFAULT 'not_required'",
            )
            self._ensure_column(
                connection,
                table_name="inspection_runs",
                column_name="fiducials_json",
                definition="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="inspection_runs",
                column_name="requires_barcode",
                definition="INTEGER NOT NULL DEFAULT 0",
            )
            self._ensure_column(
                connection,
                table_name="inspection_runs",
                column_name="barcode_status",
                definition="TEXT NOT NULL DEFAULT 'not_required'",
            )
            self._ensure_column(
                connection,
                table_name="inspection_runs",
                column_name="barcode_json",
                definition="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="defect_logs",
                column_name="run_image_id",
                definition="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="defect_logs",
                column_name="overlay_x",
                definition="REAL",
            )
            self._ensure_column(
                connection,
                table_name="defect_logs",
                column_name="overlay_y",
                definition="REAL",
            )
            self._ensure_column(
                connection,
                table_name="defect_logs",
                column_name="overlay_width",
                definition="REAL",
            )
            self._ensure_column(
                connection,
                table_name="defect_logs",
                column_name="overlay_height",
                definition="REAL",
            )
            self._ensure_column(
                connection,
                table_name="defect_logs",
                column_name="overlay_shape",
                definition="TEXT",
            )

    def persist_events(
        self,
        *,
        events: list[InferenceEvent],
        model_version: str | None = None,
        images: list[RunImageInput] | None = None,
    ) -> PersistedRun:
        if not events:
            raise ValueError("cannot persist an empty event list")

        run_id = str(uuid.uuid4())
        status = self._derive_run_status(events)
        pcb_id = events[0].pcb_id
        run_timestamp = events[0].timestamp
        image_records = images or [
            RunImageInput(
                image_path=DEMO_RUN_IMAGE_PATH,
                image_role=DEMO_RUN_IMAGE_ROLE,
                image_width=DEMO_RUN_IMAGE_WIDTH,
                image_height=DEMO_RUN_IMAGE_HEIGHT,
            )
        ]
        run_image_ids = [str(uuid.uuid4()) for _ in image_records]

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO inspection_runs (
                    id, pcb_id, timestamp, model_version, status, model_name, setup_status,
                    requires_fiducials, fiducial_status, fiducials_json,
                    requires_barcode, barcode_status, barcode_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, pcb_id, run_timestamp, model_version, status, None, "review_ready",
                    0, "not_required", None,
                    0, "not_required", None,
                ),
            )
            connection.executemany(
                """
                INSERT INTO run_images (
                    id,
                    run_id,
                    image_path,
                    image_role,
                    image_width,
                    image_height,
                    sort_order,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        image_id,
                        run_id,
                        image.image_path,
                        image.image_role,
                        image.image_width,
                        image.image_height,
                        index,
                        run_timestamp,
                    )
                    for index, (image_id, image) in enumerate(zip(run_image_ids, image_records, strict=True))
                ],
            )
            connection.executemany(
                """
                INSERT INTO defect_logs (
                    run_id,
                    run_image_id,
                    component_id,
                    defect_type,
                    severity,
                    confidence_score,
                    inference_latency_ms,
                    inspection_result,
                    timestamp,
                    overlay_x,
                    overlay_y,
                    overlay_width,
                    overlay_height,
                    overlay_shape
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        run_image_ids[self._resolve_image_index(event, len(run_image_ids))],
                        event.component_id,
                        event.defect_type,
                        self._derive_severity(event),
                        event.confidence_score,
                        event.inference_latency_ms,
                        event.inspection_result.value,
                        event.timestamp,
                        *self._resolve_overlay(event, index),
                    )
                    for index, event in enumerate(events)
                ],
            )

        return PersistedRun(run_id=run_id, pcb_id=pcb_id, status=status, event_count=len(events))

    def create_run(self, *, pcb_id: str | None = None) -> dict[str, object]:
        run_id = str(uuid.uuid4())
        run_timestamp = datetime.now(timezone.utc).isoformat()
        run_pcb_id = pcb_id.strip() if pcb_id and pcb_id.strip() else self._build_default_pcb_id(run_id)
        run_row = {
            "id": run_id,
            "pcb_id": run_pcb_id,
            "timestamp": run_timestamp,
            "model_version": None,
            "model_name": None,
            "status": "SETUP",
            "setup_status": "not_ready",
            "requires_fiducials": 0,
            "fiducial_status": "not_required",
            "fiducials": [],
            "requires_barcode": 0,
            "barcode_status": "not_required",
            "barcode": None,
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO inspection_runs (
                    id, pcb_id, timestamp, model_version, status, model_name, setup_status,
                    requires_fiducials, fiducial_status, fiducials_json,
                    requires_barcode, barcode_status, barcode_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_row["id"],
                    run_row["pcb_id"],
                    run_row["timestamp"],
                    run_row["model_version"],
                    run_row["status"],
                    run_row["model_name"],
                    run_row["setup_status"],
                    run_row["requires_fiducials"],
                    run_row["fiducial_status"],
                    None,
                    run_row["requires_barcode"],
                    run_row["barcode_status"],
                    None,
                ),
            )
        return run_row

    def update_run(
        self,
        run_id: str,
        *,
        model_name: str | None = None,
        requires_fiducials: bool | None = None,
        requires_barcode: bool | None = None,
        setup_status: str | None = None,
    ) -> dict[str, object] | None:
        run_row = self.fetch_run(run_id)
        if run_row is None:
            return None

        next_model_name = run_row.get("model_name")
        if model_name is not None:
            next_model_name = model_name.strip() or None

        next_requires_fiducials = int(bool(run_row.get("requires_fiducials")))
        if requires_fiducials is not None:
            next_requires_fiducials = int(requires_fiducials)

        next_fiducial_status = self._calculate_fiducial_status(
            run_id,
            requires_fiducials=bool(next_requires_fiducials),
            current_status=str(run_row.get("fiducial_status") or "not_required"),
        )
        next_requires_barcode = int(bool(run_row.get("requires_barcode")))
        if requires_barcode is not None:
            next_requires_barcode = int(requires_barcode)
        next_barcode_status = self._calculate_barcode_status(
            run_id,
            requires_barcode=bool(next_requires_barcode),
            current_status=str(run_row.get("barcode_status") or "not_required"),
        )
        next_setup_status = setup_status or self._calculate_setup_status(
            run_id,
            next_model_name,
            requires_fiducials=bool(next_requires_fiducials),
            fiducial_status=next_fiducial_status,
            requires_barcode=bool(next_requires_barcode),
            barcode_status=next_barcode_status,
        )

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE inspection_runs
                SET model_name = ?, requires_fiducials = ?, fiducial_status = ?,
                    requires_barcode = ?, barcode_status = ?, setup_status = ?
                WHERE id = ?
                """,
                (
                    next_model_name,
                    next_requires_fiducials,
                    next_fiducial_status,
                    next_requires_barcode,
                    next_barcode_status,
                    next_setup_status,
                    run_id,
                ),
            )
        return self.fetch_run(run_id)

    def fetch_run(self, run_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, pcb_id, timestamp, model_version, model_name, status, setup_status,
                       requires_fiducials, fiducial_status, fiducials_json,
                       requires_barcode, barcode_status, barcode_json
                FROM inspection_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["requires_fiducials"] = bool(payload.get("requires_fiducials"))
        payload["fiducials"] = json.loads(payload["fiducials_json"]) if payload.get("fiducials_json") else []
        payload["requires_barcode"] = bool(payload.get("requires_barcode"))
        payload["barcode"] = json.loads(payload["barcode_json"]) if payload.get("barcode_json") else None
        payload.pop("fiducials_json", None)
        payload.pop("barcode_json", None)
        return payload

    def fetch_defect_logs(
        self,
        run_id: str,
        *,
        component_id: str | None = None,
        defect_type: str | None = None,
        severity: str | None = None,
        inspection_result: str | None = None,
    ) -> list[dict[str, object]]:
        clauses = ["run_id = ?"]
        params: list[object] = [run_id]
        if component_id is not None:
            clauses.append("component_id = ?")
            params.append(component_id)
        if defect_type is not None:
            clauses.append("defect_type = ?")
            params.append(defect_type)
        if severity is not None:
            clauses.append("severity = ?")
            params.append(severity)
        if inspection_result is not None:
            clauses.append("inspection_result = ?")
            params.append(inspection_result)

        where_clause = " AND ".join(clauses)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, run_id, run_image_id, component_id, defect_type, severity, confidence_score,
                       inference_latency_ms, inspection_result, timestamp, overlay_x, overlay_y,
                       overlay_width, overlay_height, overlay_shape
                FROM defect_logs
                WHERE {where_clause}
                ORDER BY id ASC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def fetch_run_images(self, run_id: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at
                FROM run_images
                WHERE run_id = ?
                ORDER BY sort_order ASC, created_at ASC
                """,
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_runs(
        self,
        *,
        limit: int = 20,
        pcb_id: str | None = None,
        status: str | None = None,
        model_version: str | None = None,
        defect_type: str | None = None,
    ) -> list[dict[str, object]]:
        safe_limit = max(1, min(limit, 200))
        clauses: list[str] = []
        params: list[object] = []
        if pcb_id is not None:
            clauses.append("r.pcb_id = ?")
            params.append(pcb_id)
        if status is not None:
            clauses.append("r.status = ?")
            params.append(status)
        if model_version is not None:
            clauses.append("r.model_version = ?")
            params.append(model_version)
        if defect_type is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM defect_logs AS dx WHERE dx.run_id = r.id AND dx.defect_type = ?)"
            )
            params.append(defect_type)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(safe_limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    r.id,
                    r.pcb_id,
                    r.timestamp,
                    r.model_version,
                    r.model_name,
                    r.status,
                    r.setup_status,
                    r.requires_fiducials,
                    r.fiducial_status,
                    r.requires_barcode,
                    r.barcode_status,
                    COUNT(d.id) AS event_count
                FROM inspection_runs AS r
                LEFT JOIN defect_logs AS d ON d.run_id = r.id
                {where_sql}
                GROUP BY r.id, r.pcb_id, r.timestamp, r.model_version, r.model_name, r.status, r.setup_status,
                         r.requires_fiducials, r.fiducial_status, r.requires_barcode, r.barcode_status
                ORDER BY r.timestamp DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        payload = []
        for row in rows:
            entry = dict(row)
            entry["requires_fiducials"] = bool(entry.get("requires_fiducials"))
            entry["requires_barcode"] = bool(entry.get("requires_barcode"))
            payload.append(entry)
        return payload

    def fetch_run_with_defects(
        self,
        run_id: str,
        *,
        component_id: str | None = None,
        defect_type: str | None = None,
        severity: str | None = None,
        inspection_result: str | None = None,
    ) -> dict[str, object] | None:
        run_row = self.fetch_run(run_id)
        if run_row is None:
            return None
        self._ensure_run_assets(run_row)
        run_row["images"] = self.fetch_run_images(run_id)
        run_row["defect_logs"] = self.fetch_defect_logs(
            run_id,
            component_id=component_id,
            defect_type=defect_type,
            severity=severity,
            inspection_result=inspection_result,
        )
        run_row["event_count"] = len(run_row["defect_logs"])
        return run_row

    def add_run_image(
        self,
        run_id: str,
        *,
        image_id: str,
        image_path: str,
        image_role: str,
        image_width: int,
        image_height: int,
        created_at: str,
    ) -> dict[str, object] | None:
        if self.fetch_run(run_id) is None:
            return None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (image_id, run_id, image_path, image_role, image_width, image_height, 0, created_at),
            )
        return self.update_run(run_id)

    def detect_fiducials(self, run_id: str) -> dict[str, object] | None:
        run_row = self.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_fiducials"]:
            raise ValueError("fiducials are not required for this run")
        images = self.fetch_run_images(run_id)
        if not images:
            raise ValueError("scan image is required before fiducial detection")

        fiducials = self._build_mock_fiducials(images[0]["id"])
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE inspection_runs
                SET fiducial_status = ?, fiducials_json = ?, setup_status = ?
                WHERE id = ?
                """,
                (
                    "needs_review",
                    json.dumps(fiducials),
                    self._calculate_setup_status(
                        run_id,
                        run_row.get("model_name"),
                        requires_fiducials=True,
                        fiducial_status="needs_review",
                    ),
                    run_id,
                ),
            )
        return self.fetch_run(run_id)

    def confirm_fiducials(self, run_id: str) -> dict[str, object] | None:
        run_row = self.fetch_run(run_id)
        if run_row is None:
            return None
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE inspection_runs
                SET fiducial_status = ?, setup_status = ?
                WHERE id = ?
                """,
                (
                    "confirmed",
                    self._calculate_setup_status(
                        run_id,
                        run_row.get("model_name"),
                        requires_fiducials=bool(run_row.get("requires_fiducials")),
                        fiducial_status="confirmed",
                    ),
                    run_id,
                ),
            )
        return self.fetch_run(run_id)

    def detect_barcode(self, run_id: str) -> dict[str, object] | None:
        run_row = self.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_barcode"]:
            raise ValueError("barcode is not required for this run")
        images = self.fetch_run_images(run_id)
        if not images:
            raise ValueError("scan image is required before barcode detection")

        barcode = self._build_mock_barcode(images[0]["id"], str(run_row["pcb_id"]))
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE inspection_runs
                SET barcode_status = ?, barcode_json = ?, setup_status = ?
                WHERE id = ?
                """,
                (
                    "needs_review",
                    json.dumps(barcode),
                    self._calculate_setup_status(
                        run_id,
                        run_row.get("model_name"),
                        requires_fiducials=bool(run_row.get("requires_fiducials")),
                        fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
                        requires_barcode=True,
                        barcode_status="needs_review",
                    ),
                    run_id,
                ),
            )
        return self.fetch_run(run_id)

    def confirm_barcode(self, run_id: str) -> dict[str, object] | None:
        run_row = self.fetch_run(run_id)
        if run_row is None:
            return None
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE inspection_runs
                SET barcode_status = ?, setup_status = ?
                WHERE id = ?
                """,
                (
                    "confirmed",
                    self._calculate_setup_status(
                        run_id,
                        run_row.get("model_name"),
                        requires_fiducials=bool(run_row.get("requires_fiducials")),
                        fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
                        requires_barcode=bool(run_row.get("requires_barcode")),
                        barcode_status="confirmed",
                    ),
                    run_id,
                ),
            )
        return self.fetch_run(run_id)

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

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection,
        *,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing_columns = {row["name"] for row in rows}
        if column_name in existing_columns:
            return
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    @staticmethod
    def _build_overlay(index: int) -> dict[str, float | str]:
        columns = 4
        column = index % columns
        row = (index // columns) % 3
        return {
            "overlay_x": round(0.07 + column * 0.18, 4),
            "overlay_y": round(0.12 + row * 0.2, 4),
            "overlay_width": 0.09,
            "overlay_height": 0.09,
            "overlay_shape": "rect",
        }

    @staticmethod
    def _resolve_image_index(event: InferenceEvent, image_count: int) -> int:
        if event.run_image_index is None:
            return 0
        if event.run_image_index >= image_count:
            raise ValueError("run_image_index points to a missing image")
        return event.run_image_index

    @staticmethod
    def _resolve_overlay(event: InferenceEvent, index: int) -> tuple[float, float, float, float, str]:
        fallback = DatabaseManager._build_overlay(index)
        return (
            event.overlay_x if event.overlay_x is not None else float(fallback["overlay_x"]),
            event.overlay_y if event.overlay_y is not None else float(fallback["overlay_y"]),
            event.overlay_width if event.overlay_width is not None else float(fallback["overlay_width"]),
            event.overlay_height if event.overlay_height is not None else float(fallback["overlay_height"]),
            event.overlay_shape or str(fallback["overlay_shape"]),
        )

    def _ensure_run_assets(self, run_row: dict[str, object]) -> None:
        run_id = str(run_row["id"])
        with self._connect() as connection:
            image_rows = connection.execute(
                "SELECT id FROM run_images WHERE run_id = ? ORDER BY sort_order ASC, created_at ASC",
                (run_id,),
            ).fetchall()

            if not image_rows:
                # We no longer auto-inject DEMO_RUN_IMAGE_PATH here.
                # This allows the frontend to show the Upload UI.
                return

            run_image_id = str(image_rows[0]["id"])
            defect_rows = connection.execute(
                """
                SELECT id, run_image_id, overlay_x, overlay_y, overlay_width, overlay_height, overlay_shape
                FROM defect_logs
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()

            for index, defect_row in enumerate(defect_rows):
                needs_update = (
                    defect_row["run_image_id"] is None
                    or defect_row["overlay_x"] is None
                    or defect_row["overlay_y"] is None
                    or defect_row["overlay_width"] is None
                    or defect_row["overlay_height"] is None
                    or defect_row["overlay_shape"] is None
                )
                if not needs_update:
                    continue
                overlay = self._build_overlay(index)
                connection.execute(
                    """
                    UPDATE defect_logs
                    SET run_image_id = ?,
                        overlay_x = ?,
                        overlay_y = ?,
                        overlay_width = ?,
                        overlay_height = ?,
                        overlay_shape = ?
                    WHERE id = ?
                    """,
                    (
                        run_image_id,
                        overlay["overlay_x"],
                        overlay["overlay_y"],
                        overlay["overlay_width"],
                        overlay["overlay_height"],
                        overlay["overlay_shape"],
                        defect_row["id"],
                    ),
                )

    @staticmethod
    def _build_default_pcb_id(run_id: str) -> str:
        return f"RUN-{run_id.split('-')[0].upper()}"

    @staticmethod
    def _build_mock_fiducials(run_image_id: str) -> list[dict[str, object]]:
        return [
            {"id": "fid-1", "run_image_id": run_image_id, "x": 0.08, "y": 0.1, "width": 0.035, "height": 0.035, "confidence": 0.98},
            {"id": "fid-2", "run_image_id": run_image_id, "x": 0.86, "y": 0.12, "width": 0.035, "height": 0.035, "confidence": 0.94},
            {"id": "fid-3", "run_image_id": run_image_id, "x": 0.12, "y": 0.82, "width": 0.035, "height": 0.035, "confidence": 0.91},
        ]

    def _calculate_fiducial_status(self, run_id: str, *, requires_fiducials: bool, current_status: str) -> str:
        if not requires_fiducials:
            return "not_required"
        if not self.fetch_run_images(run_id):
            return "blocked"
        if current_status in {"needs_review", "confirmed"}:
            return current_status
        return "ready"

    def _calculate_barcode_status(self, run_id: str, *, requires_barcode: bool, current_status: str) -> str:
        if not requires_barcode:
            return "not_required"
        if not self.fetch_run_images(run_id):
            return "blocked"
        if current_status in {"needs_review", "confirmed"}:
            return current_status
        return "ready"

    def _calculate_setup_status(
        self,
        run_id: str,
        model_name: object,
        *,
        requires_fiducials: bool = False,
        fiducial_status: str = "not_required",
        requires_barcode: bool = False,
        barcode_status: str = "not_required",
    ) -> str:
        has_model = bool(model_name and str(model_name).strip())
        has_images = bool(self.fetch_run_images(run_id))
        fiducials_ready = (not requires_fiducials or fiducial_status == "confirmed")
        barcode_ready = (not requires_barcode or barcode_status == "confirmed")
        if has_model and has_images and fiducials_ready and barcode_ready:
            return "review_ready"
        if has_model or has_images:
            return "in_progress"
        return "not_ready"

    @staticmethod
    def _build_mock_barcode(run_image_id: str, pcb_id: str) -> dict[str, object]:
        return {
            "id": "barcode-1",
            "run_image_id": run_image_id,
            "x": 0.72,
            "y": 0.78,
            "width": 0.16,
            "height": 0.08,
            "confidence": 0.93,
            "decoded_value": f"{pcb_id}-LOT-01",
        }
