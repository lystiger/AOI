"""Training entry point for the AOI detection model."""
from __future__ import annotations

import json
from pathlib import Path

from ml.pipeline.dataset import DATASET_DIR, get_data_yaml_path, validate_supported_classes, verify

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_BASE_MODEL = "yolov8s.pt"
DEFAULT_EPOCHS = 100
DEFAULT_IMGSZ = 640
DEFAULT_BATCH = 16
DEFAULT_PROJECT_NAME = "aoi_model"
DEFAULT_RUN_NAME = "component_solder_v1"
DEFAULT_SEED = 42


def _write_run_manifest(save_dir: Path, *, base_model: str, epochs: int, imgsz: int, batch: int, device: str, seed: int) -> None:
    manifest = {
        "base_model": base_model,
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch,
        "device": device,
        "seed": seed,
        "data_yaml": str(get_data_yaml_path()),
    }
    (save_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def train(
    *,
    base_model: str = DEFAULT_BASE_MODEL,
    epochs: int = DEFAULT_EPOCHS,
    imgsz: int = DEFAULT_IMGSZ,
    batch: int = DEFAULT_BATCH,
    project: str = DEFAULT_PROJECT_NAME,
    name: str = DEFAULT_RUN_NAME,
    device: str = "0",
    resume: bool = False,
    seed: int = DEFAULT_SEED,
) -> Path:
    """Fine-tune a YOLOv8 model and copy the best checkpoint to ``ml/models/best.pt``."""
    from ultralytics import YOLO

    unsupported = validate_supported_classes()
    if unsupported:
        unsupported_csv = ", ".join(unsupported)
        raise ValueError(f"Dataset contains unsupported classes: {unsupported_csv}")

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
        seed=seed,
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.4,
        degrees=10.0,
        translate=0.1,
        scale=0.5,
        flipud=0.5,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.1,
        patience=20,
        save=True,
        save_period=10,
        verbose=True,
    )

    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    output_path = MODEL_DIR / "best.pt"

    import shutil

    shutil.copy2(best_weights, output_path)
    _write_run_manifest(
        Path(results.save_dir),
        base_model=base_model,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        seed=seed,
    )
    print(f"Best weights saved to: {output_path}")
    return output_path


def get_latest_weights() -> Path:
    """Return the canonical best checkpoint path."""
    weights = MODEL_DIR / "best.pt"
    if not weights.exists():
        raise FileNotFoundError(f"No trained weights found at {weights}. Run train() first.")
    return weights


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--imgsz", type=int, default=DEFAULT_IMGSZ)
    parser.add_argument("--model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--device", default="0")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    train(
        base_model=args.model,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        resume=args.resume,
        seed=args.seed,
    )
