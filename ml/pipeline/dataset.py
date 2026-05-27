"""
Dataset utilities for component/solder AOI training.

The downloader is intentionally generic: this repo no longer hardcodes a
trace-defect dataset. Configure a Roboflow project that matches the supported
AOI classes, then export in YOLOv8 format into ``ml/data/component_solder``.
"""
from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATASET_DIR = DATA_DIR / "component_solder"
EXPECTED_SPLITS = ("train", "valid", "test")
SUPPORTED_EXPORT_FORMAT = "yolov8"

AOI_DEFECT_CLASSES = [
    "missing_component",
    "misalignment",
    "reversed_polarity",
    "bent_lead",
    "lifted_lead",
    "insufficient_solder",
    "solder_bridge",
    "solder_ball",
]

ROBOFLOW_ENV_VARS = {
    "api_key": "ROBOFLOW_API_KEY",
    "workspace": "AOI_DATASET_WORKSPACE",
    "project": "AOI_DATASET_PROJECT",
    "version": "AOI_DATASET_VERSION",
}


def _env(name: str, fallback: str | None = None) -> str | None:
    value = os.environ.get(name, fallback)
    return value.strip() if isinstance(value, str) else value


def _resolve_download_config(
    *,
    api_key: str | None,
    workspace: str | None,
    project: str | None,
    version: int | None,
) -> tuple[str, str, str, int]:
    resolved_api_key = api_key or _env(ROBOFLOW_ENV_VARS["api_key"])
    resolved_workspace = workspace or _env(ROBOFLOW_ENV_VARS["workspace"])
    resolved_project = project or _env(ROBOFLOW_ENV_VARS["project"])
    resolved_version_raw = version if version is not None else _env(ROBOFLOW_ENV_VARS["version"])

    missing = []
    if not resolved_api_key:
        missing.append(ROBOFLOW_ENV_VARS["api_key"])
    if not resolved_workspace:
        missing.append(ROBOFLOW_ENV_VARS["workspace"])
    if not resolved_project:
        missing.append(ROBOFLOW_ENV_VARS["project"])
    if resolved_version_raw in (None, ""):
        missing.append(ROBOFLOW_ENV_VARS["version"])

    if missing:
        missing_csv = ", ".join(missing)
        raise EnvironmentError(
            "Missing Roboflow download configuration. Set: "
            f"{missing_csv}"
        )

    try:
        resolved_version = int(resolved_version_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("AOI_DATASET_VERSION must be an integer") from exc

    return resolved_api_key, resolved_workspace, resolved_project, resolved_version


def download(
    *,
    api_key: str | None = None,
    workspace: str | None = None,
    project: str | None = None,
    version: int | None = None,
) -> Path:
    """
    Download a Roboflow dataset in YOLOv8 format.

    The target dataset must use the supported component/solder defect classes.
    """
    from roboflow import Roboflow

    resolved_api_key, resolved_workspace, resolved_project, resolved_version = _resolve_download_config(
        api_key=api_key,
        workspace=workspace,
        project=project,
        version=version,
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rf = Roboflow(api_key=resolved_api_key)
    dataset = (
        rf.workspace(resolved_workspace)
        .project(resolved_project)
        .version(resolved_version)
        .download(SUPPORTED_EXPORT_FORMAT, location=str(DATASET_DIR))
    )
    return Path(dataset.location)


def _split_image_files(image_dir: Path) -> list[Path]:
    return sorted(
        [
            *image_dir.glob("*.jpg"),
            *image_dir.glob("*.jpeg"),
            *image_dir.glob("*.png"),
            *image_dir.glob("*.webp"),
        ]
    )


def _count_class_distribution(root: Path) -> Counter[str]:
    distribution: Counter[str] = Counter()
    class_names = load_class_names(root)
    for split in EXPECTED_SPLITS:
        label_dir = root / split / "labels"
        if not label_dir.exists():
            continue
        for label_file in sorted(label_dir.glob("*.txt")):
            for line in label_file.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                try:
                    class_index = int(parts[0])
                except ValueError:
                    continue
                class_name = class_names.get(class_index, f"unknown_{class_index}")
                distribution[class_name] += 1
    return distribution


def verify(dataset_root: Path | None = None) -> dict[str, int]:
    """
    Count images and labels per split.

    Returns a ``{split: image_count}`` dict and prints a short summary.
    Missing datasets are handled gracefully.
    """
    root = dataset_root or DATASET_DIR
    counts: dict[str, int] = {}

    for split in EXPECTED_SPLITS:
        image_dir = root / split / "images"
        label_dir = root / split / "labels"

        if not image_dir.exists():
            print(f"  [WARN] Missing split: {split}/images")
            counts[split] = 0
            continue

        images = _split_image_files(image_dir)
        labels = sorted(label_dir.glob("*.txt")) if label_dir.exists() else []
        counts[split] = len(images)
        print(f"  {split}: {len(images)} images, {len(labels)} labels")

    total = sum(counts.values())
    if total > 0:
        distribution = _count_class_distribution(root)
        if distribution:
            print("  class distribution:")
            for class_name, instance_count in distribution.most_common():
                print(f"    {class_name}: {instance_count}")

    return counts


def get_data_yaml_path(dataset_root: Path | None = None) -> Path:
    root = dataset_root or DATASET_DIR
    data_yaml = root / "data.yaml"
    if data_yaml.exists():
        return data_yaml

    yaml_candidates = sorted(root.glob("*.yaml"))
    if yaml_candidates:
        return yaml_candidates[0]

    raise FileNotFoundError(f"No data.yaml found in {root}. Run dataset.download() first.")


def load_class_names(dataset_root: Path | None = None) -> dict[int, str]:
    """
    Parse class names from data.yaml without a YAML dependency.
    Supports standard YOLOv8 ``names: [..]`` or indexed blocks.
    """
    data_yaml = get_data_yaml_path(dataset_root)
    text = data_yaml.read_text(encoding="utf-8")
    names: dict[int, str] = {}

    inline_marker = "names:"
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(inline_marker) and "[" in stripped and "]" in stripped:
            inner = stripped.split("[", 1)[1].rsplit("]", 1)[0]
            items = [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
            return {index: item for index, item in enumerate(items)}
        if ":" in stripped and stripped.split(":", 1)[0].isdigit():
            key, value = stripped.split(":", 1)
            names[int(key)] = value.strip().strip("'\"")

    return names


def validate_supported_classes(dataset_root: Path | None = None) -> list[str]:
    """
    Return unsupported class names found in ``data.yaml``.
    """
    class_names = load_class_names(dataset_root).values()
    unsupported = sorted({name for name in class_names if name not in AOI_DEFECT_CLASSES})
    return unsupported


if __name__ == "__main__":
    print("Verifying existing dataset...")
    counts = verify()
    if sum(counts.values()) == 0:
        print("Dataset not found. Configure Roboflow env vars, then call dataset.download().")
    else:
        print(f"data.yaml: {get_data_yaml_path()}")
        unsupported = validate_supported_classes()
        if unsupported:
            print("Unsupported classes detected:")
            for class_name in unsupported:
                print(f"  - {class_name}")
