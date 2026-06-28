# 09 — Performance, Scalability, Resource Consumption

**Audit part:** Part 4 (Engineering Depth) · **Severity:** High
**Assets to collect here:** resource-utilization chart, storage-growth chart,
ingestion/query-latency measurements.

## Problems in the current thesis

This is the **most damaging gap for the title** ("…Evaluation of an Observability
Framework"): the framework is described but **barely evaluated as a system.**

- **No throughput data.** Promtail→Loki ingestion rate (events/s) is never
  measured. The end-to-end freshness claim — *"an event becomes visible within a
  few seconds"* and *"5-second refresh is the practical bound on near real time"*
  (lines 360–364) — is **asserted, never measured.**
- **No resource consumption.** CPU / RAM / disk per container (FastAPI, Loki,
  Promtail, Grafana) is absent. A single `docker stats` capture would fix this.
- **No storage analysis.** Loki storage growth (MB per 1000 events) and JSONL
  growth rate are not reported — central to a logging-pipeline evaluation.
- **No scalability discussion.** Label-cardinality is mentioned conceptually
  (line 389) but never **quantified**; behavior as event volume grows is
  untested.
- **Query latency** is listed as a "measurement" (line 926, "Query
  responsiveness") but **no number is ever reported.**

## Suggestions (worklist only)

Add a **§4.x Performance and Resource Consumption** subsection with measured
numbers (cheap to produce, high marginal value):
- End-to-end freshness: inject event → measure time to appear in Grafana
  (validates the "few seconds" claim).
- `docker stats` snapshot under load → CPU/RAM per container (chart).
- Loki/JSONL storage growth per N events (chart).
- LogQL query latency for the representative queries (`tab:logql_queries`).
- Label cardinality count for the actual run.

> All of these can be captured from the existing Docker Compose stack with no new
> code — only measurement and a couple of charts.

## References & sources

- Grafana Loki performance/operations & label cardinality:
  https://grafana.com/docs/loki/latest/operations/ ·
  https://grafana.com/docs/loki/latest/get-started/labels/
- `docker stats` reference: https://docs.docker.com/reference/cli/docker/container/stats/
- Prometheus/Grafana for resource dashboards (if used to capture):
  https://prometheus.io/docs/ · https://grafana.com/docs/grafana/latest/
- General method framing: C. Majors et al., *Observability Engineering*,
  O'Reilly, 2022 (signal selection and cost).

## Figures/tables to produce

- **F15:** resource-utilization chart (CPU/RAM per container).
- **F16:** Loki/JSONL storage-growth chart.
- Table: measured end-to-end freshness, query latency, label cardinality.

## Committee questions this pre-empts

- *"You titled this 'evaluation of a framework' — what does it cost to run?
  CPU, memory, disk?"*
- *"You claim 'near real time' — measured, or assumed?"*
- *"How does Loki storage and cardinality grow with volume? Does it scale?"*
