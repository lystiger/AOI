from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError, TypeAdapter

from aoi.api.deps import DatabaseManagerDep, LogManagerDep
from aoi.api.models import EventIn, PostEventsRequest, RunImageInputIn

router = APIRouter()

event_list_adapter = TypeAdapter(list[EventIn])
event_adapter = TypeAdapter(EventIn)


def _first_pydantic_error_message(exc: ValidationError) -> str:
    first_error = exc.errors()[0]
    return str(first_error.get("msg") or "validation error")


def _parse_payload(payload: object) -> tuple[list[EventIn], str | None, list[RunImageInputIn] | None]:
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


@router.post("/events", status_code=202)
async def post_events(
    request: Request,
    database_manager: DatabaseManagerDep,
    log_manager: LogManagerDep,
) -> dict[str, object]:
    try:
        payload = await request.json()
        events, model_version, images = _parse_payload(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    domain_events = [event.to_domain() for event in events]
    domain_images = [image.to_domain() for image in images] if images is not None else None

    for event in events:
        log_manager.write_json(event.to_domain())

    persisted_run = database_manager.persist_events(
        events=domain_events,
        model_version=model_version,
        images=domain_images,
    )
    return {
        "status": "accepted",
        "run_id": persisted_run.run_id,
        "accepted": len(domain_events),
    }
