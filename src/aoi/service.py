from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from aoi.database import DatabaseManager
from aoi.log_manager import LogManager
from aoi.schema import InferenceEvent


class IngestionHandler(BaseHTTPRequestHandler):
    server_version = "AOIHTTP/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._write_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "log_path": str(self.server.log_manager.log_path),
                    "db_path": str(self.server.database_manager.db_path),
                },
            )
            return

        if parsed.path == "/runs":
            self._handle_list_runs(parsed.query)
            return

        if parsed.path.startswith("/runs/"):
            self._handle_get_run(self.path)
            return

        self._write_json(
            HTTPStatus.NOT_FOUND,
            {"status": "error", "message": "route not found"},
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/events":
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {"status": "error", "message": "route not found"},
            )
            return

        try:
            raw_body = self._read_body()
            payload = json.loads(raw_body)
            events, model_version = self._parse_payload(payload)
        except json.JSONDecodeError:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "message": "request body must be valid JSON"},
            )
            return
        except ValueError as exc:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "message": str(exc)},
            )
            return

        for event in events:
            self.server.log_manager.write_json(event)

        persisted_run = self.server.database_manager.persist_events(
            events=events,
            model_version=model_version,
        )

        self._write_json(
            HTTPStatus.ACCEPTED,
            {
                "status": "accepted",
                "accepted": len(events),
                "run_id": persisted_run.run_id,
                "run_status": persisted_run.status,
            },
        )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_body(self) -> str:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            raise ValueError("Content-Length header is required")
        try:
            length = int(content_length)
        except ValueError as exc:
            raise ValueError("Content-Length must be an integer") from exc
        if length < 1:
            raise ValueError("request body must not be empty")
        return self.rfile.read(length).decode("utf-8")

    def _parse_payload(self, payload: object) -> tuple[list[InferenceEvent], str | None]:
        model_version: str | None = None
        if isinstance(payload, dict):
            raw_model_version = payload.get("model_version")
            if raw_model_version is not None:
                if not isinstance(raw_model_version, str) or not raw_model_version.strip():
                    raise ValueError("model_version must be a non-empty string when provided")
                model_version = raw_model_version
            raw_events = payload.get("events", [payload])
        elif isinstance(payload, list):
            raw_events = payload
        else:
            raise ValueError("payload must be an event object or a list of event objects")

        if not isinstance(raw_events, list) or not raw_events:
            raise ValueError("events payload must contain at least one event")

        events: list[InferenceEvent] = []
        for item in raw_events:
            if not isinstance(item, dict):
                raise ValueError("each event must be a JSON object")
            events.append(InferenceEvent.from_dict(item))
        return events, model_version

    def _handle_list_runs(self, query_string: str) -> None:
        query = parse_qs(query_string)
        raw_limit = query.get("limit", ["20"])[0]
        try:
            limit = int(raw_limit)
        except ValueError:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "message": "limit must be an integer"},
            )
            return

        try:
            status = self._get_optional_choice(query, "status", {"PASS", "FAIL"})
        except ValueError as exc:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "message": str(exc)},
            )
            return

        runs = self.server.database_manager.list_runs(
            limit=limit,
            pcb_id=self._get_optional_string(query, "pcb_id"),
            status=status,
            model_version=self._get_optional_string(query, "model_version"),
            defect_type=self._get_optional_string(query, "defect_type"),
        )
        self._write_json(
            HTTPStatus.OK,
            {"status": "ok", "count": len(runs), "runs": runs},
        )

    def _handle_get_run(self, path: str) -> None:
        parsed = urlparse(path)
        query = parse_qs(parsed.query)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {"status": "error", "message": "route not found"},
            )
            return

        run_id = parts[1]
        try:
            filters = self._get_defect_filters(query)
        except ValueError as exc:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "message": str(exc)},
            )
            return

        if len(parts) == 2:
            run = self.server.database_manager.fetch_run_with_defects(run_id, **filters)
            if run is None:
                self._write_json(
                    HTTPStatus.NOT_FOUND,
                    {"status": "error", "message": "run not found"},
                )
                return
            self._write_json(HTTPStatus.OK, {"status": "ok", "run": run})
            return

        if len(parts) == 3 and parts[2] == "defects":
            run = self.server.database_manager.fetch_run(run_id)
            if run is None:
                self._write_json(
                    HTTPStatus.NOT_FOUND,
                    {"status": "error", "message": "run not found"},
                )
                return
            defect_logs = self.server.database_manager.fetch_defect_logs(run_id, **filters)
            self._write_json(
                HTTPStatus.OK,
                {"status": "ok", "run_id": run_id, "count": len(defect_logs), "defect_logs": defect_logs},
            )
            return

        self._write_json(
            HTTPStatus.NOT_FOUND,
            {"status": "error", "message": "route not found"},
        )

    @staticmethod
    def _get_optional_string(query: dict[str, list[str]], key: str) -> str | None:
        value = query.get(key, [None])[0]
        if value is None or not value.strip():
            return None
        return value

    @staticmethod
    def _get_optional_choice(
        query: dict[str, list[str]],
        key: str,
        allowed: set[str],
    ) -> str | None:
        value = IngestionHandler._get_optional_string(query, key)
        if value is None:
            return None
        if value not in allowed:
            allowed_values = ", ".join(sorted(allowed))
            raise ValueError(f"{key} must be one of: {allowed_values}")
        return value

    def _get_defect_filters(self, query: dict[str, list[str]]) -> dict[str, str | None]:
        return {
            "component_id": self._get_optional_string(query, "component_id"),
            "defect_type": self._get_optional_string(query, "defect_type"),
            "severity": self._get_optional_choice(query, "severity", {"none", "minor", "major", "critical"}),
            "inspection_result": self._get_optional_choice(query, "inspection_result", {"PASS", "FAIL"}),
        }

    def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class IngestionServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        log_manager: LogManager,
        database_manager: DatabaseManager,
    ) -> None:
        super().__init__(server_address, IngestionHandler)
        self.log_manager = log_manager
        self.database_manager = database_manager


def run_server(*, host: str, port: int, log_path: Path, db_path: Path) -> None:
    server = IngestionServer(
        (host, port),
        LogManager(log_path),
        DatabaseManager(db_path),
    )
    print(f"AOI ingestion service listening on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
