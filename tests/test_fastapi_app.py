from fastapi.testclient import TestClient

from aoi.api import create_app
from aoi.database import DatabaseManager
from aoi.schema import InferenceEvent, InspectionResult


def test_fastapi_health_endpoint_returns_ok(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_fastapi_list_runs_returns_recent_runs(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    persisted_run = database.persist_events(
        events=[
            InferenceEvent.create(
                pcb_id="PCB-FASTAPI-100",
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
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.get("/runs", params={"limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["runs"][0]["id"] == persisted_run.run_id
    assert payload["runs"][0]["model_version"] == "v1.0.0"
    assert payload["runs"][0]["setup_status"] == "review_ready"


def test_fastapi_get_run_returns_embedded_defect_logs(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    persisted_run = database.persist_events(
        events=[
            InferenceEvent.create(
                pcb_id="PCB-FASTAPI-200",
                component_id="R200",
                inspection_result=InspectionResult.FAIL,
                defect_type="LIFTED_LEAD",
                confidence_score=0.83,
                inference_latency_ms=28,
                timestamp="2026-04-18T12:05:00+00:00",
            )
        ]
    )
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.get(f"/runs/{persisted_run.run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["id"] == persisted_run.run_id
    assert payload["run"]["images"] == []
    assert payload["run"]["event_count"] == 1
    assert payload["run"]["defect_logs"][0]["defect_type"] == "LIFTED_LEAD"


def test_fastapi_get_run_returns_not_found_for_missing_run(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.get("/runs/missing-run")

    assert response.status_code == 404
    assert response.json() == {"status": "error", "message": "run not found"}
