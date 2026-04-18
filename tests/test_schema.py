from aoi.schema import InferenceEvent, InspectionResult


def test_inference_event_serializes_expected_fields() -> None:
    event = InferenceEvent.create(
        pcb_id="PCB-0001",
        component_id="R101",
        inspection_result=InspectionResult.FAIL,
        defect_type="MISALIGNMENT",
        confidence_score=0.82,
        inference_latency_ms=42,
        timestamp="2026-04-18T12:00:00+00:00",
    )

    assert event.to_dict() == {
        "timestamp": "2026-04-18T12:00:00+00:00",
        "pcb_id": "PCB-0001",
        "component_id": "R101",
        "inspection_result": "FAIL",
        "defect_type": "MISALIGNMENT",
        "confidence_score": 0.82,
        "inference_latency_ms": 42,
    }


def test_inference_event_rejects_invalid_confidence() -> None:
    try:
        InferenceEvent.create(
            pcb_id="PCB-0001",
            component_id="R101",
            inspection_result=InspectionResult.PASS,
            defect_type="NO_DEFECT",
            confidence_score=1.5,
            inference_latency_ms=10,
        )
    except ValueError as exc:
        assert "confidence_score" in str(exc)
    else:
        raise AssertionError("Expected ValueError")

