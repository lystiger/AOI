# 06 — Monitoring vs Observability (Conceptual Framing)

**Audit part:** Part 1 / Related Work (§1.4) · **Severity:** Medium
**Asset to collect here:** definitions table / framing diagram.

## Problems in the current thesis

- The title and abstract use **"observability,"** but §1.4.1 (lines 241–247)
  conflates it loosely with monitoring and cites only the SRE book
  (`burns2016sre`). The distinction (monitoring = known-unknowns / predefined
  dashboards; observability = unknown-unknowns / ask new questions of raw data)
  is **stated weakly and not anchored** to the canonical literature.
- This matters because your **own contribution is really "monitoring"** (fixed
  dashboards + 3 predefined alert thresholds) more than full observability — the
  thesis would be *stronger* if it were honest about where it sits on that
  spectrum, and explicitly scoped logs-only (no traces, line 1210).
- The "near real time" definition (5-second refresh, line 363) is an
  observability-freshness claim that is **asserted, not measured** (see folder 09).

## Suggestions (worklist only)

- In §1.4.1 add precise definitions with citations and a small table:
  *monitoring vs observability*, and *the three pillars (logs/metrics/traces)*.
  Then state clearly: this thesis implements **log-based monitoring with
  observability-style ad-hoc LogQL querying**, not full three-pillar
  observability.
- Reframe the limitation (§4.2.6) as a deliberate scope choice backed by the
  literature, not an omission.

## References & sources

- C. Majors, L. Fong-Jones, G. Miranda, *Observability Engineering*, O'Reilly,
  2022 — canonical definition (currently absent from the thesis).
- C. Sridharan, *Distributed Systems Observability*, O'Reilly, 2018 — three
  pillars.
- B. Beyer et al., *Site Reliability Engineering*, O'Reilly, 2016 (already cited
  `burns2016sre`) — monitoring/SRE baseline.
- S. Shankar & A. Parameswaran, "Towards Observability for Production ML
  Pipelines," *PVLDB* 15(13), 2022 (already cited) — keep, ties ML to
  observability.

## Figures/tables to produce

- **T (framing):** Monitoring vs Observability vs the three pillars — where this
  thesis sits.

## Committee questions this pre-empts

- *"Define observability. Is what you built actually observability, or
  monitoring with fixed dashboards?"*
- *"Your title claims observability but you have no traces and three fixed
  alerts — defend the scope."*
