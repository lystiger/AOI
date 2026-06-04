# System Architecture: AOI Inference Monitoring

## Purpose

This document describes the repository architecture from the perspective of the
monitoring thesis. The primary question is not how to maximize detector
accuracy, but how to make AI inference behavior observable inside an AOI
workflow.

## End-to-End Data Flow

1. PCB images are uploaded or simulated inspection events are generated.
2. The AOI backend converts results into structured inference events.
3. Events are validated and persisted through the FastAPI application.
4. The same events are appended to JSONL log files for observability.
5. Promtail scrapes the logs and forwards them to Loki.
6. Grafana queries Loki to visualize operational behavior.
7. Operators review boards and defects through the AOI workstation.

## Component Map

### Backend

- `src/aoi/api/`: HTTP routes for health, runs, setup, and events
- `src/aoi/schema.py`: event and run data structures
- `src/aoi/database.py`: SQLite persistence
- `src/aoi/log_manager.py`: structured JSONL logging
- `src/aoi/mock_inference.py`: controlled synthetic event generation
- `src/aoi/vision_service.py`: AOI-oriented image and detection helpers

### Frontend

- `web/src/components/`: review workspace, setup flow, PCB viewer, sidebars
- `web/src/hooks/`: data fetching and workspace state management
- `web/src/styles/`: layout and visual styling

### Observability Stack

- `deploy/promtail/config.yml`: log scraping and label extraction
- `deploy/loki/config.yml`: log aggregation backend
- `deploy/grafana/provisioning/`: dashboards and datasource provisioning
- `docker-compose.yml`: local multi-service deployment

## Monitoring Contract

The monitoring design depends on a stable event schema. Each inference event
should capture enough information to support both operational dashboards and
manual investigation.

Key fields:

- `timestamp`
- `pcb_id`
- `component_id`
- `inspection_result`
- `defect_type`
- `confidence_score`
- `inference_latency_ms`
- overlay geometry fields
- operator review state

These fields allow the system to answer practical questions:

- How many events were produced recently?
- Which boards generated failures?
- Did latency increase abnormally?
- Are specific defect types dominating?
- Can a suspicious run be traced back to exact event records?

## Design Trade-Offs

### SQLite

SQLite is acceptable for the current thesis stage because the platform is a
local AOI prototype with moderate write volume and a strong need for simple
setup. It should not be presented as the long-term production persistence
solution.

### Log-Centric Monitoring

The thesis intentionally adopts a log-centric architecture built around
Promtail, Loki, and Grafana. This is simpler than full distributed tracing and
sufficient for the current scope:

- event traffic visibility
- board-level traceability
- defect-type analysis
- latency observation
- anomaly detection experiments

### Mock Inference Support

Synthetic event generation is a feature, not a weakness, for this thesis stage.
It allows controlled anomaly testing before a production-ready detector is fully
integrated.

## Thesis-Relevant Architecture Questions

The architecture is designed to support evaluation of these questions:

- Can the system distinguish normal and abnormal inference behavior?
- Can failures be isolated by board, defect type, or time window?
- Can latency degradation be detected without inspecting raw model internals?
- Can a lightweight local stack provide credible observability evidence?

## Out of Scope

This architecture document does not treat CBAM, YOLOv8 ablations, or
component-detection benchmarking as the thesis core. Those remain supporting ML
workstreams that may eventually feed the inference backend, but they are not the
main architectural claim of the monitoring thesis.
