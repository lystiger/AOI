import json
import threading
from urllib import request

from aoi.database import DatabaseManager
from aoi.log_manager import LogManager
from aoi.schema import InferenceEvent, InspectionResult
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


def test_list_runs_returns_recent_runs(tmp_path) -> None:
    log_path = tmp_path / "inference.jsonl"
    db_path = tmp_path / "aoi.db"
    database = DatabaseManager(db_path)
    persisted_run = database.persist_events(
        events=[
            InferenceEvent.create(
                pcb_id="PCB-0100",
                component_id="U100",
                inspection_result=InspectionResult.FAIL,
                defect_type="MISALIGNMENT",
                confidence_score=0.92,
                inference_latency_ms=21,
                timestamp="2026-04-18T12:00:00+00:00",
            )
        ],
        model_version="v1.0.0",
    )
    server = IngestionServer(("127.0.0.1", 0), LogManager(log_path), database)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/runs?limit=5", timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result["count"] == 1
    assert result["runs"][0]["id"] == persisted_run.run_id
    assert result["runs"][0]["model_version"] == "v1.0.0"


def test_get_run_returns_embedded_defect_logs(tmp_path) -> None:
    log_path = tmp_path / "inference.jsonl"
    db_path = tmp_path / "aoi.db"
    database = DatabaseManager(db_path)
    persisted_run = database.persist_events(
        events=[
            InferenceEvent.create(
                pcb_id="PCB-0200",
                component_id="R200",
                inspection_result=InspectionResult.FAIL,
                defect_type="LIFTED_LEAD",
                confidence_score=0.83,
                inference_latency_ms=28,
                timestamp="2026-04-18T12:05:00+00:00",
            )
        ]
    )
    server = IngestionServer(("127.0.0.1", 0), LogManager(log_path), database)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with request.urlopen(f"http://127.0.0.1:{server.server_port}/runs/{persisted_run.run_id}", timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result["run"]["id"] == persisted_run.run_id
    assert len(result["run"]["images"]) == 1
    assert result["run"]["images"][0]["image_path"] == "/mock/pcb-example-2nd.png"
    assert result["run"]["event_count"] == 1
    assert result["run"]["defect_logs"][0]["defect_type"] == "LIFTED_LEAD"
    assert result["run"]["defect_logs"][0]["overlay_shape"] == "rect"
    assert result["run"]["defect_logs"][0]["run_image_id"] == result["run"]["images"][0]["id"]


def test_post_events_accepts_explicit_images_and_overlay_metadata(tmp_path) -> None:
    log_path = tmp_path / "inference.jsonl"
    db_path = tmp_path / "aoi.db"
    server = IngestionServer(("127.0.0.1", 0), LogManager(log_path), DatabaseManager(db_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    payload = {
        "images": [
            {
                "image_path": "/runs/PCB-IMG/images/top.png",
                "image_role": "top_view",
                "image_width": 1600,
                "image_height": 900,
            },
            {
                "image_path": "/runs/PCB-IMG/images/crop.png",
                "image_role": "crop_view",
                "image_width": 800,
                "image_height": 800,
            },
        ],
        "events": [
            {
                "pcb_id": "PCB-IMG",
                "component_id": "U101",
                "inspection_result": "FAIL",
                "defect_type": "MISALIGNMENT",
                "confidence_score": 0.88,
                "inference_latency_ms": 31,
                "run_image_index": 1,
                "overlay_x": 0.33,
                "overlay_y": 0.44,
                "overlay_width": 0.07,
                "overlay_height": 0.05,
                "overlay_shape": "rect",
            }
        ],
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
        with request.urlopen(
            f"http://127.0.0.1:{server.server_port}/runs/{result['run_id']}",
            timeout=5,
        ) as response:
            run_payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert len(run_payload["run"]["images"]) == 2
    assert run_payload["run"]["images"][1]["image_role"] == "crop_view"
    assert run_payload["run"]["defect_logs"][0]["run_image_id"] == run_payload["run"]["images"][1]["id"]
    assert run_payload["run"]["defect_logs"][0]["overlay_x"] == 0.33


def test_list_runs_supports_status_and_pcb_filters(tmp_path) -> None:
    log_path = tmp_path / "inference.jsonl"
    db_path = tmp_path / "aoi.db"
    database = DatabaseManager(db_path)
    database.persist_events(
        events=[
            InferenceEvent.create(
                pcb_id="PCB-1000",
                component_id="U100",
                inspection_result=InspectionResult.FAIL,
                defect_type="MISALIGNMENT",
                confidence_score=0.9,
                inference_latency_ms=20,
                timestamp="2026-04-18T12:10:00+00:00",
            )
        ]
    )
    database.persist_events(
        events=[
            InferenceEvent.create(
                pcb_id="PCB-2000",
                component_id="U200",
                inspection_result=InspectionResult.PASS,
                defect_type="NO_DEFECT",
                confidence_score=0.99,
                inference_latency_ms=18,
                timestamp="2026-04-18T12:11:00+00:00",
            )
        ]
    )
    server = IngestionServer(("127.0.0.1", 0), LogManager(log_path), database)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with request.urlopen(
            f"http://127.0.0.1:{server.server_port}/runs?status=PASS&pcb_id=PCB-2000",
            timeout=5,
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result["count"] == 1
    assert result["runs"][0]["pcb_id"] == "PCB-2000"
    assert result["runs"][0]["status"] == "PASS"


def test_run_defects_support_filters(tmp_path) -> None:
    log_path = tmp_path / "inference.jsonl"
    db_path = tmp_path / "aoi.db"
    database = DatabaseManager(db_path)
    persisted_run = database.persist_events(
        events=[
            InferenceEvent.create(
                pcb_id="PCB-3000",
                component_id="U300",
                inspection_result=InspectionResult.FAIL,
                defect_type="MISALIGNMENT",
                confidence_score=0.84,
                inference_latency_ms=25,
                timestamp="2026-04-18T12:20:00+00:00",
            ),
            InferenceEvent.create(
                pcb_id="PCB-3000",
                component_id="U301",
                inspection_result=InspectionResult.PASS,
                defect_type="NO_DEFECT",
                confidence_score=0.98,
                inference_latency_ms=19,
                timestamp="2026-04-18T12:20:01+00:00",
            ),
        ]
    )
    server = IngestionServer(("127.0.0.1", 0), LogManager(log_path), database)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with request.urlopen(
            f"http://127.0.0.1:{server.server_port}/runs/{persisted_run.run_id}/defects?inspection_result=FAIL&defect_type=MISALIGNMENT",
            timeout=5,
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result["count"] == 1
    assert result["defect_logs"][0]["component_id"] == "U300"
