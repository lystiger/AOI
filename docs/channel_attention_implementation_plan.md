# Channel Attention Implementation Plan

Last updated: 2026-05-31

## Goal

Implement the E2 experiment first:

- baseline: existing `YOLOv8s`
- variant: `YOLOv8s + channel attention only`

This is the safest first code step before full CBAM because it isolates one mechanism and lowers implementation risk.

## Repository-Level Strategy

The current repository already has:

- dataset preparation
- component training/evaluation entry points
- reporting
- baseline metrics

What is missing is the model-variant layer.

Recommended implementation approach:

1. Add a small model-variant abstraction in `ml/pipeline/`
2. Keep the existing training CLI intact
3. Introduce a variant selector such as:
   - `baseline`
   - `channel_attention`
   - `full_cbam`

## Minimal Code Plan

### Step 1: Add Attention Module Definitions

Create a file such as:

- `ml/pipeline/attention_modules.py`

Add:

- channel attention block
- spatial attention block
- CBAM wrapper

For E2, only the channel attention block needs to be active.

### Step 2: Add Backbone Injection Logic

Create a file such as:

- `ml/pipeline/model_variants.py`

Responsibilities:

- load YOLOv8 base model
- identify target backbone `C2f` blocks
- wrap or replace them with attention-augmented modules

Important constraint:

- do not modify the PANet neck or detection head for E2

### Step 3: Extend Training Entry Point

Update the component training path to accept:

- `--variant baseline`
- `--variant channel_attention`
- later `--variant full_cbam`

The run manifest should record the chosen variant.

### Step 4: Extend Evaluation Reporting

Evaluation should also record:

- variant name
- insertion points
- latency effect relative to baseline

## Recommended Insertion Scope

Start with channel attention after selected backbone `C2f` stages only.

Do not scatter attention everywhere initially.

Reason:

- easier ablation
- easier debugging
- lower latency risk
- cleaner thesis story

## Validation Checklist

Before claiming E2 results:

- confirm tensor shapes are unchanged through the model
- confirm training still converges
- confirm evaluation artifacts still generate
- compare E2 directly against E1 using the same split and hyperparameters

## Expected Outcome

Best-case outcome:

- improved mAP and per-class F1
- modest latency increase

Acceptable outcome:

- no major gain, but a clean negative result with controlled methodology

Either way, it is still thesis-valid because the contribution is the ablation itself, not only a positive accuracy jump.
