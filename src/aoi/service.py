from __future__ import annotations

import json
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image, UnidentifiedImageError

from aoi.database import DatabaseManager
from aoi.log_manager import LogManager
from aoi.schema import InferenceEvent, RunImageInput


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
            parts = [p for p in parsed.path.split("/") if p]
            # Pattern: /runs/<run_id>/images/<image_id>
            if len(parts) == 4 and parts[2] == "images":
                self._handle_get_image(parts[1], parts[3])
                return
            self._handle_get_run(self.path)
            return

        self._write_json(
            HTTPStatus.NOT_FOUND,
            {"status": "error", "message": "route not found"},
        )

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/runs":
            self._handle_create_run()
            return

        if parsed.path == "/events":
            self._handle_post_events()
            return

        # Pattern: /runs/<run_id>/images
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) == 3 and parts[0] == "runs" and parts[2] == "images":
            self._handle_post_run_image(parts[1])
            return
        if len(parts) == 4 and parts[0] == "runs" and parts[2] == "fiducials" and parts[3] == "detect":
            self._handle_detect_fiducials(parts[1])
            return
        if len(parts) == 4 and parts[0] == "runs" and parts[2] == "fiducials" and parts[3] == "confirm":
            self._handle_confirm_fiducials(parts[1])
            return
        if len(parts) == 4 and parts[0] == "runs" and parts[2] == "barcode" and parts[3] == "detect":
            self._handle_detect_barcode(parts[1])
            return
        if len(parts) == 4 and parts[0] == "runs" and parts[2] == "barcode" and parts[3] == "confirm":
            self._handle_confirm_barcode(parts[1])
            return

        self._write_json(
            HTTPStatus.NOT_FOUND,
            {"status": "error", "message": "route not found"},
        )

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) == 2 and parts[0] == "runs":
            self._handle_patch_run(parts[1])
            return

        self._write_json(
            HTTPStatus.NOT_FOUND,
            {"status": "error", "message": "route not found"},
        )

    def _handle_post_events(self) -> None:
        try:
            raw_body = self._read_body()
            payload = json.loads(raw_body)
            events, model_version, images = self._parse_payload(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": str(exc)})
            return

        for event in events:
            self.server.log_manager.write_json(event)

        persisted_run = self.server.database_manager.persist_events(
            events=events,
            model_version=model_version,
            images=images,
        )

        self._write_json(
            HTTPStatus.ACCEPTED,
            {
                "status": "accepted",
                "run_id": persisted_run.run_id,
                "accepted": len(events),
            },
        )

    def _handle_create_run(self) -> None:
        try:
            raw_body = self._read_body()
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError) as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": str(exc)})
            return

        if not isinstance(payload, dict):
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "payload must be a JSON object"})
            return

        pcb_id = payload.get("pcb_id")
        if pcb_id is not None and (not isinstance(pcb_id, str) or not pcb_id.strip()):
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "pcb_id must be a non-empty string"})
            return

        run = self.server.database_manager.create_run(pcb_id=pcb_id)
        self._write_json(HTTPStatus.CREATED, {"status": "ok", "run": run})

    def _handle_patch_run(self, run_id: str) -> None:
        try:
            raw_body = self._read_body()
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError) as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": str(exc)})
            return

        if not isinstance(payload, dict):
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "payload must be a JSON object"})
            return

        model_name = payload.get("model_name")
        if "model_name" in payload and model_name is not None and (not isinstance(model_name, str) or not model_name.strip()):
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "message": "model_name must be a non-empty string"},
            )
            return
        requires_fiducials = payload.get("requires_fiducials")
        if "requires_fiducials" in payload and not isinstance(requires_fiducials, bool):
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "message": "requires_fiducials must be a boolean"},
            )
            return
        requires_barcode = payload.get("requires_barcode")
        if "requires_barcode" in payload and not isinstance(requires_barcode, bool):
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "message": "requires_barcode must be a boolean"},
            )
            return

        run = self.server.database_manager.update_run(
            run_id,
            model_name=model_name if "model_name" in payload else None,
            requires_fiducials=requires_fiducials if "requires_fiducials" in payload else None,
            requires_barcode=requires_barcode if "requires_barcode" in payload else None,
        )
        if run is None:
            self._write_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "run not found"})
            return
        self._write_json(HTTPStatus.OK, {"status": "ok", "run": run})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _handle_post_run_image(self, run_id: str) -> None:
        run = self.server.database_manager.fetch_run(run_id)
        if not run:
            self._write_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "run not found"})
            return

        content_length_str = self.headers.get("Content-Length", "0")
        try:
            content_length = int(content_length_str)
        except ValueError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "invalid content length"})
            return

        if content_length == 0:
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "empty image body"})
            return

        image_data = self.rfile.read(content_length)
        
        ext = "png"
        content_type = self.headers.get("Content-Type", "image/png")
        if "jpeg" in content_type:
            ext = "jpg"
            
        image_filename = f"scan.{ext}"
        run_dir = self.server.storage_path / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        file_path = run_dir / image_filename

        with open(file_path, "wb") as f:
            f.write(image_data)

        image_width, image_height = self._read_image_size(image_data)

        image_id = str(uuid.uuid4())
        updated_run = self.server.database_manager.add_run_image(
            run_id,
            image_id=image_id,
            image_path=f"/runs/{run_id}/images/{image_id}",
            image_role="full_board",
            image_width=image_width,
            image_height=image_height,
            created_at=str(run["timestamp"]),
        )
        if updated_run is None:
            self._write_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "run not found"})
            return

        self._write_json(HTTPStatus.CREATED, {"status": "ok", "image_id": image_id, "run": updated_run})

    def _handle_detect_fiducials(self, run_id: str) -> None:
        try:
            run = self.server.database_manager.detect_fiducials(run_id)
        except ValueError as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": str(exc)})
            return
        if run is None:
            self._write_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "run not found"})
            return
        self._write_json(HTTPStatus.OK, {"status": "ok", "run": run})

    def _handle_confirm_fiducials(self, run_id: str) -> None:
        run = self.server.database_manager.confirm_fiducials(run_id)
        if run is None:
            self._write_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "run not found"})
            return
        self._write_json(HTTPStatus.OK, {"status": "ok", "run": run})

    def _handle_detect_barcode(self, run_id: str) -> None:
        try:
            run = self.server.database_manager.detect_barcode(run_id)
        except ValueError as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": str(exc)})
            return
        if run is None:
            self._write_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "run not found"})
            return
        self._write_json(HTTPStatus.OK, {"status": "ok", "run": run})

    def _handle_confirm_barcode(self, run_id: str) -> None:
        run = self.server.database_manager.confirm_barcode(run_id)
        if run is None:
            self._write_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "run not found"})
            return
        self._write_json(HTTPStatus.OK, {"status": "ok", "run": run})

    def _handle_get_image(self, run_id: str, image_id: str) -> None:
        run_dir = self.server.storage_path / run_id
        image_file = None
        for ext in ["png", "jpg", "jpeg"]:
            candidate = run_dir / f"scan.{ext}"
            if candidate.exists():
                image_file = candidate
                break

        if not image_file:
            self._write_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "image not found"})
            return

        self.send_response(HTTPStatus.OK)
        content_type = "image/png" if image_file.suffix == ".png" else "image/jpeg"
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(image_file.stat().st_size))
        self.end_headers()
        with open(image_file, "rb") as f:
            self.wfile.write(f.read())

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

    @staticmethod
    def _read_image_size(image_data: bytes) -> tuple[int, int]:
        try:
            with Image.open(BytesIO(image_data)) as image:
                width, height = image.size
        except UnidentifiedImageError as exc:
            raise ValueError("unsupported image format; upload a valid image file") from exc

        if width < 1 or height < 1:
            raise ValueError("invalid image dimensions")
        return width, height

    def _parse_payload(
        self, payload: object
    ) -> tuple[list[InferenceEvent], str | None, list[RunImageInput] | None]:
        model_version: str | None = None
        images: list[RunImageInput] | None = None
        if isinstance(payload, dict):
            raw_model_version = payload.get("model_version")
            if raw_model_version is not None:
                if not isinstance(raw_model_version, str) or not raw_model_version.strip():
                    raise ValueError("model_version must be a non-empty string when provided")
                model_version = raw_model_version
            raw_images = payload.get("images")
            if raw_images is not None:
                if not isinstance(raw_images, list) or not raw_images:
                    raise ValueError("images must be a non-empty list when provided")
                images = []
                for item in raw_images:
                    if not isinstance(item, dict):
                        raise ValueError("each image must be a JSON object")
                    images.append(RunImageInput.from_dict(item))
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
        return events, model_version, images

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
        storage_path: Path | None = None,
    ) -> None:
        super().__init__(server_address, IngestionHandler)
        self.log_manager = log_manager
        self.database_manager = database_manager
        self.storage_path = storage_path or (database_manager.db_path.parent / "run-assets")
        self.storage_path.mkdir(parents=True, exist_ok=True)


def run_server(*, host: str, port: int, log_path: Path, db_path: Path, storage_path: Path) -> None:
    server = IngestionServer(
        (host, port),
        LogManager(log_path),
        DatabaseManager(db_path),
        storage_path,
    )
    print(f"AOI ingestion service listening on http://{host}:{port}", flush=True)
    print(f"Storing run assets in: {storage_path.absolute()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
