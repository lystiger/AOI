from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum


class InspectionResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(slots=True)
class RunImageInput:
    image_path: str
    image_role: str
    image_width: int
    image_height: int

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "RunImageInput":
        image_path = cls._require_string(payload, "image_path")
        image_role = cls._require_string(payload, "image_role")
        image_width = int(payload.get("image_width", 0))
        image_height = int(payload.get("image_height", 0))
        if image_width < 1:
            raise ValueError("image_width must be a positive integer")
        if image_height < 1:
            raise ValueError("image_height must be a positive integer")
        return cls(
            image_path=image_path,
            image_role=image_role,
            image_width=image_width,
            image_height=image_height,
        )

    @staticmethod
    def _require_string(payload: dict[str, object], field_name: str) -> str:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value


@dataclass(slots=True)
class InferenceEvent:
    timestamp: str
    pcb_id: str
    component_id: str
    inspection_result: InspectionResult
    defect_type: str
    confidence_score: float
    inference_latency_ms: int
    run_image_index: int | None = None
    overlay_x: float | None = None
    overlay_y: float | None = None
    overlay_width: float | None = None
    overlay_height: float | None = None
    overlay_shape: str | None = None

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
        run_image_index: int | None = None,
        overlay_x: float | None = None,
        overlay_y: float | None = None,
        overlay_width: float | None = None,
        overlay_height: float | None = None,
        overlay_shape: str | None = None,
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
            run_image_index=run_image_index,
            overlay_x=overlay_x,
            overlay_y=overlay_y,
            overlay_width=overlay_width,
            overlay_height=overlay_height,
            overlay_shape=overlay_shape,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "InferenceEvent":
        raw_result = payload.get("inspection_result")
        if raw_result is None:
            raise ValueError("inspection_result is required")

        timestamp = payload.get("timestamp")
        if timestamp is None:
            event_timestamp = None
        elif isinstance(timestamp, str) and timestamp.strip():
            event_timestamp = timestamp
            cls._validate_timestamp(event_timestamp)
        else:
            raise ValueError("timestamp must be a non-empty ISO8601 string")

        try:
            inspection_result = InspectionResult(str(raw_result))
        except ValueError as exc:
            raise ValueError("inspection_result must be PASS or FAIL") from exc

        confidence_score = payload.get("confidence_score")
        inference_latency_ms = payload.get("inference_latency_ms")
        if confidence_score is None:
            raise ValueError("confidence_score is required")
        if inference_latency_ms is None:
            raise ValueError("inference_latency_ms is required")

        return cls.create(
            timestamp=event_timestamp,
            pcb_id=cls._require_string(payload, "pcb_id"),
            component_id=cls._require_string(payload, "component_id"),
            inspection_result=inspection_result,
            defect_type=cls._require_string(payload, "defect_type"),
            confidence_score=float(confidence_score),
            inference_latency_ms=int(inference_latency_ms),
            run_image_index=cls._get_optional_non_negative_int(payload, "run_image_index"),
            overlay_x=cls._get_optional_normalized_float(payload, "overlay_x"),
            overlay_y=cls._get_optional_normalized_float(payload, "overlay_y"),
            overlay_width=cls._get_optional_normalized_float(payload, "overlay_width"),
            overlay_height=cls._get_optional_normalized_float(payload, "overlay_height"),
            overlay_shape=cls._get_optional_string(payload, "overlay_shape"),
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

    @staticmethod
    def _get_optional_non_negative_int(payload: dict[str, object], field_name: str) -> int | None:
        value = payload.get(field_name)
        if value is None:
            return None
        parsed = int(value)
        if parsed < 0:
            raise ValueError(f"{field_name} must be a non-negative integer")
        return parsed

    @staticmethod
    def _get_optional_normalized_float(payload: dict[str, object], field_name: str) -> float | None:
        value = payload.get(field_name)
        if value is None:
            return None
        parsed = float(value)
        if not 0.0 <= parsed <= 1.0:
            raise ValueError(f"{field_name} must be between 0.0 and 1.0")
        return parsed

    @staticmethod
    def _get_optional_string(payload: dict[str, object], field_name: str) -> str | None:
        value = payload.get(field_name)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value

    @staticmethod
    def _require_string(payload: dict[str, object], field_name: str) -> str:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value

    @staticmethod
    def _validate_timestamp(timestamp: str) -> None:
        candidate = timestamp.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("timestamp must be a valid ISO8601 string") from exc

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["inspection_result"] = self.inspection_result.value
        return payload
