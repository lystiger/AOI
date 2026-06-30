from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from aoi.api.deps import DatabaseManagerDep, LogManagerDep
from aoi.api.models import parse_post_events_payload

router = APIRouter()


@router.post("/events", status_code=202)
async def post_events(
    request: Request,
    database_manager: DatabaseManagerDep,
    log_manager: LogManagerDep,
) -> dict[str, object]:
    try:
        payload = await request.json()
        events, model_version, images = parse_post_events_payload(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    domain_events = [event.to_domain() for event in events]
    domain_images = [image.to_domain() for image in images] if images is not None else None

    for event in events:
        log_manager.write_json(event.to_domain(), model_version=model_version)

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
