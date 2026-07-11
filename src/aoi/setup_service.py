from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
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
        requires_fovs: bool | None = None,
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

        next_requires_fovs = bool(run_row.get("requires_fovs"))
        if requires_fovs is not None:
            next_requires_fovs = requires_fovs

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
            requires_fovs=next_requires_fovs,
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
            requires_fovs=next_requires_fovs,
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
        updated_run = self.update_run(run_id)
        self._refresh_component_detection(run_id)
        return self.database.fetch_run(run_id) if updated_run is not None else None

    def _refresh_component_detection(self, run_id: str) -> None:
        run_row = self.database.fetch_run(run_id)
        if run_row is None:
            return
        images = self.database.fetch_run_images(run_id)
        if not images:
            self.database.update_component_detection(
                run_id,
                component_detection_status="blocked",
                components_json=None,
            )
            return

        components: list[dict[str, object]] = []
        failed_images = 0
        for image in images:
            try:
                detected_components = self.vision_service.detect_components(image, run_id)
            except ValueError:
                failed_images += 1
                continue
            components.extend(
                {
                    **component,
                    "image_role": image.get("image_role"),
                }
                for component in detected_components
            )

        status = "detected" if components else "failed" if failed_images == len(images) else "empty"
        self.database.update_component_detection(
            run_id,
            component_detection_status=status,
            components_json=json.dumps(components) if components else None,
        )

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

    def save_model_fovs(self, model_name: str, fovs: list[dict[str, object]]) -> list[dict[str, object]]:
        normalized_model_name = model_name.strip()
        if not normalized_model_name:
            raise ValueError("model_name must be a non-empty string")

        normalized_fovs: list[dict[str, object]] = []
        for index, entry in enumerate(fovs):
            normalized_fovs.append(
                {
                    "id": str(entry.get("id") or f"fov-{index + 1}").strip(),
                    "label": str(entry.get("label") or "").strip(),
                    "x": float(entry["x"]),
                    "y": float(entry["y"]),
                    "width": float(entry["width"]),
                    "height": float(entry["height"]),
                    "sort_order": index,
                }
            )

        return self.database.replace_model_fovs(normalized_model_name, normalized_fovs)

    def generate_run_fov_crops(self, run_id: str) -> dict[str, object] | None:
        run_row = self.database.fetch_run(run_id)
        if run_row is None:
            return None

        model_name = str(run_row.get("model_name") or "").strip()
        if not model_name:
            raise ValueError("model_name is required before generating FOV crops")

        fovs = self.database.fetch_model_fovs(model_name)
        if not fovs:
            raise ValueError("no FOVs are configured for this model")

        images = self.database.fetch_run_images(run_id)
        if not images:
            raise ValueError("scan image is required before generating FOV crops")

        source_image = images[0]
        source_file = self.vision_service.resolve_run_image_file(run_id, source_image)
        board_region = self.vision_service.detect_board_region(source_image, run_id)
        removed_images = self.database.delete_run_images_by_role_prefix(run_id, "fov:")
        self._delete_generated_fov_assets(removed_images)

        with self.vision_service.open_image_file(source_file) as image:
            run_dir = self.database.storage_path / run_id / "fovs"
            run_dir.mkdir(parents=True, exist_ok=True)
            next_sort_order = self.database.next_run_image_sort_order(run_id)
            for index, fov in enumerate(fovs):
                crop_box = self._resolve_fov_crop_box(image.size, board_region, fov)
                crop = image.crop(crop_box)
                filename = f"{fov['id']}.png"
                file_path = run_dir / filename
                crop.save(file_path, format="PNG")
                image_id = str(uuid.uuid4())
                self.database.insert_run_image(
                    image_id=image_id,
                    run_id=run_id,
                    image_path=str(file_path),
                    image_role=f"fov:{fov['id']}",
                    image_width=crop.width,
                    image_height=crop.height,
                    sort_order=next_sort_order + index,
                    created_at=str(run_row["timestamp"]),
                )

        self._refresh_component_detection(run_id)
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
        requires_fovs: bool | None = None,
        requires_fiducials: bool = False,
        fiducial_status: str = "not_required",
        requires_barcode: bool = False,
        barcode_status: str = "not_required",
    ) -> str:
        has_model = bool(model_name and str(model_name).strip())
        images = self.database.fetch_run_images(run_id)
        has_images = bool(images)
        if requires_fovs is None:
            run_row = self.database.fetch_run(run_id)
            requires_fovs = bool(run_row and run_row.get("requires_fovs"))
        model_fovs = self.database.fetch_model_fovs(str(model_name)) if has_model else []
        fov_image_count = sum(1 for image in images if str(image.get("image_role") or "").startswith("fov:"))
        fovs_ready = not requires_fovs or (bool(model_fovs) and fov_image_count >= len(model_fovs))
        fiducials_ready = not requires_fiducials or fiducial_status == "confirmed"
        barcode_ready = not requires_barcode or barcode_status == "confirmed"
        if has_model and has_images and fovs_ready and fiducials_ready and barcode_ready:
            return "review_ready"
        if has_model or has_images:
            return "in_progress"
        return "not_ready"

    @staticmethod
    def _resolve_fov_crop_box(
        image_size: tuple[int, int],
        board_region: dict[str, float],
        fov: dict[str, object],
    ) -> tuple[int, int, int, int]:
        image_width, image_height = image_size
        board_min_x = int(round(float(board_region["x"]) * image_width))
        board_min_y = int(round(float(board_region["y"]) * image_height))
        board_width = max(1, int(round(float(board_region["width"]) * image_width)))
        board_height = max(1, int(round(float(board_region["height"]) * image_height)))
        board_max_x = min(image_width, board_min_x + board_width)
        board_max_y = min(image_height, board_min_y + board_height)

        crop_min_x = board_min_x + int(round(float(fov["x"]) * board_width))
        crop_min_y = board_min_y + int(round(float(fov["y"]) * board_height))
        crop_max_x = crop_min_x + max(1, int(round(float(fov["width"]) * board_width)))
        crop_max_y = crop_min_y + max(1, int(round(float(fov["height"]) * board_height)))

        return (
            max(0, min(crop_min_x, image_width - 1)),
            max(0, min(crop_min_y, image_height - 1)),
            max(1, min(crop_max_x, board_max_x, image_width)),
            max(1, min(crop_max_y, board_max_y, image_height)),
        )

    @staticmethod
    def _delete_generated_fov_assets(images: list[dict[str, object]]) -> None:
        for image in images:
            image_path = Path(str(image.get("image_path") or "")).expanduser()
            if image_path.is_file():
                image_path.unlink(missing_ok=True)

    @staticmethod
    def _build_default_pcb_id(run_id: str) -> str:
        return f"RUN-{run_id.split('-')[0].upper()}"
