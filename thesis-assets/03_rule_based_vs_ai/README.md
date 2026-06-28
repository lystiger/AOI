# 03 — Rule-Based AOI vs AI-Assisted AOI (and Human-in-the-Loop)

**Audit part:** Part 1 (Industrial Context) · **Severity:** High
**Asset to collect here:** rule-based vs AI-AOI comparison table; HITL loop
diagram.

## Problems in the current thesis

- The **core motivation** — that AI-assisted AOI needs operational visibility
  beyond accuracy — rests on an **uncited, undeveloped contrast** between
  traditional rule-based AOI and AI-assisted AOI. The Introduction never
  explains how classical AOI works (golden-template / reference comparison,
  rule thresholds) or why AI changes the failure modes (false calls, drift,
  out-of-distribution boards).
- **Human-in-the-loop is built but never framed.** You implemented an operator
  review workstation (Fig. `review-workspace`, §3.2.5) — a genuine contribution
  — yet there is no theory of HITL inspection, operator accept/reject, or how
  human feedback closes the loop. It is under-sold.
- The confidence and drift scenarios (S04, S09) implicitly assume an AI detector
  whose behavior degrades, but the thesis never establishes *why* AI detectors
  drift (input/board-mix change, calibration), so the scenarios read as
  arbitrary.

## Suggestions (worklist only)

- Add a short subsection contrasting **rule-based vs AI-assisted AOI** with a
  comparison table (detection method, adaptability, false-call behavior,
  explainability, why monitoring matters more for AI).
- Add a **HITL paragraph** framing your review workstation: AI proposes →
  operator confirms/overrides → outcome is logged as reviewable evidence. Tie
  this to `inspection_result` review state in SQLite.
- Use this to justify S04 (out-of-distribution → low confidence) and S09 (drift)
  as *expected AI failure modes*, not invented scenarios.

## References & sources

- R. Ebayyeh & A. Mousavi, *IEEE Access* 8 (2020) — rule-based vs learning-based
  AOI. https://doi.org/10.1109/ACCESS.2020.3029127
- W. Ling & N. A. M. Isa, "PCB Defect Detection Methods Based on Image
  Processing, ML and DL: A Survey," *IEEE Access* 11 (2023).
  https://doi.org/10.1109/ACCESS.2023.3245093
- S. Amershi et al., "Software Engineering for Machine Learning: A Case Study,"
  *ICSE-SEIP* 2019 (already cited as `amershi2019case`) — HITL/data feedback.
- R. (Munro) Monarch, *Human-in-the-Loop Machine Learning*, Manning, 2021.
- J. Gama et al., "A Survey on Concept Drift Adaptation," *ACM Computing
  Surveys* 46(4), 2014. https://doi.org/10.1145/2523813 (justifies S09).

## Figures/tables to produce

- **T1:** Rule-based vs AI-assisted AOI comparison table (§1.x).
- **Fig:** HITL loop diagram (AI → operator review → logged outcome), can reuse
  [`docs/pics/usecase.png`](../../docs/pics/usecase.png) as a basis.

## Committee questions this pre-empts

- *"How does traditional AOI work, and what specifically does AI change that
  makes observability necessary?"*
- *"You built an operator workstation — what is the human-in-the-loop model?"*
- *"Why would an AI detector drift (S09)? Justify the scenario."*

---

## UPDATE — confirmed vendor facts (author-supplied) + primary evidence

The rule-based vs AI-AOI contrast can now be backed by **real machines the host
works with**, not just literature:

| Machine | Type | Evidence / how it detects |
|---|---|---|
| **Holly** | Modern **rule-based** AOI | Primary source: `hollymachine.pdf` in folder 01 — CAD-driven programming + multi-angle RGB/White lighting + luminance/threshold/template algorithms (Mark Tracing, Chip Tracing, Luminance Mean/Span/Extraction, HSV Extraction, Template Matching, Gradient Tracing). **No ML.** |
| **JUTZE** | **AI** AOI | Vendor uses learning-based detection (confirm exact models with vendor docs). |
| **Flytake** | **AI multimodal** AOI | Multimodal pipeline incl. YOLO (Ultralytics) / YOLOv8 + OCR + more. Ref: https://flytake.com/page-nsW5tB.php |

**How to use this in the thesis**
- Build the rule-based-vs-AI comparison table (T1) with **Holly as the concrete
  rule-based example** and **JUTZE / Flytake as the AI examples** — this grounds
  the motivation in the host's real equipment instead of generic claims.
- The Holly algorithm slides (deck pages 20–38, see
  [../01_aoi_machine/CATALOG.md](../01_aoi_machine/CATALOG.md)) are primary
  evidence that classic AOI is threshold-based and therefore brittle to
  appearance variation — which is exactly what motivates AI-AOI and, in turn, the
  observability this thesis adds.
- A human-in-the-loop diagram is provided at
  [../diagrams/hitl_loop.mmd](../diagrams/hitl_loop.mmd).

> Caution for the Codex agent / author: cite the Flytake page as a vendor source;
> do not assert specific JUTZE model internals without a confirming reference.
