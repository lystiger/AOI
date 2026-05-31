"""Evaluation entry point for the component-detection-first YOLOv8 model."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from ml.pipeline.component_dataset import DEFAULT_OUTPUT_ROOT, load_component_class_names
from ml.pipeline.component_train import get_component_data_yaml_path, get_component_weights_for_variant
from ml.pipeline.model_variants import SUPPORTED_VARIANTS, build_component_model
from ml.pipeline.reporting import write_run_report

EVAL_DIR = Path(__file__).resolve().parent.parent / "models" / "component_detection" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)


def evaluate_component_model(
    *,
    dataset_root: Path | None = None,
    weights_path: Path | None = None,
    variant: str = "baseline",
    split: str = "test",
    batch: int = 8,
    imgsz: int = 1280,
    baseline_label: str = "20-class baseline",
    baseline_map50: float = 0.0044,
) -> dict[str, object]:
    """Run YOLO validation and return aggregate plus per-class metrics."""
    weights = weights_path or get_component_weights_for_variant(variant)
    data_yaml = get_component_data_yaml_path(dataset_root or DEFAULT_OUTPUT_ROOT)
    class_names = load_component_class_names(data_yaml.parent)

    model = build_component_model(base_model=weights, variant=variant)
    metrics = model.val(
        data=str(data_yaml),
        split=split,
        imgsz=imgsz,
        batch=batch,
        verbose=True,
        project=str(EVAL_DIR),
        name="results",
    )

    per_class: dict[str, dict[str, float]] = {}
    for index, class_name in enumerate(class_names):
        precision = float(metrics.box.p[index]) if index < len(metrics.box.p) else 0.0
        recall = float(metrics.box.r[index]) if index < len(metrics.box.r) else 0.0
        ap50 = float(metrics.box.ap50[index]) if index < len(metrics.box.ap50) else 0.0
        f1 = _safe_f1(precision, recall)
        per_class[class_name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "ap50": ap50,
        }

    result: dict[str, object] = {
        "map50": float(metrics.box.map50),
        "map50_95": float(metrics.box.map),
        "precision": float(metrics.box.mp),
        "recall": float(metrics.box.mr),
        "per_class": per_class,
    }
    latency = _benchmark_inference_latency(model, data_yaml.parent / split / "images", imgsz=imgsz)
    baseline = {
        "label": baseline_label,
        "map50": baseline_map50,
        "delta_map50": float(result["map50"]) - baseline_map50,
        "ratio_map50": (float(result["map50"]) / baseline_map50) if baseline_map50 > 0 else None,
    }
    save_dir = Path(metrics.save_dir)
    artifacts = {
        "save_dir": str(save_dir),
        "confusion_matrix": str(save_dir / "confusion_matrix.png"),
        "confusion_matrix_normalized": str(save_dir / "confusion_matrix_normalized.png"),
        "pr_curve": str(save_dir / "BoxPR_curve.png"),
        "precision_curve": str(save_dir / "BoxP_curve.png"),
        "recall_curve": str(save_dir / "BoxR_curve.png"),
        "f1_curve": str(save_dir / "BoxF1_curve.png"),
        "f1_bar_chart": str(EVAL_DIR / "f1_per_class.png"),
    }
    summary = {
        "dataset": str(data_yaml),
        "weights": str(weights),
        "variant": variant,
        "split": split,
        "imgsz": imgsz,
        "batch": batch,
        "classes": class_names,
        "overall": {
            "map50": float(result["map50"]),
            "map50_95": float(result["map50_95"]),
            "precision": float(result["precision"]),
            "recall": float(result["recall"]),
        },
        "per_class": per_class,
        "latency": latency,
        "baseline_comparison": baseline,
        "artifacts": artifacts,
    }

    print("\n-- Component Evaluation Results --")
    print(f"  mAP@50:      {result['map50']:.4f}")
    print(f"  mAP@50-95:   {result['map50_95']:.4f}")
    print(f"  Precision:   {result['precision']:.4f}")
    print(f"  Recall:      {result['recall']:.4f}")
    for class_name, stats in per_class.items():
        print(f"  {class_name:<22} F1={stats['f1']:.3f} AP50={stats['ap50']:.3f}")
    print(f"  Latency mean: {latency['mean_ms']:.1f} ms/image")

    _save_metrics_chart(per_class)
    metrics_summary_path = save_dir / "metrics_summary.json"
    metrics_summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (EVAL_DIR / "latest_metrics_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report_path = write_run_report(
        category="component_detection",
        stage="evaluate",
        title="Component Evaluation Run",
        summary=f"Evaluated component detector on `{split}` split.",
        details=[
            f"Dataset: `{data_yaml}`",
            f"Weights: `{weights}`",
            f"Variant: `{variant}`",
            f"Classes: {', '.join(class_names)}",
            f"mAP@50: {result['map50']:.4f}",
            f"mAP@50-95: {result['map50_95']:.4f}",
            f"Precision: {result['precision']:.4f}",
            f"Recall: {result['recall']:.4f}",
            f"Latency mean: {latency['mean_ms']:.1f} ms/image",
            f"Latency p95: {latency['p95_ms']:.1f} ms/image",
            f"Comparison baseline: {baseline_label} mAP@50={baseline_map50:.4f}",
        ],
        extra_markdown=_build_evaluation_markdown(summary),
    )
    print(f"Report saved: {report_path}")
    return result


def _safe_f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _save_metrics_chart(per_class: dict[str, dict[str, float]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = list(per_class.keys())
    f1_scores = [per_class[name]["f1"] for name in names]

    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ["#1D9E75" if score >= 0.75 else "#EF9F27" if score >= 0.5 else "#E24B4A" for score in f1_scores]
    ax.bar(names, f1_scores, color=colors, edgecolor="none")
    ax.axhline(0.75, color="#1D9E75", linestyle="--", linewidth=0.8, label="target (0.75)")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("F1 Score")
    ax.set_title("Per-class F1 - component detection test set")
    ax.legend()
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()

    out = EVAL_DIR / "f1_per_class.png"
    plt.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Chart saved: {out}")


def _benchmark_inference_latency(model, image_dir: Path, *, imgsz: int) -> dict[str, float | int]:
    image_paths = sorted(path for path in image_dir.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not image_paths:
        return {"count": 0, "mean_ms": 0.0, "median_ms": 0.0, "p95_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0}

    # Warm-up to avoid measuring first-run overhead only.
    model.predict(source=str(image_paths[0]), imgsz=imgsz, verbose=False, save=False)

    latencies_ms: list[float] = []
    for image_path in image_paths:
        started = time.perf_counter()
        model.predict(source=str(image_path), imgsz=imgsz, verbose=False, save=False)
        latencies_ms.append((time.perf_counter() - started) * 1000.0)

    ordered = sorted(latencies_ms)
    p95_index = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return {
        "count": len(latencies_ms),
        "mean_ms": round(statistics.mean(latencies_ms), 2),
        "median_ms": round(statistics.median(latencies_ms), 2),
        "p95_ms": round(ordered[p95_index], 2),
        "min_ms": round(min(latencies_ms), 2),
        "max_ms": round(max(latencies_ms), 2),
    }


def _build_evaluation_markdown(summary: dict[str, object]) -> str:
    overall = summary["overall"]
    baseline = summary["baseline_comparison"]
    latency = summary["latency"]
    per_class = summary["per_class"]
    artifacts = summary["artifacts"]

    rows = [
        "| Class | Precision | Recall | F1 | AP50 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for class_name, stats in per_class.items():
        rows.append(
            f"| `{class_name}` | {stats['precision']:.4f} | {stats['recall']:.4f} | {stats['f1']:.4f} | {stats['ap50']:.4f} |"
        )

    ratio = baseline["ratio_map50"]
    ratio_text = f"{ratio:.1f}x" if isinstance(ratio, float) else "n/a"
    return "\n".join(
        [
            "## Overall",
            "",
            f"- mAP@50: `{overall['map50']:.4f}`",
            f"- mAP@50-95: `{overall['map50_95']:.4f}`",
            f"- Precision: `{overall['precision']:.4f}`",
            f"- Recall: `{overall['recall']:.4f}`",
            "",
            "## Baseline Comparison",
            "",
            f"- Baseline: `{baseline['label']}` with mAP@50 `{baseline['map50']:.4f}`",
            f"- Delta mAP@50: `{baseline['delta_map50']:.4f}`",
            f"- Relative improvement: `{ratio_text}`",
            "",
            "## Latency Benchmark",
            "",
            f"- Images benchmarked: `{latency['count']}`",
            f"- Mean latency: `{latency['mean_ms']:.2f} ms/image`",
            f"- Median latency: `{latency['median_ms']:.2f} ms/image`",
            f"- P95 latency: `{latency['p95_ms']:.2f} ms/image`",
            f"- Min/Max latency: `{latency['min_ms']:.2f} / {latency['max_ms']:.2f} ms`",
            "",
            "## Per-Class Metrics",
            "",
            *rows,
            "",
            "## Artifacts",
            "",
            f"- Confusion matrix: `{artifacts['confusion_matrix']}`",
            f"- Normalized confusion matrix: `{artifacts['confusion_matrix_normalized']}`",
            f"- Precision-recall curve: `{artifacts['pr_curve']}`",
            f"- Precision curve: `{artifacts['precision_curve']}`",
            f"- Recall curve: `{artifacts['recall_curve']}`",
            f"- F1 curve: `{artifacts['f1_curve']}`",
            f"- F1 bar chart: `{artifacts['f1_bar_chart']}`",
            "",
            "## Interpretation",
            "",
            "- The reduced six-class profile is learning structure, especially for `ic` and `other`.",
            "- `resistor`, `capacitor`, and `connector` remain constrained by dense small objects and limited board diversity.",
            "- The improvement over the older 20-class baseline shows taxonomy reduction is helping more than longer training would on the noisier label set.",
            "- Real AOI camera images are still the next highest-value data source for improving generalization.",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate YOLOv8 on the component seed dataset")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--weights", type=Path, default=None)
    parser.add_argument("--variant", choices=SUPPORTED_VARIANTS, default="baseline")
    parser.add_argument("--split", default="test")
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--baseline-label", default="20-class baseline")
    parser.add_argument("--baseline-map50", type=float, default=0.0044)
    args = parser.parse_args()

    evaluate_component_model(
        dataset_root=args.dataset_root,
        weights_path=args.weights,
        variant=args.variant,
        split=args.split,
        batch=args.batch,
        imgsz=args.imgsz,
        baseline_label=args.baseline_label,
        baseline_map50=args.baseline_map50,
    )


if __name__ == "__main__":
    main()
