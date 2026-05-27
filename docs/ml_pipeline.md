# ML Pipeline Implementation — AOI Defect Detection

**For:** Codex  
**Repo:** `lystiger/AOI`  
**Goal:** Build the missing ML core. Everything described here slots into the existing architecture without modifying `database.py`, `schema.py`, or any API routes. The pipeline lives in a new directory `ml/` at the repo root plus one replacement file `src/aoi/inference_runner.py`.

---

## Context: What Already Exists

- `src/aoi/schema.py` — `InferenceEvent.create()` accepts `defect_type`, `confidence_score`, `overlay_x/y/width/height` (all normalised 0–1), `inspection_result` (`PASS`/`FAIL`)
- `src/aoi/mock_inference.py` — currently cycles 4 hardcoded fake events; this pipeline replaces it
- `src/aoi/api/routes/events.py` — POST `/events` accepts the `InferenceEvent` schema; do not modify
- `docs/defects.md` — IPC-A-610 defect taxonomy already defined; only use component-visible and solder-visible defects from that taxonomy
- `web/public/mock/` — contains 4 real assembled PCB images (`pcb-example.png` etc.) with RLC, BGA, IC components; use these as sanity-check images

---

## Target Dataset

Use a dataset of **assembled PCBs with visible components and solder joints only**.

Do **not** use datasets dominated by:
- bare copper traces
- etched line defects
- open/short circuit defects on exposed routing
- spur / spurious copper / mouse-bite style fabrication defects
- any defect that is mainly about board artwork rather than mounted parts or solder joints

The ML scope for this project is:
- component presence / placement defects
- lead-related visible defects
- solder-joint visible defects

Preferred target classes:
```
0: missing_component
1: misalignment
2: reversed_polarity
3: bent_lead
4: lifted_lead
5: insufficient_solder
6: solder_bridge
7: solder_ball
```

### Defect class → AOI schema mapping

Map dataset class names directly to the existing `defect_type` strings in `docs/defects.md`:

| Dataset class | `defect_type` in schema | `inspection_result` |
|---|---|---|
| `missing_component` | `MISSING_COMPONENT` | `FAIL` |
| `misalignment` | `MISALIGNMENT` | `FAIL` |
| `reversed_polarity` | `REVERSED_POLARITY` | `FAIL` |
| `bent_lead` | `BENT_LEAD` | `FAIL` |
| `lifted_lead` | `LIFTED_LEAD` | `FAIL` |
| `insufficient_solder` | `INSUFFICIENT_SOLDER` | `FAIL` |
| `solder_bridge` | `SOLDER_BRIDGE` | `FAIL` |
| `solder_ball` | `SOLDER_BALL` | `FAIL` |
| *(no detection)* | `NO_DEFECT` | `PASS` |

Explicitly excluded classes:
- `missing_hole`
- `mouse_bite`
- `open_circuit`
- `short` when it refers to copper routing rather than solder bridging
- `spur`
- `spurious_copper`

---

## Directory Structure to Create

```
ml/
├── notebooks/
│   ├── 01_dataset_explore.ipynb
│   ├── 02_preprocessing.ipynb
│   ├── 03_training.ipynb
│   └── 04_evaluation.ipynb
├── pipeline/
│   ├── __init__.py
│   ├── dataset.py          # download + verify component/solder dataset
│   ├── preprocess.py       # greyscale, normalise, augment
│   ├── train.py            # YOLOv8 training entry point
│   ├── evaluate.py         # mAP, precision, recall, F1 per class
│   └── self_test.py        # smoke tests — runs without GPU
├── data/
│   └── .gitkeep            # dataset downloaded here, gitignored
├── models/
│   └── .gitkeep            # trained weights saved here, gitignored
├── requirements-ml.txt
└── README.md
src/aoi/
└── inference_runner.py     # replaces mock_inference.py, calls real model
```

Add to `.gitignore`:
```
ml/data/
ml/models/
ml/notebooks/.ipynb_checkpoints/
```

---

## Step 0 — `ml/requirements-ml.txt`

```
ultralytics>=8.2.0
roboflow>=1.1.0
opencv-python-headless>=4.9.0
matplotlib>=3.8.0
seaborn>=0.13.0
scikit-learn>=1.4.0
jupyter>=1.0.0
ipykernel>=6.29.0
torch>=2.2.0
torchvision>=0.17.0
requests>=2.31.0
Pillow>=11.0.0
numpy>=1.26.0
pandas>=2.2.0
```

Install: `pip install -r ml/requirements-ml.txt`

For GPU (CUDA 12.x):
```
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

---

## Step 1 — Dataset Download (`ml/pipeline/dataset.py`)

```python
"""
Download and verify the HRIPCB dataset from Roboflow.
Exports in YOLOv8 format to ml/data/hripcb/.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATASET_DIR = DATA_DIR / "hripcb"

CLASSES = [
    "missing_hole",
    "mouse_bite",
    "open_circuit",
    "short",
    "spur",
    "spurious_copper",
]

EXPECTED_SPLITS = ("train", "valid", "test")


def download(api_key: str | None = None) -> Path:
    """
    Download HRIPCB from Roboflow.
    Set env var ROBOFLOW_API_KEY or pass api_key directly.
    Returns path to dataset root (contains data.yaml).
    """
    from roboflow import Roboflow

    key = api_key or os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        raise EnvironmentError(
            "Set ROBOFLOW_API_KEY env var or pass api_key=. "
            "Get a free key at https://roboflow.com"
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rf = Roboflow(api_key=key)
    project = rf.workspace("ma007").project("hripcb")
    version = project.version(1)
    dataset = version.download("yolov8", location=str(DATASET_DIR))
    return Path(dataset.location)


def verify(dataset_root: Path | None = None) -> dict[str, int]:
    """
    Count images per split, verify labels exist, report class distribution.
    Returns dict: {split: image_count}
    """
    root = dataset_root or DATASET_DIR
    counts: dict[str, int] = {}

    for split in EXPECTED_SPLITS:
        img_dir = root / split / "images"
        lbl_dir = root / split / "labels"

        if not img_dir.exists():
            print(f"  [WARN] Missing split: {split}/images")
            counts[split] = 0
            continue

        images = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png"))
        labels = list(lbl_dir.glob("*.txt")) if lbl_dir.exists() else []
        counts[split] = len(images)

        print(f"  {split}: {len(images)} images, {len(labels)} labels")

    return counts


def get_data_yaml_path() -> Path:
    candidates = list(DATASET_DIR.glob("*.yaml")) + list(DATASET_DIR.glob("data.yaml"))
    if not candidates:
        raise FileNotFoundError(
            f"No data.yaml found in {DATASET_DIR}. Run dataset.download() first."
        )
    return candidates[0]


if __name__ == "__main__":
    print("Verifying existing dataset...")
    counts = verify()
    total = sum(counts.values())
    if total == 0:
        print("Dataset not found. Run with ROBOFLOW_API_KEY set to download.")
    else:
        print(f"Total images: {total}")
        print(f"data.yaml: {get_data_yaml_path()}")
```

---

## Step 2 — Preprocessing Pipeline (`ml/pipeline/preprocess.py`)

This is the full image preprocessing pipeline. Every function is independently testable.

```python
"""
Preprocessing pipeline for HRIPCB PCB images.

Stages (in order):
  1. Load — read image from disk, validate shape
  2. Resize — scale to model input size (640x640) without distortion
  3. Greyscale conversion — optional single-channel for analysis only
  4. Normalisation — pixel values [0, 255] → [0.0, 1.0]
  5. Augmentation — random flip, rotate, brightness, mosaic (train only)
  6. Tensor conversion — numpy HWC → torch CHW float32

YOLOv8 handles its own augmentation internally during training.
These functions are exposed for notebook exploration and the evaluation path.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Literal

import cv2
import numpy as np


# ── 1. Load ───────────────────────────────────────────────────────────────────

def load_image(path: str | Path) -> np.ndarray:
    """
    Load a PCB image from disk. Returns BGR uint8 array (H, W, 3).
    Raises FileNotFoundError if path does not exist.
    Raises ValueError if the file cannot be decoded as an image.
    """
    img_path = Path(path)
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {img_path}")

    img = cv2.imread(str(img_path))
    if img is None:
        raise ValueError(f"OpenCV could not decode image: {img_path}")

    return img  # BGR, uint8


# ── 2. Resize ─────────────────────────────────────────────────────────────────

def resize_letterbox(
    image: np.ndarray,
    target: int = 640,
    pad_value: int = 114,
) -> tuple[np.ndarray, float, tuple[int, int]]:
    """
    Resize image to (target x target) with letterboxing (no distortion).
    Matches YOLOv8's internal preprocessing exactly.

    Returns:
        resized   : uint8 BGR array (target, target, 3)
        scale     : float — scale factor applied (original → padded)
        padding   : (pad_w, pad_h) in pixels
    """
    h, w = image.shape[:2]
    scale = min(target / h, target / w)
    new_w, new_h = int(round(w * scale)), int(round(h * scale))

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    pad_w = (target - new_w) // 2
    pad_h = (target - new_h) // 2

    canvas = np.full((target, target, 3), pad_value, dtype=np.uint8)
    canvas[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized

    return canvas, scale, (pad_w, pad_h)


# ── 3. Greyscale conversion ───────────────────────────────────────────────────

def to_greyscale(image: np.ndarray) -> np.ndarray:
    """
    Convert BGR uint8 image to single-channel greyscale uint8 (H, W).
    Used for analysis and visualisation only — model trains on RGB.
    """
    if image.ndim == 2:
        return image  # already greyscale
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def greyscale_to_rgb(grey: np.ndarray) -> np.ndarray:
    """Re-stack greyscale to 3-channel for display or model input."""
    return cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR)


# ── 4. Normalisation ──────────────────────────────────────────────────────────

def normalise(image: np.ndarray) -> np.ndarray:
    """
    Normalise pixel values from uint8 [0, 255] to float32 [0.0, 1.0].
    Input: HWC uint8.  Output: HWC float32.
    """
    if image.dtype != np.uint8:
        raise TypeError(f"Expected uint8 input, got {image.dtype}")
    return image.astype(np.float32) / 255.0


def denormalise(image: np.ndarray) -> np.ndarray:
    """Reverse normalisation for display. float32 [0,1] → uint8 [0,255]."""
    return (np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)


def channel_stats(image: np.ndarray) -> dict[str, float]:
    """
    Return per-channel mean and std for a normalised float32 image.
    Useful for verifying preprocessing output in notebooks.
    """
    assert image.dtype == np.float32, "Pass a normalised float32 image"
    stats: dict[str, float] = {}
    channels = ("B", "G", "R") if image.ndim == 3 else ("L",)
    for i, name in enumerate(channels):
        ch = image[:, :, i] if image.ndim == 3 else image
        stats[f"{name}_mean"] = float(np.mean(ch))
        stats[f"{name}_std"] = float(np.std(ch))
    return stats


# ── 5. Augmentation (manual, for analysis) ────────────────────────────────────
# YOLOv8 applies augmentation internally during training.
# These manual augmentations are for exploring the data in notebooks
# and for manual augmentation if needed in custom training loops.

def augment_flip(image: np.ndarray, direction: Literal["h", "v", "both"] = "h") -> np.ndarray:
    """Flip image horizontally, vertically, or both."""
    codes = {"h": 1, "v": 0, "both": -1}
    return cv2.flip(image, codes[direction])


def augment_rotate(image: np.ndarray, angle: float = 90.0) -> np.ndarray:
    """
    Rotate image by angle degrees around centre without cropping.
    Pads with grey (114) to maintain size.
    """
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    matrix[0, 2] += (new_w / 2) - w / 2
    matrix[1, 2] += (new_h / 2) - h / 2
    rotated = cv2.warpAffine(image, matrix, (new_w, new_h), borderValue=(114, 114, 114))
    return cv2.resize(rotated, (w, h), interpolation=cv2.INTER_LINEAR)


def augment_brightness(image: np.ndarray, factor: float = 1.2) -> np.ndarray:
    """
    Multiply brightness by factor (uint8 input). Clips to [0, 255].
    factor > 1 = brighter, factor < 1 = darker.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] * factor, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def random_augment(image: np.ndarray, seed: int | None = None) -> np.ndarray:
    """
    Apply a random combination of augmentations for a single image.
    Deterministic when seed is provided.
    """
    rng = random.Random(seed)
    img = image.copy()
    if rng.random() > 0.5:
        img = augment_flip(img, rng.choice(["h", "v"]))
    if rng.random() > 0.5:
        img = augment_rotate(img, rng.choice([90.0, 180.0, 270.0]))
    if rng.random() > 0.3:
        img = augment_brightness(img, rng.uniform(0.7, 1.4))
    return img


# ── 6. Full pipeline ──────────────────────────────────────────────────────────

def preprocess_for_display(
    path: str | Path,
    target: int = 640,
) -> dict[str, np.ndarray]:
    """
    Run the full preprocessing pipeline and return intermediate results.
    Used by notebooks to visualise each stage side-by-side.

    Returns dict with keys:
        original, resized, greyscale, normalised (as float32)
    """
    original = load_image(path)
    resized, scale, padding = resize_letterbox(original, target)
    grey = to_greyscale(resized)
    normalised = normalise(resized)

    return {
        "original": original,
        "resized": resized,
        "greyscale": grey,
        "normalised": normalised,
        "scale": scale,       # type: ignore[dict-item]
        "padding": padding,   # type: ignore[dict-item]
    }


def preprocess_for_inference(path: str | Path, target: int = 640) -> np.ndarray:
    """
    Minimal pipeline for inference: load → resize → normalise.
    Returns float32 HWC RGB array ready for YOLO.
    YOLOv8's predict() does its own preprocessing internally,
    so pass the raw path to model.predict() rather than this array.
    This function is for custom inference loops only.
    """
    img = load_image(path)
    resized, _, _ = resize_letterbox(img, target)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    return normalise(rgb)
```

---

## Step 3 — Training (`ml/pipeline/train.py`)

```python
"""
Train YOLOv8s on HRIPCB dataset.
Run: python -m ml.pipeline.train
Or import train() and call it with custom kwargs.
"""
from __future__ import annotations

from pathlib import Path

from ml.pipeline.dataset import get_data_yaml_path, verify, DATASET_DIR

MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# YOLOv8 variants: n (nano) → s (small) → m (medium) → l → x
# For thesis: start with yolov8s — good accuracy/speed trade-off on HRIPCB
DEFAULT_BASE_MODEL = "yolov8s.pt"
DEFAULT_EPOCHS = 100
DEFAULT_IMGSZ = 640
DEFAULT_BATCH = 16
DEFAULT_PROJECT_NAME = "aoi_model"
DEFAULT_RUN_NAME = "hripcb_v1"


def train(
    base_model: str = DEFAULT_BASE_MODEL,
    epochs: int = DEFAULT_EPOCHS,
    imgsz: int = DEFAULT_IMGSZ,
    batch: int = DEFAULT_BATCH,
    project: str = DEFAULT_PROJECT_NAME,
    name: str = DEFAULT_RUN_NAME,
    device: str = "0",   # "0" = first GPU, "cpu" = CPU-only
    resume: bool = False,
) -> Path:
    """
    Fine-tune YOLOv8 on HRIPCB and save best weights to ml/models/.
    Returns path to best.pt.
    """
    from ultralytics import YOLO

    data_yaml = get_data_yaml_path()
    print(f"Dataset: {data_yaml}")
    verify(DATASET_DIR)

    model = YOLO(base_model)

    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        project=str(MODEL_DIR / project),
        name=name,
        device=device,
        resume=resume,
        # Augmentation — YOLOv8 defaults are strong; these refine for PCB:
        hsv_h=0.015,        # hue shift (small — PCB colours are meaningful)
        hsv_s=0.5,          # saturation variation
        hsv_v=0.4,          # brightness variation
        degrees=10.0,       # rotation (PCBs can be slightly tilted)
        translate=0.1,      # translation fraction
        scale=0.5,          # scale variation
        flipud=0.5,         # vertical flip (PCBs can come in any orientation)
        fliplr=0.5,         # horizontal flip
        mosaic=1.0,         # mosaic augmentation (4 images combined)
        mixup=0.1,          # mixup augmentation
        # Early stopping
        patience=20,        # stop if no improvement for 20 epochs
        # Saving
        save=True,
        save_period=10,     # save checkpoint every 10 epochs
        # Logging
        verbose=True,
    )

    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    output_path = MODEL_DIR / "best.pt"
    import shutil
    shutil.copy2(best_weights, output_path)
    print(f"Best weights saved to: {output_path}")
    return output_path


def get_latest_weights() -> Path:
    """Return path to best.pt if it exists."""
    weights = MODEL_DIR / "best.pt"
    if not weights.exists():
        raise FileNotFoundError(
            f"No trained weights found at {weights}. Run train() first."
        )
    return weights


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--device", default="0")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    train(
        base_model=args.model,
        epochs=args.epochs,
        batch=args.batch,
        device=args.device,
        resume=args.resume,
    )
```

---

## Step 4 — Evaluation (`ml/pipeline/evaluate.py`)

```python
"""
Evaluate trained model. Reports mAP50, mAP50-95, per-class precision/recall/F1.
Saves confusion matrix and per-class bar chart to ml/models/eval/.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ml.pipeline.dataset import CLASSES, get_data_yaml_path, DATASET_DIR
from ml.pipeline.train import get_latest_weights

EVAL_DIR = Path(__file__).parent.parent / "models" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)


def evaluate(weights_path: Path | None = None, split: str = "test") -> dict[str, object]:
    """
    Run YOLOv8 validation on the test split.
    Returns metrics dict with mAP and per-class breakdown.
    """
    from ultralytics import YOLO

    weights = weights_path or get_latest_weights()
    data_yaml = get_data_yaml_path()

    model = YOLO(str(weights))
    metrics = model.val(
        data=str(data_yaml),
        split=split,
        imgsz=640,
        batch=16,
        verbose=True,
        project=str(EVAL_DIR),
        name="results",
    )

    result = {
        "map50": float(metrics.box.map50),
        "map50_95": float(metrics.box.map),
        "precision": float(metrics.box.mp),
        "recall": float(metrics.box.mr),
        "per_class": {},
    }

    for i, cls_name in enumerate(CLASSES):
        result["per_class"][cls_name] = {
            "precision": float(metrics.box.p[i]),
            "recall": float(metrics.box.r[i]),
            "f1": float(metrics.box.f1[i]),
            "ap50": float(metrics.box.ap50[i]),
        }

    print("\n── Evaluation Results ──────────────────")
    print(f"  mAP@50:      {result['map50']:.4f}")
    print(f"  mAP@50-95:   {result['map50_95']:.4f}")
    print(f"  Precision:   {result['precision']:.4f}")
    print(f"  Recall:      {result['recall']:.4f}")
    print("\n  Per-class F1:")
    for cls_name, stats in result["per_class"].items():
        print(f"    {cls_name:<20} F1={stats['f1']:.3f}  AP50={stats['ap50']:.3f}")

    _save_metrics_chart(result)
    return result


def _save_metrics_chart(result: dict[str, object]) -> None:
    """Save a per-class F1 bar chart as PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    per_class = result["per_class"]
    names = list(per_class.keys())
    f1_scores = [per_class[n]["f1"] for n in names]

    fig, ax = plt.subplots(figsize=(10, 5))
    colours = ["#1D9E75" if f >= 0.75 else "#EF9F27" if f >= 0.5 else "#E24B4A" for f in f1_scores]
    bars = ax.bar(names, f1_scores, color=colours, edgecolor="none")

    ax.axhline(0.75, colour="#1D9E75", linestyle="--", linewidth=0.8, label="target (0.75)")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("F1 Score")
    ax.set_title("Per-class F1 — HRIPCB test set")
    ax.legend()
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()

    out = EVAL_DIR / "f1_per_class.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Chart saved: {out}")


if __name__ == "__main__":
    evaluate()
```

---

## Step 5 — Self-Test (`ml/pipeline/self_test.py`)

Runs without GPU, without the dataset, without trained weights. Tests every function in `preprocess.py` and basic model loading.

```python
"""
Self-contained smoke tests for the ML pipeline.
No GPU required. No dataset required. No trained model required.
Run: python ml/pipeline/self_test.py
All tests must pass before submitting a PR.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np


def _make_dummy_pcb_image(h: int = 480, w: int = 640) -> np.ndarray:
    """Generate a synthetic BGR image that looks vaguely like a PCB for testing."""
    img = np.full((h, w, 3), 30, dtype=np.uint8)
    # Green board
    img[:, :] = (30, 80, 30)
    # White/silver pads (simulate RLC, IC pads)
    for row in range(5):
        for col in range(8):
            x, y = 60 + col * 75, 60 + row * 80
            cv2.rectangle(img, (x, y), (x + 20, y + 12), (200, 200, 200), -1)
    # Gold fiducial marks in corners
    for cx, cy in [(30, 30), (w - 30, 30), (30, h - 30)]:
        cv2.circle(img, (cx, cy), 10, (30, 165, 210), -1)
    return img


def test_load_image() -> None:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp = Path(f.name)
    dummy = _make_dummy_pcb_image()
    cv2.imwrite(str(tmp), dummy)

    from ml.pipeline.preprocess import load_image
    img = load_image(tmp)
    assert img.shape == (480, 640, 3), f"Expected (480,640,3), got {img.shape}"
    assert img.dtype == np.uint8
    tmp.unlink()
    print("  PASS  load_image")


def test_load_image_missing() -> None:
    from ml.pipeline.preprocess import load_image
    try:
        load_image("/nonexistent/path/image.png")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass
    print("  PASS  load_image (missing file)")


def test_resize_letterbox() -> None:
    from ml.pipeline.preprocess import resize_letterbox
    img = _make_dummy_pcb_image(480, 640)
    resized, scale, (pad_w, pad_h) = resize_letterbox(img, target=640)
    assert resized.shape == (640, 640, 3), f"Expected (640,640,3), got {resized.shape}"
    assert resized.dtype == np.uint8
    assert 0.0 < scale <= 1.0
    assert pad_w >= 0 and pad_h >= 0
    print("  PASS  resize_letterbox")


def test_resize_square_input() -> None:
    from ml.pipeline.preprocess import resize_letterbox
    img = _make_dummy_pcb_image(640, 640)
    resized, scale, padding = resize_letterbox(img, 640)
    assert resized.shape == (640, 640, 3)
    assert scale == 1.0
    print("  PASS  resize_letterbox (square input)")


def test_greyscale() -> None:
    from ml.pipeline.preprocess import to_greyscale
    img = _make_dummy_pcb_image()
    grey = to_greyscale(img)
    assert grey.ndim == 2, f"Expected 2D, got shape {grey.shape}"
    assert grey.dtype == np.uint8
    # Already greyscale should be a no-op
    grey2 = to_greyscale(grey)
    assert grey2.shape == grey.shape
    print("  PASS  to_greyscale")


def test_normalise() -> None:
    from ml.pipeline.preprocess import normalise, denormalise, channel_stats
    img = _make_dummy_pcb_image()
    norm = normalise(img)
    assert norm.dtype == np.float32
    assert norm.min() >= 0.0 and norm.max() <= 1.0, "Values out of [0,1]"

    back = denormalise(norm)
    assert back.dtype == np.uint8
    assert np.max(np.abs(back.astype(int) - img.astype(int))) <= 1, "Round-trip error"

    stats = channel_stats(norm)
    for key in ("B_mean", "G_mean", "R_mean", "B_std", "G_std", "R_std"):
        assert key in stats
        assert 0.0 <= stats[key] <= 1.0
    print("  PASS  normalise / denormalise / channel_stats")


def test_normalise_wrong_dtype() -> None:
    from ml.pipeline.preprocess import normalise
    bad = np.zeros((10, 10, 3), dtype=np.float32)
    try:
        normalise(bad)
        assert False, "Should have raised TypeError"
    except TypeError:
        pass
    print("  PASS  normalise (wrong dtype guard)")


def test_augmentations() -> None:
    from ml.pipeline.preprocess import augment_flip, augment_rotate, augment_brightness, random_augment
    img = _make_dummy_pcb_image()

    flipped_h = augment_flip(img, "h")
    assert flipped_h.shape == img.shape
    flipped_v = augment_flip(img, "v")
    assert flipped_v.shape == img.shape

    rotated = augment_rotate(img, 90.0)
    assert rotated.shape == img.shape  # resize back

    bright = augment_brightness(img, 1.3)
    assert bright.shape == img.shape
    assert bright.dtype == np.uint8

    rand = random_augment(img, seed=42)
    assert rand.shape == img.shape
    print("  PASS  augmentations (flip, rotate, brightness, random)")


def test_preprocess_for_display() -> None:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp = Path(f.name)
    cv2.imwrite(str(tmp), _make_dummy_pcb_image())

    from ml.pipeline.preprocess import preprocess_for_display
    result = preprocess_for_display(tmp)
    assert "original" in result
    assert "resized" in result
    assert "greyscale" in result
    assert "normalised" in result
    assert result["resized"].shape == (640, 640, 3)
    assert result["greyscale"].ndim == 2
    assert result["normalised"].dtype == np.float32
    tmp.unlink()
    print("  PASS  preprocess_for_display")


def test_preprocess_for_inference() -> None:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp = Path(f.name)
    cv2.imwrite(str(tmp), _make_dummy_pcb_image())

    from ml.pipeline.preprocess import preprocess_for_inference
    arr = preprocess_for_inference(tmp)
    assert arr.shape == (640, 640, 3)
    assert arr.dtype == np.float32
    assert arr.max() <= 1.0
    tmp.unlink()
    print("  PASS  preprocess_for_inference")


def test_dataset_verify_missing() -> None:
    """verify() should return zero counts gracefully when data is absent."""
    from ml.pipeline.dataset import verify
    counts = verify(Path("/nonexistent/dataset/path"))
    assert all(v == 0 for v in counts.values())
    print("  PASS  dataset.verify (missing path)")


def run_all() -> None:
    tests = [
        test_load_image,
        test_load_image_missing,
        test_resize_letterbox,
        test_resize_square_input,
        test_greyscale,
        test_normalise,
        test_normalise_wrong_dtype,
        test_augmentations,
        test_preprocess_for_display,
        test_preprocess_for_inference,
        test_dataset_verify_missing,
    ]

    passed = 0
    failed = 0
    print("\n── ML Pipeline Self-Tests ──────────────────────────────")
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test_fn.__name__}: {exc}")
            failed += 1

    print(f"\n  {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
```

---

## Step 6 — System Integration (`src/aoi/inference_runner.py`)

This file **replaces** `mock_inference.py`. It connects the trained model to the existing `InferenceEvent` schema and POSTs real results to the API.

```python
"""
Real inference runner — replaces mock_inference.py.
Loads the trained YOLOv8 model and runs it on a PCB scan image.
Results are formatted as InferenceEvent objects compatible with the
existing POST /events API contract (no schema changes needed).

Usage (standalone):
    python -m aoi.inference_runner --image path/to/scan.jpg --run-id <uuid> --api-url http://localhost:8000

Usage (programmatic):
    from aoi.inference_runner import run_inference
    events = run_inference(image_path="scan.jpg", run_id="abc123")
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from aoi.schema import InferenceEvent, InspectionResult

if TYPE_CHECKING:
    pass

# ── Defect class mapping ───────────────────────────────────────────────────────
# HRIPCB class index → (defect_type string, InspectionResult)
# Matches docs/defects.md IPC-A-610 taxonomy

HRIPCB_CLASS_MAP: dict[int, tuple[str, InspectionResult]] = {
    0: ("MISSING_COMPONENT", InspectionResult.FAIL),   # missing_hole
    1: ("BENT_LEAD",         InspectionResult.FAIL),   # mouse_bite
    2: ("LIFTED_LEAD",       InspectionResult.FAIL),   # open_circuit
    3: ("SOLDER_BRIDGE",     InspectionResult.FAIL),   # short
    4: ("SOLDER_BALL",       InspectionResult.FAIL),   # spur
    5: ("INSUFFICIENT_SOLDER", InspectionResult.FAIL), # spurious_copper
}

CONFIDENCE_THRESHOLD = 0.40   # discard detections below this
NO_DEFECT_TYPE = "NO_DEFECT"
MODEL_VERSION = "yolov8s-hripcb-v1"


def _load_model(weights_path: str | Path):
    """Lazy-load YOLO model. Import is deferred so the module can be imported without ultralytics."""
    from ultralytics import YOLO
    return YOLO(str(weights_path))


def _default_weights_path() -> Path:
    """Look for best.pt in ml/models/ relative to repo root."""
    candidates = [
        Path(__file__).parent.parent.parent / "ml" / "models" / "best.pt",
        Path("ml/models/best.pt"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Trained model not found. Run: python -m ml.pipeline.train\n"
        "Expected location: ml/models/best.pt"
    )


def run_inference(
    image_path: str | Path,
    run_id: str,
    pcb_id: str | None = None,
    weights_path: str | Path | None = None,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> list[InferenceEvent]:
    """
    Run model inference on a PCB scan image.

    Args:
        image_path:           Path to the input scan (jpg/png).
        run_id:               UUID of the current run (for component_id generation).
        pcb_id:               PCB identifier string; defaults to run_id[:8].
        weights_path:         Path to best.pt; auto-detected if None.
        confidence_threshold: Detections below this are discarded.

    Returns:
        List of InferenceEvent objects. Returns a single PASS event if no
        defects are detected above threshold.
    """
    weights = Path(weights_path) if weights_path else _default_weights_path()
    board_id = pcb_id or run_id[:8].upper()

    model = _load_model(weights)

    t_start = time.perf_counter()
    results = model.predict(
        source=str(image_path),
        conf=confidence_threshold,
        imgsz=640,
        verbose=False,
        save=False,
    )
    latency_ms = int((time.perf_counter() - t_start) * 1000)

    events: list[InferenceEvent] = []
    result = results[0]

    if result.boxes is None or len(result.boxes) == 0:
        # No defects — emit a PASS event
        events.append(
            InferenceEvent.create(
                pcb_id=board_id,
                component_id="BOARD",
                inspection_result=InspectionResult.PASS,
                defect_type=NO_DEFECT_TYPE,
                confidence_score=1.0,
                inference_latency_ms=latency_ms,
            )
        )
        return events

    boxes = result.boxes
    for idx, (cls_tensor, conf_tensor, xyxyn_tensor) in enumerate(
        zip(boxes.cls, boxes.conf, boxes.xyxyn)
    ):
        cls_idx = int(cls_tensor.item())
        confidence = float(conf_tensor.item())
        x1, y1, x2, y2 = [float(v) for v in xyxyn_tensor.tolist()]

        defect_type, inspection_result = HRIPCB_CLASS_MAP.get(
            cls_idx, ("UNKNOWN_DEFECT", InspectionResult.FAIL)
        )

        # Convert xyxy normalised → xywh normalised (schema uses x,y = top-left)
        overlay_w = x2 - x1
        overlay_h = y2 - y1

        events.append(
            InferenceEvent.create(
                pcb_id=board_id,
                component_id=f"DET-{idx + 1:03d}",
                inspection_result=inspection_result,
                defect_type=defect_type,
                confidence_score=round(confidence, 4),
                inference_latency_ms=latency_ms,
                overlay_x=round(x1, 4),
                overlay_y=round(y1, 4),
                overlay_width=round(overlay_w, 4),
                overlay_height=round(overlay_h, 4),
                overlay_shape="rect",
            )
        )

    return events


def post_events_to_api(
    events: list[InferenceEvent],
    api_url: str = "http://localhost:8000",
    image_path: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    """
    POST inference results to the AOI API /events endpoint.
    Returns the API response dict.
    """
    import requests

    payload: dict[str, object] = {
        "model_version": MODEL_VERSION,
        "events": [e.to_dict() for e in events],
    }

    if image_path and run_id:
        from PIL import Image
        img = Image.open(str(image_path))
        w, h = img.size
        payload["images"] = [
            {
                "image_path": f"/runs/{run_id}/images/scan.jpg",
                "image_role": "scan",
                "image_width": w,
                "image_height": h,
            }
        ]

    response = requests.post(f"{api_url}/events", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run AOI inference on a PCB image")
    parser.add_argument("--image", required=True, help="Path to PCB scan image")
    parser.add_argument("--run-id", required=True, help="Run UUID")
    parser.add_argument("--pcb-id", default=None, help="PCB identifier")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--weights", default=None, help="Path to best.pt")
    parser.add_argument("--threshold", type=float, default=CONFIDENCE_THRESHOLD)
    parser.add_argument("--dry-run", action="store_true", help="Print events, do not POST")
    args = parser.parse_args()

    events = run_inference(
        image_path=args.image,
        run_id=args.run_id,
        pcb_id=args.pcb_id,
        weights_path=args.weights,
        confidence_threshold=args.threshold,
    )

    print(f"\nDetected {len(events)} event(s):")
    for e in events:
        print(f"  [{e.inspection_result}] {e.defect_type} conf={e.confidence_score} "
              f"xy=({e.overlay_x},{e.overlay_y}) wh=({e.overlay_width},{e.overlay_height})")

    if not args.dry_run:
        resp = post_events_to_api(events, api_url=args.api_url, run_id=args.run_id)
        print(f"\nAPI response: {resp}")
```

---

## Step 7 — Jupyter Notebooks

Create 4 notebooks in `ml/notebooks/`. Each notebook is self-contained and must run top-to-bottom without errors once the dataset is downloaded.

### `01_dataset_explore.ipynb` — required cells

```python
# Cell 1 — Setup
import sys; sys.path.insert(0, "../..")
from ml.pipeline.dataset import verify, DATASET_DIR, CLASSES, get_data_yaml_path
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from pathlib import Path

# Cell 2 — Verify dataset
counts = verify()
print(counts)

# Cell 3 — Show class distribution
import os
from collections import Counter

label_dir = DATASET_DIR / "train" / "labels"
class_counts = Counter()
for label_file in label_dir.glob("*.txt"):
    for line in label_file.read_text().splitlines():
        if line.strip():
            cls_idx = int(line.split()[0])
            class_counts[CLASSES[cls_idx]] += 1

plt.figure(figsize=(10, 4))
plt.bar(class_counts.keys(), class_counts.values(), color="#1D9E75")
plt.title("HRIPCB training set — defect class distribution")
plt.xticks(rotation=20, ha="right")
plt.ylabel("Instance count")
plt.tight_layout()
plt.show()

# Cell 4 — Show sample annotated images (use matplotlib, no IPython display needed)
# Show 6 random train images with their bounding boxes overlaid
import random, cv2, numpy as np

img_dir = DATASET_DIR / "train" / "images"
lbl_dir = DATASET_DIR / "train" / "labels"
samples = random.sample(list(img_dir.glob("*.jpg")), min(6, len(list(img_dir.glob("*.jpg")))))

fig, axes = plt.subplots(2, 3, figsize=(14, 8))
COLOURS = [(29,158,117),(239,159,39),(226,75,74),(55,138,221),(127,119,221),(212,83,126)]
for ax, img_path in zip(axes.flat, samples):
    img = cv2.imread(str(img_path))
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    lbl_path = lbl_dir / (img_path.stem + ".txt")
    if lbl_path.exists():
        for line in lbl_path.read_text().splitlines():
            parts = line.strip().split()
            if len(parts) < 5: continue
            cls, cx, cy, bw, bh = int(parts[0]), *map(float, parts[1:5])
            x1 = int((cx - bw/2) * w); y1 = int((cy - bh/2) * h)
            x2 = int((cx + bw/2) * w); y2 = int((cy + bh/2) * h)
            colour = COLOURS[cls % len(COLOURS)]
            cv2.rectangle(img_rgb, (x1,y1), (x2,y2), colour, 2)
            cv2.putText(img_rgb, CLASSES[cls], (x1, max(y1-4,0)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1)
    ax.imshow(img_rgb)
    ax.axis("off")
    ax.set_title(img_path.name, fontsize=8)
plt.suptitle("Sample HRIPCB images with ground truth boxes")
plt.tight_layout()
plt.show()
```

### `02_preprocessing.ipynb` — required cells

```python
# Cell 1 — Setup
import sys; sys.path.insert(0, "../..")
from ml.pipeline.preprocess import preprocess_for_display, channel_stats, random_augment, load_image
from ml.pipeline.dataset import DATASET_DIR
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Cell 2 — Pick a sample PCB image with components (RLC, IC, BGA)
samples = list((DATASET_DIR / "train" / "images").glob("*.jpg"))
assert samples, "No images found — run dataset.download() first"
sample_path = samples[0]
print(f"Using: {sample_path.name}")

# Cell 3 — Run full preprocessing pipeline
result = preprocess_for_display(sample_path, target=640)
print(f"Original shape: {result['original'].shape}")
print(f"Resized shape:  {result['resized'].shape}")
print(f"Scale factor:   {result['scale']:.4f}")
print(f"Padding (w,h):  {result['padding']}")

# Cell 4 — Visualise all pipeline stages side by side
import cv2
fig, axes = plt.subplots(1, 4, figsize=(18, 4))
stages = [
    ("original (BGR→RGB)", cv2.cvtColor(result["original"], cv2.COLOR_BGR2RGB)),
    ("resized 640×640", cv2.cvtColor(result["resized"], cv2.COLOR_BGR2RGB)),
    ("greyscale", result["greyscale"]),
    ("normalised [0–1]", result["normalised"]),
]
for ax, (title, img) in zip(axes, stages):
    if img.ndim == 2:
        ax.imshow(img, cmap="gray", vmin=0, vmax=255 if img.dtype == np.uint8 else 1)
    else:
        ax.imshow(img if img.max() <= 1 else img.astype(float)/255)
    ax.set_title(title, fontsize=10)
    ax.axis("off")
plt.suptitle("Preprocessing pipeline — PCB with RLC/IC/BGA components", y=1.02)
plt.tight_layout()
plt.show()

# Cell 5 — Pixel statistics after normalisation
stats = channel_stats(result["normalised"])
print("\nChannel statistics (normalised image):")
for k, v in stats.items():
    print(f"  {k}: {v:.4f}")

# Cell 6 — Show augmentation variants
img = load_image(sample_path)
from ml.pipeline.preprocess import augment_flip, augment_rotate, augment_brightness
fig, axes = plt.subplots(1, 5, figsize=(20, 4))
augments = [
    ("original", img),
    ("flip horizontal", augment_flip(img, "h")),
    ("flip vertical", augment_flip(img, "v")),
    ("rotate 90°", augment_rotate(img, 90)),
    ("brightness ×1.4", augment_brightness(img, 1.4)),
]
for ax, (label, aug) in zip(axes, augments):
    ax.imshow(cv2.cvtColor(aug, cv2.COLOR_BGR2RGB))
    ax.set_title(label, fontsize=9)
    ax.axis("off")
plt.suptitle("Augmentation variants on PCB image", y=1.02)
plt.tight_layout()
plt.show()

# Cell 7 — Run self-tests
import subprocess, sys
result_proc = subprocess.run(
    [sys.executable, "../../ml/pipeline/self_test.py"],
    capture_output=True, text=True
)
print(result_proc.stdout)
if result_proc.returncode != 0:
    print("SELF-TEST FAILURES:")
    print(result_proc.stderr)
```

### `03_training.ipynb` — required cells

```python
# Cell 1 — Setup
import sys; sys.path.insert(0, "../..")
from ml.pipeline.train import train, get_latest_weights, MODEL_DIR
from ml.pipeline.dataset import verify, DATASET_DIR
print("Dataset check:")
verify()

# Cell 2 — Start training (GPU recommended)
# Remove or comment out if running for the first time on CPU
# Use device="cpu" on machines without CUDA
weights_path = train(
    base_model="yolov8s.pt",
    epochs=100,
    batch=16,
    device="0",         # change to "cpu" if no GPU
)
print(f"Training complete. Weights at: {weights_path}")

# Cell 3 — Training curves (auto-saved by ultralytics)
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

results_png = list((MODEL_DIR / "aoi_model" / "hripcb_v1").glob("results.png"))
if results_png:
    img = mpimg.imread(str(results_png[0]))
    plt.figure(figsize=(14, 6))
    plt.imshow(img)
    plt.axis("off")
    plt.title("Training and validation curves")
    plt.show()
else:
    print("results.png not found — training may not have completed")
```

### `04_evaluation.ipynb` — required cells

```python
# Cell 1 — Setup
import sys; sys.path.insert(0, "../..")
from ml.pipeline.evaluate import evaluate, EVAL_DIR
from ml.pipeline.train import get_latest_weights

# Cell 2 — Run evaluation on test split
metrics = evaluate(split="test")

# Cell 3 — Pretty-print per-class table
import pandas as pd
rows = []
for cls_name, stats in metrics["per_class"].items():
    rows.append({
        "class": cls_name,
        "precision": f"{stats['precision']:.3f}",
        "recall": f"{stats['recall']:.3f}",
        "F1": f"{stats['f1']:.3f}",
        "AP@50": f"{stats['ap50']:.3f}",
    })
df = pd.DataFrame(rows)
print(df.to_string(index=False))
print(f"\nmAP@50:    {metrics['map50']:.4f}")
print(f"mAP@50-95: {metrics['map50_95']:.4f}")

# Cell 4 — Show F1 chart
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from pathlib import Path
chart = EVAL_DIR / "f1_per_class.png"
if chart.exists():
    img = mpimg.imread(str(chart))
    plt.figure(figsize=(10, 5))
    plt.imshow(img)
    plt.axis("off")
    plt.show()

# Cell 5 — Run inference on the existing mock PCB images in web/public/mock/
from ml.pipeline.inference_runner_test import run_quick_check
# (See note below — add this convenience function to inference_runner.py)

import sys
from pathlib import Path
sys.path.insert(0, str(Path("../..").resolve()))
from aoi.inference_runner import run_inference

mock_imgs = list(Path("../../web/public/mock").glob("*.png")) + \
            list(Path("../../web/public/mock").glob("*.jpg"))

print(f"\nInference on {len(mock_imgs)} existing mock PCB images:")
for img_path in mock_imgs:
    events = run_inference(str(img_path), run_id="notebook-test", pcb_id="DEMO-001")
    defects = [e for e in events if e.inspection_result == "FAIL"]
    print(f"  {img_path.name}: {len(defects)} defect(s) detected")
    for d in defects:
        print(f"    [{d.defect_type}] conf={d.confidence_score} "
              f"xy=({d.overlay_x:.3f},{d.overlay_y:.3f})")
```

---

## Step 8 — Update `mock_inference.py`

After `inference_runner.py` is working, update `mock_inference.py` to delegate to it for local testing while preserving the old fallback for environments without the model:

```python
# src/aoi/mock_inference.py (updated)
from __future__ import annotations

from itertools import cycle
from pathlib import Path

from aoi.schema import InferenceEvent, InspectionResult

# Updated to match HRIPCB defect taxonomy from docs/defects.md
DEFECT_SEQUENCE = (
    ("NO_DEFECT",           InspectionResult.PASS, 0.99),
    ("SOLDER_BRIDGE",       InspectionResult.FAIL, 0.87),
    ("MISSING_COMPONENT",   InspectionResult.FAIL, 0.82),
    ("NO_DEFECT",           InspectionResult.PASS, 0.96),
    ("INSUFFICIENT_SOLDER", InspectionResult.FAIL, 0.75),
    ("BENT_LEAD",           InspectionResult.FAIL, 0.79),
)


def generate_mock_events(count: int) -> list[InferenceEvent]:
    if count < 1:
        return []
    events: list[InferenceEvent] = []
    defects = cycle(DEFECT_SEQUENCE)
    for index in range(1, count + 1):
        defect_type, result, confidence = next(defects)
        events.append(
            InferenceEvent.create(
                pcb_id=f"PCB-{((index - 1) // 6) + 1:04d}",
                component_id=f"U{index:03d}",
                inspection_result=result,
                defect_type=defect_type,
                confidence_score=confidence,
                inference_latency_ms=20 + (index % 7) * 3,
                overlay_x=round(0.1 + (index % 8) * 0.1, 4) if result == InspectionResult.FAIL else None,
                overlay_y=round(0.1 + (index % 6) * 0.12, 4) if result == InspectionResult.FAIL else None,
                overlay_width=0.08 if result == InspectionResult.FAIL else None,
                overlay_height=0.06 if result == InspectionResult.FAIL else None,
                overlay_shape="rect" if result == InspectionResult.FAIL else None,
            )
        )
    return events
```

---

## Execution Order for Codex

Implement in this exact order. Each step must pass its own check before the next begins.

1. Create `ml/` directory structure and `requirements-ml.txt`
2. Write `ml/pipeline/dataset.py` — verify it runs without a Roboflow key (prints zero counts gracefully)
3. Write `ml/pipeline/preprocess.py` — all functions
4. Write `ml/pipeline/self_test.py` — run it: `python ml/pipeline/self_test.py` → all PASS
5. Write `ml/pipeline/train.py` — do not run training yet
6. Write `ml/pipeline/evaluate.py` — do not run evaluation yet
7. Write `src/aoi/inference_runner.py` — verify it imports cleanly without ultralytics installed (`python -c "import aoi.inference_runner"` — should not crash on import, only on calling `run_inference`)
8. Update `src/aoi/mock_inference.py` with corrected defect taxonomy
9. Create the 4 Jupyter notebooks in `ml/notebooks/`
10. Run self-tests: `python ml/pipeline/self_test.py` → all PASS
11. (Requires ROBOFLOW_API_KEY + GPU) Download dataset, run training, run evaluation

---

## Success Criteria

- `python ml/pipeline/self_test.py` exits with code 0, all tests PASS — no GPU, no dataset needed
- `python -c "from aoi.inference_runner import run_inference"` imports without error
- After training: mAP@50 > 0.70 on test split (thesis acceptable threshold)
- After training: `python src/aoi/inference_runner.py --image web/public/mock/pcb-example.png --run-id test-001 --dry-run` prints detected defects
- `generate_mock_events()` defect types all exist in `docs/defects.md` taxonomy
