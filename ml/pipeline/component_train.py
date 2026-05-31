"""Training entry point for the component-detection-first YOLOv8 model."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from ml.pipeline.component_dataset import DEFAULT_OUTPUT_ROOT, load_component_class_names
from ml.pipeline.model_variants import SUPPORTED_VARIANTS, build_component_model, get_variant_config
from ml.pipeline.reporting import write_run_report

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "component_detection"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_BASE_MODEL = "yolov8s.pt"
DEFAULT_EPOCHS = 100
DEFAULT_IMGSZ = 1280
DEFAULT_BATCH = 8
DEFAULT_PROJECT_NAME = "component_detection"
DEFAULT_RUN_NAME = "pcb_seed_v1"
DEFAULT_SEED = 42


def get_component_data_yaml_path(dataset_root: Path | None = None) -> Path:
    root = dataset_root or DEFAULT_OUTPUT_ROOT
    data_yaml = root / "data.yaml"
    if not data_yaml.exists():
        raise FileNotFoundError(
            f"Component dataset not found at {data_yaml}. "
            "Run: python -m ml.pipeline.component_dataset --overwrite"
        )
    return data_yaml


def verify_component_dataset(dataset_root: Path | None = None) -> dict[str, int]:
    root = dataset_root or DEFAULT_OUTPUT_ROOT
    counts: dict[str, int] = {}
    for split in ("train", "val", "test"):
        image_dir = root / split / "images"
        label_dir = root / split / "labels"
        images = (
            sorted(
                path
                for path in image_dir.iterdir()
                if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
            )
            if image_dir.exists()
            else []
        )
        labels = sorted(label_dir.glob("*.txt")) if label_dir.exists() else []
        counts[split] = len(images)
        print(f"  {split}: {len(images)} images, {len(labels)} labels")
    return counts


def _write_run_manifest(
    save_dir: Path,
    *,
    data_yaml: Path,
    classes: list[str],
    variant: str,
    base_model: str,
    epochs: int,
    imgsz: int,
    batch: int,
    device: str,
    seed: int,
) -> None:
    manifest = {
        "task": "component_detection",
        "variant": variant,
        "classes": classes,
        "base_model": base_model,
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch,
        "device": device,
        "seed": seed,
        "data_yaml": str(data_yaml),
    }
    (save_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def train_component_model(
    *,
    dataset_root: Path | None = None,
    variant: str = "baseline",
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
    """Fine-tune a YOLOv8 detector on the component seed dataset."""
    data_yaml = get_component_data_yaml_path(dataset_root)
    classes = load_component_class_names(data_yaml.parent)
    variant_config = get_variant_config(variant)
    print(f"Dataset: {data_yaml}")
    verify_component_dataset(data_yaml.parent)

    model = build_component_model(base_model=base_model, variant=variant)
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
        degrees=5.0,
        translate=0.05,
        scale=0.25,
        flipud=0.0,
        fliplr=0.5,
        mosaic=0.2,
        mixup=0.0,
        hsv_h=0.01,
        hsv_s=0.2,
        hsv_v=0.2,
        patience=20,
        save=True,
        save_period=10,
        verbose=True,
    )

    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    output_path = MODEL_DIR / f"best-{variant}.pt"
    shutil.copy2(best_weights, output_path)
    if variant == "baseline":
        shutil.copy2(best_weights, MODEL_DIR / "best.pt")
    _write_run_manifest(
        Path(results.save_dir),
        data_yaml=data_yaml,
        classes=classes,
        variant=variant,
        base_model=base_model,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        seed=seed,
    )
    report_path = write_run_report(
        category="component_detection",
        stage="train",
        title="Component Training Run",
        summary=f"Finished component training run `{name}`.",
        details=[
            f"Dataset: `{data_yaml}`",
            f"Variant: `{variant}`",
            f"Attention type: `{variant_config.attention_type}`",
            f"Classes: {', '.join(classes)}",
            f"Epochs: {epochs}",
            f"Image size: {imgsz}",
            f"Batch: {batch}",
            f"Device: {device}",
            f"Best weights: `{output_path}`",
            f"Save dir: `{results.save_dir}`",
        ],
    )
    print(f"Report saved: {report_path}")
    print(f"Best weights saved to: {output_path}")
    return output_path


def get_latest_component_weights() -> Path:
    weights = MODEL_DIR / "best-baseline.pt"
    legacy = MODEL_DIR / "best.pt"
    if not weights.exists():
        if legacy.exists():
            return legacy
        raise FileNotFoundError(f"No trained component weights found at {weights}. Run train_component_model() first.")
    return weights


def get_component_weights_for_variant(variant: str) -> Path:
    if variant == "baseline":
        return get_latest_component_weights()
    weights = MODEL_DIR / f"best-{variant}.pt"
    if not weights.exists():
        raise FileNotFoundError(f"No trained component weights found for variant `{variant}` at {weights}")
    return weights


def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLOv8 on the component seed dataset")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--imgsz", type=int, default=DEFAULT_IMGSZ)
    parser.add_argument("--model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--variant", choices=SUPPORTED_VARIANTS, default="baseline")
    parser.add_argument("--device", default="0")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    train_component_model(
        dataset_root=args.dataset_root,
        variant=args.variant,
        base_model=args.model,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        resume=args.resume,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
