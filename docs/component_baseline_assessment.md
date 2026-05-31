# Component Baseline Assessment

Last updated: 2026-05-31

## Scope

This note summarizes the current component-detection-first baseline while real AOI images are still being collected.

The active taxonomy is the reduced 6-class profile:

- `resistor`
- `capacitor`
- `connector`
- `ic`
- `led`
- `other`

## Overall Result

Held-out `test` split metrics for the current trained model:

- `mAP@50`: `0.0953`
- `mAP@50-95`: `0.0617`
- `precision`: `0.2057`
- `recall`: `0.1581`

Compared with the earlier 20-class baseline:

- baseline `mAP@50`: `0.0044`
- current `mAP@50`: `0.0953`
- delta: `+0.0909`

This is a clear improvement, but still far below a production threshold.

## Per-Class Interpretation

Current strongest classes:

- `ic`: AP50 `0.379`
- `other`: AP50 `0.109`
- `capacitor`: AP50 `0.053`

Current weakest classes:

- `resistor`
- `led`
- `connector`

Interpretation:

- `ic` performs best because packages are visually larger and more distinct.
- `other` is working as intended: it absorbs long-tail component families without forcing the model to learn many fragile rare classes.
- Dense small-part classes remain hard because the seed dataset is limited in board diversity, camera geometry, and real AOI appearance.

## Confusion Matrix and Curves

Key artifact locations:

- Confusion matrix: `ml/models/component_detection/eval/results-2/confusion_matrix.png`
- Normalized confusion matrix: `ml/models/component_detection/eval/results-2/confusion_matrix_normalized.png`
- Precision-recall curve: `ml/models/component_detection/eval/results-2/BoxPR_curve.png`
- Precision curve: `ml/models/component_detection/eval/results-2/BoxP_curve.png`
- Recall curve: `ml/models/component_detection/eval/results-2/BoxR_curve.png`
- F1 curve: `ml/models/component_detection/eval/results-2/BoxF1_curve.png`

These should be reviewed together, not in isolation:

- confusion matrix for where the model is mixing classes
- PR curves for class separability
- F1 behavior for threshold sensitivity

## Inference Latency

The evaluation pipeline now benchmarks inference on the split images and persists the summary in:

- `ml/models/component_detection/eval/latest_metrics_summary.json`

This gives:

- mean latency per image
- median latency
- p95 latency
- min/max latency

Latency should be tracked alongside accuracy because CPU-only AOI fallback is a real deployment scenario.

## Conclusion

The current trained model is useful as a technical proof that:

- the component-first pipeline works
- the reduced taxonomy is better than the original noisy 20-class setup
- the repo can now generate measurable, reportable component-detection baselines

The next major gain will not come from minor hyperparameter tuning. It will come from real PCB images captured in the actual AOI environment, labeled using this reduced class scheme.
