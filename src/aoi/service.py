from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aoi.database import DatabaseManager
from aoi.log_manager import LogManager
from aoi.schema import InferenceEvent


class IngestionHandler(BaseHTTPRequestHandler):
    server_version = "AOIHTTP/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {"status": "error", "message": "route not found"},
            )
            return

        self._write_json(
            HTTPStatus.OK,
            {
                "status": "ok",
                "log_path": str(self.server.log_manager.log_path),
                "db_path": str(self.server.database_manager.db_path),
            },
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
