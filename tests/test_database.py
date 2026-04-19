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
    assert len(run_images) == 1
    assert run_images[0]["image_path"] == "/mock/pcb-example-2nd.png"
    assert len(defect_rows) == 2
    assert defect_rows[0]["severity"] == "major"
    assert defect_rows[0]["run_image_id"] == run_images[0]["id"]
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
    assert len(run["images"]) == 1
    assert run["images"][0]["image_path"] == "/mock/pcb-example-2nd.png"
    assert run["defect_logs"][0]["run_image_id"] == run["images"][0]["id"]
    assert run["defect_logs"][0]["overlay_shape"] == "rect"


def test_create_run_initializes_setup_state(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")

    run = database.create_run()

    assert run["id"]
    assert run["pcb_id"].startswith("RUN-")
    assert run["status"] == "SETUP"
    assert run["model_name"] is None
    assert run["setup_status"] == "not_ready"


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
