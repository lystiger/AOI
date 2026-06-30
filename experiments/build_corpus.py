"""Build the real-image evaluation corpus for the AOI anomaly scenarios.

Derives four image pools from the normalized DsPCBSD+ dataset:

- ``defective/`` : real defect boards (the all-defective DsPCBSD+ test split) -> FAIL events
- ``good/``      : in-distribution defect-FREE crops (regions of test images with no
                   defect annotation) -> PASS events. DsPCBSD+ has no clean boards, so we
                   carve defect-free windows out of real boards instead.
- ``degraded/``  : blurred / noisy / downscaled copies of the DEFECTIVE boards -> drives
                   the S04 confidence-drop scenario: the model still finds the defect but
                   at genuinely lower confidence (degrading clean boards gives no detection
                   to drop, so we degrade defective boards instead)
- ``corrupt/``   : truncated / empty / garbage files -> drives the S06 board-failure path

``showcase/`` is left for the user's own (assembled) boards, used only for qualitative
out-of-distribution captures in the thesis, never for metrics.
"""
from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[1] / "ml" / "data" / "dspcbsd_plus"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "ml" / "data" / "corpus"


def _iter_defect_boxes(label_path: Path) -> list[tuple[float, float, float, float]]:
    """Return normalized (x1, y1, x2, y2) defect boxes from a YOLO label file."""
    boxes: list[tuple[float, float, float, float]] = []
    if not label_path.exists():
        return boxes
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            xc, yc, w, h = (float(v) for v in parts[1:5])
        except ValueError:
            continue
        boxes.append((xc - w / 2, yc - h / 2, xc + w / 2, yc + h / 2))
    return boxes


def _window_is_clear(
    window: tuple[float, float, float, float],
    boxes: list[tuple[float, float, float, float]],
    margin: float,
) -> bool:
    wx1, wy1, wx2, wy2 = window
    for bx1, by1, bx2, by2 in boxes:
        if not (wx2 < bx1 - margin or wx1 > bx2 + margin or wy2 < by1 - margin or wy1 > by2 + margin):
            return False
    return True


def build_defective(test_images: Path, out_dir: Path, count: int, rng: random.Random) -> int:
    images = sorted(p for p in test_images.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    rng.shuffle(images)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for image in images[:count]:
        shutil.copy2(image, out_dir / image.name)
        written += 1
    return written


def build_good_crops(
    test_images: Path,
    test_labels: Path,
    out_dir: Path,
    count: int,
    rng: random.Random,
    crop_frac: float = 0.35,
    margin: float = 0.02,
    tries_per_image: int = 12,
) -> int:
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    images = sorted(p for p in test_images.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    rng.shuffle(images)
    written = 0
    for image in images:
        if written >= count:
            break
        boxes = _iter_defect_boxes(test_labels / f"{image.stem}.txt")
        placed = False
        for _ in range(tries_per_image):
            x1 = rng.uniform(0.0, 1.0 - crop_frac)
            y1 = rng.uniform(0.0, 1.0 - crop_frac)
            window = (x1, y1, x1 + crop_frac, y1 + crop_frac)
            if not _window_is_clear(window, boxes, margin):
                continue
            with Image.open(image) as handle:
                w, h = handle.size
                box_px = (int(x1 * w), int(y1 * h), int((x1 + crop_frac) * w), int((y1 + crop_frac) * h))
                handle.crop(box_px).save(out_dir / f"good_{image.stem}.jpg")
            written += 1
            placed = True
            break
        if not placed:
            continue
    return written


def build_degraded(good_dir: Path, out_dir: Path, rng: random.Random) -> int:
    import numpy as np
    from PIL import Image, ImageFilter

    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for image_path in sorted(good_dir.glob("*.jpg")):
        with Image.open(image_path) as handle:
            base = handle.convert("RGB")
            w, h = base.size

            base.filter(ImageFilter.GaussianBlur(radius=3.5)).save(out_dir / f"blur_{image_path.stem}.jpg")

            arr = np.asarray(base).astype("float32")
            noise_rng = np.random.default_rng(rng.randrange(2**32))
            noisy = np.clip(arr + noise_rng.normal(0, 22, arr.shape), 0, 255).astype("uint8")
            Image.fromarray(noisy).save(out_dir / f"noise_{image_path.stem}.jpg")

            small = base.resize((max(1, w // 4), max(1, h // 4))).resize((w, h))
            small.save(out_dir / f"small_{image_path.stem}.jpg")
        written += 3
    return written


def build_corrupt(reference_dir: Path, out_dir: Path, count: int = 8) -> int:
    """Write a variety of unreadable image files so the board-failure pool isn't 3 points."""
    import os

    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0

    def emit(name: str, data: bytes) -> None:
        nonlocal written
        (out_dir / name).write_bytes(data)
        written += 1

    emit("empty.jpg", b"")                        # zero bytes
    emit("onebyte.jpg", b"\xff")                  # single byte
    emit("header_only.jpg", b"\xff\xd8\xff\xe0")  # JPEG markers, no image data
    for i in range(2):
        emit(f"garbage_{i + 1}.jpg", os.urandom(800))  # random non-image bytes

    refs = sorted(reference_dir.glob("*.jpg"))
    for i, ref in enumerate(refs[: max(0, count - written)]):
        data = ref.read_bytes()
        emit(f"truncated_{i + 1}.jpg", data[: max(1, len(data) // (6 + i))])

    return written


def build_corpus(
    *,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    out: Path = DEFAULT_OUT,
    n_defective: int = 60,
    n_good: int = 60,
    seed: int = 42,
    overwrite: bool = False,
) -> dict[str, int]:
    test_images = dataset_root / "test" / "images"
    test_labels = dataset_root / "test" / "labels"
    if not test_images.exists():
        raise FileNotFoundError(
            f"Test images not found at {test_images}. Build the dataset first:\n"
            "  python -m ml.pipeline.dspcbsd_dataset --source-root <raw> --output-root ml/data/dspcbsd_plus --overwrite"
        )

    if out.exists():
        if not overwrite:
            raise FileExistsError(f"Corpus already exists: {out} (pass --overwrite)")
        shutil.rmtree(out)

    rng = random.Random(seed)
    counts = {
        "defective": build_defective(test_images, out / "defective", n_defective, rng),
        "good": build_good_crops(test_images, test_labels, out / "good", n_good, rng),
    }
    counts["degraded"] = build_degraded(out / "defective", out / "degraded", rng)
    counts["corrupt"] = build_corrupt(out / "defective", out / "corrupt")

    showcase = out / "showcase"
    showcase.mkdir(parents=True, exist_ok=True)
    (showcase / "README.txt").write_text(
        "Drop your own (assembled) PCB photos here for qualitative out-of-distribution\n"
        "captures only. The model was trained on bare-copper boards, so it over-triggers\n"
        "on populated boards; do not use these for PASS/metrics.\n",
        encoding="utf-8",
    )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the real-image evaluation corpus from DsPCBSD+")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--n-defective", type=int, default=60)
    parser.add_argument("--n-good", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    counts = build_corpus(
        dataset_root=args.dataset_root,
        out=args.out,
        n_defective=args.n_defective,
        n_good=args.n_good,
        seed=args.seed,
        overwrite=args.overwrite,
    )
    print("Corpus built at", args.out)
    for name, value in counts.items():
        print(f"  {name}: {value}")


if __name__ == "__main__":
    main()
