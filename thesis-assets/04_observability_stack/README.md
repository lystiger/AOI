# 04 — Observability Stack & Technology Selection

**Audit part:** Part 2 (Technology Selection) · **Severity:** High
**Assets to collect here:** logs-vs-metrics-vs-traces table; expanded
design-decision table with citations.

## Problems in the current thesis

- `Table tab:design_decisions` (lines 829–846) is a good skeleton but **every
  cell is a one-line opinion with zero citations and zero benchmarks.**
- Several stack choices are **never justified at all**:
  - **React** simply appears (§3.2.1) — no comparison to Vue/Angular.
  - **Docker / Docker Compose** is used but never argued (reproducibility/IaC).
  - **Promtail** is used but never compared to Fluent Bit / Vector / OTel
    Collector / Grafana Alloy (note: Promtail is now in maintenance vs Alloy).
- **The single biggest unjustified architectural decision — logs (Loki) over
  metrics (Prometheus) — is never discussed.** Future Work even admits "compare
  log-based monitoring with richer metrics or tracing" (line 1231), confirming
  the gap exists.
- **OpenTelemetry is invisible.** OTel is the CNCF standard for exactly this
  problem; an examiner will ask "why not OTel?" and the thesis has no answer.

## Suggestions (worklist only)

- Add a *"Why logs, not metrics/traces"* paragraph in §3.1 with a **three-pillars
  table** (logs vs metrics vs traces) showing which your design uses and why a
  log-centric approach fits a bounded AOI workflow.
- Add an explicit **"Why not OpenTelemetry"** sentence: logs-only is the scope;
  OTel traces/metrics are future work.
- Add a **Citation column** to `tab:design_decisions`; back each row with a
  reference (see below). Add rows for React, Docker, Promtail.

## References & sources

- C. Majors, L. Fong-Jones, G. Miranda, *Observability Engineering*, O'Reilly,
  2022 (logs/metrics/traces). · C. Sridharan, *Distributed Systems
  Observability*, O'Reilly, 2018.
- **OpenTelemetry Specification** (CNCF). https://opentelemetry.io/docs/specs/otel/
- **Prometheus docs** (CNCF). https://prometheus.io/docs/introduction/overview/
- FastAPI: https://fastapi.tiangolo.com · throughput evidence:
  **TechEmpower Web Framework Benchmarks** https://www.techempower.com/benchmarks/
- SQLite (peer-reviewed): K. P. Gaffney et al., "SQLite: Past, Present, and
  Future," *PVLDB* 15(12), 2022. https://doi.org/10.14778/3554821.3554842
- Docker: D. Merkel, "Docker: Lightweight Linux Containers…," *Linux Journal*
  2014(239); D. Bernstein, "Containers and Cloud," *IEEE Cloud Computing* 1(3),
  2014. https://doi.org/10.1109/MCC.2014.51
- React: https://react.dev · Log shippers: Grafana Alloy
  https://grafana.com/docs/alloy/ · Fluent Bit https://fluentbit.io ·
  Vector https://vector.dev
- Structured logging: 12-Factor App "Logs" https://12factor.net/logs

## Figures/tables to produce

- **T4:** Logs vs Metrics vs Traces (three pillars) — §3.1.
- **T3 (partial):** expand `tab:design_decisions` with a Citation column and
  rows for React, Docker, Promtail.
- **F7:** Docker Compose service-topology diagram (also referenced in folder 08).

## Committee questions this pre-empts

- *"Why logs over metrics? Why Loki over Prometheus?"*
- *"Why not OpenTelemetry, the CNCF standard for this?"*
- *"Every design-decision row is an assertion — what is the evidence?"*
- *"Why React? Why Docker? Why Promtail specifically?"*
