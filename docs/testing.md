# Testing Protocol

This document defines the validation flow for the monitoring-focused AOI thesis.
The purpose is to verify that the application emits structured inference events,
that the observability stack captures them correctly, and that anomaly scenarios
produce measurable signals in Grafana and Loki.

## Scope

This testing protocol covers:

- API-level event ingestion
- JSONL log persistence
- Promtail log shipping
- Loki queryability
- Grafana dashboard visibility
- anomaly scenario validation

It does not attempt to fully validate model accuracy. Model-quality evaluation is
treated as supporting ML work, not the core thesis claim.

## Phase 1: API and Schema Validation

Goal:
Confirm that `POST /events` accepts well-formed AOI event payloads and rejects
invalid data.

Checks:

- send a valid event with `pcb_id`, `component_id`, `inspection_result`,
  `defect_type`, `confidence_score`, and `inference_latency_ms`
- verify the API returns success
- send invalid payloads such as missing fields or out-of-range confidence values
- verify validation errors are returned

Expected outcome:

- valid events are accepted and persisted
- invalid events are rejected without corrupting the event log

## Phase 2: Logging Validation

Goal:
Confirm that accepted events are written as structured JSON lines and can be
shipped by Promtail.

Checks:

- send a controlled batch of test events
- verify new entries appear in `logs/inference.jsonl` or the configured AOI log
  output
- verify each line contains machine-readable fields rather than free-form text
- confirm Promtail can scrape the file without parse errors

Expected outcome:

- every accepted event appears once in the log file
- the log schema remains consistent across entries

## Phase 3: Loki Query Validation

Goal:
Confirm that shipped events are queryable by the fields needed for the thesis.

Checks:

- query total events over a recent time window
- query only `FAIL` events
- query by `pcb_id`
- query by `defect_type`
- query high-latency events using `inference_latency_ms`

Expected outcome:

- LogQL queries return the expected subsets
- label-based and JSON-field-based filtering both work

## Phase 4: Grafana Dashboard Validation

Goal:
Confirm that the default AOI dashboard reflects the incoming inference traffic.

Checks:

- verify event-count panels respond after sending batches
- verify fail-count panels change when failure-heavy batches are sent
- verify latency panels reflect different latency ranges
- verify raw log panels show the inserted events

Expected outcome:

- dashboard panels change within the normal scrape/query delay
- the dashboard is usable for both quick status checks and drill-down review

## Phase 5: Anomaly Scenario Validation

Goal:
Validate the thesis claim that the monitoring stack can distinguish healthy and
abnormal operating conditions.

Primary scenarios:

- normal baseline traffic
- elevated fail-rate traffic
- latency spike traffic
- confidence-drop traffic
- recovery after anomaly

Reference:

- `docs/anomaly_testing.md`

Checks:

- run each scenario
- capture the corresponding Grafana behavior
- verify Loki queries isolate the anomaly
- record timings, counts, and thresholds used

Expected outcome:

- each scenario produces a distinct and explainable monitoring signature
- anomalies are visible without manual inspection of raw application internals

## Minimum Evidence to Save

For each thesis demonstration run, save:

- scenario name and execution time
- sample API payload used
- relevant Loki queries
- Grafana screenshots
- short interpretation of what changed and why it matters

## Success Criteria

The monitoring system is considered thesis-ready if:

- structured events flow from the AOI app into the logging stack
- Loki can isolate failures, board IDs, and latency anomalies
- Grafana clearly visualizes baseline versus abnormal behavior
- anomaly experiments produce repeatable evidence for the evaluation chapter
