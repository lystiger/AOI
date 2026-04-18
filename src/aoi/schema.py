from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum


class InspectionResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(slots=True)
class InferenceEvent:
    timestamp: str
    pcb_id: str
    component_id: str
    inspection_result: InspectionResult
    defect_type: str
    confidence_score: float
    inference_latency_ms: int

    @classmethod
    def create(
        cls,
        *,
        pcb_id: str,
        component_id: str,
        inspection_result: InspectionResult,
        defect_type: str,
        confidence_score: float,
        inference_latency_ms: int,
        timestamp: str | None = None,
    ) -> "InferenceEvent":
        cls._validate(
            pcb_id=pcb_id,
            component_id=component_id,
            defect_type=defect_type,
            confidence_score=confidence_score,
            inference_latency_ms=inference_latency_ms,
        )
        event_timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        return cls(
            timestamp=event_timestamp,
            pcb_id=pcb_id,
            component_id=component_id,
            inspection_result=inspection_result,
            defect_type=defect_type,
            confidence_score=confidence_score,
            inference_latency_ms=inference_latency_ms,
        )

    @staticmethod
    def _validate(
        *,
        pcb_id: str,
        component_id: str,
        defect_type: str,
        confidence_score: float,
        inference_latency_ms: int,
    ) -> None:
        if not pcb_id.strip():
            raise ValueError("pcb_id must not be empty")
        if not component_id.strip():
            raise ValueError("component_id must not be empty")
        if not defect_type.strip():
            raise ValueError("defect_type must not be empty")
        if not 0.0 <= confidence_score <= 1.0:
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        if inference_latency_ms < 0:
            raise ValueError("inference_latency_ms must be non-negative")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["inspection_result"] = self.inspection_result.value
        return payload

