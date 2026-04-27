from pathlib import Path

from PIL import Image, ImageDraw

from aoi.database import DatabaseManager
from aoi.schema import InferenceEvent, InspectionResult, RunImageInput


def _create_fiducial_board_image(path: Path, *, size: tuple[int, int] = (1600, 900), include_marks: bool = True) -> Path:
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


def _insert_run_image(database: DatabaseManager, run: dict[str, object], image_path: Path, *, image_id: str = "img-1") -> None:
    with Image.open(image_path) as image:
        width, height = image.size

    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (image_id, run["id"], str(image_path), "full_board", width, height, 0, run["timestamp"]),
        )


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


def test_fetch_run_with_defects_does_not_invent_images_or_overlay_metadata_for_legacy_rows(tmp_path) -> None:
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
    assert run["defect_logs"][0]["overlay_shape"] is None
    assert run["defect_logs"][0]["overlay_x"] is None


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
    image_path = _create_fiducial_board_image(tmp_path / "fid-board.png")
    _insert_run_image(database, run, image_path)

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


def test_detect_fiducials_can_fail_and_manual_save_recovers_run(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-FID-FAIL")
    image_path = _create_fiducial_board_image(tmp_path / "fid-fail-board.png", size=(900, 700), include_marks=False)
    _insert_run_image(database, run, image_path)

    database.update_run(run["id"], model_name="MODEL-FID", requires_fiducials=True)

    try:
        database.detect_fiducials(run["id"])
    except ValueError as exc:
        assert "found fewer than 3 fiducial candidates" in str(exc)
    else:
        raise AssertionError("expected fiducial detection to fail")

    failed_run = database.fetch_run(run["id"])
    assert failed_run is not None
    assert failed_run["fiducial_status"] == "failed"
    assert failed_run["setup_status"] == "in_progress"

    recovered_run = database.save_manual_fiducials(
        run["id"],
        [
            {"x": 0.08, "y": 0.1, "width": 0.035, "height": 0.035},
            {"x": 0.86, "y": 0.12, "width": 0.035, "height": 0.035},
            {"x": 0.12, "y": 0.82, "width": 0.035, "height": 0.035},
        ],
    )

    assert recovered_run is not None
    assert recovered_run["fiducial_status"] == "confirmed"
    assert len(recovered_run["fiducials"]) == 3
    assert recovered_run["setup_status"] == "review_ready"


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


def test_detect_barcode_can_fail_and_manual_save_recovers_run(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-BAR-FAIL")

    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], "/runs/bar-fail/images/img-1", "full_board", 800, 420, 0, run["timestamp"]),
        )

    database.update_run(run["id"], model_name="MODEL-BAR", requires_barcode=True)

    try:
        database.detect_barcode(run["id"])
    except ValueError as exc:
        assert "resolution is too small" in str(exc)
    else:
        raise AssertionError("expected barcode detection to fail")

    failed_run = database.fetch_run(run["id"])
    assert failed_run is not None
    assert failed_run["barcode_status"] == "failed"
    assert failed_run["setup_status"] == "in_progress"

    recovered_run = database.save_manual_barcode(
        run["id"],
        {"x": 0.72, "y": 0.78, "width": 0.16, "height": 0.08, "decoded_value": "PCB-BAR-FAIL-LOT-01"},
    )

    assert recovered_run is not None
    assert recovered_run["barcode_status"] == "confirmed"
    assert recovered_run["barcode"]["decoded_value"] == "PCB-BAR-FAIL-LOT-01"
    assert recovered_run["setup_status"] == "review_ready"


def test_update_run_model_change_clears_confirmed_setup_artifacts(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-REWORK")
    image_path = _create_fiducial_board_image(tmp_path / "rework-board.png")
    _insert_run_image(database, run, image_path)

    database.update_run(run["id"], model_name="MODEL-A", requires_fiducials=True, requires_barcode=True)
    database.detect_fiducials(run["id"])
    database.confirm_fiducials(run["id"])
    database.detect_barcode(run["id"])
    database.confirm_barcode(run["id"])

    updated_run = database.update_run(run["id"], model_name="MODEL-B")

    assert updated_run is not None
    assert updated_run["model_name"] == "MODEL-B"
    assert updated_run["fiducials"] == []
    assert updated_run["barcode"] is None
    assert updated_run["fiducial_status"] == "ready"
    assert updated_run["barcode_status"] == "ready"
    assert updated_run["setup_status"] == "in_progress"


def test_update_run_targeted_requirement_toggle_only_resets_affected_step(tmp_path) -> None:
    database = DatabaseManager(tmp_path / "aoi.db")
    run = database.create_run(pcb_id="PCB-TOGGLE")
    image_path = _create_fiducial_board_image(tmp_path / "toggle-board.png")
    _insert_run_image(database, run, image_path)

    database.update_run(run["id"], model_name="MODEL-T", requires_fiducials=True, requires_barcode=True)
    database.detect_fiducials(run["id"])
    database.confirm_fiducials(run["id"])
    database.detect_barcode(run["id"])
    database.confirm_barcode(run["id"])

    updated_run = database.update_run(run["id"], requires_barcode=False)

    assert updated_run is not None
    assert updated_run["fiducial_status"] == "confirmed"
    assert updated_run["fiducials"]
    assert updated_run["barcode_status"] == "not_required"
    assert updated_run["barcode"] is None
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
