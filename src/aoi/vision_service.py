from __future__ import annotations

from collections import deque
import importlib.util
from pathlib import Path

from PIL import Image, ImageFilter, UnidentifiedImageError


REFERENCE_COMPONENT_MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "references"
    / "PCB-Component-Detection-main"
    / "PCB-Component-Detection-main"
    / "pcbComponent_net.pth"
)

REFERENCE_COMPONENT_LABELS = (
    "resistor",
    "capacitor",
    "inductor",
    "diode",
    "led",
    "ic",
    "transistor",
    "connector",
    "jumper",
    "emi_filter",
    "button",
    "clock",
    "transformer",
    "potentiometer",
    "heatsink",
    "fuse",
    "ferrite_bead",
    "buzzer",
    "display",
    "battery",
)

REFERENCE_COMPONENT_LABEL_THRESHOLDS = {
    "resistor": 0.60,
    "connector": 0.50,
    "led": 0.50,
    "ic": 0.50,
}


class VisionService:
    def __init__(self, *, db_path: Path, storage_path: Path) -> None:
        self.db_path = db_path
        self.storage_path = storage_path
        self._component_classifier: object | None = None
        self._component_classifier_loaded = False

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
        board_mask = self._build_board_region_mask(working_image)
        component_mask = self._build_component_candidate_mask(working_image)
        components = self._extract_mask_components(component_mask, *working_image.size)
        candidates = self._score_component_candidates(
            components,
            run_image_id=str(image["id"]),
            image_size=working_image.size,
            original_size=(original_width, original_height),
            scale=scale,
            board_mask=board_mask,
        )
        return self._classify_component_candidates(candidates, rgb_image)

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
        hsv_image = image.convert("HSV")
        width, height = hsv_image.size
        hsv_pixels = hsv_image.load()

        hue_buckets = [0] * 256
        board_samples: list[tuple[int, int, int]] = []
        for y in range(height):
            for x in range(width):
                hue, saturation, value = hsv_pixels[x, y]
                # Ignore probable white backdrop and near-black framing noise.
                if (saturation <= 20 and value >= 242) or value <= 18:
                    continue
                if saturation >= 30 and 28 <= value <= 240:
                    hue_buckets[hue] += saturation

        dominant_hue = max(range(256), key=lambda index: hue_buckets[index]) if any(hue_buckets) else 85

        for y in range(height):
            for x in range(width):
                hue, saturation, value = hsv_pixels[x, y]
                if (saturation <= 20 and value >= 242) or value <= 18:
                    continue
                if VisionService._circular_hue_distance(hue, dominant_hue) <= 18 and saturation >= 25 and value <= 235:
                    board_samples.append((hue, saturation, value))

        if board_samples:
            board_saturation = sum(sample[1] for sample in board_samples) / len(board_samples)
            board_value = sum(sample[2] for sample in board_samples) / len(board_samples)
        else:
            board_saturation = 90.0
            board_value = 120.0

        mask = [0] * (width * height)
        for y in range(height):
            for x in range(width):
                hue, saturation, value = hsv_pixels[x, y]
                if (saturation <= 20 and value >= 242) or value <= 18:
                    continue

                hue_distance = VisionService._circular_hue_distance(hue, dominant_hue)
                bright_metallic = saturation <= 55 and 55 <= value <= 240
                dark_body = value <= max(42, int(board_value - 22))
                hue_shifted = hue_distance >= 16 and value >= 28
                saturation_shifted = abs(saturation - board_saturation) >= 28 and value >= 28
                board_like = hue_distance <= 14 and abs(saturation - board_saturation) <= 22 and abs(value - board_value) <= 26
                if not board_like and (bright_metallic or dark_body or hue_shifted or saturation_shifted):
                    mask[(y * width) + x] = 255

        mask_image = Image.new("L", (width, height))
        mask_image.putdata(mask)
        cleaned = mask_image.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        return [1 if value >= 128 else 0 for value in cleaned.tobytes()]

    @staticmethod
    def _build_board_region_mask(image: Image.Image) -> list[int]:
        hsv_image = image.convert("HSV")
        width, height = hsv_image.size
        hsv_pixels = hsv_image.load()

        hue_buckets = [0] * 256
        for y in range(height):
            for x in range(width):
                hue, saturation, value = hsv_pixels[x, y]
                if (saturation <= 20 and value >= 242) or value <= 18:
                    continue
                if saturation >= 30 and 28 <= value <= 240:
                    hue_buckets[hue] += saturation

        dominant_hue = max(range(256), key=lambda index: hue_buckets[index]) if any(hue_buckets) else 85
        board_mask = [0] * (width * height)
        for y in range(height):
            for x in range(width):
                hue, saturation, value = hsv_pixels[x, y]
                if (saturation <= 20 and value >= 242) or value <= 18:
                    continue
                hue_distance = VisionService._circular_hue_distance(hue, dominant_hue)
                if hue_distance <= 18 and saturation >= 25 and value <= 235:
                    board_mask[(y * width) + x] = 1
        return board_mask

    @staticmethod
    def _circular_hue_distance(first: int, second: int) -> int:
        diff = abs(first - second)
        return min(diff, 256 - diff)

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
        board_mask: list[int] | None = None,
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
        board_mask: list[int] | None = None,
    ) -> list[dict[str, object]]:
        width, height = image_size
        original_width, original_height = original_size
        image_area = width * height
        edge_margin_x = max(6, int(width * 0.012))
        edge_margin_y = max(6, int(height * 0.012))
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
            touches_left_edge = component["min_x"] <= edge_margin_x
            touches_top_edge = component["min_y"] <= edge_margin_y
            touches_right_edge = component["max_x"] >= (width - 1 - edge_margin_x)
            touches_bottom_edge = component["max_y"] >= (height - 1 - edge_margin_y)
            touches_edge = touches_left_edge or touches_top_edge or touches_right_edge or touches_bottom_edge

            fill_ratio = component["area"] / max(box_area, 1)
            aspect_ratio = box_width / max(box_height, 1)
            if fill_ratio < 0.3 or fill_ratio > 1.0:
                continue
            if aspect_ratio < 0.2 or aspect_ratio > 5.0:
                continue
            # Reject UI chrome and image-frame artifacts that cling to the outer edge.
            if touches_edge and (box_width >= width * 0.025 or box_height >= height * 0.025):
                continue
            if touches_edge and component["area"] < int(image_area * 0.0012):
                continue
            if board_mask is not None and not VisionService._candidate_is_on_board(component, board_mask, width, height):
                continue

            normalized_width = min((box_width * scale) / original_width, 1.0)
            normalized_height = min((box_height * scale) / original_height, 1.0)
            normalized_area = normalized_width * normalized_height
            confidence = min(0.99, 0.4 + (fill_ratio * 0.35) + min(normalized_area * 4.0, 0.24))
            expanded_box = VisionService._expand_component_box(
                min_x=component["min_x"],
                min_y=component["min_y"],
                max_x=component["max_x"],
                max_y=component["max_y"],
                image_width=width,
                image_height=height,
            )
            expanded_width = expanded_box["max_x"] - expanded_box["min_x"] + 1
            expanded_height = expanded_box["max_y"] - expanded_box["min_y"] + 1
            candidates.append(
                {
                    "id": f"cmp-{len(candidates) + 1}",
                    "run_image_id": run_image_id,
                    "x": round(max((expanded_box["min_x"] * scale) / original_width, 0.0), 4),
                    "y": round(max((expanded_box["min_y"] * scale) / original_height, 0.0), 4),
                    "width": round(min((expanded_width * scale) / original_width, 1.0), 4),
                    "height": round(min((expanded_height * scale) / original_height, 1.0), 4),
                    "confidence": round(confidence, 3),
                    "label": "component_candidate",
                }
            )

        candidates.sort(key=lambda entry: (float(entry["confidence"]), float(entry["width"]) * float(entry["height"])), reverse=True)
        return candidates[:64]

    @staticmethod
    def _candidate_is_on_board(
        component: dict[str, int],
        board_mask: list[int],
        width: int,
        height: int,
    ) -> bool:
        box_width = component["max_x"] - component["min_x"] + 1
        box_height = component["max_y"] - component["min_y"] + 1
        pad_x = max(4, int(box_width * 0.2))
        pad_y = max(4, int(box_height * 0.2))
        left = max(0, component["min_x"] - pad_x)
        right = min(width - 1, component["max_x"] + pad_x)
        top = max(0, component["min_y"] - pad_y)
        bottom = min(height - 1, component["max_y"] + pad_y)
        center_x = (component["min_x"] + component["max_x"]) // 2
        center_y = (component["min_y"] + component["max_y"]) // 2

        sample_xs = {
            left,
            component["min_x"],
            center_x,
            component["max_x"],
            right,
        }
        sample_ys = {
            top,
            component["min_y"],
            center_y,
            component["max_y"],
            bottom,
        }
        hits = 0
        total = 0
        for sample_x in sample_xs:
            for sample_y in sample_ys:
                inside_component = (
                    component["min_x"] <= sample_x <= component["max_x"]
                    and component["min_y"] <= sample_y <= component["max_y"]
                )
                if inside_component:
                    continue
                clamped_x = min(max(sample_x, 0), width - 1)
                clamped_y = min(max(sample_y, 0), height - 1)
                total += 1
                hits += board_mask[(clamped_y * width) + clamped_x]
        return hits / max(total, 1) >= 0.25

    @staticmethod
    def _expand_component_box(
        *,
        min_x: int,
        min_y: int,
        max_x: int,
        max_y: int,
        image_width: int,
        image_height: int,
    ) -> dict[str, int]:
        box_width = max_x - min_x + 1
        box_height = max_y - min_y + 1
        pad_x = max(3, int(box_width * 0.12))
        pad_y = max(3, int(box_height * 0.12))
        return {
            "min_x": max(0, min_x - pad_x),
            "min_y": max(0, min_y - pad_y),
            "max_x": min(image_width - 1, max_x + pad_x),
            "max_y": min(image_height - 1, max_y + pad_y),
        }

    def _classify_component_candidates(
        self,
        candidates: list[dict[str, object]],
        image: Image.Image,
    ) -> list[dict[str, object]]:
        classifier = self._load_reference_component_classifier()
        if classifier is None:
            return candidates

        classified: list[dict[str, object]] = []
        for candidate in candidates:
            predicted_label, confidence = classifier.classify(image, candidate)
            enriched = dict(candidate)
            if predicted_label is not None:
                enriched["predicted_label"] = predicted_label
            if confidence is not None:
                enriched["classification_confidence"] = confidence
            classification_quality = self._classify_component_label_quality(predicted_label, confidence)
            if classification_quality is not None:
                enriched["label_quality"] = classification_quality
            if predicted_label is not None and classification_quality in {"accepted", "strong"}:
                enriched["label"] = predicted_label
            classified.append(enriched)
        return classified

    @staticmethod
    def _classify_component_label_quality(predicted_label: str | None, confidence: float | None) -> str | None:
        if predicted_label is None or confidence is None:
            return None
        threshold = REFERENCE_COMPONENT_LABEL_THRESHOLDS.get(predicted_label, 0.45)
        if confidence >= max(0.72, threshold + 0.15):
            return "strong"
        if confidence >= threshold:
            return "accepted"
        if confidence >= max(0.3, threshold - 0.08):
            return "suspect"
        return "rejected"

    def _load_reference_component_classifier(self) -> object | None:
        if self._component_classifier_loaded:
            return self._component_classifier
        self._component_classifier_loaded = True

        if not REFERENCE_COMPONENT_MODEL_PATH.exists():
            self._component_classifier = None
            return None
        if importlib.util.find_spec("torch") is None:
            self._component_classifier = None
            return None

        try:
            self._component_classifier = _ReferenceComponentClassifier(REFERENCE_COMPONENT_MODEL_PATH)
        except Exception:
            self._component_classifier = None
        return self._component_classifier

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


class _ReferenceComponentClassifier:
    def __init__(self, model_path: Path) -> None:
        import torch
        from torch import nn
        import torch.nn.functional as F

        self._torch = torch
        self._nn = nn
        self._F = F
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = self._build_model().to(self._device)
        state_dict = torch.load(model_path, map_location=self._device)
        self._model.load_state_dict(state_dict)
        self._model.eval()

    def _build_model(self):
        nn = self._nn
        F = self._F

        class NeuralNetwork(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.conv1 = nn.Conv2d(3, 6, 5)
                self.pool = nn.MaxPool2d(2, 2)
                self.conv2 = nn.Conv2d(6, 16, 5)
                self.fc1 = nn.Linear(16 * 5 * 5, 120)
                self.fc2 = nn.Linear(120, 84)
                self.fc3 = nn.Linear(84, len(REFERENCE_COMPONENT_LABELS))

            def forward(self, x):
                x = self.pool(F.relu(self.conv1(x)))
                x = self.pool(F.relu(self.conv2(x)))
                x = x.flatten(1)
                x = F.relu(self.fc1(x))
                x = F.relu(self.fc2(x))
                x = self.fc3(x)
                return x

        return NeuralNetwork()

    def classify(
        self,
        image: Image.Image,
        candidate: dict[str, object],
    ) -> tuple[str | None, float | None]:
        crop = self._crop_candidate(image, candidate)
        if crop is None:
            return None, None
        tensor = self._to_tensor(crop)
        with self._torch.no_grad():
            logits = self._model(tensor)
            probs = self._torch.softmax(logits, dim=1)
            conf_tensor, class_tensor = self._torch.max(probs, dim=1)
        confidence = round(float(conf_tensor.item()), 4)
        label = REFERENCE_COMPONENT_LABELS[int(class_tensor.item())]
        return label, confidence

    def _crop_candidate(self, image: Image.Image, candidate: dict[str, object]) -> Image.Image | None:
        width, height = image.size
        x = int(float(candidate["x"]) * width)
        y = int(float(candidate["y"]) * height)
        crop_width = max(1, int(float(candidate["width"]) * width))
        crop_height = max(1, int(float(candidate["height"]) * height))
        x2 = min(width, x + crop_width)
        y2 = min(height, y + crop_height)
        if x2 <= x or y2 <= y:
            return None
        return image.crop((x, y, x2, y2))

    def _to_tensor(self, crop: Image.Image):
        torch = self._torch
        crop = crop.convert("RGB")
        side = max(crop.size)
        square = Image.new("RGB", (side, side), color=(0, 0, 0))
        offset = ((side - crop.width) // 2, (side - crop.height) // 2)
        square.paste(crop, offset)
        resized = square.resize((32, 32), Image.Resampling.BILINEAR)
        data = torch.ByteTensor(bytearray(resized.tobytes())).float() / 255.0
        tensor = data.view(32, 32, 3).permute(2, 0, 1).unsqueeze(0)
        return tensor.to(self._device)
