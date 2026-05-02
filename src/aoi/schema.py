from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum


class InspectionResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class OperatorReview(StrEnum):
    NONE = "NONE"
    CONFIRMED_PASS = "CONFIRMED_PASS"
    CONFIRMED_FAIL = "CONFIRMED_FAIL"
    OVERRULED_PASS = "OVERRULED_PASS"
    OVERRULED_FAIL = "OVERRULED_FAIL"


@dataclass(slots=True)
class RunImageInput:
    image_path: str
    image_role: str
    image_width: int
    image_height: int

    @classmethod
    def create(
        cls,
        *,
        image_path: str,
        image_role: str,
        image_width: int,
        image_height: int,
    ) -> "RunImageInput":
        cls._require_non_empty_string(image_path, "image_path")
        cls._require_non_empty_string(image_role, "image_role")
        cls._require_positive_int(image_width, "image_width")
        cls._require_positive_int(image_height, "image_height")
        return cls(
            image_path=image_path,
            image_role=image_role,
            image_width=image_width,
            image_height=image_height,
        )

    @staticmethod
    def _require_non_empty_string(value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value

    @staticmethod
    def _require_positive_int(value: int, field_name: str) -> int:
        if value < 1:
            raise ValueError(f"{field_name} must be a positive integer")
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
    operator_review: OperatorReview = OperatorReview.NONE

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
        operator_review: OperatorReview | None = None,
    ) -> "InferenceEvent":
        cls._require_non_empty_string(pcb_id, "pcb_id", empty_message="pcb_id must not be empty")
        cls._require_non_empty_string(component_id, "component_id", empty_message="component_id must not be empty")
        cls._require_non_empty_string(defect_type, "defect_type", empty_message="defect_type must not be empty")
        cls._require_confidence_score(confidence_score)
        cls._require_non_negative_int(inference_latency_ms, "inference_latency_ms")
        cls._validate_optional_timestamp(timestamp)
        cls._validate_optional_non_negative_int(run_image_index, "run_image_index")
        cls._validate_optional_normalized_float(overlay_x, "overlay_x")
        cls._validate_optional_normalized_float(overlay_y, "overlay_y")
        cls._validate_optional_normalized_float(overlay_width, "overlay_width")
        cls._validate_optional_normalized_float(overlay_height, "overlay_height")
        cls._validate_optional_string(overlay_shape, "overlay_shape")
        event_timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        review = operator_review or OperatorReview.NONE
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
            operator_review=review,
        )

    @staticmethod
    def _require_non_empty_string(value: object, field_name: str, *, empty_message: str | None = None) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(empty_message or f"{field_name} must be a non-empty string")
        return value

    @staticmethod
    def _require_confidence_score(confidence_score: float) -> None:
        if not 0.0 <= confidence_score <= 1.0:
            raise ValueError("confidence_score must be between 0.0 and 1.0")

    @staticmethod
    def _require_non_negative_int(value: int, field_name: str) -> int:
        if value < 0:
            raise ValueError(f"{field_name} must be non-negative")
        return value

    @staticmethod
    def _validate_timestamp(timestamp: str) -> None:
        candidate = timestamp.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("timestamp must be a valid ISO8601 string") from exc

    @staticmethod
    def _validate_optional_timestamp(timestamp: object) -> str | None:
        if timestamp is None:
            return None
        if not isinstance(timestamp, str) or not timestamp.strip():
            raise ValueError("timestamp must be a non-empty ISO8601 string")
        InferenceEvent._validate_timestamp(timestamp)
        return timestamp

    @staticmethod
    def _validate_optional_non_negative_int(value: int | None, field_name: str) -> int | None:
        if value is None:
            return None
        return InferenceEvent._require_non_negative_int(value, field_name)

    @staticmethod
    def _validate_optional_normalized_float(value: float | None, field_name: str) -> float | None:
        if value is None:
            return None
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{field_name} must be between 0.0 and 1.0")
        return value

    @staticmethod
    def _validate_optional_string(value: object, field_name: str) -> str | None:
        if value is None:
            return None
        return InferenceEvent._require_non_empty_string(value, field_name)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["inspection_result"] = self.inspection_result.value
        payload["operator_review"] = self.operator_review.value
        return payload
