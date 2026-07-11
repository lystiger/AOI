from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


def _validate_optional_non_empty_string(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pcb_id: str | None = None

    @field_validator("pcb_id")
    @classmethod
    def validate_pcb_id(cls, value: str | None) -> str | None:
        return _validate_optional_non_empty_string(value, "pcb_id")


class UpdateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str | None = None
    requires_fovs: bool | None = None
    requires_fiducials: bool | None = None
    requires_barcode: bool | None = None

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str | None) -> str | None:
        return _validate_optional_non_empty_string(value, "model_name")
