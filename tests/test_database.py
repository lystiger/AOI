from aoi.database import DatabaseManager
from aoi.schema import InferenceEvent, InspectionResult, RunImageInput


def test_persist_events_creates_run_and_defect_logs(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    events = [
        InferenceEvent.create(
            pcb_id="PCB-0001",
            component_id="R101",
            inspection_result=InspectionResult.FAIL,
            defect_type="MISALIGNMENT",
            confidence_score=0.88,
            inference_latency_ms=31,
            timestamp="2026-04-18T12:00:00+00:00",
        ),
        InferenceEvent.create(
            pcb_id="PCB-0001",
            component_id="C202",
            inspection_result=InspectionResult.PASS,
            defect_type="NO_DEFECT",
            confidence_score=0.99,
            inference_latency_ms=17,
            timestamp="2026-04-18T12:00:01+00:00",
        ),
    ]

    persisted_run = database.persist_events(events=events, model_version="v1.2.3")

    run_row = database.fetch_run(persisted_run.run_id)
    defect_rows = database.fetch_defect_logs(persisted_run.run_id)
    run_images = database.fetch_run_images(persisted_run.run_id)

    assert run_row is not None
    assert run_row["pcb_id"] == "PCB-0001"
    assert run_row["status"] == "FAIL"
    assert run_row["model_version"] == "v1.2.3"
    assert run_row["model_name"] is None
    assert run_row["setup_status"] == "review_ready"
    assert run_row["requires_fiducials"] is False
    assert run_row["fiducial_status"] == "not_required"
    assert run_row["requires_barcode"] is False
    assert run_row["barcode_status"] == "not_required"
    assert run_images == []
    assert len(defect_rows) == 2
    assert defect_rows[0]["severity"] == "major"
    assert defect_rows[0]["run_image_id"] is None
    assert defect_rows[0]["overlay_shape"] == "rect"
    assert defect_rows[0]["overlay_x"] is not None
    assert defect_rows[1]["severity"] == "none"


def test_fetch_run_with_defects_backfills_image_and_overlay_metadata_for_legacy_rows(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")

    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO inspection_runs (id, pcb_id, timestamp, model_version, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("legacy-run", "PCB-LEGACY", "2026-04-19T12:00:00+00:00", None, "FAIL"),
        )
        connection.execute(
            """
            INSERT INTO defect_logs (
                run_id,
                component_id,
                defect_type,
                severity,
                confidence_score,
                inference_latency_ms,
                inspection_result,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("legacy-run", "U001", "MISALIGNMENT", "major", 0.91, 22, "FAIL", "2026-04-19T12:00:00+00:00"),
        )

    run = database.fetch_run_with_defects("legacy-run")

    assert run is not None
    assert run["images"] == []
    assert run["defect_logs"][0]["run_image_id"] is None
    assert run["defect_logs"][0]["overlay_shape"] == "rect"


def test_create_run_initializes_setup_state(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")

    run = database.create_run()

    assert run["id"]
    assert run["pcb_id"].startswith("RUN-")
    assert run["status"] == "SETUP"
    assert run["model_name"] is None
    assert run["setup_status"] == "not_ready"
    assert run["requires_fiducials"] is False
    assert run["fiducial_status"] == "not_required"
    assert run["requires_barcode"] is False
    assert run["barcode_status"] == "not_required"


def test_update_run_marks_review_ready_once_model_and_image_exist(tmp_path) -> None:
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

    updated_run = database.update_run(run["id"], model_name="MODEL-123")

    assert updated_run is not None
    assert updated_run["model_name"] == "MODEL-123"
    assert updated_run["setup_status"] == "review_ready"


def test_detect_and_confirm_fiducials_updates_run_state(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-FID")

    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], "/runs/fid/images/img-1", "full_board", 1600, 900, 0, run["timestamp"]),
        )

    updated_run = database.update_run(run["id"], model_name="MODEL-FID", requires_fiducials=True)
    assert updated_run is not None
    assert updated_run["fiducial_status"] == "ready"
    assert updated_run["setup_status"] == "in_progress"

    detected_run = database.detect_fiducials(run["id"])
    assert detected_run is not None
    assert detected_run["fiducial_status"] == "needs_review"
    assert len(detected_run["fiducials"]) == 3

    confirmed_run = database.confirm_fiducials(run["id"])
    assert confirmed_run is not None
    assert confirmed_run["fiducial_status"] == "confirmed"
    assert confirmed_run["setup_status"] == "review_ready"


def test_detect_and_confirm_barcode_updates_run_state(tmp_path) -> None:
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

    updated_run = database.update_run(run["id"], model_name="MODEL-BAR", requires_barcode=True)
    assert updated_run is not None
    assert updated_run["barcode_status"] == "ready"
    assert updated_run["setup_status"] == "in_progress"

    detected_run = database.detect_barcode(run["id"])
    assert detected_run is not None
    assert detected_run["barcode_status"] == "needs_review"
    assert detected_run["barcode"]["decoded_value"] == "PCB-BAR-LOT-01"

    confirmed_run = database.confirm_barcode(run["id"])
    assert confirmed_run is not None
    assert confirmed_run["barcode_status"] == "confirmed"
    assert confirmed_run["setup_status"] == "review_ready"


def test_persist_events_uses_provided_run_images_and_overlay_coordinates(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    persisted_run = database.persist_events(
        events=[
            InferenceEvent.create(
                pcb_id="PCB-IMG",
                component_id="U001",
                inspection_result=InspectionResult.FAIL,
                defect_type="MISALIGNMENT",
                confidence_score=0.9,
                inference_latency_ms=21,
                timestamp="2026-04-19T12:10:00+00:00",
                run_image_index=1,
                overlay_x=0.4,
                overlay_y=0.3,
                overlay_width=0.05,
                overlay_height=0.06,
                overlay_shape="rect",
            )
        ],
        images=[
            RunImageInput(
                image_path="/runs/PCB-IMG/images/top.png",
                image_role="top_view",
                image_width=1600,
                image_height=900,
            ),
            RunImageInput(
                image_path="/runs/PCB-IMG/images/detail.png",
                image_role="detail_crop",
                image_width=800,
                image_height=800,
            ),
        ],
    )

    run = database.fetch_run_with_defects(persisted_run.run_id)

    assert run is not None
    assert len(run["images"]) == 2
    assert run["images"][1]["image_role"] == "detail_crop"
    assert run["defect_logs"][0]["run_image_id"] == run["images"][1]["id"]
    assert run["defect_logs"][0]["overlay_x"] == 0.4


def test_delete_run_removes_run_images_and_defect_logs(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    persisted_run = database.persist_events(
        events=[
            InferenceEvent.create(
                pcb_id="PCB-DEL",
                component_id="U404",
                inspection_result=InspectionResult.FAIL,
                defect_type="MISSING",
                confidence_score=0.91,
                inference_latency_ms=22,
                timestamp="2026-04-20T12:00:00+00:00",
            )
        ]
    )

    deleted = database.delete_run(persisted_run.run_id)

    assert deleted is True
    assert database.fetch_run(persisted_run.run_id) is None
    assert database.fetch_run_images(persisted_run.run_id) == []
    assert database.fetch_defect_logs(persisted_run.run_id) == []
