"""Tests for the real defect inference runner, using a fake YOLO model (no ultralytics)."""
from __future__ import annotations

import pytest

from aoi.api.models.events import EventIn
from aoi.inference_runner import (
    DEFECT_LABELS,
    NO_DEFECT_TYPE,
    defect_type_for,
    run_inference,
)
from aoi.schema import InspectionResult


class _Scalar:
    def __init__(self, value: float) -> None:
        self._value = value

    def item(self) -> float:
        return self._value


class _Vec:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def tolist(self) -> list[float]:
        return list(self._values)


class _Boxes:
    def __init__(self, cls: list[int], conf: list[float], xyxyn: list[list[float]]) -> None:
        self.cls = [_Scalar(c) for c in cls]
        self.conf = [_Scalar(c) for c in conf]
        self.xyxyn = [_Vec(b) for b in xyxyn]

    def __len__(self) -> int:
        return len(self.cls)


class _Result:
    def __init__(self, names: dict[int, str], boxes: _Boxes | None) -> None:
        self.names = names
        self.boxes = boxes


class _FakeModel:
    def __init__(self, result: _Result) -> None:
        self._result = result
        self.names = result.names

    def predict(self, **_kwargs):
        return [self._result]


def test_detections_become_fail_events_with_normalized_overlays():
    model = _FakeModel(
        _Result(
            names={0: "open", 1: "mouse_bite"},
            boxes=_Boxes(
                cls=[0, 1],
                conf=[0.91, 0.55],
                xyxyn=[[0.1, 0.2, 0.4, 0.6], [0.5, 0.5, 0.7, 0.9]],
            ),
        )
    )
    events = run_inference("board.jpg", model=model, pcb_id="PCB-1", run_image_index=0)

    assert [e.defect_type for e in events] == ["OPEN_CIRCUIT", "MOUSE_BITE"]
    assert all(e.inspection_result == InspectionResult.FAIL for e in events)
    first = events[0]
    assert first.overlay_x == 0.1 and first.overlay_y == 0.2
    assert first.overlay_width == pytest.approx(0.3) and first.overlay_height == pytest.approx(0.4)
    assert first.overlay_shape == "rect"
    assert all(e.run_image_index == 0 for e in events)


def test_no_detections_yields_single_pass_event():
    model = _FakeModel(_Result(names={0: "open"}, boxes=None))
    events = run_inference("clean.jpg", model=model, pcb_id="PCB-2")

    assert len(events) == 1
    assert events[0].inspection_result == InspectionResult.PASS
    assert events[0].defect_type == NO_DEFECT_TYPE
    assert events[0].component_id == "BOARD"


def test_overlay_coordinates_are_clamped_into_unit_range():
    # A box partly outside the frame must not produce out-of-range overlay values,
    # which the schema (0..1) would otherwise reject.
    model = _FakeModel(
        _Result(names={0: "spur"}, boxes=_Boxes(cls=[0], conf=[0.8], xyxyn=[[-0.1, 0.0, 1.2, 1.0]]))
    )
    events = run_inference("edge.jpg", model=model, pcb_id="PCB-3")
    box = events[0]
    assert 0.0 <= box.overlay_x <= 1.0
    assert 0.0 <= box.overlay_width <= 1.0


def test_emitted_events_satisfy_the_api_event_contract():
    model = _FakeModel(
        _Result(names={0: "conductor_scratch"}, boxes=_Boxes(cls=[0], conf=[0.7], xyxyn=[[0.2, 0.2, 0.5, 0.5]]))
    )
    events = run_inference("c.jpg", model=model, pcb_id="PCB-4", run_image_index=0)
    # The API would reject malformed events; round-trip through its inbound model.
    for event in events:
        EventIn.model_validate(event.to_dict())


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("open", "OPEN_CIRCUIT"),
        ("Open Circuit", "OPEN_CIRCUIT"),
        ("OP", "OPEN_CIRCUIT"),
        ("mouse-bite", "MOUSE_BITE"),
        ("spurious_copper", "SPURIOUS_COPPER"),
        ("some_new_class", "SOME_NEW_CLASS"),
    ],
)
def test_defect_type_for_normalizes_and_tolerates_unknowns(raw, expected):
    assert defect_type_for(raw) == expected


def test_all_documented_defect_labels_are_clean_strings():
    for value in DEFECT_LABELS.values():
        assert value and value == value.upper() and " " not in value
