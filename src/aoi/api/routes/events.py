from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from aoi.api.deps import DatabaseManagerDep, LogManagerDep
from aoi.schema import InferenceEvent, RunImageInput

router = APIRouter()


def _parse_payload(payload: object) -> tuple[list[InferenceEvent], str | None, list[RunImageInput] | None]:
    model_version: str | None = None
    images: list[RunImageInput] | None = None
    if isinstance(payload, dict):
        raw_model_version = payload.get("model_version")
        if raw_model_version is not None:
            if not isinstance(raw_model_version, str) or not raw_model_version.strip():
                raise ValueError("model_version must be a non-empty string when provided")
            model_version = raw_model_version

        raw_images = payload.get("images")
        if raw_images is not None:
            if not isinstance(raw_images, list) or not raw_images:
                raise ValueError("images must be a non-empty list when provided")
            images = []
            for item in raw_images:
                if not isinstance(item, dict):
                    raise ValueError("each image must be a JSON object")
                images.append(RunImageInput.from_dict(item))

        raw_events = payload.get("events", [payload])
    elif isinstance(payload, list):
        raw_events = payload
    else:
        raise ValueError("payload must be an event object or a list of event objects")

    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("events payload must contain at least one event")

    events: list[InferenceEvent] = []
    for item in raw_events:
        if not isinstance(item, dict):
            raise ValueError("each event must be a JSON object")
        events.append(InferenceEvent.from_dict(item))
    return events, model_version, images


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
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for event in events:
        log_manager.write_json(event)

    persisted_run = database_manager.persist_events(
        events=events,
        model_version=model_version,
        images=images,
    )
    return {
        "status": "accepted",
        "run_id": persisted_run.run_id,
        "accepted": len(events),
    }
