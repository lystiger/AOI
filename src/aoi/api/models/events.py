from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from aoi.schema import InferenceEvent, InspectionResult, RunImageInput


def _require_non_empty_string(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _first_pydantic_error_message(exc: ValidationError) -> str:
    first_error = exc.errors()[0]
    return str(first_error.get("msg") or "validation error")


class RunImageInputIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_path: str
    image_role: str
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)

    @field_validator("image_path", "image_role")
    @classmethod
    def validate_non_empty_string(cls, value: str, info) -> str:
        return _require_non_empty_string(value, info.field_name)

    def to_domain(self) -> RunImageInput:
        return RunImageInput(
            image_path=self.image_path,
            image_role=self.image_role,
            image_width=self.image_width,
            image_height=self.image_height,
        )


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str | None = None
    pcb_id: str
    component_id: str
    inspection_result: InspectionResult
    defect_type: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    inference_latency_ms: int = Field(ge=0)
    run_image_index: int | None = Field(default=None, ge=0)
    overlay_x: float | None = Field(default=None, ge=0.0, le=1.0)
    overlay_y: float | None = Field(default=None, ge=0.0, le=1.0)
    overlay_width: float | None = Field(default=None, ge=0.0, le=1.0)
    overlay_height: float | None = Field(default=None, ge=0.0, le=1.0)
    overlay_shape: str | None = None

    @field_validator("pcb_id", "component_id", "defect_type")
    @classmethod
    def validate_required_strings(cls, value: str, info) -> str:
        return _require_non_empty_string(value, info.field_name)

    @field_validator("overlay_shape")
    @classmethod
    def validate_optional_string(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _require_non_empty_string(value, info.field_name)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError("timestamp must be a non-empty ISO8601 string")
        candidate = value.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("timestamp must be a valid ISO8601 string") from exc
        return value

    def to_domain(self) -> InferenceEvent:
        return InferenceEvent.create(
            timestamp=self.timestamp,
            pcb_id=self.pcb_id,
            component_id=self.component_id,
            inspection_result=self.inspection_result,
            defect_type=self.defect_type,
            confidence_score=self.confidence_score,
            inference_latency_ms=self.inference_latency_ms,
            run_image_index=self.run_image_index,
            overlay_x=self.overlay_x,
            overlay_y=self.overlay_y,
            overlay_width=self.overlay_width,
            overlay_height=self.overlay_height,
            overlay_shape=self.overlay_shape,
            operator_review=self.operator_review,
        )


class PostEventsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_version: str | None = None
    images: list[RunImageInputIn] | None = None
    events: list[EventIn]

    @field_validator("model_version")
    @classmethod
    def validate_model_version(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_non_empty_string(value, "model_version")

    @field_validator("events")
    @classmethod
    def validate_events_not_empty(cls, value: list[EventIn]) -> list[EventIn]:
        if not value:
            raise ValueError("events payload must contain at least one event")
        return value

    @field_validator("images")
    @classmethod
    def validate_images_not_empty(cls, value: list[RunImageInputIn] | None) -> list[RunImageInputIn] | None:
        if value is not None and not value:
            raise ValueError("images must be a non-empty list when provided")
        return value


event_list_adapter = TypeAdapter(list[EventIn])
event_adapter = TypeAdapter(EventIn)


def parse_post_events_payload(payload: object) -> tuple[list[EventIn], str | None, list[RunImageInputIn] | None]:
    try:
        if isinstance(payload, list):
            events = event_list_adapter.validate_python(payload)
            if not events:
                raise ValueError("events payload must contain at least one event")
            return events, None, None

        if isinstance(payload, dict) and "events" not in payload and "images" not in payload and "model_version" not in payload:
            event = event_adapter.validate_python(payload)
            return [event], None, None

        request_model = PostEventsRequest.model_validate(payload)
        return request_model.events, request_model.model_version, request_model.images
    except ValidationError as exc:
        raise ValueError(_first_pydantic_error_message(exc)) from exc
    except TypeError as exc:
        raise ValueError("payload must be an event object or a list of event objects") from exc
rom exc
