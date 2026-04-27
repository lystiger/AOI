from aoi.schema import InferenceEvent, InspectionResult, RunImageInput


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
        "run_image_index": None,
        "overlay_x": None,
        "overlay_y": None,
        "overlay_width": None,
        "overlay_height": None,
        "overlay_shape": None,
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
def test_run_image_input_create_validates_expected_fields() -> None:
    image = RunImageInput.create(
        image_path="/runs/PCB-0001/images/top.png",
        image_role="top_view",
        image_width=1600,
        image_height=900,
    )

    assert image.image_path == "/runs/PCB-0001/images/top.png"
    assert image.image_role == "top_view"
    assert image.image_width == 1600
    assert image.image_height == 900
