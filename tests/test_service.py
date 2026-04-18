import json
import threading
from urllib import request

from aoi.database import DatabaseManager
from aoi.log_manager import LogManager
from aoi.service import IngestionServer


def test_health_endpoint_returns_ok(tmp_path) -> None:
    log_path = tmp_path / "inference.jsonl"
    db_path = tmp_path / "aoi.db"
    server = IngestionServer(("127.0.0.1", 0), LogManager(log_path), DatabaseManager(db_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/health", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert payload["status"] == "ok"


def test_post_events_persists_records(tmp_path) -> None:
    log_path = tmp_path / "inference.jsonl"
    db_path = tmp_path / "aoi.db"
    server = IngestionServer(("127.0.0.1", 0), LogManager(log_path), DatabaseManager(db_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    payload = {
        "events": [
            {
                "pcb_id": "PCB-0001",
                "component_id": "R101",
                "inspection_result": "FAIL",
                "defect_type": "MISALIGNMENT",
                "confidence_score": 0.88,
                "inference_latency_ms": 31,
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        f"http://127.0.0.1:{server.server_port}/events",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result["accepted"] == 1
    assert "run_id" in result
    assert log_path.exists()
