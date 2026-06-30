# AOI ML Pipeline

This directory contains the isolated ML workflow for AOI defect detection.

> **Direction update:** the real defect detector targets **PCB fabrication / trace
> defects** using the **DsPCBSD+** dataset (CC-BY-4.0). The earlier component-detection
> pipeline (resistor/capacitor/… on the WACV/Roboflow seeds) remains in the repo as
> baseline tooling but is superseded by the defect model. See
> `docs/implementation/REAL_INFERENCE_INTEGRATION_PLAN.md`.

Defect detector scope (DsPCBSD+ fabrication/trace defects):

Supported defect labels (model classes — abbreviation → schema `defect_type`):
- `SH`   → `SHORT`
- `SP`   → `SPUR`
- `SC`   → `SPURIOUS_COPPER`
- `OP`   → `OPEN_CIRCUIT`
- `MB`   → `MOUSE_BITE`
- `HB`   → `HOLE_BREAKOUT`
- `CS`   → `CONDUCTOR_SCRATCH`
- `CFO`  → `CONDUCTOR_FOREIGN_OBJECT`
- `BMFO` → `BASE_MATERIAL_FOREIGN_OBJECT`

Defect-detector quick start:

```bash
# build dataset (deterministic split), then train on Colab GPU (see ml/notebooks/colab_train_dspcbsd.ipynb)
python -m ml.pipeline.dspcbsd_dataset --source-root <unzipped DsPCBSD+> --output-root ml/data/dspcbsd_plus --overwrite
# run real inference over a folder of boards
python -m aoi.inference_runner --image-dir <folder> --dry-run
```

---

Legacy component-detection pipeline (baseline tooling):

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
python -m ml.pipeline.component_dataset --profile reduced --overwrite
python -m ml.pipeline.component_train --variant baseline --device cpu
python -m ml.pipeline.component_evaluate --variant baseline --split test
```

Notebook split:

- Defect-first notebooks: `ml/notebooks/01_dataset_explore.ipynb` through `04_evaluation.ipynb`
- Component-first notebooks: `ml/notebooks/11_component_dataset_explore.ipynb`, `12_component_training.ipynb`, `13_component_evaluation.ipynb`

Component-detection seed dataset:

- `python -m ml.pipeline.component_dataset --profile reduced --overwrite`
- Source: `docs/references/pcb_wacv_2019/pcb_wacv_2019`
- Output: `ml/data/component_detection_seed`
- Purpose: convert the WACV 2019 PCB annotations into a YOLOv8-ready board-level dataset with normalized component classes

Class normalization rules:

- Reduced profile keeps: `resistor`, `capacitor`, `connector`, `ic`, `led`, `other`
- Full profile keeps: `resistor`, `capacitor`, `inductor`, `diode`, `led`, `ic`, `transistor`, `connector`, `jumper`, `emi_filter`, `button`, `clock`, `transformer`, `potentiometer`, `heatsink`, `fuse`, `ferrite_bead`, `buzzer`, `display`, `battery`
- Drops annotation noise such as silkscreen text, pads, pins, test points, and unknown labels
- In reduced mode, any supported component outside the core classes is collapsed into `other`
- Maps aliases such as `electrolytic capacitor -> capacitor`, `ferrite bead -> ferrite_bead`, `emi filter -> emi_filter`, `zener -> diode`, `switch -> button`

When your real AOI images are ready, label them with the same normalized class set so they can be merged into `component_detection_seed` without changing downstream training code.

Run reports:

- Component dataset builds, training runs, and evaluations each write a small Markdown report under `ml/reports/component_detection/`

Model variants:

- `baseline`: unmodified YOLOv8s
- `channel_attention`: wraps selected backbone `C2f` blocks with channel attention
- `full_cbam`: wraps selected backbone `C2f` blocks with full CBAM
