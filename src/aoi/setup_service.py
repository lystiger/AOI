from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from aoi.vision_service import VisionService

if TYPE_CHECKING:
    from aoi.database import DatabaseManager


class SetupService:
    def __init__(self, database: DatabaseManager, vision_service: VisionService) -> None:
        self.database = database
        self.vision_service = vision_service

    def create_run(self, *, pcb_id: str | None = None) -> dict[str, object]:
        run_id = str(uuid.uuid4())
        run_timestamp = datetime.now(timezone.utc).isoformat()
        run_pcb_id = pcb_id.strip() if pcb_id and pcb_id.strip() else self._build_default_pcb_id(run_id)
        self.database.insert_run(
            run_id=run_id,
            pcb_id=run_pcb_id,
            timestamp=run_timestamp,
            model_version=None,
            status="SETUP",
            model_name=None,
            setup_status="not_ready",
            requires_fiducials=False,
            fiducial_status="not_required",
            fiducials_json=None,
            requires_barcode=False,
            barcode_status="not_required",
            barcode_json=None,
        )
        run = self.database.fetch_run(run_id)
        if run is None:
            raise ValueError("failed to create run")
        return run

    def update_run(
        self,
        run_id: str,
        *,
        model_name: str | None = None,
        requires_fiducials: bool | None = None,
        requires_barcode: bool | None = None,
        setup_status: str | None = None,
    ) -> dict[str, object] | None:
        run_row = self.database.fetch_run(run_id)
        if run_row is None:
            return None

        current_model_name = str(run_row.get("model_name") or "").strip()
        next_model_name = run_row.get("model_name")
        if model_name is not None:
            next_model_name = model_name.strip() or None
        next_model_name_text = str(next_model_name or "").strip()
        model_changed = model_name is not None and next_model_name_text != current_model_name

        next_requires_fiducials = bool(run_row.get("requires_fiducials"))
        current_requires_fiducials = next_requires_fiducials
        if requires_fiducials is not None:
            next_requires_fiducials = requires_fiducials
        fiducial_requirement_changed = next_requires_fiducials != current_requires_fiducials

        current_fiducial_status = str(run_row.get("fiducial_status") or "not_required")
        next_fiducial_status = current_fiducial_status
        next_fiducials_json = json.dumps(run_row.get("fiducials") or []) if run_row.get("fiducials") else None
        if model_changed or fiducial_requirement_changed:
            next_fiducials_json = None
            if not next_requires_fiducials:
                next_fiducial_status = "not_required"
            else:
                next_fiducial_status = "ready" if self.database.fetch_run_images(run_id) else "blocked"

        next_fiducial_status = self._calculate_fiducial_status(
            run_id,
            requires_fiducials=next_requires_fiducials,
            current_status=next_fiducial_status,
        )

        next_requires_barcode = bool(run_row.get("requires_barcode"))
        current_requires_barcode = next_requires_barcode
        if requires_barcode is not None:
            next_requires_barcode = requires_barcode
        barcode_requirement_changed = next_requires_barcode != current_requires_barcode

        current_barcode_status = str(run_row.get("barcode_status") or "not_required")
        next_barcode_status = current_barcode_status
        next_barcode_json = json.dumps(run_row.get("barcode")) if run_row.get("barcode") else None
        if model_changed or barcode_requirement_changed:
            next_barcode_json = None
            if not next_requires_barcode:
                next_barcode_status = "not_required"
            else:
                next_barcode_status = "ready" if self.database.fetch_run_images(run_id) else "blocked"

        next_barcode_status = self._calculate_barcode_status(
            run_id,
            requires_barcode=next_requires_barcode,
            current_status=next_barcode_status,
        )
        next_setup_status = setup_status or self._calculate_setup_status(
            run_id,
            next_model_name,
            requires_fiducials=next_requires_fiducials,
            fiducial_status=next_fiducial_status,
            requires_barcode=next_requires_barcode,
            barcode_status=next_barcode_status,
        )

        next_status = str(run_row.get("status") or "SETUP")
        if next_setup_status != "review_ready":
            next_status = "SETUP"

        self.database.update_run_setup_state(
            run_id,
            model_name=next_model_name,
            requires_fiducials=next_requires_fiducials,
            fiducial_status=next_fiducial_status,
            fiducials_json=next_fiducials_json,
            requires_barcode=next_requires_barcode,
            barcode_status=next_barcode_status,
            barcode_json=next_barcode_json,
            setup_status=next_setup_status,
            status=next_status,
        )
        return self.database.fetch_run(run_id)

    def add_run_image(
        self,
        run_id: str,
        *,
        image_id: str,
        image_path: str,
        image_role: str,
        image_width: int,
        image_height: int,
        created_at: str,
    ) -> dict[str, object] | None:
        if self.database.fetch_run(run_id) is None:
            return None
        self.database.insert_run_image(
            image_id=image_id,
            run_id=run_id,
            image_path=image_path,
            image_role=image_role,
            image_width=image_width,
            image_height=image_height,
            sort_order=0,
            created_at=created_at,
        )
        return self.update_run(run_id)

    def detect_fiducials(self, run_id: str) -> dict[str, object] | None:
        run_row = self.database.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_fiducials"]:
            raise ValueError("fiducials are not required for this run")
        images = self.database.fetch_run_images(run_id)
        if not images:
            raise ValueError("scan image is required before fiducial detection")

        detection_failure = self.vision_service.detect_fiducial_failure(images[0], run_id)
        if detection_failure is not None:
            self.database.update_run_setup_state(
                run_id,
                model_name=run_row.get("model_name"),
                requires_fiducials=True,
                fiducial_status="failed",
                fiducials_json=None,
                requires_barcode=bool(run_row.get("requires_barcode")),
                barcode_status=str(run_row.get("barcode_status") or "not_required"),
                barcode_json=json.dumps(run_row.get("barcode")) if run_row.get("barcode") else None,
                setup_status=self._calculate_setup_status(
                    run_id,
                    run_row.get("model_name"),
                    requires_fiducials=True,
                    fiducial_status="failed",
                    requires_barcode=bool(run_row.get("requires_barcode")),
                    barcode_status=str(run_row.get("barcode_status") or "not_required"),
                ),
                status=str(run_row.get("status") or "SETUP"),
            )
            raise ValueError(detection_failure)

        fiducials = self.vision_service.detect_fiducials(images[0], run_id)
        self.database.update_run_setup_state(
            run_id,
            model_name=run_row.get("model_name"),
            requires_fiducials=True,
            fiducial_status="needs_review",
            fiducials_json=json.dumps(fiducials),
            requires_barcode=bool(run_row.get("requires_barcode")),
            barcode_status=str(run_row.get("barcode_status") or "not_required"),
            barcode_json=json.dumps(run_row.get("barcode")) if run_row.get("barcode") else None,
            setup_status=self._calculate_setup_status(
                run_id,
                run_row.get("model_name"),
                requires_fiducials=True,
                fiducial_status="needs_review",
                requires_barcode=bool(run_row.get("requires_barcode")),
                barcode_status=str(run_row.get("barcode_status") or "not_required"),
            ),
            status=str(run_row.get("status") or "SETUP"),
        )
        return self.database.fetch_run(run_id)

    def confirm_fiducials(self, run_id: str) -> dict[str, object] | None:
        run_row = self.database.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_fiducials"]:
            raise ValueError("fiducials are not required for this run")
        if str(run_row.get("fiducial_status") or "") != "needs_review":
            raise ValueError("fiducials must be in needs_review before confirmation")

        self.database.update_run_setup_state(
            run_id,
            model_name=run_row.get("model_name"),
            requires_fiducials=bool(run_row.get("requires_fiducials")),
            fiducial_status="confirmed",
            fiducials_json=json.dumps(run_row.get("fiducials") or []) if run_row.get("fiducials") else None,
            requires_barcode=bool(run_row.get("requires_barcode")),
            barcode_status=str(run_row.get("barcode_status") or "not_required"),
            barcode_json=json.dumps(run_row.get("barcode")) if run_row.get("barcode") else None,
            setup_status=self._calculate_setup_status(
                run_id,
                run_row.get("model_name"),
                requires_fiducials=bool(run_row.get("requires_fiducials")),
                fiducial_status="confirmed",
                requires_barcode=bool(run_row.get("requires_barcode")),
                barcode_status=str(run_row.get("barcode_status") or "not_required"),
            ),
            status=str(run_row.get("status") or "SETUP"),
        )
        return self.database.fetch_run(run_id)

    def save_manual_fiducials(self, run_id: str, fiducials: list[dict[str, object]]) -> dict[str, object] | None:
        run_row = self.database.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_fiducials"]:
            raise ValueError("fiducials are not required for this run")
        images = self.database.fetch_run_images(run_id)
        if not images:
            raise ValueError("scan image is required before saving fiducials")

        normalized_fiducials = self.vision_service.normalize_manual_fiducials(fiducials, str(images[0]["id"]))
        self.database.update_run_setup_state(
            run_id,
            model_name=run_row.get("model_name"),
            requires_fiducials=True,
            fiducial_status="confirmed",
            fiducials_json=json.dumps(normalized_fiducials),
            requires_barcode=bool(run_row.get("requires_barcode")),
            barcode_status=str(run_row.get("barcode_status") or "not_required"),
            barcode_json=json.dumps(run_row.get("barcode")) if run_row.get("barcode") else None,
            setup_status=self._calculate_setup_status(
                run_id,
                run_row.get("model_name"),
                requires_fiducials=True,
                fiducial_status="confirmed",
                requires_barcode=bool(run_row.get("requires_barcode")),
                barcode_status=str(run_row.get("barcode_status") or "not_required"),
            ),
            status=str(run_row.get("status") or "SETUP"),
        )
        return self.database.fetch_run(run_id)

    def detect_barcode(self, run_id: str) -> dict[str, object] | None:
        run_row = self.database.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_barcode"]:
            raise ValueError("barcode is not required for this run")
        images = self.database.fetch_run_images(run_id)
        if not images:
            raise ValueError("scan image is required before barcode detection")

        detection_failure = self.vision_service.detect_barcode_failure(images[0])
        if detection_failure is not None:
            self.database.update_run_setup_state(
                run_id,
                model_name=run_row.get("model_name"),
                requires_fiducials=bool(run_row.get("requires_fiducials")),
                fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
                fiducials_json=json.dumps(run_row.get("fiducials") or []) if run_row.get("fiducials") else None,
                requires_barcode=True,
                barcode_status="failed",
                barcode_json=None,
                setup_status=self._calculate_setup_status(
                    run_id,
                    run_row.get("model_name"),
                    requires_fiducials=bool(run_row.get("requires_fiducials")),
                    fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
                    requires_barcode=True,
                    barcode_status="failed",
                ),
                status=str(run_row.get("status") or "SETUP"),
            )
            raise ValueError(detection_failure)

        barcode = self.vision_service.build_mock_barcode(str(images[0]["id"]), str(run_row["pcb_id"]))
        self.database.update_run_setup_state(
            run_id,
            model_name=run_row.get("model_name"),
            requires_fiducials=bool(run_row.get("requires_fiducials")),
            fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
            fiducials_json=json.dumps(run_row.get("fiducials") or []) if run_row.get("fiducials") else None,
            requires_barcode=True,
            barcode_status="needs_review",
            barcode_json=json.dumps(barcode),
            setup_status=self._calculate_setup_status(
                run_id,
                run_row.get("model_name"),
                requires_fiducials=bool(run_row.get("requires_fiducials")),
                fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
                requires_barcode=True,
                barcode_status="needs_review",
            ),
            status=str(run_row.get("status") or "SETUP"),
        )
        return self.database.fetch_run(run_id)

    def confirm_barcode(self, run_id: str) -> dict[str, object] | None:
        run_row = self.database.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_barcode"]:
            raise ValueError("barcode is not required for this run")
        if str(run_row.get("barcode_status") or "") != "needs_review":
            raise ValueError("barcode must be in needs_review before confirmation")

        self.database.update_run_setup_state(
            run_id,
            model_name=run_row.get("model_name"),
            requires_fiducials=bool(run_row.get("requires_fiducials")),
            fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
            fiducials_json=json.dumps(run_row.get("fiducials") or []) if run_row.get("fiducials") else None,
            requires_barcode=bool(run_row.get("requires_barcode")),
            barcode_status="confirmed",
            barcode_json=json.dumps(run_row.get("barcode")) if run_row.get("barcode") else None,
            setup_status=self._calculate_setup_status(
                run_id,
                run_row.get("model_name"),
                requires_fiducials=bool(run_row.get("requires_fiducials")),
                fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
                requires_barcode=bool(run_row.get("requires_barcode")),
                barcode_status="confirmed",
            ),
            status=str(run_row.get("status") or "SETUP"),
        )
        return self.database.fetch_run(run_id)

    def save_manual_barcode(self, run_id: str, barcode: dict[str, object]) -> dict[str, object] | None:
        run_row = self.database.fetch_run(run_id)
        if run_row is None:
            return None
        if not run_row["requires_barcode"]:
            raise ValueError("barcode is not required for this run")
        images = self.database.fetch_run_images(run_id)
        if not images:
            raise ValueError("scan image is required before saving barcode")

        normalized_barcode = self.vision_service.normalize_manual_barcode(barcode, str(images[0]["id"]))
        self.database.update_run_setup_state(
            run_id,
            model_name=run_row.get("model_name"),
            requires_fiducials=bool(run_row.get("requires_fiducials")),
            fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
            fiducials_json=json.dumps(run_row.get("fiducials") or []) if run_row.get("fiducials") else None,
            requires_barcode=True,
            barcode_status="confirmed",
            barcode_json=json.dumps(normalized_barcode),
            setup_status=self._calculate_setup_status(
                run_id,
                run_row.get("model_name"),
                requires_fiducials=bool(run_row.get("requires_fiducials")),
                fiducial_status=str(run_row.get("fiducial_status") or "not_required"),
                requires_barcode=True,
                barcode_status="confirmed",
            ),
            status=str(run_row.get("status") or "SETUP"),
        )
        return self.database.fetch_run(run_id)

    def _calculate_fiducial_status(self, run_id: str, *, requires_fiducials: bool, current_status: str) -> str:
        if not requires_fiducials:
            return "not_required"
        if not self.database.fetch_run_images(run_id):
            return "blocked"
        if current_status in {"needs_review", "confirmed", "failed"}:
            return current_status
        return "ready"

    def _calculate_barcode_status(self, run_id: str, *, requires_barcode: bool, current_status: str) -> str:
        if not requires_barcode:
            return "not_required"
        if not self.database.fetch_run_images(run_id):
            return "blocked"
        if current_status in {"needs_review", "confirmed", "failed"}:
            return current_status
        return "ready"

    def _calculate_setup_status(
        self,
        run_id: str,
        model_name: object,
        *,
        requires_fiducials: bool = False,
        fiducial_status: str = "not_required",
        requires_barcode: bool = False,
        barcode_status: str = "not_required",
    ) -> str:
        has_model = bool(model_name and str(model_name).strip())
        has_images = bool(self.database.fetch_run_images(run_id))
        fiducials_ready = not requires_fiducials or fiducial_status == "confirmed"
        barcode_ready = not requires_barcode or barcode_status == "confirmed"
        if has_model and has_images and fiducials_ready and barcode_ready:
            return "review_ready"
        if has_model or has_images:
            return "in_progress"
        return "not_ready"

    @staticmethod
    def _build_default_pcb_id(run_id: str) -> str:
        return f"RUN-{run_id.split('-')[0].upper()}"
