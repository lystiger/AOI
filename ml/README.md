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
# Repo/dev environment for tests and API work
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Separate ML environment
python3 -m venv venv
source venv/bin/activate
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
python -m ml.pipeline.component_dataset --overwrite
python -m ml.pipeline.train --device cpu
python -m ml.pipeline.evaluate
```

Component-first baseline:

```bash
source venv/bin/activate
python -m ml.pipeline.component_dataset --overwrite
python -m ml.pipeline.component_train --device cpu
python -m ml.pipeline.component_evaluate --split test
```

Notebook split:

- Defect-first notebooks: `ml/notebooks/01_dataset_explore.ipynb` through `04_evaluation.ipynb`
- Component-first notebooks: `ml/notebooks/11_component_dataset_explore.ipynb`, `12_component_training.ipynb`, `13_component_evaluation.ipynb`

Component-detection seed dataset:

- `python -m ml.pipeline.component_dataset --overwrite`
- Source: `docs/references/pcb_wacv_2019/pcb_wacv_2019`
- Output: `ml/data/component_detection_seed`
- Purpose: convert the WACV 2019 PCB annotations into a YOLOv8-ready board-level dataset with normalized component classes

Class normalization rules:

- Keeps: `resistor`, `capacitor`, `inductor`, `diode`, `led`, `ic`, `transistor`, `connector`, `jumper`, `emi_filter`, `button`, `clock`, `transformer`, `potentiometer`, `heatsink`, `fuse`, `ferrite_bead`, `buzzer`, `display`, `battery`
- Drops annotation noise such as silkscreen text, pads, pins, test points, and unknown labels
- Maps aliases such as `electrolytic capacitor -> capacitor`, `ferrite bead -> ferrite_bead`, `emi filter -> emi_filter`, `zener -> diode`, `switch -> button`

When your real AOI images are ready, label them with the same normalized class set so they can be merged into `component_detection_seed` without changing downstream training code.
