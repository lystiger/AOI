"""Standalone defect-inference model server.

This is the heavy half of the split: torch + ultralytics + the trained weights live only
here, so the main AOI API image can stay lean and reach inference over HTTP only when it is
actually needed (e.g. behind a ``demo`` Docker Compose profile). The service is stateless —
image bytes in, defect events out — and speaks the same event schema the ``/events`` endpoint
accepts, so the API can rebuild domain events with the parsing it already has.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request

from aoi.inference_runner import (
    CONFIDENCE_THRESHOLD,
    MODEL_VERSION,
    load_defect_model,
    run_inference,
)


def create_inference_app(*, weights_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="AOI Inference Service", version="0.1.0")
    app.state.weights_path = weights_path
    app.state.defect_model = None

    def _model():
        """Load the model once per process; reuse it across requests."""
        if app.state.defect_model is None:
            app.state.defect_model = load_defect_model(app.state.weights_path)
        return app.state.defect_model

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "model_loaded": app.state.defect_model is not None}

    @app.post("/infer")
    async def infer(
        request: Request,
        pcb_id: str = Query(..., min_length=1),
        run_id: str | None = Query(default=None),
        confidence: float = Query(default=CONFIDENCE_THRESHOLD, ge=0.0, le=1.0),
    ) -> dict[str, object]:
        image_data = await request.body()
        if not image_data:
            raise HTTPException(status_code=400, detail="empty image body")

        try:
            model = _model()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="inference runtime unavailable; install ultralytics",
            ) from exc

        # run_inference reads from a path, so buffer the uploaded bytes to a temp file.
        with tempfile.NamedTemporaryFile(suffix=".png") as handle:
            handle.write(image_data)
            handle.flush()
            events = run_inference(
                handle.name,
                model=model,
                run_id=run_id,
                pcb_id=pcb_id,
                confidence_threshold=confidence,
            )

        return {"model_version": MODEL_VERSION, "events": [event.to_dict() for event in events]}

    return app
