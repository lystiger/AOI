from aoi.database import DatabaseManager
from aoi.schema import InferenceEvent, InspectionResult


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

    assert run_row is not None
    assert run_row["pcb_id"] == "PCB-0001"
    assert run_row["status"] == "FAIL"
    assert run_row["model_version"] == "v1.2.3"
    assert len(defect_rows) == 2
    assert defect_rows[0]["severity"] == "major"
    assert defect_rows[1]["severity"] == "none"
