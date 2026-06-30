# Real Inference Integration Plan (DsPCBSD+ YOLOv8)

Goal: replace synthetic inference events with a **real trained YOLOv8 model** so the
observability pipeline monitors authentic CNN inference, and exercise all 9 anomaly
scenarios with the real model. Scope chosen: **real end-to-end path + controlled
fault-injection** for timing-only anomalies.

## Status

- ✅ **WS1** dataset normalizer — `ml/pipeline/dspcbsd_dataset.py`
- ✅ **WS2** trained model — **mAP@50 0.82** (baseline + channel_attention), Colab GPU notebook
- ✅ **WS3** inference runner wired — `src/aoi/inference_runner.py` (+ `BOARD_FAILURE`)
- ✅ **WS4** real-image corpus — `experiments/build_corpus.py`
- ✅ **WS5** all 9 scenarios re-pointed onto the real model + corpus
- 🔄 **WS6** live run + dashboards + write-up — see [WS6_RUNBOOK.md](WS6_RUNBOOK.md)

## Decisions (locked)

- **Dataset:** DsPCBSD+ — 9 trace-defect classes, 10,259 images / 20,276 instances,
  ships in YOLO + COCO format, CC-BY-4.0. Source: Kaggle
  (`enisteper1/dataset-of-pcb-surface-defects-dspcbsd`) or the Nature/Science Data Bank repo.
- **Taxonomy:** switch the thesis from solder/component defects → fabrication/trace
  defects. `defect_type` is a free-form string in `schema.py`, so this is a string swap,
  not a schema migration.
- **Authenticity framing:** the model quality is *not* the thesis headline (this is a
  monitoring thesis). Real inference + honest metrics + controlled injection for timing.

## Defect taxonomy mapping (DsPCBSD+ → schema `defect_type`)

| DsPCBSD+ class | schema `defect_type` |
|---|---|
| short (SH) | `SHORT` |
| spur (SP) | `SPUR` |
| spurious copper (SC) | `SPURIOUS_COPPER` |
| open (OP) | `OPEN_CIRCUIT` |
| mouse bite (MB) | `MOUSE_BITE` |
| hole breakout (HB) | `HOLE_BREAKOUT` |
| conductor scratch (CS) | `CONDUCTOR_SCRATCH` |
| conductor foreign object (CFO) | `CONDUCTOR_FOREIGN_OBJECT` |
| base material foreign object (BMFO) | `BASE_MATERIAL_FOREIGN_OBJECT` |
| (nothing above threshold) | `NO_DEFECT` (→ PASS) |

> The class-map keys must match the *exact* `names:` spelling in the downloaded
> `data.yaml`. Confirm after download before wiring `inference_runner`.

## Current-state facts this plan relies on

- Pipeline is event-driven: everything flows through `POST /events` → JSONL → Promtail
  → Loki → Grafana. Nothing downstream cares whether events are mock or real.
- `src/aoi/inference_runner.py` already runs real YOLO via ultralytics but is (a) not
  wired to anything, (b) pointed at a non-existent `ml/models/best.pt`, and (c) has a
  defect-class map that would crash on any real model. All three get fixed here.
- `ml/pipeline/component_train.py` is variant-aware and takes `--dataset-root`; it reads
  classes from `data.yaml`. It generalizes to DsPCBSD+ with no code change.
- Two venvs: `.venv` (dev/API/tests), `venv` (ML/ultralytics). Inference runs in the ML
  venv and POSTs to the API over HTTP — clean separation, no env merge needed.
  (`venv_broken_lzma_20260531` is dead; remove it.)

## Workstreams

### 1. Dataset acquisition + prep  *(critical path)*
- Download DsPCBSD+ into `ml/data/dspcbsd_plus/`.
- Ensure/author `data.yaml` (`path`, `train/val/test`, `nc: 9`, `names:`). If only one
  split ships, create an 80/10/10 split (seeded).
- Add `ml/pipeline/dspcbsd_dataset.py` (download verify + split + manifest) mirroring the
  existing `component_dataset.py` reporting style → `ml/reports/defect_detection/`.

### 2. Train the real defect model
- `python -m ml.pipeline.component_train --variant baseline --dataset-root ml/data/dspcbsd_plus`
  → `ml/models/defect_detection/best-baseline.pt`.
- Also train `--variant channel_attention` (feeds S09 + the attention-contribution story).
- Keep an under-trained checkpoint (`epoch0.pt`) for S09 degradation.
- Evaluate on the held-out test split → `metrics_summary.json`, confusion matrix, PR/F1
  curves (reuse `component_evaluate.py`). **Report honest mAP/precision/recall.**
- **Compute note:** 10k images on CPU is many hours. The dataset is already on Kaggle —
  train on a Kaggle/Colab GPU, download `best.pt` back. Plumbing (WS3) can proceed in
  parallel using `yolov8s.pt` as a stand-in.

### 3. Fix + wire `inference_runner.py`
- Fix `_default_weights_path()` → `ml/models/defect_detection/best.pt` (keep a fallback).
- Replace `DATASET_TO_SCHEMA_DEFECT` with the 9-class map above.
- Update `MODEL_VERSION` → e.g. `yolov8s-dspcbsd-v1`.
- Add a **batch driver**: `run_inference_dir(image_dir, ...)` that runs the model over a
  folder and POSTs events to `/events` — same pattern the scenarios already use.
- Expose via a CLI subcommand (`aoi run-inference --image-dir ... --variant ...`).
- Keep the unsupported-class guard (with a complete map it won't fire; it catches drift).

### 4. Real-image corpus
- `corpus/good/` — defect-free DsPCBSD+ templates (PASS baseline).
- `corpus/defective/` — DsPCBSD+ test defectives (real FAILs, with GT labels).
- `corpus/degraded/` — blurred/noisy/downscaled variants of good images (S04). Add a
  small generator script.
- `corpus/corrupt/` — truncated/blank/zero-byte images (S06 error path).
- Your own boards → `board_dataset/showcase/` for **qualitative** thesis captures only
  (no GT labels → not used for metrics).

### 5. Re-point the 9 scenarios to the real model
Scenarios keep their `ScenarioResult` + observability shape; they now call the real
inference driver over a chosen folder / model variant instead of hardcoding events.

| # | Scenario | Real-AI driver | Type |
|---|---|---|---|
| S01 | Normal baseline | model over `corpus/good` | Real |
| S02 | High defect rate | model over `corpus/defective` | Real input |
| S03 | Latency spike | real latency + induced CPU load / larger `imgsz`; inject offset fallback | Hybrid |
| S04 | Confidence drop | model over `corpus/degraded` (real lower confidence) | Real |
| S05 | Missing/open defect | model over OPEN/missing-hole images | Real |
| S06 | Board failure | model over `corpus/corrupt` → no detections / error → board FAIL | Real |
| S07 | Recovery | sequence defective → good (fail-rate up then down) | Real ordering |
| S08 | Intermittent fault | randomly interleave good/defective | Real scheduling |
| S09 | Model degradation | `best.pt` vs `epoch0.pt` (or baseline vs channel_attention) on same images | Real |

→ 8 of 9 genuinely real; only S03 timing may be injected.

### 6. Testing & validation (three layers)
1. **Unit/integration (pytest, dev venv):**
   - class-map completeness: every dataset class → a schema string.
   - `run_inference` on a fixture image with a *mocked* YOLO model → valid `InferenceEvent`s
     (keeps ultralytics out of CI).
   - new `defect_type` strings pass schema validation.
   - scenario drivers emit valid `/events` payloads against a fake endpoint.
2. **End-to-end smoke (ML venv + running stack):**
   - bring up docker stack + API; run driver over a small real folder; confirm events in
     Loki via LogQL and overlays in the React review UI.
3. **Full experiment suite (thesis evaluation):**
   - `python -m experiments.runner` over all 9 with the real model; capture Grafana per
     scenario; record real fail-rate, confidence histograms, latency p50/p95; regenerate
     the evaluation report (`experiments/report.py`).
   - **Accuracy evidence:** since the DsPCBSD+ test split is labeled, report real
     mAP/precision/recall — this is the "authenticated AI" proof for the thesis.

## Sequencing / critical path
- **P1** dataset download + `data.yaml` + taxonomy constants — ~half day.
- **P2** train baseline + channel_attention + eval (GPU) — GPU-bound.
- **P3** fix+wire `inference_runner` + CLI driver (stand-in weights) — ~half day, parallel to P2.
- **P4** corpus prep + degraded/corrupt generators — ~half day.
- **P5** re-point 9 scenarios → real driver — ~1 day.
- **P6** 3-layer tests + full suite + dashboard capture + report — ~1–2 days.

## Thesis write-up deltas
- Revise `ml/README.md` scope paragraph: solder/component → fabrication/trace defects.
- Replace "mock events" language with "real inference; controlled injection for timing."
- Add real confusion matrix, PR/F1 curves, latency histogram, and the mock-vs-real
  structural-equivalence note (pipeline identical, signals now authentic).
