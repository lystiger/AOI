# Thesis Assets — Audit Notes Index

This folder holds **audit notes only** — problems and suggestions for the thesis
[`docs/paper/thesis_usth.tex`](../docs/paper/thesis_usth.tex). These `.md` files
**do not change the paper**; they are a worklist for what evidence, references,
figures, and justification are missing, organized by topic. Each folder is meant
to also collect the actual asset (figure/photo/diagram) once produced.

| Folder | Topic | Audit part | Severity |
|---|---|---|---|
| [01_aoi_machine](01_aoi_machine/README.md) | AOI machine overview | Industrial context | High |
| [02_pcb_pipeline](02_pcb_pipeline/README.md) | PCB/SMT pipeline + defects | Industrial context | High |
| [03_rule_based_vs_ai](03_rule_based_vs_ai/README.md) | Rule-based vs AI-AOI + HITL | Industrial context | High |
| [04_observability_stack](04_observability_stack/README.md) | Stack choices (FastAPI/React/Docker/logs) | Technology selection | High |
| [05_loki_vs_elk](05_loki_vs_elk/README.md) | Loki vs ELK/OpenSearch, Grafana vs Kibana | Technology selection | High |
| [06_monitoring_vs_observability](06_monitoring_vs_observability/README.md) | Conceptual framing | Related work | Medium |
| [07_experiment_methodology](07_experiment_methodology/README.md) | Experiments S01–S09 | Experiments | Medium |
| [08_frontend_backend](08_frontend_backend/README.md) | API/DB/frontend/Docker depth | Engineering depth | High |
| [09_performance](09_performance/README.md) | Latency/throughput/resources | Engineering depth | High |
| [10_references_NOTES.md](10_references_NOTES.md) | Reference list problems | References | High |

## Cross-cutting problems (apply to the whole paper)

1. **`10_references.bib` is empty (1 byte).** The thesis still uses manual
   `\bibitem` entries (14 total). See [10_references_NOTES.md](10_references_NOTES.md).
2. **Unused evidence already captured.** `s02, s04, s05, s06, s07, s08` Grafana
   screenshots exist in [`assets/readme/anomaly/`](../assets/readme/anomaly/) but
   the thesis embeds only `s01, s03, s09`. The text *describes* the S02/S06/S07
   captures (thesis lines ~880–887) without showing them.
3. **Three core architecture "figures" are ASCII text boxes**, not diagrams:
   `fig:scope_loop`, `fig:implemented_architecture`, `fig:experiment_workflow`.
4. **No industrial grounding** despite the host being a real SMT manufacturer
   (FUYU / Foxconn Industrial Internet). See folders 01–03.
5. **No measured performance/resource data** despite the title being about an
   observability *framework*. See folder 09.

## Material added so far

- **Holly AOI deck** extracted to `01_aoi_machine/page-01..38.jpg` with a
  page index in [01_aoi_machine/CATALOG.md](01_aoi_machine/CATALOG.md). Confirms
  Holly = rule-based; provides real machine + defect photos.
- **Mermaid diagrams** (grounded in the real code) in
  [diagrams/](diagrams/README.md): architecture, event sequence, SMT pipeline,
  HITL loop, Docker topology, SQLite ER. Render via mermaid.live or `mmdc`.
- **Vendor facts** for the rule-based-vs-AI table recorded in folder 03: Holly
  (rule-based), JUTZE (AI), Flytake (AI multimodal, YOLOv8/OCR).
- The thesis generator `docs/paper/build_usth_latex.py` has been **retired**
  (deleted; recoverable from git) so edits to `thesis_usth.tex` are not clobbered.
