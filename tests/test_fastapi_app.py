from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from aoi.api import create_app
from aoi.database import DatabaseManager
from aoi.schema import InferenceEvent, InspectionResult


def _create_fiducial_board_image(path, *, size=(1600, 900), include_marks=True):
    image = Image.new("RGB", size, color=(26, 150, 98))
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, size[0] - 30, size[1] - 30), outline=(230, 245, 235), width=8)
    draw.rectangle((size[0] * 0.32, size[1] * 0.24, size[0] * 0.68, size[1] * 0.74), outline=(190, 220, 210), width=5)

    if include_marks:
        radii = max(18, min(size) // 28)
        centers = [
            (int(size[0] * 0.09), int(size[1] * 0.12)),
            (int(size[0] * 0.89), int(size[1] * 0.14)),
            (int(size[0] * 0.12), int(size[1] * 0.84)),
            (int(size[0] * 0.88), int(size[1] * 0.86)),
        ]
        for center_x, center_y in centers:
            draw.ellipse(
                (center_x - radii, center_y - radii, center_x + radii, center_y + radii),
                fill=(215, 176, 56),
                outline=(245, 235, 185),
                width=max(3, radii // 5),
            )
            inner = max(6, radii // 2)
            draw.ellipse(
                (center_x - inner, center_y - inner, center_x + inner, center_y + inner),
                fill=(26, 150, 98),
            )

    image.save(path)
    return path


def _create_component_board_image(path, *, size=(1600, 900)):
    image = Image.new("RGB", size, color=(28, 126, 82))
    draw = ImageDraw.Draw(image)
    component_boxes = [
        (150, 120, 320, 250),
        (520, 180, 710, 340),
        (980, 430, 1160, 590),
        (310, 520, 460, 650),
    ]
    fills = [(40, 40, 46), (182, 182, 182), (68, 68, 74), (210, 198, 120)]
    outlines = [(220, 220, 220), (245, 245, 245), (210, 210, 210), (245, 230, 160)]
    for box, fill, outline in zip(component_boxes, fills, outlines, strict=True):
        draw.rounded_rectangle(box, radius=12, fill=fill, outline=outline, width=4)
    image.save(path)
    return path


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


def test_fastapi_post_events_persists_records(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.post(
        "/events",
        json={
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
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] == 1
    assert "run_id" in payload
    assert (tmp_path / "inference.jsonl").exists()


def test_fastapi_post_events_accepts_single_event_object_payload(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.post(
        "/events",
        json={
            "pcb_id": "PCB-SINGLE",
            "component_id": "R101",
            "inspection_result": "FAIL",
            "defect_type": "MISALIGNMENT",
            "confidence_score": 0.88,
            "inference_latency_ms": 31,
        },
    )

    assert response.status_code == 202
    assert response.json()["accepted"] == 1


def test_fastapi_post_events_accepts_event_list_payload(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.post(
        "/events",
        json=[
            {
                "pcb_id": "PCB-LIST",
                "component_id": "R101",
                "inspection_result": "FAIL",
                "defect_type": "MISALIGNMENT",
                "confidence_score": 0.88,
                "inference_latency_ms": 31,
            }
        ],
    )

    assert response.status_code == 202
    assert response.json()["accepted"] == 1


def test_fastapi_post_events_rejects_invalid_confidence(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.post(
        "/events",
        json={
            "events": [
                {
                    "pcb_id": "PCB-BAD",
                    "component_id": "R101",
                    "inspection_result": "FAIL",
                    "defect_type": "MISALIGNMENT",
                    "confidence_score": 1.5,
                    "inference_latency_ms": 31,
                }
            ]
        },
    )

    assert response.status_code == 422
    assert "less than or equal to 1" in response.json()["message"]


def test_fastapi_create_run_rejects_unexpected_fields_with_standard_validation_error(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.post("/runs", json={"unexpected": True})

    assert response.status_code == 422
    assert response.json() == {"status": "error", "message": "Extra inputs are not permitted"}


def test_fastapi_list_runs_rejects_invalid_status_query_with_standard_validation_error(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.get("/runs", params={"status": "BROKEN"})

    assert response.status_code == 422
    assert "Input should be 'PASS' or 'FAIL'" in response.json()["message"]


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


def test_fastapi_post_events_accepts_explicit_images_and_overlay_metadata(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.post(
        "/events",
        json={
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
        },
    )

    assert response.status_code == 202
    result = response.json()
    run_response = client.get(f"/runs/{result['run_id']}")

    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert len(run_payload["run"]["images"]) == 2
    assert run_payload["run"]["images"][1]["image_role"] == "crop_view"
    assert run_payload["run"]["defect_logs"][0]["run_image_id"] == run_payload["run"]["images"][1]["id"]
    assert run_payload["run"]["defect_logs"][0]["overlay_x"] == 0.33


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


def test_fastapi_upload_run_image_stores_metadata_and_asset(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-UPLOAD")
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)
    image_path = _create_component_board_image(tmp_path / "upload-components.png")
    buffer = BytesIO()
    Image.open(image_path).save(buffer, format="PNG")

    response = client.post(
        f"/runs/{run['id']}/images",
        content=buffer.getvalue(),
        headers={"Content-Type": "image/png"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "ok"
    stored_images = database.fetch_run_images(run["id"])
    assert len(stored_images) == 1
    assert stored_images[0]["image_width"] == 1600
    assert stored_images[0]["image_height"] == 900
    assert (tmp_path / "storage" / run["id"] / "scan.png").exists()
    refreshed_run = database.fetch_run(run["id"])
    assert refreshed_run is not None
    assert refreshed_run["component_detection_status"] == "detected"
    assert len(refreshed_run["components"]) >= 3


def test_fastapi_get_run_image_returns_uploaded_asset(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-IMG")
    storage_path = tmp_path / "storage"
    run_dir = storage_path / run["id"]
    run_dir.mkdir(parents=True)
    image_path = run_dir / "scan.png"
    buffer = BytesIO()
    Image.new("RGB", (400, 300), color=(12, 34, 56)).save(buffer, format="PNG")
    image_bytes = buffer.getvalue()
    image_path.write_bytes(image_bytes)
    database.add_run_image(
        run["id"],
        image_id="img-1",
        image_path=f"/runs/{run['id']}/images/img-1",
        image_role="full_board",
        image_width=400,
        image_height=300,
        created_at=str(run["timestamp"]),
    )
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=storage_path,
    )
    client = TestClient(app)

    response = client.get(f"/runs/{run['id']}/images/img-1")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == image_bytes


def test_fastapi_get_run_returns_detected_components_after_upload(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-COMP")
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)
    image_path = _create_component_board_image(tmp_path / "component-board.png")
    buffer = BytesIO()
    Image.open(image_path).save(buffer, format="PNG")

    upload_response = client.post(
        f"/runs/{run['id']}/images",
        content=buffer.getvalue(),
        headers={"Content-Type": "image/png"},
    )
    run_response = client.get(f"/runs/{run['id']}")

    assert upload_response.status_code == 201
    assert run_response.status_code == 200
    run_payload = run_response.json()["run"]
    assert run_payload["component_detection_status"] == "detected"
    assert len(run_payload["components"]) >= 3
    assert run_payload["components"][0]["run_image_id"] == run_payload["images"][0]["id"]


def test_fastapi_fiducial_detection_and_confirmation_endpoints(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-FID")
    image_path = _create_fiducial_board_image(tmp_path / "fid-fastapi-board.png")
    with Image.open(image_path) as image:
        width, height = image.size
    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], str(image_path), "full_board", width, height, 0, run["timestamp"]),
        )
    database.update_run(run["id"], model_name="MODEL-FID", requires_fiducials=True)
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    detect_response = client.post(f"/runs/{run['id']}/fiducials/detect", json={})
    confirm_response = client.post(f"/runs/{run['id']}/fiducials/confirm", json={})

    assert detect_response.status_code == 200
    assert confirm_response.status_code == 200
    detect_payload = detect_response.json()
    confirm_payload = confirm_response.json()
    assert detect_payload["run"]["fiducial_status"] == "needs_review"
    assert len(detect_payload["run"]["fiducials"]) == 3
    assert confirm_payload["run"]["fiducial_status"] == "confirmed"
    assert confirm_payload["run"]["setup_status"] == "review_ready"


def test_fastapi_fiducial_detection_failure_and_manual_recovery_endpoints(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-FID-FAIL")
    image_path = _create_fiducial_board_image(tmp_path / "fid-fastapi-fail-board.png", size=(900, 700), include_marks=False)
    with Image.open(image_path) as image:
        width, height = image.size
    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], str(image_path), "full_board", width, height, 0, run["timestamp"]),
        )
    database.update_run(run["id"], model_name="MODEL-FID", requires_fiducials=True)
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    detect_response = client.post(f"/runs/{run['id']}/fiducials/detect", json={})
    failed_run = database.fetch_run(run["id"])
    manual_response = client.post(
        f"/runs/{run['id']}/fiducials/manual",
        json={
            "fiducials": [
                {"x": 0.08, "y": 0.1, "width": 0.035, "height": 0.035},
                {"x": 0.86, "y": 0.12, "width": 0.035, "height": 0.035},
                {"x": 0.12, "y": 0.82, "width": 0.035, "height": 0.035},
            ]
        },
    )

    assert detect_response.status_code == 400
    assert detect_response.json()["message"].startswith("fiducial detection failed")
    assert failed_run is not None
    assert failed_run["fiducial_status"] == "failed"
    assert manual_response.status_code == 200
    assert manual_response.json()["run"]["fiducial_status"] == "confirmed"
    assert manual_response.json()["run"]["setup_status"] == "review_ready"


def test_fastapi_manual_fiducials_rejects_short_payload_at_api_boundary(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-FID-SHORT")
    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], "/runs/fid/images/img-1", "full_board", 1600, 900, 0, run["timestamp"]),
        )
    database.update_run(run["id"], model_name="MODEL-FID", requires_fiducials=True)
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.post(
        f"/runs/{run['id']}/fiducials/manual",
        json={"fiducials": [{"x": 0.08, "y": 0.1, "width": 0.035, "height": 0.035}]},
    )

    assert response.status_code == 422
    assert response.json() == {"status": "error", "message": "Value error, at least 3 fiducials are required"}


def test_fastapi_barcode_detection_and_confirmation_endpoints(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-BAR")
    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], "/runs/bar/images/img-1", "full_board", 1600, 900, 0, run["timestamp"]),
        )
    database.update_run(run["id"], model_name="MODEL-BAR", requires_barcode=True)
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    detect_response = client.post(f"/runs/{run['id']}/barcode/detect", json={})
    confirm_response = client.post(f"/runs/{run['id']}/barcode/confirm", json={})

    assert detect_response.status_code == 200
    assert confirm_response.status_code == 200
    detect_payload = detect_response.json()
    confirm_payload = confirm_response.json()
    assert detect_payload["run"]["barcode_status"] == "needs_review"
    assert detect_payload["run"]["barcode"]["decoded_value"] == "PCB-BAR-LOT-01"
    assert confirm_payload["run"]["barcode_status"] == "confirmed"
    assert confirm_payload["run"]["setup_status"] == "review_ready"


def test_fastapi_barcode_detection_failure_and_manual_recovery_endpoints(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-BAR-FAIL")
    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], "/runs/bar/images/img-1", "full_board", 800, 420, 0, run["timestamp"]),
        )
    database.update_run(run["id"], model_name="MODEL-BAR", requires_barcode=True)
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    detect_response = client.post(f"/runs/{run['id']}/barcode/detect", json={})
    failed_run = database.fetch_run(run["id"])
    manual_response = client.post(
        f"/runs/{run['id']}/barcode/manual",
        json={
            "barcode": {
                "x": 0.72,
                "y": 0.78,
                "width": 0.16,
                "height": 0.08,
                "decoded_value": "PCB-BAR-FAIL-LOT-01",
            }
        },
    )

    assert detect_response.status_code == 400
    assert detect_response.json()["message"].startswith("barcode detection failed")
    assert failed_run is not None
    assert failed_run["barcode_status"] == "failed"
    assert manual_response.status_code == 200
    assert manual_response.json()["run"]["barcode_status"] == "confirmed"
    assert manual_response.json()["run"]["barcode"]["decoded_value"] == "PCB-BAR-FAIL-LOT-01"
    assert manual_response.json()["run"]["setup_status"] == "review_ready"


def test_fastapi_manual_barcode_rejects_blank_decoded_value_at_api_boundary(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-BAR-BLANK")
    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], "/runs/bar/images/img-1", "full_board", 1600, 900, 0, run["timestamp"]),
        )
    database.update_run(run["id"], model_name="MODEL-BAR", requires_barcode=True)
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    response = client.post(
        f"/runs/{run['id']}/barcode/manual",
        json={"barcode": {"x": 0.72, "y": 0.78, "width": 0.16, "height": 0.08, "decoded_value": "  "}},
    )

    assert response.status_code == 422
    assert response.json() == {"status": "error", "message": "Value error, decoded_value must be a non-empty string"}


def test_fastapi_review_defect_patch(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "aoi.db",
        log_path=tmp_path / "inference.jsonl",
        storage_path=tmp_path / "storage",
    )
    client = TestClient(app)

    # 1. Create a run with a defect
    post_resp = client.post(
        "/events",
        json={
            "pcb_id": "PCB-REVIEW",
            "component_id": "C202",
            "inspection_result": "FAIL",
            "defect_type": "SHORT",
            "confidence_score": 0.95,
            "inference_latency_ms": 10,
        },
    )
    run_id = post_resp.json()["run_id"]

    # 2. Get the defect ID
    run_resp = client.get(f"/runs/{run_id}")
    defect_id = run_resp.json()["run"]["defect_logs"][0]["id"]

    # 3. Patch the review
    patch_resp = client.patch(
        f"/runs/{run_id}/defects/{defect_id}/review",
        json={"status": "CONFIRMED_FAIL"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["operator_review"] == "CONFIRMED_FAIL"

    # 4. Verify in run detail
    final_run_resp = client.get(f"/runs/{run_id}")
    assert final_run_resp.json()["run"]["defect_logs"][0]["operator_review"] == "CONFIRMED_FAIL"

    # 5. Non-existent defect
    bad_patch = client.patch(
        f"/runs/{run_id}/defects/9999/review",
        json={"status": "OVERRULED_PASS"},
    )
    assert bad_patch.status_code == 404
