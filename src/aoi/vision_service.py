from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter, UnidentifiedImageError


class VisionService:
    def __init__(self, *, db_path: Path, storage_path: Path) -> None:
        self.db_path = db_path
        self.storage_path = storage_path

    def detect_fiducial_failure(self, image: dict[str, object], run_id: str) -> str | None:
        width = int(image.get("image_width") or 0)
        height = int(image.get("image_height") or 0)
        if width < 320 or height < 240:
            return "fiducial detection failed: scan resolution is too small for reliable alignment"
        try:
            fiducials = self.detect_fiducials(image, run_id)
        except ValueError as exc:
            return str(exc)
        if len(fiducials) < 3:
            return "fiducial detection failed: found fewer than 3 fiducial candidates"
        return None

    def detect_components(self, image: dict[str, object], run_id: str) -> list[dict[str, object]]:
        image_file = self._resolve_run_image_file(run_id, image)
        try:
            with Image.open(image_file) as source_image:
                rgb_image = source_image.convert("RGB")
        except (FileNotFoundError, UnidentifiedImageError) as exc:
            raise ValueError(f"component detection failed: unable to read scan image from {image_file}") from exc

        original_width, original_height = rgb_image.size
        working_image, scale = self._prepare_detection_image(rgb_image)
        component_mask = self._build_component_candidate_mask(working_image)
        components = self._extract_mask_components(component_mask, *working_image.size)
        return self._score_component_candidates(
            components,
            run_image_id=str(image["id"]),
            image_size=working_image.size,
            original_size=(original_width, original_height),
            scale=scale,
        )

    @staticmethod
    def detect_barcode_failure(image: dict[str, object]) -> str | None:
        if int(image.get("image_width") or 0) < 960 or int(image.get("image_height") or 0) < 540:
            return "barcode detection failed: scan resolution is too small for reliable decoding"
        return None

    @staticmethod
    def build_mock_barcode(run_image_id: str, pcb_id: str) -> dict[str, object]:
        return {
            "id": "barcode-1",
            "run_image_id": run_image_id,
            "x": 0.72,
            "y": 0.78,
            "width": 0.16,
            "height": 0.08,
            "confidence": 0.93,
            "decoded_value": f"{pcb_id}-LOT-01",
        }

    @staticmethod
    def normalize_manual_fiducials(fiducials: list[dict[str, object]], run_image_id: str) -> list[dict[str, object]]:
        if len(fiducials) < 3:
            raise ValueError("at least 3 fiducials are required")
        return [
            VisionService._normalize_detection_box(entry, run_image_id=run_image_id, fallback_id=f"fid-{index + 1}")
            for index, entry in enumerate(fiducials)
        ]

    @staticmethod
    def normalize_manual_barcode(barcode: dict[str, object], run_image_id: str) -> dict[str, object]:
        return VisionService._normalize_detection_box(
            barcode,
            run_image_id=run_image_id,
            fallback_id="barcode-1",
            require_decoded_value=True,
        )

    def detect_fiducials(self, image: dict[str, object], run_id: str) -> list[dict[str, object]]:
        image_file = self._resolve_run_image_file(run_id, image)
        try:
            with Image.open(image_file) as source_image:
                rgb_image = source_image.convert("RGB")
        except (FileNotFoundError, UnidentifiedImageError) as exc:
            raise ValueError(f"fiducial detection failed: unable to read scan image from {image_file}") from exc

        original_width, original_height = rgb_image.size
        working_image, scale = self._prepare_detection_image(rgb_image)
        candidate_mask = self._build_fiducial_candidate_mask(working_image)
        components = self._extract_mask_components(candidate_mask, *working_image.size)
        candidates = self._score_fiducial_components(
            components,
            run_image_id=str(image["id"]),
            image_size=working_image.size,
            original_size=(original_width, original_height),
            scale=scale,
        )
        fiducials = self._select_fiducial_candidates(candidates)
        if len(fiducials) < 3:
            raise ValueError("fiducial detection failed: found fewer than 3 fiducial candidates")
        return fiducials

    def _resolve_run_image_file(self, run_id: str, image: dict[str, object]) -> Path:
        image_path = str(image.get("image_path") or "").strip()
        if not image_path:
            raise ValueError("fiducial detection failed: scan image path is empty")

        path = Path(image_path)
        if path.is_absolute() and path.exists():
            return path
        if path.exists():
            return path.resolve()

        if image_path.startswith(f"/runs/{run_id}/images/"):
            run_dir = self.storage_path / run_id
            for pattern in ("scan.png", "scan.jpg", "scan.jpeg", "scan.webp"):
                candidate = run_dir / pattern
                if candidate.exists():
                    return candidate

        candidate = self.db_path.parent / image_path.lstrip("/")
        if candidate.exists():
            return candidate
        raise ValueError(f"fiducial detection failed: scan image file does not exist for {image_path}")

    @staticmethod
    def _prepare_detection_image(image: Image.Image) -> tuple[Image.Image, float]:
        width, height = image.size
        max_dimension = max(width, height)
        if max_dimension <= 1000:
            return image, 1.0
        scale = max_dimension / 1000.0
        resized = image.resize((max(1, int(width / scale)), max(1, int(height / scale))), Image.Resampling.LANCZOS)
        return resized, scale

    @staticmethod
    def _build_fiducial_candidate_mask(image: Image.Image) -> list[int]:
        hsv_image = image.convert("HSV")
        width, height = hsv_image.size
        hsv_pixels = hsv_image.load()
        mask = [0] * (width * height)
        for y in range(height):
            for x in range(width):
                hue, saturation, value = hsv_pixels[x, y]
                gold_like = 12 <= hue <= 48 and saturation >= 55 and value >= 90
                bright_neutral = saturation <= 40 and value >= 175
                if gold_like or bright_neutral:
                    mask[(y * width) + x] = 255

        mask_image = Image.new("L", (width, height))
        mask_image.putdata(mask)
        cleaned = mask_image.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
        return [1 if value >= 128 else 0 for value in cleaned.tobytes()]

    @staticmethod
    def _build_component_candidate_mask(image: Image.Image) -> list[int]:
        rgb_image = image.convert("RGB")
        width, height = rgb_image.size
        pixels = rgb_image.load()

        border_pixels: list[tuple[int, int, int]] = []
        sample_step = max(1, min(width, height) // 80)
        for x in range(0, width, sample_step):
            border_pixels.append(pixels[x, 0])
            border_pixels.append(pixels[x, height - 1])
        for y in range(0, height, sample_step):
            border_pixels.append(pixels[0, y])
            border_pixels.append(pixels[width - 1, y])

        if not border_pixels:
            return [0] * (width * height)

        board_red = sum(pixel[0] for pixel in border_pixels) / len(border_pixels)
        board_green = sum(pixel[1] for pixel in border_pixels) / len(border_pixels)
        board_blue = sum(pixel[2] for pixel in border_pixels) / len(border_pixels)
        board_brightness = (board_red + board_green + board_blue) / 3.0

        mask = [0] * (width * height)
        for y in range(height):
            for x in range(width):
                red, green, blue = pixels[x, y]
                diff = abs(red - board_red) + abs(green - board_green) + abs(blue - board_blue)
                brightness = (red + green + blue) / 3.0
                brightness_gap = abs(brightness - board_brightness)
                is_candidate = diff >= 90 or brightness_gap >= 45 or (red + blue) > (green + 55)
                if is_candidate:
                    mask[(y * width) + x] = 255

        mask_image = Image.new("L", (width, height))
        mask_image.putdata(mask)
        cleaned = mask_image.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        return [1 if value >= 128 else 0 for value in cleaned.tobytes()]

    @staticmethod
    def _extract_mask_components(mask: list[int], width: int | None = None, height: int | None = None) -> list[dict[str, int]]:
        if width is None or height is None:
            raise ValueError("mask width and height are required")
        visited = [False] * len(mask)
        components: list[dict[str, int]] = []
        for start_index, value in enumerate(mask):
            if value == 0 or visited[start_index]:
                continue
            queue: deque[int] = deque([start_index])
            visited[start_index] = True
            area = 0
            min_x = width
            min_y = height
            max_x = 0
            max_y = 0
            while queue:
                index = queue.popleft()
                x = index % width
                y = index // width
                area += 1
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                for delta_x, delta_y in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
                    next_x = x + delta_x
                    next_y = y + delta_y
                    if next_x < 0 or next_x >= width or next_y < 0 or next_y >= height:
                        continue
                    next_index = (next_y * width) + next_x
                    if visited[next_index] or mask[next_index] == 0:
                        continue
                    visited[next_index] = True
                    queue.append(next_index)
            components.append(
                {
                    "area": area,
                    "min_x": min_x,
                    "min_y": min_y,
                    "max_x": max_x,
                    "max_y": max_y,
                }
            )
        return components

    @staticmethod
    def _score_fiducial_components(
        components: list[dict[str, int]],
        *,
        run_image_id: str,
        image_size: tuple[int, int],
        original_size: tuple[int, int],
        scale: float,
    ) -> list[dict[str, object]]:
        width, height = image_size
        original_width, original_height = original_size
        image_area = width * height
        diagonal = (width**2 + height**2) ** 0.5
        candidates: list[dict[str, object]] = []
        for component in components:
            box_width = component["max_x"] - component["min_x"] + 1
            box_height = component["max_y"] - component["min_y"] + 1
            box_area = box_width * box_height
            if component["area"] < max(20, int(image_area * 0.00008)):
                continue
            if component["area"] > int(image_area * 0.02):
                continue
            aspect_ratio = box_width / max(box_height, 1)
            if aspect_ratio < 0.45 or aspect_ratio > 2.2:
                continue
            fill_ratio = component["area"] / max(box_area, 1)
            if fill_ratio < 0.2 or fill_ratio > 0.95:
                continue

            center_x = (component["min_x"] + component["max_x"]) / 2
            center_y = (component["min_y"] + component["max_y"]) / 2
            corner_distances = {
                "top_left": (center_x**2 + center_y**2) ** 0.5,
                "top_right": ((width - center_x) ** 2 + center_y**2) ** 0.5,
                "bottom_left": (center_x**2 + (height - center_y) ** 2) ** 0.5,
                "bottom_right": ((width - center_x) ** 2 + (height - center_y) ** 2) ** 0.5,
            }
            nearest_corner = min(corner_distances, key=corner_distances.get)
            corner_proximity = 1.0 - (corner_distances[nearest_corner] / max(diagonal, 1.0))
            size_balance = 1.0 - abs(box_width - box_height) / max(box_width, box_height, 1)
            score = (corner_proximity * 2.5) + size_balance + fill_ratio

            candidates.append(
                {
                    "id": f"fid-{len(candidates) + 1}",
                    "run_image_id": run_image_id,
                    "x": max((component["min_x"] * scale) / original_width, 0.0),
                    "y": max((component["min_y"] * scale) / original_height, 0.0),
                    "width": min((box_width * scale) / original_width, 1.0),
                    "height": min((box_height * scale) / original_height, 1.0),
                    "confidence": round(min(0.99, 0.45 + (score / 6.0)), 3),
                    "score": score,
                    "corner": nearest_corner,
                }
            )
        return candidates

    @staticmethod
    def _score_component_candidates(
        components: list[dict[str, int]],
        *,
        run_image_id: str,
        image_size: tuple[int, int],
        original_size: tuple[int, int],
        scale: float,
    ) -> list[dict[str, object]]:
        width, height = image_size
        original_width, original_height = original_size
        image_area = width * height
        candidates: list[dict[str, object]] = []
        for component in components:
            box_width = component["max_x"] - component["min_x"] + 1
            box_height = component["max_y"] - component["min_y"] + 1
            box_area = box_width * box_height
            if component["area"] < max(60, int(image_area * 0.00018)):
                continue
            if component["area"] > int(image_area * 0.18):
                continue
            if box_width < 8 or box_height < 8:
                continue

            fill_ratio = component["area"] / max(box_area, 1)
            aspect_ratio = box_width / max(box_height, 1)
            if fill_ratio < 0.3 or fill_ratio > 1.0:
                continue
            if aspect_ratio < 0.2 or aspect_ratio > 5.0:
                continue

            normalized_width = min((box_width * scale) / original_width, 1.0)
            normalized_height = min((box_height * scale) / original_height, 1.0)
            normalized_area = normalized_width * normalized_height
            confidence = min(0.99, 0.4 + (fill_ratio * 0.35) + min(normalized_area * 4.0, 0.24))
            candidates.append(
                {
                    "id": f"cmp-{len(candidates) + 1}",
                    "run_image_id": run_image_id,
                    "x": round(max((component["min_x"] * scale) / original_width, 0.0), 4),
                    "y": round(max((component["min_y"] * scale) / original_height, 0.0), 4),
                    "width": round(normalized_width, 4),
                    "height": round(normalized_height, 4),
                    "confidence": round(confidence, 3),
                    "label": "component_candidate",
                }
            )

        candidates.sort(key=lambda entry: (float(entry["confidence"]), float(entry["width"]) * float(entry["height"])), reverse=True)
        return candidates[:64]

    @staticmethod
    def _select_fiducial_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
        sorted_candidates = sorted(candidates, key=lambda item: float(item["score"]), reverse=True)
        selected: list[dict[str, object]] = []
        used_corners: set[str] = set()
        for candidate in sorted_candidates:
            corner = str(candidate["corner"])
            if corner in used_corners:
                continue
            selected.append(
                {
                    "id": f"fid-{len(selected) + 1}",
                    "run_image_id": candidate["run_image_id"],
                    "x": round(float(candidate["x"]), 4),
                    "y": round(float(candidate["y"]), 4),
                    "width": round(float(candidate["width"]), 4),
                    "height": round(float(candidate["height"]), 4),
                    "confidence": float(candidate["confidence"]),
                }
            )
            used_corners.add(corner)
            if len(selected) == 3:
                break
        if len(selected) >= 3:
            return selected
        for candidate in sorted_candidates:
            if len(selected) >= 3:
                break
            normalized = {
                "id": f"fid-{len(selected) + 1}",
                "run_image_id": candidate["run_image_id"],
                "x": round(float(candidate["x"]), 4),
                "y": round(float(candidate["y"]), 4),
                "width": round(float(candidate["width"]), 4),
                "height": round(float(candidate["height"]), 4),
                "confidence": float(candidate["confidence"]),
            }
            if normalized not in selected:
                selected.append(normalized)
        return selected

    @staticmethod
    def _normalize_detection_box(
        payload: dict[str, object],
        *,
        run_image_id: str,
        fallback_id: str,
        require_decoded_value: bool = False,
    ) -> dict[str, object]:
        decoded_value = str(payload.get("decoded_value") or "").strip()
        if require_decoded_value and not decoded_value:
            raise ValueError("decoded_value must be a non-empty string")

        normalized = {
            "id": str(payload.get("id") or fallback_id),
            "run_image_id": run_image_id,
            "x": VisionService._require_normalized_float(payload, "x"),
            "y": VisionService._require_normalized_float(payload, "y"),
            "width": VisionService._require_positive_normalized_float(payload, "width"),
            "height": VisionService._require_positive_normalized_float(payload, "height"),
            "confidence": VisionService._optional_normalized_confidence(payload.get("confidence")),
        }
        if require_decoded_value:
            normalized["decoded_value"] = decoded_value
        return normalized

    @staticmethod
    def _require_normalized_float(payload: dict[str, object], key: str) -> float:
        value = payload.get(key)
        if not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a number")
        number = float(value)
        if number < 0 or number > 1:
            raise ValueError(f"{key} must be between 0 and 1")
        return number

    @staticmethod
    def _require_positive_normalized_float(payload: dict[str, object], key: str) -> float:
        number = VisionService._require_normalized_float(payload, key)
        if number <= 0:
            raise ValueError(f"{key} must be greater than 0")
        return number

    @staticmethod
    def _optional_normalized_confidence(value: object) -> float:
        if value is None:
            return 1.0
        if not isinstance(value, (int, float)):
            raise ValueError("confidence must be a number")
        number = float(value)
        if number < 0 or number > 1:
            raise ValueError("confidence must be between 0 and 1")
        return number
