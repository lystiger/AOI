from __future__ import annotations

import json
import sqlite3
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageFilter, UnidentifiedImageError

from aoi.schema import InferenceEvent, InspectionResult, RunImageInput


@dataclass(slots=True)
class PersistedRun:
    run_id: str
    pcb_id: str
    status: str
    event_count: int


class DatabaseManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.storage_path = self.db_path.parent / "run-assets"
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
        image_records = images or []
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
                        run_image_ids[self._resolve_image_index(event, len(run_image_ids))]
                        if run_image_ids
                        else None,
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
        run_row["requires_fiducials"] = False
        run_row["requires_barcode"] = False
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

        current_model_name = str(run_row.get("model_name") or "").strip()
        next_model_name = run_row.get("model_name")
        if model_name is not None:
            next_model_name = model_name.strip() or None
        next_model_name_text = str(next_model_name or "").strip()
        model_changed = model_name is not None and next_model_name_text != current_model_name

        next_requires_fiducials = int(bool(run_row.get("requires_fiducials")))
        current_requires_fiducials = next_requires_fiducials
        if requires_fiducials is not None:
            next_requires_fiducials = int(requires_fiducials)
        fiducial_requirement_changed = next_requires_fiducials != current_requires_fiducials

        current_fiducial_status = str(run_row.get("fiducial_status") or "not_required")
        next_fiducial_status = current_fiducial_status
        next_fiducials_json = json.dumps(run_row.get("fiducials") or []) if run_row.get("fiducials") else None
        if model_changed or fiducial_requirement_changed:
            next_fiducials_json = None
            if not bool(next_requires_fiducials):
                next_fiducial_status = "not_required"
            else:
                next_fiducial_status = "ready" if self.fetch_run_images(run_id) else "blocked"

        next_fiducial_status = self._calculate_fiducial_status(
            run_id,
            requires_fiducials=bool(next_requires_fiducials),
            current_status=next_fiducial_status,
        )
        next_requires_barcode = int(bool(run_row.get("requires_barcode")))
        current_requires_barcode = next_requires_barcode
        if requires_barcode is not None:
            next_requires_barcode = int(requires_barcode)
        barcode_requirement_changed = next_requires_barcode != current_requires_barcode

        current_barcode_status = str(run_row.get("barcode_status") or "not_required")
        next_barcode_status = current_barcode_status
        next_barcode_json = json.dumps(run_row.get("barcode")) if run_row.get("barcode") else None
        if model_changed or barcode_requirement_changed:
            next_barcode_json = None
            if not bool(next_requires_barcode):
                next_barcode_status = "not_required"
            else:
                next_barcode_status = "ready" if self.fetch_run_images(run_id) else "blocked"
        next_barcode_status = self._calculate_barcode_status(
            run_id,
            requires_barcode=bool(next_requires_barcode),
            current_status=next_barcode_status,
        )
        next_setup_status = setup_status or self._calculate_setup_status(
            run_id,
            next_model_name,
            requires_fiducials=bool(next_requires_fiducials),
            fiducial_status=next_fiducial_status,
            requires_barcode=bool(next_requires_barcode),
            barcode_status=next_barcode_status,
        )

        next_status = str(run_row.get("status") or "SETUP")
        if next_setup_status != "review_ready":
            next_status = "SETUP"

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE inspection_runs
                SET model_name = ?, requires_fiducials = ?, fiducial_status = ?, fiducials_json = ?,
                    requires_barcode = ?, barcode_status = ?, barcode_json = ?, setup_status = ?,
                    status = ?
                WHERE id = ?
                """,
                (
                    next_model_name,
                    next_requires_fiducials,
                    next_fiducial_status,
                    next_fiducials_json,
                    next_requires_barcode,
                    next_barcode_status,
                    next_barcode_json,
                    next_setup_status,
                    next_status,
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

    def delete_run(self, run_id: str) -> bool:
        if self.fetch_run(run_id) is None:
            return False

        with self._connect() as connection:
            connection.execute("DELETE FROM defect_logs WHERE run_id = ?", (run_id,))
            connection.execute("DELETE FROM run_images WHERE run_id = ?", (run_id,))
            connection.execute("DELETE FROM inspection_runs WHERE id = ?", (run_id,))
        return True

    def detect_fiducials(self, run_id: str) -> dict[str, object] | None:
        run_row = self.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_fiducials"]:
            raise ValueError("fiducials are not required for this run")
        images = self.fetch_run_images(run_id)
        if not images:
            raise ValueError("scan image is required before fiducial detection")

        detection_failure = self._detect_fiducial_failure(images[0], run_id)
        if detection_failure is not None:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE inspection_runs
                    SET fiducial_status = ?, fiducials_json = ?, setup_status = ?
                    WHERE id = ?
                    """,
                    (
                        "failed",
                        None,
                        self._calculate_setup_status(
                            run_id,
                            run_row.get("model_name"),
                            requires_fiducials=True,
                            fiducial_status="failed",
                            requires_barcode=bool(run_row.get("requires_barcode")),
                            barcode_status=str(run_row.get("barcode_status") or "not_required"),
                        ),
                        run_id,
                    ),
                )
            raise ValueError(detection_failure)

        fiducials = self._detect_fiducials_from_image(images[0], run_id)
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
                        requires_barcode=bool(run_row.get("requires_barcode")),
                        barcode_status=str(run_row.get("barcode_status") or "not_required"),
                    ),
                    run_id,
                ),
            )
        return self.fetch_run(run_id)

    def confirm_fiducials(self, run_id: str) -> dict[str, object] | None:
        run_row = self.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_fiducials"]:
            raise ValueError("fiducials are not required for this run")
        if str(run_row.get("fiducial_status") or "") != "needs_review":
            raise ValueError("fiducials must be in needs_review before confirmation")
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
                        requires_barcode=bool(run_row.get("requires_barcode")),
                        barcode_status=str(run_row.get("barcode_status") or "not_required"),
                    ),
                    run_id,
                ),
            )
        return self.fetch_run(run_id)

    def save_manual_fiducials(self, run_id: str, fiducials: list[dict[str, object]]) -> dict[str, object] | None:
        run_row = self.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_fiducials"]:
            raise ValueError("fiducials are not required for this run")
        images = self.fetch_run_images(run_id)
        if not images:
            raise ValueError("scan image is required before saving fiducials")

        normalized_fiducials = self._normalize_manual_fiducials(fiducials, images[0]["id"])
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE inspection_runs
                SET fiducial_status = ?, fiducials_json = ?, setup_status = ?
                WHERE id = ?
                """,
                (
                    "confirmed",
                    json.dumps(normalized_fiducials),
                    self._calculate_setup_status(
                        run_id,
                        run_row.get("model_name"),
                        requires_fiducials=True,
                        fiducial_status="confirmed",
                        requires_barcode=bool(run_row.get("requires_barcode")),
                        barcode_status=str(run_row.get("barcode_status") or "not_required"),
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

        detection_failure = self._detect_barcode_failure(images[0])
        if detection_failure is not None:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE inspection_runs
                    SET barcode_status = ?, barcode_json = ?, setup_status = ?
                    WHERE id = ?
                    """,
                    (
                        "failed",
                        None,
                        self._calculate_setup_status(
                            run_id,
                            run_row.get("model_name"),
                            requires_fiducials=bool(run_row.get("requires_fiducials")),
                            fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
                            requires_barcode=True,
                            barcode_status="failed",
                        ),
                        run_id,
                    ),
                )
            raise ValueError(detection_failure)

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
        if not run_row["requires_barcode"]:
            raise ValueError("barcode is not required for this run")
        if str(run_row.get("barcode_status") or "") != "needs_review":
            raise ValueError("barcode must be in needs_review before confirmation")
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

    def save_manual_barcode(self, run_id: str, barcode: dict[str, object]) -> dict[str, object] | None:
        run_row = self.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_barcode"]:
            raise ValueError("barcode is not required for this run")
        images = self.fetch_run_images(run_id)
        if not images:
            raise ValueError("scan image is required before saving barcode")

        normalized_barcode = self._normalize_manual_barcode(barcode, images[0]["id"])
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE inspection_runs
                SET barcode_status = ?, barcode_json = ?, setup_status = ?
                WHERE id = ?
                """,
                (
                    "confirmed",
                    json.dumps(normalized_barcode),
                    self._calculate_setup_status(
                        run_id,
                        run_row.get("model_name"),
                        requires_fiducials=bool(run_row.get("requires_fiducials")),
                        fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
                        requires_barcode=True,
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
        if image_count == 0:
            return 0
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

    @staticmethod
    def _build_default_pcb_id(run_id: str) -> str:
        return f"RUN-{run_id.split('-')[0].upper()}"

    def _calculate_fiducial_status(self, run_id: str, *, requires_fiducials: bool, current_status: str) -> str:
        if not requires_fiducials:
            return "not_required"
        if not self.fetch_run_images(run_id):
            return "blocked"
        if current_status in {"needs_review", "confirmed", "failed"}:
            return current_status
        return "ready"

    def _calculate_barcode_status(self, run_id: str, *, requires_barcode: bool, current_status: str) -> str:
        if not requires_barcode:
            return "not_required"
        if not self.fetch_run_images(run_id):
            return "blocked"
        if current_status in {"needs_review", "confirmed", "failed"}:
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

    def _detect_fiducial_failure(self, image: dict[str, object], run_id: str) -> str | None:
        width = int(image.get("image_width") or 0)
        height = int(image.get("image_height") or 0)
        if width < 320 or height < 240:
            return "fiducial detection failed: scan resolution is too small for reliable alignment"
        try:
            fiducials = self._detect_fiducials_from_image(image, run_id)
        except ValueError as exc:
            return str(exc)
        if len(fiducials) < 3:
            return "fiducial detection failed: found fewer than 3 fiducial candidates"
        return None

    @staticmethod
    def _detect_barcode_failure(image: dict[str, object]) -> str | None:
        if int(image.get("image_width") or 0) < 960 or int(image.get("image_height") or 0) < 540:
            return "barcode detection failed: scan resolution is too small for reliable decoding"
        return None

    @staticmethod
    def _normalize_detection_box(
        payload: dict[str, object],
        *,
        run_image_id: str,
        fallback_id: str,
        require_decoded_value: bool = False,
    ) -> dict[str, object]:
        decoded_value = str(payload.get("decoded_value") or "").strip()
        if require_decoded_value and not decoded_value:
            raise ValueError("decoded_value must be a non-empty string")

        normalized = {
            "id": str(payload.get("id") or fallback_id),
            "run_image_id": run_image_id,
            "x": DatabaseManager._require_normalized_float(payload, "x"),
            "y": DatabaseManager._require_normalized_float(payload, "y"),
            "width": DatabaseManager._require_positive_normalized_float(payload, "width"),
            "height": DatabaseManager._require_positive_normalized_float(payload, "height"),
            "confidence": DatabaseManager._optional_normalized_confidence(payload.get("confidence")),
        }
        if require_decoded_value:
            normalized["decoded_value"] = decoded_value
        return normalized

    @staticmethod
    def _normalize_manual_fiducials(fiducials: list[dict[str, object]], run_image_id: str) -> list[dict[str, object]]:
        if len(fiducials) < 3:
            raise ValueError("at least 3 fiducials are required")
        return [
            DatabaseManager._normalize_detection_box(entry, run_image_id=run_image_id, fallback_id=f"fid-{index + 1}")
            for index, entry in enumerate(fiducials)
        ]

    @staticmethod
    def _normalize_manual_barcode(barcode: dict[str, object], run_image_id: str) -> dict[str, object]:
        return DatabaseManager._normalize_detection_box(
            barcode,
            run_image_id=run_image_id,
            fallback_id="barcode-1",
            require_decoded_value=True,
        )

    @staticmethod
    def _require_normalized_float(payload: dict[str, object], key: str) -> float:
        value = payload.get(key)
        if not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a number")
        number = float(value)
        if number < 0 or number > 1:
            raise ValueError(f"{key} must be between 0 and 1")
        return number

    @staticmethod
    def _require_positive_normalized_float(payload: dict[str, object], key: str) -> float:
        number = DatabaseManager._require_normalized_float(payload, key)
        if number <= 0:
            raise ValueError(f"{key} must be greater than 0")
        return number

    @staticmethod
    def _optional_normalized_confidence(value: object) -> float:
        if value is None:
            return 1.0
        if not isinstance(value, (int, float)):
            raise ValueError("confidence must be a number")
        number = float(value)
        if number < 0 or number > 1:
            raise ValueError("confidence must be between 0 and 1")
        return number

    def _detect_fiducials_from_image(self, image: dict[str, object], run_id: str) -> list[dict[str, object]]:
        image_file = self._resolve_run_image_file(run_id, image)
        try:
            with Image.open(image_file) as source_image:
                rgb_image = source_image.convert("RGB")
        except (FileNotFoundError, UnidentifiedImageError) as exc:
            raise ValueError(f"fiducial detection failed: unable to read scan image from {image_file}") from exc

        original_width, original_height = rgb_image.size
        working_image, scale = self._prepare_detection_image(rgb_image)
        candidate_mask = self._build_fiducial_candidate_mask(working_image)
        components = self._extract_mask_components(candidate_mask, *working_image.size)
        candidates = self._score_fiducial_components(
            components,
            run_image_id=str(image["id"]),
            image_size=working_image.size,
            original_size=(original_width, original_height),
            scale=scale,
        )
        fiducials = self._select_fiducial_candidates(candidates)
        if len(fiducials) < 3:
            raise ValueError("fiducial detection failed: found fewer than 3 fiducial candidates")
        return fiducials

    def _resolve_run_image_file(self, run_id: str, image: dict[str, object]) -> Path:
        image_path = str(image.get("image_path") or "").strip()
        if not image_path:
            raise ValueError("fiducial detection failed: scan image path is empty")

        path = Path(image_path)
        if path.is_absolute() and path.exists():
            return path
        if path.exists():
            return path.resolve()

        if image_path.startswith(f"/runs/{run_id}/images/"):
            run_dir = self.storage_path / run_id
            for pattern in ("scan.png", "scan.jpg", "scan.jpeg", "scan.webp"):
                candidate = run_dir / pattern
                if candidate.exists():
                    return candidate

        candidate = self.db_path.parent / image_path.lstrip("/")
        if candidate.exists():
            return candidate
        raise ValueError(f"fiducial detection failed: scan image file does not exist for {image_path}")

    @staticmethod
    def _prepare_detection_image(image: Image.Image) -> tuple[Image.Image, float]:
        width, height = image.size
        max_dimension = max(width, height)
        if max_dimension <= 1000:
            return image, 1.0
        scale = max_dimension / 1000.0
        resized = image.resize((max(1, int(width / scale)), max(1, int(height / scale))), Image.Resampling.LANCZOS)
        return resized, scale

    @staticmethod
    def _build_fiducial_candidate_mask(image: Image.Image) -> list[int]:
        hsv_image = image.convert("HSV")
        width, height = hsv_image.size
        hsv_pixels = hsv_image.load()
        mask = [0] * (width * height)
        for y in range(height):
            for x in range(width):
                hue, saturation, value = hsv_pixels[x, y]
                gold_like = 12 <= hue <= 48 and saturation >= 55 and value >= 90
                bright_neutral = saturation <= 40 and value >= 175
                if gold_like or bright_neutral:
                    mask[(y * width) + x] = 255

        mask_image = Image.new("L", (width, height))
        mask_image.putdata(mask)
        cleaned = mask_image.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
        return [1 if value >= 128 else 0 for value in cleaned.tobytes()]

    @staticmethod
    def _extract_mask_components(mask: list[int], width: int | None = None, height: int | None = None) -> list[dict[str, int]]:
        if width is None or height is None:
            raise ValueError("mask width and height are required")
        visited = [False] * len(mask)
        components: list[dict[str, int]] = []
        for start_index, value in enumerate(mask):
            if value == 0 or visited[start_index]:
                continue
            queue: deque[int] = deque([start_index])
            visited[start_index] = True
            area = 0
            min_x = width
            min_y = height
            max_x = 0
            max_y = 0
            while queue:
                index = queue.popleft()
                x = index % width
                y = index // width
                area += 1
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                for delta_x, delta_y in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
                    next_x = x + delta_x
                    next_y = y + delta_y
                    if next_x < 0 or next_x >= width or next_y < 0 or next_y >= height:
                        continue
                    next_index = (next_y * width) + next_x
                    if visited[next_index] or mask[next_index] == 0:
                        continue
                    visited[next_index] = True
                    queue.append(next_index)
            components.append(
                {
                    "area": area,
                    "min_x": min_x,
                    "min_y": min_y,
                    "max_x": max_x,
                    "max_y": max_y,
                }
            )
        return components

    @staticmethod
    def _score_fiducial_components(
        components: list[dict[str, int]],
        *,
        run_image_id: str,
        image_size: tuple[int, int],
        original_size: tuple[int, int],
        scale: float,
    ) -> list[dict[str, object]]:
        width, height = image_size
        original_width, original_height = original_size
        image_area = width * height
        diagonal = (width**2 + height**2) ** 0.5
        candidates: list[dict[str, object]] = []
        for component in components:
            box_width = component["max_x"] - component["min_x"] + 1
            box_height = component["max_y"] - component["min_y"] + 1
            box_area = box_width * box_height
            if component["area"] < max(20, int(image_area * 0.00008)):
                continue
            if component["area"] > int(image_area * 0.02):
                continue
            aspect_ratio = box_width / max(box_height, 1)
            if aspect_ratio < 0.45 or aspect_ratio > 2.2:
                continue
            fill_ratio = component["area"] / max(box_area, 1)
            if fill_ratio < 0.2 or fill_ratio > 0.95:
                continue

            center_x = (component["min_x"] + component["max_x"]) / 2
            center_y = (component["min_y"] + component["max_y"]) / 2
            corner_distances = {
                "top_left": (center_x**2 + center_y**2) ** 0.5,
                "top_right": ((width - center_x) ** 2 + center_y**2) ** 0.5,
                "bottom_left": (center_x**2 + (height - center_y) ** 2) ** 0.5,
                "bottom_right": ((width - center_x) ** 2 + (height - center_y) ** 2) ** 0.5,
            }
            nearest_corner = min(corner_distances, key=corner_distances.get)
            corner_proximity = 1.0 - (corner_distances[nearest_corner] / max(diagonal, 1.0))
            size_balance = 1.0 - abs(box_width - box_height) / max(box_width, box_height, 1)
            score = (corner_proximity * 2.5) + size_balance + fill_ratio

            candidates.append(
                {
                    "id": f"fid-{len(candidates) + 1}",
                    "run_image_id": run_image_id,
                    "x": max((component["min_x"] * scale) / original_width, 0.0),
                    "y": max((component["min_y"] * scale) / original_height, 0.0),
                    "width": min((box_width * scale) / original_width, 1.0),
                    "height": min((box_height * scale) / original_height, 1.0),
                    "confidence": round(min(0.99, 0.45 + (score / 6.0)), 3),
                    "score": score,
                    "corner": nearest_corner,
                }
            )
        return candidates

    @staticmethod
    def _select_fiducial_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
        sorted_candidates = sorted(candidates, key=lambda item: float(item["score"]), reverse=True)
        selected: list[dict[str, object]] = []
        used_corners: set[str] = set()
        for candidate in sorted_candidates:
            corner = str(candidate["corner"])
            if corner in used_corners:
                continue
            selected.append(
                {
                    "id": f"fid-{len(selected) + 1}",
                    "run_image_id": candidate["run_image_id"],
                    "x": round(float(candidate["x"]), 4),
                    "y": round(float(candidate["y"]), 4),
                    "width": round(float(candidate["width"]), 4),
                    "height": round(float(candidate["height"]), 4),
                    "confidence": float(candidate["confidence"]),
                }
            )
            used_corners.add(corner)
            if len(selected) == 3:
                break
        if len(selected) >= 3:
            return selected
        for candidate in sorted_candidates:
            if len(selected) >= 3:
                break
            normalized = {
                "id": f"fid-{len(selected) + 1}",
                "run_image_id": candidate["run_image_id"],
                "x": round(float(candidate["x"]), 4),
                "y": round(float(candidate["y"]), 4),
                "width": round(float(candidate["width"]), 4),
                "height": round(float(candidate["height"]), 4),
                "confidence": float(candidate["confidence"]),
            }
            if normalized not in selected:
                selected.append(normalized)
        return selected
