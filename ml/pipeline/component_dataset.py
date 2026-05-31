"""Prepare a YOLOv8 component-detection seed dataset from ``pcb_wacv_2019``."""
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

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
DEFAULT_SOURCE_ROOT = Path(__file__).resolve().parents[2] / "docs" / "references" / "pcb_wacv_2019" / "pcb_wacv_2019"
DEFAULT_OUTPUT_ROOT = DATA_ROOT / "component_detection_seed"

COMPONENT_CLASSES = [
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
CLASS_TO_INDEX = {name: index for index, name in enumerate(COMPONENT_CLASSES)}

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
    ("emi filter", "emi_filter"),
    ("ferrite bead", "ferrite_bead"),
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


def _sanitize_label(raw_label: str) -> str:
    label = raw_label.strip().strip('"').lower()
    label = re.sub(r"\s+", " ", label)
    return label


def normalize_component_label(raw_label: str) -> str | None:
    label = _sanitize_label(raw_label)
    if not label:
        return None

    for alias, canonical in _ALIASES:
        if alias in label:
            return canonical

    if any(marker in label for marker in _EXCLUDE_MARKERS):
        return None

    return None


def _resolve_image_path(folder: Path, filename: str) -> Path:
    candidates = [folder / filename]
    stem = Path(filename).stem
    candidates.extend(folder.glob(f"{stem}.*"))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Image file referenced by XML not found: {folder / filename}")


def load_board_annotation(xml_path: Path) -> BoardAnnotation:
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
        class_name = normalize_component_label(obj.findtext("name", ""))
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


def _iter_board_annotations(source_root: Path) -> list[BoardAnnotation]:
    annotations: list[BoardAnnotation] = []
    for xml_path in sorted(source_root.glob("*/*.xml")):
        annotations.append(load_board_annotation(xml_path))
    if not annotations:
        raise FileNotFoundError(f"No XML annotations found under {source_root}")
    return annotations


def _yolo_line(box: BoundingBox, *, width: int, height: int) -> str:
    x_center = ((box.xmin + box.xmax) / 2.0) / width
    y_center = ((box.ymin + box.ymax) / 2.0) / height
    box_width = (box.xmax - box.xmin) / width
    box_height = (box.ymax - box.ymin) / height
    return (
        f"{CLASS_TO_INDEX[box.class_name]} "
        f"{x_center:.6f} {y_center:.6f} {box_width:.6f} {box_height:.6f}"
    )


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

    train_ids = set(ordered[:train_count])
    val_ids = set(ordered[train_count:train_count + val_count])
    test_ids = set(ordered[train_count + val_count:])
    return {"train": train_ids, "val": val_ids, "test": test_ids}


def _write_data_yaml(output_root: Path) -> None:
    lines = [
        f"path: {output_root.resolve()}",
        "train: train/images",
        "val: val/images",
        "test: test/images",
        "",
        f"nc: {len(COMPONENT_CLASSES)}",
        "names:",
    ]
    lines.extend(f"  {index}: {name}" for index, name in enumerate(COMPONENT_CLASSES))
    (output_root / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_component_dataset(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    seed: int = 42,
    overwrite: bool = False,
) -> dict[str, object]:
    annotations = _iter_board_annotations(source_root)
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
        split_name = next(
            split for split, board_ids in board_splits.items() if annotation.board_id in board_ids
        )
        boards_per_split[split_name].append(annotation.board_id)
        if not annotation.boxes:
            dropped_annotations += 1
            continue

        image_name = f"{annotation.board_id}__{annotation.image_path.name}"
        label_name = f"{annotation.board_id}__{annotation.image_path.stem}.txt"
        image_target = output_root / split_name / "images" / image_name
        label_target = output_root / split_name / "labels" / label_name
        shutil.copy2(annotation.image_path, image_target)
        yolo_lines = [_yolo_line(box, width=annotation.width, height=annotation.height) for box in annotation.boxes]
        label_target.write_text("\n".join(yolo_lines) + "\n", encoding="utf-8")

        split_image_counts[split_name] += 1
        split_box_counts[split_name] += len(annotation.boxes)
        for box in annotation.boxes:
            class_counts[box.class_name] += 1

    _write_data_yaml(output_root)
    manifest = {
        "source_root": str(source_root.resolve()),
        "seed": seed,
        "classes": COMPONENT_CLASSES,
        "split_image_counts": dict(split_image_counts),
        "split_box_counts": dict(split_box_counts),
        "class_counts": dict(sorted(class_counts.items())),
        "dropped_empty_boards": dropped_annotations,
        "boards_per_split": {key: sorted(set(value)) for key, value in boards_per_split.items()},
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert pcb_wacv_2019 into a YOLOv8 component dataset")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    manifest = build_component_dataset(
        source_root=args.source_root,
        output_root=args.output_root,
        seed=args.seed,
        overwrite=args.overwrite,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
