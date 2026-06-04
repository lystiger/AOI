# Master Workflow

This document summarizes the repository workflow that supports the monitoring
thesis. It intentionally describes a practical observability loop rather than an
autonomous self-healing system.

## Monitoring Workflow

1. The AOI application receives images or simulated events.
2. The backend converts results into structured `InferenceEvent` payloads.
3. Events are persisted through the API and appended to JSONL logs.
4. Promtail scrapes the log files and forwards them to Loki.
5. Grafana dashboards visualize event volume, failures, boards seen, and
   latency behavior.
6. Operators or researchers inspect anomalies through dashboards and LogQL
   queries.
7. Findings are recorded for debugging, evaluation, or thesis reporting.

## Implementation Order

| Order | Component | Purpose |
| --- | --- | --- |
| 1 | Docker stack | Start Loki, Promtail, Grafana, backend, and frontend locally |
| 2 | Structured logging | Ensure AOI events are emitted as stable JSON records |
| 3 | Event ingestion | Validate that the API persists accepted events |
| 4 | Dashboard baseline | Confirm Grafana reflects normal AOI traffic |
| 5 | Anomaly scenarios | Inject abnormal event patterns for evaluation |
| 6 | Reporting | Save queries, screenshots, and conclusions for the thesis |

## Non-Goals

The current workflow does not claim:

- automatic production-line shutdown
- autonomous root-cause analysis
- self-healing remediation logic

Those may be future extensions, but they are outside the present thesis scope.
