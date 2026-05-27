# AOI ML Pipeline

This directory contains the isolated ML workflow for AOI defect detection.

Scope:
- visible component defects
- visible lead defects
- visible solder defects

Excluded:
- bare copper trace defects
- etching/fabrication line defects
- routing-level open/short defects that are not visible as component or solder faults

Supported defect labels:
- `missing_component`
- `misalignment`
- `reversed_polarity`
- `bent_lead`
- `lifted_lead`
- `insufficient_solder`
- `solder_bridge`
- `solder_ball`

Quick start:

```bash
pip install -r ml/requirements-ml.txt
python ml/pipeline/self_test.py
```

To download a dataset from Roboflow, configure:

```bash
export ROBOFLOW_API_KEY=...
export AOI_DATASET_WORKSPACE=...
export AOI_DATASET_PROJECT=...
export AOI_DATASET_VERSION=...
```

Then run:

```bash
python -m ml.pipeline.dataset
python -m ml.pipeline.train --device cpu
python -m ml.pipeline.evaluate
```
