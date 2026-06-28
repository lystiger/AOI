# 02 — PCB Manufacturing Pipeline, SMT Line & Defect Taxonomy

**Audit part:** Part 1 (Industrial Context) · **Severity:** High
**Assets to collect here:** SMT-line flowchart; annotated PCB defect photos;
IPC-A-610 defect table.

## Problems in the current thesis

- **No PCB manufacturing pipeline** is described. A reader never learns where AOI
  sits in the flow (stencil print → SPI → pick-and-place → reflow → **AOI** →
  repair). Without it, "board-level traceability" (S06) and "defect composition"
  (§4.1.5) have no physical context.
- **No SMT production line** description (tact time, inline vs offline, line
  balancing). This is the missing yardstick for your "5-second refresh" /
  "near real time" claim (lines 360–364).
- **Common AOI defects are logged but never defined.** The thesis emits
  `defect_type` values — `SOLDER_BRIDGE`, `MISSING_COMPONENT`,
  `INSUFFICIENT_SOLDER`, `BENT_LEAD`, `MISALIGNMENT`, `SOLDER_BALL` (§4.1.5,
  lines 987–991) — but never explains what they are or cites a standard.
  **Your own [`docs/defects.md`](../../docs/defects.md) says these are
  "IPC-A-610 Compliant," yet IPC-A-610 is never cited.**
- **No industrial workflow KPIs.** The terms **false-call rate** and **escape
  rate** — the defining metrics of industrial AOI — never appear, even though
  your fail-rate and confidence signals map directly to them.

## Suggestions (worklist only)

- In the new §1.x background subsection add:
  - an SMT-line flowchart locating AOI in the process;
  - a defect-taxonomy table (reuse [`docs/defects.md`](../../docs/defects.md)
    grouped by Solder / Placement / Lead defects) cited to **IPC-A-610**;
  - 2–3 annotated real defect photos from [`docs/pcb/`](../../docs/pcb/).
- In Discussion (§4.2) connect your signals to industry KPIs: fail-rate spike ≈
  process fault; low-confidence storm ≈ rising false-call risk; board-level
  isolation (S06) ≈ traceability for the repair loop.

## References & sources

- **IPC-A-610H**, *Acceptability of Electronic Assemblies*, IPC.
  https://www.electronics.org/ipc-610-acceptability-electronics-assemblies-endorsement-program  (also J-STD-001 for soldering)
- C. Coombs & H. Holden, *Printed Circuits Handbook*, 7th ed., McGraw-Hill (SMT
  process chapters).
- R. Prasad, *Surface Mount Technology: Principles and Practice*, Springer.
- M. Moganti et al., "Automatic PCB Inspection Algorithms: A Survey," *Computer
  Vision and Image Understanding* (Elsevier) 63(2), 1996.
  https://doi.org/10.1006/cviu.1996.0017
- Public PCB defect datasets for example imagery: DeepPCB; HRIPCB / PKU-Market-PCB.

## Figures/tables to produce

- **F1:** SMT line → AOI pipeline flowchart (§1.x).
- **F3:** Annotated PCB defect photos (solder bridge, missing component, bent
  lead) using [`docs/pcb/`](../../docs/pcb/).
- **T2:** IPC-A-610 defect taxonomy table (from `docs/defects.md`).

## Committee questions this pre-empts

- *"You log six defect types — what are they, and on what standard?"*
- *"Where does AOI sit in the manufacturing process you claim to support?"*
- *"What is the false-call rate, and how does your monitoring relate to it?"*
