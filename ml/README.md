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
python3 -m venv .venv
source .venv/bin/activate
pip install -r ml/requirements-ml-cpu.txt
python ml/pipeline/self_test.py
```

Package files:

- `ml/requirements-ml.txt`: shared ML dependencies without PyTorch wheel selection
- `ml/requirements-ml-cpu.txt`: CPU-safe install path for PyTorch + shared ML dependencies

If you need GPU wheels later, install `torch` and `torchvision` explicitly for the target CUDA version, then install:

```bash
pip install -r ml/requirements-ml.txt
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
