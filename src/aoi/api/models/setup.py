from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _require_non_empty_string(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


class DetectionBoxIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("id")
    @classmethod
    def validate_optional_id(cls, value: str | None) -> str | None:
        return _require_non_empty_string(value, "id")


class BarcodeIn(DetectionBoxIn):
    decoded_value: str

    @field_validator("decoded_value")
    @classmethod
    def validate_decoded_value(cls, value: str) -> str:
        validated = _require_non_empty_string(value, "decoded_value")
        assert validated is not None
        return validated


class ManualFiducialsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fiducials: list[DetectionBoxIn]

    @field_validator("fiducials")
    @classmethod
    def validate_fiducials(cls, value: list[DetectionBoxIn]) -> list[DetectionBoxIn]:
        if len(value) < 3:
            raise ValueError("at least 3 fiducials are required")
        return value


class ManualBarcodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    barcode: BarcodeIn
