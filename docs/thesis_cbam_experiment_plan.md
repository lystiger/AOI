# Thesis CBAM Experiment Plan

Last updated: 2026-05-31

## Title

Attention-Augmented YOLOv8 for PCB Component and Defect-Focused Inspection

## Objective

This experiment plan evaluates whether attention mechanisms improve YOLOv8 performance on PCB inspection imagery, especially where targets are:

- small
- visually sparse
- easily overwhelmed by repetitive background structure

The central thesis claim to test is:

> Adding attention to the YOLOv8 backbone improves the model's ability to focus on informative PCB regions and yields better detection quality than the baseline architecture under the same training protocol.

## Architecture Variants

Three controlled experiments are proposed:

| Experiment ID | Variant | Description |
| --- | --- | --- |
| E1 | Baseline YOLOv8s | unmodified baseline detector |
| E2 | YOLOv8s + Channel Attention | backbone with channel attention only |
| E3 | YOLOv8s + Full CBAM | backbone with channel + spatial attention |

Reference architecture figure:

- `docs/pics/cbam_yolov8_novel_arch.svg`

## Hypotheses

### H1: Channel Attention

Channel attention will improve feature selection by amplifying relevant PCB component/defect responses and suppressing noisy feature maps.

Expected effect:

- moderate improvement over baseline
- limited latency increase

### H2: Full CBAM

Full CBAM will further improve localization by combining channel selection with spatial attention over sparse defect/component regions.

Expected effect:

- best accuracy among the three variants
- slightly higher inference cost than channel attention only

## Controlled Variables

To keep the ablation valid, the following must remain fixed across all three experiments:

- same train/validation/test split
- same class taxonomy
- same preprocessing
- same augmentation policy
- same optimizer and scheduler
- same number of epochs
- same image size
- same confidence threshold and NMS policy during evaluation
- same hardware or clearly documented hardware differences

## Dataset Notes

The experiment can be run in two modes:

### Mode A: Internal Engineering Benchmark

Use the reduced local taxonomy:

- `resistor`
- `capacitor`
- `connector`
- `ic`
- `led`
- `other`

This supports practical AOI iteration and internal comparison between E1, E2, and E3.

### Mode B: Benchmark-Reproducible Study

Use the original benchmark taxonomy/protocol if the thesis intends to compare against published work on `pcb_wacv_2019`.

Important:

- internal reduced-taxonomy runs are valid for local ablation
- they are not directly comparable to published SOTA unless the benchmark protocol is matched

## Evaluation Metrics

Each experiment should report:

- mAP@50
- mAP@50-95
- precision
- recall
- per-class precision
- per-class recall
- per-class F1
- per-class AP50
- confusion matrix
- normalized confusion matrix
- precision-recall curve
- inference latency mean
- inference latency median
- inference latency p95

## Results Table Template

| Variant | mAP@50 | mAP@50-95 | Precision | Recall | Mean Latency (ms/img) | P95 Latency (ms/img) | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| E1 Baseline YOLOv8s |  |  |  |  |  |  |  |
| E2 + Channel Attention |  |  |  |  |  |  |  |
| E3 + Full CBAM |  |  |  |  |  |  |  |

## Per-Class Table Template

Create one table per experiment or one combined comparison table:

| Class | Precision | Recall | F1 | AP50 |
| --- | ---: | ---: | ---: | ---: |
| resistor |  |  |  |  |
| capacitor |  |  |  |  |
| connector |  |  |  |  |
| ic |  |  |  |  |
| led |  |  |  |  |
| other |  |  |  |  |

## Analysis Questions

When writing the thesis discussion, answer these explicitly:

1. Does channel attention improve over the baseline?
2. Does full CBAM improve further over channel attention alone?
3. Which classes benefit most from attention?
4. Is the accuracy gain worth the latency cost?
5. Does attention help larger structured parts more than dense small passive parts?
6. Are improvements consistent across both validation and test splits?

## Interpretation Guide

### If E2 > E1 and E3 > E2

This supports the thesis claim that progressively richer attention improves PCB-focused detection.

### If E2 > E1 but E3 ≈ E2 or worse

This suggests channel selection helps, but spatial attention may be too costly or unnecessary for the current dataset scale.

### If all three are similar

This suggests the main bottleneck is data quality/domain mismatch rather than architecture.

### If E3 improves accuracy but latency increases significantly

This creates a useful engineering trade-off discussion rather than a failed result.

## Minimum Artifact Checklist

For each experiment, save:

- run manifest
- training curves
- confusion matrix
- PR curves
- latency summary
- markdown evaluation report

## Thesis Write-Up Outline

Suggested subsection structure:

1. Problem Motivation
2. Baseline YOLOv8 Architecture
3. Proposed Attention Modification
4. Experimental Design
5. Results
6. Discussion of Accuracy vs Latency Trade-Off
7. Threats to Validity

## Threats to Validity

Document these explicitly:

- reduced class taxonomy may not match published benchmark taxonomy
- seed dataset may not match real AOI imaging conditions
- small dataset size may limit architectural conclusions
- latency measured on CPU may differ significantly from deployment hardware

## Recommended Next Step

Implement E2 first before E3.

Reason:

- it isolates the contribution of channel attention
- it reduces implementation complexity
- it gives a cleaner intermediate ablation point before adding full CBAM
