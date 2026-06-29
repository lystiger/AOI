"""Normalize a downloaded DsPCBSD+ dataset into the YOLOv8 layout training expects.

DsPCBSD+ (Nature Scientific Data, 2024; CC-BY-4.0) ships in YOLO format, but the exact
on-disk layout of a given download varies (flat ``images/``+``labels/``, per-split dirs,
or images and ``.txt`` side by side). This script discovers whatever layout is present
and writes a clean ``train/val/test`` + ``data.yaml`` tree at ``--output-root`` so the
existing pipeline can train directly:

    python -m ml.pipeline.dspcbsd_dataset --source-root <unzipped> --output-root ml/data/dspcbsd_plus --overwrite
    python -m ml.pipeline.component_train  --variant baseline --dataset-root ml/data/dspcbsd_plus

The dataset's own class order is preserved so the existing YOLO label indices stay valid.
Splits already present in the download are respected; a missing ``val``/``test`` is carved
from ``train``; a download with no splits at all is re-split deterministically.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
from collections import Counter
from pathlib import Path

from ml.pipeline.component_dataset import _load_yolo_names, _write_data_yaml
from ml.pipeline.reporting import write_run_report

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
DEFAULT_OUTPUT_ROOT = DATA_ROOT / "dspcbsd_plus"

# Fallback class order from the DsPCBSD+ paper, used ONLY when the download carries no
# class metadata. If this path is taken, VERIFY the order against the dataset before trust.
DOCUMENTED_CLASSES = [
    "short",
    "spur",
    "spurious_copper",
    "open",
    "mouse_bite",
    "hole_breakout",
    "conductor_scratch",
    "conductor_foreign_object",
    "base_material_foreign_object",
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
CONVERT_EXTS = {".bmp", ".tif", ".tiff"}  # converted to .png so the trainer can read them
SPLIT_ALIASES = {"train": "train", "training": "train", "valid": "val", "val": "val", "test": "test"}
CLASS_FILE_NAMES = ("classes.txt", "obj.names", "names.txt")


def _discover_class_names(source_root: Path) -> list[str] | None:
    """Read the dataset's own class names (authoritative ordering) if any exist."""
    for yaml_path in sorted(source_root.rglob("*.yaml")) + sorted(source_root.rglob("*.yml")):
        try:
            names = _load_yolo_names(yaml_path)
        except (ValueError, OSError):
            continue
        if names:
            print(f"Class names from {yaml_path.relative_to(source_root)}: {names}")
            return names
    for class_file in CLASS_FILE_NAMES:
        for path in sorted(source_root.rglob(class_file)):
            names = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if names:
                print(f"Class names from {path.relative_to(source_root)}: {names}")
                return names
    return None


def _split_for_path(image_path: Path, source_root: Path) -> str | None:
    for part in (segment.lower() for segment in image_path.relative_to(source_root).parts):
        if part in SPLIT_ALIASES:
            return SPLIT_ALIASES[part]
    return None


def _label_for_image(image_path: Path) -> Path | None:
    sibling = image_path.with_suffix(".txt")
    if sibling.exists():
        return sibling
    parts = list(image_path.parts)
    for index in range(len(parts) - 1, -1, -1):
        if parts[index].lower() == "images":
            parts[index] = "labels"
            candidate = Path(*parts).with_suffix(".txt")
            return candidate if candidate.exists() else None
    return None


def _carve(items: list, ratio: float, seed: int) -> tuple[list, list]:
    """Return (remaining, carved) — a deterministic ``ratio`` slice carved off ``items``."""
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    count = max(1, int(len(shuffled) * ratio)) if shuffled else 0
    return shuffled[count:], shuffled[:count]


def _resplit(items: list, *, seed: int, val_ratio: float, test_ratio: float) -> dict[str, list]:
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    total = len(shuffled)
    n_test = max(1, int(total * test_ratio)) if total >= 3 else 0
    n_val = max(1, int(total * val_ratio)) if total >= 3 else 0
    return {
        "test": shuffled[:n_test],
        "val": shuffled[n_test:n_test + n_val],
        "train": shuffled[n_test + n_val:],
    }


def build_dspcbsd_dataset(
    *,
    source_root: Path,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    seed: int = 42,
    val_ratio: float = 0.1,
    overwrite: bool = False,
) -> dict[str, object]:
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if not source_root.exists():
        raise FileNotFoundError(f"Source dataset not found: {source_root}")

    class_names = _discover_class_names(source_root)
    if class_names is None:
        print("WARNING: no class metadata found in download; using documented DsPCBSD+ order.")
        print("         VERIFY label indices match this order before trusting the model.")
        class_names = list(DOCUMENTED_CLASSES)

    buckets: dict[str | None, list[tuple[Path, Path | None]]] = {"train": [], "val": [], "test": [], None: []}
    for image in source_root.rglob("*"):
        if not image.is_file() or image.suffix.lower() not in IMAGE_EXTS | CONVERT_EXTS:
            continue
        if output_root in image.resolve().parents:
            continue  # skip a previous output if nested under the source
        split = _split_for_path(image, source_root)
        buckets[split if split in ("train", "val", "test") else None].append((image, _label_for_image(image)))

    total_found = sum(len(v) for v in buckets.values())
    if total_found == 0:
        raise FileNotFoundError(f"No images found under {source_root}")

    if any(buckets[split] for split in ("train", "val", "test")):
        train, val, test = buckets["train"] + buckets[None], buckets["val"], buckets["test"]
        if not val and train:
            train, val = _carve(train, val_ratio, seed)
        if not test and train:
            train, test = _carve(train, val_ratio, seed + 1)
        splits = {"train": train, "val": val, "test": test}
    else:
        splits = _resplit(buckets[None], seed=seed, val_ratio=val_ratio, test_ratio=val_ratio)

    if output_root.exists():
        if not overwrite:
            raise FileExistsError(f"Output directory already exists: {output_root} (pass --overwrite)")
        shutil.rmtree(output_root)
    for split in ("train", "val", "test"):
        (output_root / split / "images").mkdir(parents=True, exist_ok=True)
        (output_root / split / "labels").mkdir(parents=True, exist_ok=True)

    split_image_counts: Counter[str] = Counter()
    split_box_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    negatives: Counter[str] = Counter()
    missing_labels = 0

    for split, items in splits.items():
        used_stems: set[str] = set()
        for image, label in items:
            stem, suffix = image.stem, 1
            while stem in used_stems:
                stem = f"{image.stem}_dup{suffix}"
                suffix += 1
            used_stems.add(stem)

            if image.suffix.lower() in CONVERT_EXTS:
                from PIL import Image

                out_image = output_root / split / "images" / f"{stem}.png"
                with Image.open(image) as handle:
                    handle.convert("RGB").save(out_image)
            else:
                out_image = output_root / split / "images" / f"{stem}{image.suffix.lower()}"
                shutil.copy2(image, out_image)

            out_label = output_root / split / "labels" / f"{stem}.txt"
            text = label.read_text(encoding="utf-8") if label and label.exists() else ""
            if not (label and label.exists()):
                missing_labels += 1
            out_label.write_text(text if text.endswith("\n") or not text else text + "\n", encoding="utf-8")

            if not text.strip():
                negatives[split] += 1
            for line in text.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0].lstrip("-").isdigit():
                    index = int(parts[0])
                    split_box_counts[split] += 1
                    name = class_names[index] if 0 <= index < len(class_names) else f"class_{index}"
                    class_counts[name] += 1
            split_image_counts[split] += 1

    _write_data_yaml(output_root, class_names)
    manifest = {
        "source_root": str(source_root),
        "output_root": str(output_root),
        "seed": seed,
        "classes": class_names,
        "split_image_counts": dict(split_image_counts),
        "split_box_counts": dict(split_box_counts),
        "class_counts": dict(sorted(class_counts.items())),
        "negative_images": dict(negatives),
        "images_missing_labels": missing_labels,
    }
    report_path = write_run_report(
        category="defect_detection",
        stage="dataset",
        title="DsPCBSD+ Dataset Build",
        summary=f"Normalized DsPCBSD+ into YOLOv8 layout at `{output_root}`.",
        details=[
            f"Source: `{source_root}`",
            f"Classes ({len(class_names)}): {', '.join(class_names)}",
            f"Split images: {dict(split_image_counts)}",
            f"Split boxes: {dict(split_box_counts)}",
            f"Negative (defect-free) images: {dict(negatives)}",
            f"Images missing a label file: {missing_labels}",
        ],
    )
    manifest["report_path"] = str(report_path)
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize DsPCBSD+ into the YOLOv8 training layout")
    parser.add_argument("--source-root", type=Path, required=True, help="Path to the unzipped DsPCBSD+ download")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Fraction carved for val/test when absent")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    manifest = build_dspcbsd_dataset(
        source_root=args.source_root,
        output_root=args.output_root,
        seed=args.seed,
        val_ratio=args.val_ratio,
        overwrite=args.overwrite,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
