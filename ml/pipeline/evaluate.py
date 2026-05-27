"""Evaluation entry point for the AOI detection model."""
from __future__ import annotations

from pathlib import Path

from ml.pipeline.dataset import AOI_DEFECT_CLASSES, get_data_yaml_path
from ml.pipeline.train import get_latest_weights

EVAL_DIR = Path(__file__).resolve().parent.parent / "models" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)


def evaluate(weights_path: Path | None = None, split: str = "test") -> dict[str, object]:
    """Run YOLO validation and return aggregate plus per-class metrics."""
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

    per_class: dict[str, dict[str, float]] = {}
    for index, class_name in enumerate(AOI_DEFECT_CLASSES):
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

    print("\n-- Evaluation Results --")
    print(f"  mAP@50:      {result['map50']:.4f}")
    print(f"  mAP@50-95:   {result['map50_95']:.4f}")
    print(f"  Precision:   {result['precision']:.4f}")
    print(f"  Recall:      {result['recall']:.4f}")
    for class_name, stats in per_class.items():
        print(f"  {class_name:<22} F1={stats['f1']:.3f} AP50={stats['ap50']:.3f}")

    _save_metrics_chart(per_class)
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

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#1D9E75" if score >= 0.75 else "#EF9F27" if score >= 0.5 else "#E24B4A" for score in f1_scores]
    ax.bar(names, f1_scores, color=colors, edgecolor="none")
    ax.axhline(0.75, color="#1D9E75", linestyle="--", linewidth=0.8, label="target (0.75)")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("F1 Score")
    ax.set_title("Per-class F1 - component/solder AOI test set")
    ax.legend()
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()

    out = EVAL_DIR / "f1_per_class.png"
    plt.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Chart saved: {out}")


if __name__ == "__main__":
    evaluate()
