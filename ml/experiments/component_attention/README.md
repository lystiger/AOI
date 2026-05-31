# Component Attention Experiments

This folder scaffolds the three controlled thesis experiments for PCB component detection.

Experiment set:

- `e1_baseline.yaml`: unmodified YOLOv8s
- `e2_channel_attention.yaml`: YOLOv8s with channel attention only
- `e3_full_cbam.yaml`: YOLOv8s with full CBAM

The purpose is not to lock the final hyperparameters prematurely. It is to make the experiment matrix explicit and reproducible.

Common rules:

- use the same dataset split for all runs
- keep optimizer, epochs, image size, augmentation, and evaluation thresholds aligned unless the thesis explicitly studies them
- change only the attention variant between E1, E2, and E3

Suggested execution flow:

1. Confirm the baseline path with `e1_baseline.yaml`
2. Implement and run channel attention only with `e2_channel_attention.yaml`
3. Implement and run full CBAM with `e3_full_cbam.yaml`
4. Compare all three in one shared result table
