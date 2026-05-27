from __future__ import annotations

from itertools import cycle

from aoi.schema import InferenceEvent, InspectionResult


DEFECT_SEQUENCE = (
    ("NO_DEFECT", InspectionResult.PASS, 0.99),
    ("MISALIGNMENT", InspectionResult.FAIL, 0.81),
    ("INSUFFICIENT_SOLDER", InspectionResult.FAIL, 0.77),
    ("SOLDER_BRIDGE", InspectionResult.FAIL, 0.86),
    ("NO_DEFECT", InspectionResult.PASS, 0.96),
    ("MISSING_COMPONENT", InspectionResult.FAIL, 0.82),
    ("BENT_LEAD", InspectionResult.FAIL, 0.79),
)


def generate_mock_events(count: int) -> list[InferenceEvent]:
    if count < 1:
        return []

    events: list[InferenceEvent] = []
    defects = cycle(DEFECT_SEQUENCE)

    for index in range(1, count + 1):
        defect_type, result, confidence = next(defects)
        events.append(
            InferenceEvent.create(
                pcb_id=f"PCB-{((index - 1) // 6) + 1:04d}",
                component_id=f"U{index:03d}",
                inspection_result=result,
                defect_type=defect_type,
                confidence_score=confidence,
                inference_latency_ms=20 + (index % 7) * 3,
                overlay_x=round(0.1 + (index % 8) * 0.1, 4) if result == InspectionResult.FAIL else None,
                overlay_y=round(0.1 + (index % 6) * 0.12, 4) if result == InspectionResult.FAIL else None,
                overlay_width=0.08 if result == InspectionResult.FAIL else None,
                overlay_height=0.06 if result == InspectionResult.FAIL else None,
                overlay_shape="rect" if result == InspectionResult.FAIL else None,
            )
        )

    return events
