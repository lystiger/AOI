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


def test_fastapi_create_run_creates_empty_setup_run(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.post("/runs", json={})

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["run"]["status"] == "SETUP"
    assert payload["run"]["setup_status"] == "not_ready"
    assert payload["run"]["model_name"] is None
    assert payload["run"]["requires_fiducials"] is False
    assert payload["run"]["requires_barcode"] is False


def test_fastapi_patch_run_updates_model_name_and_setup_status(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-SETUP")
    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], "/runs/setup/images/img-1", "full_board", 1600, 900, 0, run["timestamp"]),
        )
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.patch(
        f"/runs/{run['id']}",
        json={"model_name": "MODEL-123", "requires_fiducials": True, "requires_barcode": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["run"]["model_name"] == "MODEL-123"
    assert payload["run"]["setup_status"] == "in_progress"
    assert payload["run"]["requires_fiducials"] is True
    assert payload["run"]["fiducial_status"] == "ready"
    assert payload["run"]["requires_barcode"] is True
    assert payload["run"]["barcode_status"] == "ready"


def test_fastapi_patch_run_model_change_forces_setup_reentry(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-REWORK")
    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], "/runs/rework/images/img-1", "full_board", 1600, 900, 0, run["timestamp"]),
        )
    database.update_run(run["id"], model_name="MODEL-A", requires_fiducials=True, requires_barcode=True)
    with database._connect() as connection:
        connection.execute(
            """
            UPDATE inspection_runs
            SET fiducials_json = ?, barcode_json = ?, fiducial_status = ?, barcode_status = ?, setup_status = ?
            WHERE id = ?
            """,
            ('[{"id":"fid-1"}]', '{"id":"barcode-1","decoded_value":"PCB-REWORK-LOT-01"}', "confirmed", "confirmed", "review_ready", run["id"]),
        )
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.patch(f"/runs/{run['id']}", json={"model_name": "MODEL-B"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["run"]["model_name"] == "MODEL-B"
    assert payload["run"]["fiducials"] == []
    assert payload["run"]["barcode"] is None
    assert payload["run"]["fiducial_status"] == "ready"
    assert payload["run"]["barcode_status"] == "ready"
    assert payload["run"]["setup_status"] == "in_progress"


def test_fastapi_delete_run_removes_run_and_assets(tmp_path) -> None:
    storage_path = tmp_path / "run-assets"
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-DELETE")
    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], f"/runs/{run['id']}/images/img-1", "full_board", 1600, 900, 0, run["timestamp"]),
        )
    run_dir = storage_path / run["id"]
    run_dir.mkdir(parents=True)
    (run_dir / "scan.png").write_bytes(b"fake-image")
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=storage_path,
    )
    client = TestClient(app)

    response = client.delete(f"/runs/{run['id']}")
    missing_response = client.get(f"/runs/{run['id']}")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "run_id": run["id"]}
    assert missing_response.status_code == 404
    assert not run_dir.exists()
