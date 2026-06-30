# WS6 Runbook — Real-Model Evaluation & Write-Up

Everything up to here (WS1–WS5) is done and on `main`: real DsPCBSD+ model (mAP@50 0.82),
wired inference runner, real-image corpus, and all 9 scenarios driven by the real model.
WS6 is **running** the suite against the live stack, **capturing** the evidence, and
**updating** the thesis. The run needs your machine (Docker + Grafana/Loki).

## 0. Environments

Two venvs, talking over HTTP (the clean split we've used throughout):

- **API + stack** → dev venv `.venv` (has FastAPI/uvicorn).
- **Scenarios / model** → ML venv `venv` (has ultralytics).

## 1. Bring up the stack

```bash
docker compose up -d                      # Grafana :3000, Loki :3100, Promtail
.venv/bin/python -m aoi.cli serve-http \
    --output logs/inference.jsonl &       # API :8000 -> JSONL that Promtail ships
```

Confirm: `curl -s localhost:8000/health`, Grafana at http://localhost:3000, Loki at :3100.

## 2. Build the corpus (once)

```bash
venv/bin/python -m experiments.build_corpus --overwrite
```
Needs `ml/data/dspcbsd_plus/test/` (the normalized dataset). If missing, rebuild it:
`venv/bin/python -m ml.pipeline.dspcbsd_dataset --source-root ml/data/_dl --output-root ml/data/dspcbsd_plus --overwrite`.

## 3. Run the real evaluation suite

```bash
venv/bin/python -m experiments.runner            # all 9 scenarios, real model -> Loki
# or a subset:  venv/bin/python -m experiments.runner --scenarios S01 S02 S09
```

Each scenario stays isolatable in Loki by `pcb_id` prefix:
`PCB-BASELINE / PCB-HIGHFAIL / PCB-LATENCY / PCB-LOWCONF / PCB-FLOOD / PCB-NORMAL+PCB-DEAD /
PCB-FAULT+PCB-RECOVERED / PCB-INTERMIT / PCB-DRIFT`. S09 also tags `model_version`
(`yolov8s-dspcbsd-baseline` vs `-channel_attention`).

## 4. Capture evidence

- **Grafana dashboards** per scenario (fail-rate, confidence, latency panels) — same shots
  as the current README, now real. Save under `assets/readme/anomaly/` / `thesis-assets/`.
- **Generate the results doc:**
  ```bash
  .venv/bin/python -m experiments.report --output docs/experiments/anomaly_results_real.md
  ```
- **Model accuracy evidence** (already produced in training, downloaded under
  `ml/models/defect_detection/eval/`): `latest_metrics_summary.json` (mAP@50 0.82,
  per-class P/R/F1), `confusion_matrix.png`, `BoxPR_curve.png`, `f1_per_class.png`.

## 5. Sanity expectations (what a good run looks like)

| Scenario | Expect in Grafana/Loki |
|---|---|
| S01 baseline | ~85–90% PASS (few real false positives) |
| S02 high-defect | ~100% FAIL, real DsPCBSD+ classes |
| S03 latency | latency ramps to ~2000ms; predictions real |
| S04 confidence drop | lower mean confidence than S02 + missed defects |
| S05 single-defect flood | one class ~100% of FAILs |
| S06 board failure | `BOARD_FAILURE` events isolated amid PASS traffic |
| S07 recovery | fail-rate high then drops |
| S08 intermittent | PASS-heavy with bursts at positions 5/11/17 |
| S09 drift | confidence/fail-rate shift across the two `model_version`s |

---

## Thesis write-up checklist (the longer pole)

Code is done; these are documentation edits. Each ☐ is a concrete swap.

- ☐ **Framing:** replace "mock / synthetic inference events" with "real model inference;
  controlled fault-injection only for timing (S03)". One coherent narrative:
  *monitor real inference, inject anomalies to validate the monitor.*
- ☐ **Defect taxonomy:** update text/tables from the solder/component vocabulary
  (`SOLDER_BRIDGE`, `MISSING_COMPONENT`…) to DsPCBSD+ fabrication/trace classes
  (`SHORT, SPUR, SPURIOUS_COPPER, OPEN_CIRCUIT, MOUSE_BITE, HOLE_BREAKOUT,
  CONDUCTOR_SCRATCH, CONDUCTOR_FOREIGN_OBJECT, BASE_MATERIAL_FOREIGN_OBJECT`).
- ☐ **Model results section:** add mAP@50 0.82, per-class P/R/F1 table, confusion matrix,
  PR/F1 curves from `ml/models/defect_detection/eval/`.
- ☐ **Scenario chapter:** describe each scenario as real-model-driven (per the table above);
  note S03 latency is the one injected signal.
- ☐ **Domain-shift caveat (do not skip):** the model is trained on bare-copper boards and
  over-triggers on assembled boards; state this as an honest observability finding (it
  strengthens the work). Your own boards belong in a qualitative OOD figure, not metrics.
- ☐ **README + Grafana captures:** refresh "Results at a Glance" and the anomaly dashboard
  images with the real run; old captures hardcode the solder labels.
- ☐ **ml/README scope:** change the stated scope from solder/component defects to
  fabrication/trace defects to match the chosen dataset.

## Done / on `main` (for reference in the methodology chapter)
- Dataset: `ml/pipeline/dspcbsd_dataset.py` (deterministic normalize, seed 42).
- Training: Colab GPU notebook `ml/notebooks/colab_train_dspcbsd.ipynb`.
- Inference: `src/aoi/inference_runner.py` (+ `BOARD_FAILURE` handling).
- Corpus: `experiments/build_corpus.py`.
- Scenarios: `experiments/scenarios/` (real-model-driven), `experiments/report.py`.
