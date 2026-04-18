import json

from aoi.log_manager import LogManager
from aoi.mock_inference import generate_mock_events


def test_log_manager_writes_jsonl(tmp_path) -> None:
    log_path = tmp_path / "inference.jsonl"
    manager = LogManager(log_path)

    for event in generate_mock_events(3):
        manager.write_json(event)

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()

    assert len(lines) == 3
    first_record = json.loads(lines[0])
    assert first_record["pcb_id"] == "PCB-0001"
    assert "inspection_result" in first_record


def test_log_manager_reads_back_records(tmp_path) -> None:
    log_path = tmp_path / "inference.jsonl"
    manager = LogManager(log_path)

    for event in generate_mock_events(2):
        manager.write_json(event)

    records = manager.read_all()

    assert len(records) == 2
    assert records[1]["component_id"] == "U002"
