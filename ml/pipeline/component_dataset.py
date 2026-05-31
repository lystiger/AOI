"""Prepare YOLOv8 component-detection seed datasets from reference PCB datasets."""
from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from ml.pipeline.reporting import write_run_report

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
DEFAULT_SOURCE_ROOT = Path(__file__).resolve().parents[2] / "docs" / "references" / "pcb_wacv_2019" / "pcb_wacv_2019"
DEFAULT_ROBOFLOW_SOURCE_ROOT = (
    Path(__file__).resolve().parents[2] / "docs" / "references" / "roboflow_printed_circuit_board_v4_yolov8"
)
DEFAULT_OUTPUT_ROOT = DATA_ROOT / "component_detection_seed"
DEFAULT_PROFILE = "reduced"
DEFAULT_SOURCE_FORMAT = "wacv_xml"

FULL_COMPONENT_CLASSES = [
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
]
REDUCED_COMPONENT_CLASSES = [
    "resistor",
    "capacitor",
    "connector",
    "ic",
    "led",
    "other",
]
CLASS_PROFILES = {
    "full": FULL_COMPONENT_CLASSES,
    "reduced": REDUCED_COMPONENT_CLASSES,
}
SOURCE_FORMATS = ("wacv_xml", "roboflow_yolo")

_EXCLUDE_MARKERS = (
    "text",
    "component text",
    "test point",
    "test",
    "pins",
    "pads",
    "unknown",
    "unlabeled",
)

_ALIASES = (
    ("electrolytic capacitor", "capacitor"),
    ("capacitor jumper", "capacitor"),
    ("emi filter", "emi_filter"),
    ("ferrite bead", "ferrite_bead"),
    ("resistor network", "resistor"),
    ("resistor jumper", "resistor"),
    ("zener", "diode"),
    ("switch", "button"),
    ("button", "button"),
    ("connector", "connector"),
    ("jumper", "jumper"),
    ("resistor", "resistor"),
    ("capacitor", "capacitor"),
    ("inductor", "inductor"),
    ("diode", "diode"),
    ("led", "led"),
    ("ic", "ic"),
    ("transistor", "transistor"),
    ("clock", "clock"),
    ("transformer", "transformer"),
    ("potentiometer", "potentiometer"),
    ("heatsink", "heatsink"),
    ("fuse", "fuse"),
    ("buzzer", "buzzer"),
    ("display", "display"),
    ("battery", "battery"),
)


@dataclass(slots=True)
class BoundingBox:
    class_name: str
    xmin: int
    ymin: int
    xmax: int
    ymax: int


@dataclass(slots=True)
class BoardAnnotation:
    board_id: str
    image_path: Path
    width: int
    height: int
    boxes: list[BoundingBox]


def get_component_classes(profile: str = DEFAULT_PROFILE) -> list[str]:
    try:
        return CLASS_PROFILES[profile]
    except KeyError as exc:
        raise ValueError(f"Unsupported class profile: {profile}") from exc


def _sanitize_label(raw_label: str) -> str:
    label = raw_label.strip().strip('"').lower()
    label = label.replace("_", " ")
    label = re.sub(r"\s+", " ", label)
    return label


def _canonical_component_label(raw_label: str) -> str | None:
    label = _sanitize_label(raw_label)
    if not label:
        return None
    for alias, canonical in _ALIASES:
        if alias in label:
            return canonical
    if any(marker in label for marker in _EXCLUDE_MARKERS):
        return None
    return None


def normalize_component_label(raw_label: str, *, profile: str = DEFAULT_PROFILE) -> str | None:
    canonical = _canonical_component_label(raw_label)
    if canonical is None:
        return None
    classes = get_component_classes(profile)
    if canonical in classes:
        return canonical
    return "other" if "other" in classes else None


def _resolve_image_path(folder: Path, filename: str) -> Path:
    candidates = [folder / filename]
    stem = Path(filename).stem
    candidates.extend(folder.glob(f"{stem}.*"))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Image file referenced by XML not found: {folder / filename}")


def load_board_annotation(xml_path: Path, *, profile: str = DEFAULT_PROFILE) -> BoardAnnotation:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    filename = root.findtext("filename")
    width = int(root.findtext("size/width", "0"))
    height = int(root.findtext("size/height", "0"))
    if not filename or width <= 0 or height <= 0:
        raise ValueError(f"Invalid annotation metadata in {xml_path}")

    image_path = _resolve_image_path(xml_path.parent, filename)
    boxes: list[BoundingBox] = []
    for obj in root.findall("object"):
        class_name = normalize_component_label(obj.findtext("name", ""), profile=profile)
        if class_name is None:
            continue
        box = obj.find("bndbox")
        if box is None:
            continue
        xmin = int(float(box.findtext("xmin", "0")))
        ymin = int(float(box.findtext("ymin", "0")))
        xmax = int(float(box.findtext("xmax", "0")))
        ymax = int(float(box.findtext("ymax", "0")))
        if xmax <= xmin or ymax <= ymin:
            continue
        boxes.append(BoundingBox(class_name, xmin, ymin, xmax, ymax))

    return BoardAnnotation(
        board_id=xml_path.parent.name,
        image_path=image_path,
        width=width,
        height=height,
        boxes=boxes,
    )


def _iter_board_annotations(source_root: Path, *, profile: str) -> list[BoardAnnotation]:
    annotations = [load_board_annotation(xml_path, profile=profile) for xml_path in sorted(source_root.glob("*/*.xml"))]
    if not annotations:
        raise FileNotFoundError(f"No XML annotations found under {source_root}")
    return annotations


def _load_yolo_names(data_yaml: Path) -> list[str]:
    names: dict[int, str] = {}
    in_names = False
    for line in data_yaml.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "names:":
            in_names = True
            continue
        if not in_names:
            continue
        if not stripped:
            break
        if stripped.startswith("- "):
            names[len(names)] = stripped[2:].strip().strip("'\"")
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        if key.strip().isdigit():
            names[int(key.strip())] = value.strip().strip("'\"")
    if names:
        return [names[index] for index in sorted(names)]

    match = re.search(r"names:\s*\[(.*)\]", data_yaml.read_text(encoding="utf-8"), re.DOTALL)
    if not match:
        raise ValueError(f"Unable to parse class names from {data_yaml}")
    raw = match.group(1)
    return [item.strip().strip("'\"") for item in raw.split(",") if item.strip()]


def _load_roboflow_board_annotations(source_root: Path, *, profile: str) -> list[BoardAnnotation]:
    data_yaml = source_root / "data.yaml"
    if not data_yaml.exists():
        raise FileNotFoundError(f"Roboflow dataset metadata not found at {data_yaml}")
    source_names = _load_yolo_names(data_yaml)

    annotations: list[BoardAnnotation] = []
    for split_name in ("train", "val", "test"):
        image_dir = source_root / split_name / "images"
        label_dir = source_root / split_name / "labels"
        if not image_dir.exists() or not label_dir.exists():
            continue

        for image_path in sorted(path for path in image_dir.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}):
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                continue

            width, height = _read_image_size(image_path)
            boxes: list[BoundingBox] = []
            for line in label_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                parts = stripped.split()
                if len(parts) != 5:
                    continue
                try:
                    class_index = int(parts[0])
                    x_center, y_center, box_width, box_height = (float(value) for value in parts[1:])
                except ValueError:
                    continue
                if not (0 <= class_index < len(source_names)):
                    continue

                class_name = normalize_component_label(source_names[class_index], profile=profile)
                if class_name is None:
                    continue

                xmin, ymin, xmax, ymax = _denormalize_yolo_box(
                    x_center=x_center,
                    y_center=y_center,
                    box_width=box_width,
                    box_height=box_height,
                    width=width,
                    height=height,
                )
                if xmax <= xmin or ymax <= ymin:
                    continue
                boxes.append(BoundingBox(class_name, xmin, ymin, xmax, ymax))

            board_id = _roboflow_board_id_from_name(image_path.stem)
            annotations.append(
                BoardAnnotation(
                    board_id=board_id,
                    image_path=image_path,
                    width=width,
                    height=height,
                    boxes=boxes,
                )
            )

    if not annotations:
        raise FileNotFoundError(f"No YOLO annotations found under {source_root}")
    return annotations


def _roboflow_board_id_from_name(stem: str) -> str:
    board_id = stem.split(".rf.", 1)[0]
    board_id = re.sub(r"(?i)(?:_(?:jpg|jpeg|png))+$", "", board_id)
    return board_id


def _read_image_size(image_path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(image_path) as image:
        return image.size


def _denormalize_yolo_box(
    *,
    x_center: float,
    y_center: float,
    box_width: float,
    box_height: float,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    xmin = max(0, int(round((x_center - box_width / 2.0) * width)))
    ymin = max(0, int(round((y_center - box_height / 2.0) * height)))
    xmax = min(width, int(round((x_center + box_width / 2.0) * width)))
    ymax = min(height, int(round((y_center + box_height / 2.0) * height)))
    return xmin, ymin, xmax, ymax


def _load_annotations(source_root: Path, *, source_format: str, profile: str) -> list[BoardAnnotation]:
    if source_format == "wacv_xml":
        return _iter_board_annotations(source_root, profile=profile)
    if source_format == "roboflow_yolo":
        return _load_roboflow_board_annotations(source_root, profile=profile)
    raise ValueError(f"Unsupported source format: {source_format}")


def _yolo_line(box: BoundingBox, *, width: int, height: int, class_to_index: dict[str, int]) -> str:
    x_center = ((box.xmin + box.xmax) / 2.0) / width
    y_center = ((box.ymin + box.ymax) / 2.0) / height
    box_width = (box.xmax - box.xmin) / width
    box_height = (box.ymax - box.ymin) / height
    return f"{class_to_index[box.class_name]} {x_center:.6f} {y_center:.6f} {box_width:.6f} {box_height:.6f}"


def split_boards(
    board_ids: list[str],
    *,
    seed: int = 42,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> dict[str, set[str]]:
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    if not 0 <= val_ratio < 1:
        raise ValueError("val_ratio must be between 0 and 1")
    if train_ratio + val_ratio >= 1:
        raise ValueError("train_ratio + val_ratio must be less than 1")

    ordered = sorted(set(board_ids))
    rng = random.Random(seed)
    rng.shuffle(ordered)

    total = len(ordered)
    train_count = max(1, round(total * train_ratio))
    val_count = max(1, round(total * val_ratio)) if total >= 3 else max(0, total - train_count)
    if train_count + val_count >= total:
        val_count = max(0, total - train_count - 1)
    test_count = total - train_count - val_count
    if test_count <= 0 and total >= 2:
        test_count = 1
        if val_count > 1:
            val_count -= 1
        elif train_count > 1:
            train_count -= 1

    return {
        "train": set(ordered[:train_count]),
        "val": set(ordered[train_count:train_count + val_count]),
        "test": set(ordered[train_count + val_count:]),
    }


def _write_data_yaml(output_root: Path, classes: list[str]) -> None:
    lines = [
        f"path: {output_root.resolve()}",
        "train: train/images",
        "val: val/images",
        "test: test/images",
        "",
        f"nc: {len(classes)}",
        "names:",
    ]
    lines.extend(f"  {index}: {name}" for index, name in enumerate(classes))
    (output_root / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_component_class_names(dataset_root: Path | None = None) -> list[str]:
    root = dataset_root or DEFAULT_OUTPUT_ROOT
    data_yaml = root / "data.yaml"
    if not data_yaml.exists():
        raise FileNotFoundError(f"No data.yaml found at {data_yaml}")

    names: dict[int, str] = {}
    for line in data_yaml.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if ":" in stripped and stripped.split(":", 1)[0].isdigit():
            key, value = stripped.split(":", 1)
            names[int(key)] = value.strip().strip("'\"")
    return [names[index] for index in sorted(names)]


def build_component_dataset(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    source_format: str = DEFAULT_SOURCE_FORMAT,
    profile: str = DEFAULT_PROFILE,
    seed: int = 42,
    overwrite: bool = False,
) -> dict[str, object]:
    classes = get_component_classes(profile)
    class_to_index = {name: index for index, name in enumerate(classes)}
    annotations = _load_annotations(source_root, source_format=source_format, profile=profile)
    board_splits = split_boards([annotation.board_id for annotation in annotations], seed=seed)

    if output_root.exists():
        if not overwrite:
            raise FileExistsError(f"Output directory already exists: {output_root}")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    split_image_counts: Counter[str] = Counter()
    split_box_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    dropped_annotations = 0
    boards_per_split: dict[str, list[str]] = defaultdict(list)

    for split_name in ("train", "val", "test"):
        (output_root / split_name / "images").mkdir(parents=True, exist_ok=True)
        (output_root / split_name / "labels").mkdir(parents=True, exist_ok=True)

    for annotation in annotations:
        split_name = next(split for split, board_ids in board_splits.items() if annotation.board_id in board_ids)
        boards_per_split[split_name].append(annotation.board_id)
        if not annotation.boxes:
            dropped_annotations += 1
            continue

        image_name = f"{annotation.board_id}__{annotation.image_path.name}"
        label_name = f"{annotation.board_id}__{annotation.image_path.stem}.txt"
        image_target = output_root / split_name / "images" / image_name
        label_target = output_root / split_name / "labels" / label_name
        shutil.copy2(annotation.image_path, image_target)
        yolo_lines = [
            _yolo_line(box, width=annotation.width, height=annotation.height, class_to_index=class_to_index)
            for box in annotation.boxes
        ]
        label_target.write_text("\n".join(yolo_lines) + "\n", encoding="utf-8")

        split_image_counts[split_name] += 1
        split_box_counts[split_name] += len(annotation.boxes)
        for box in annotation.boxes:
            class_counts[box.class_name] += 1

    _write_data_yaml(output_root, classes)
    manifest = {
        "source_root": str(source_root.resolve()),
        "source_format": source_format,
        "profile": profile,
        "seed": seed,
        "classes": classes,
        "split_image_counts": dict(split_image_counts),
        "split_box_counts": dict(split_box_counts),
        "class_counts": dict(sorted(class_counts.items())),
        "dropped_empty_boards": dropped_annotations,
        "boards_per_split": {key: sorted(set(value)) for key, value in boards_per_split.items()},
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report_path = write_run_report(
        category="component_detection",
        stage="dataset",
        title=f"Component Dataset Build ({profile})",
        summary=f"Built {profile} component seed dataset at `{output_root}`.",
        details=[
            f"Source format: `{source_format}`",
            f"Classes: {', '.join(classes)}",
            f"Split images: {dict(split_image_counts)}",
            f"Split boxes: {dict(split_box_counts)}",
            f"Dropped empty boards: {dropped_annotations}",
        ],
    )
    manifest["report_path"] = str(report_path)
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert reference PCB datasets into a YOLOv8 component dataset")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--source-format", choices=SOURCE_FORMATS, default=DEFAULT_SOURCE_FORMAT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--profile", choices=sorted(CLASS_PROFILES), default=DEFAULT_PROFILE)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    manifest = build_component_dataset(
        source_root=args.source_root,
        output_root=args.output_root,
        source_format=args.source_format,
        profile=args.profile,
        seed=args.seed,
        overwrite=args.overwrite,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
