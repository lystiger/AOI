# AOI Industrial AI System
## Inference Logging, Review, and Monitoring Platform

Target environment: Industrial AOI workflow / PCB inspection  
Document role: Repository-aligned system overview for the monitoring thesis

---

## 1. System Overview

This project implements an AI-assisted AOI (Automatic Optical Inspection)
workflow for PCB review with a strong emphasis on inference observability. The
system combines:

- an AOI backend for runs, images, and event ingestion
- a review workstation for operator inspection
- structured logging for inference events
- a Loki--Promtail--Grafana stack for operational monitoring

The current thesis direction is monitoring-first. The central claim is that an
AI inference service should be observable as an operational system, not treated
only as a source of offline model predictions.

---

## 2. Thesis Scope

At the current stage, the project should be understood as an AOI review and
monitoring platform with AI integration points already defined.

### Implemented now

- FastAPI backend with routes for runs, setup, health, and event ingestion
- React review workstation for image and defect inspection
- structured event schema for inference-like outputs
- JSONL log persistence for downstream observability
- Docker-based Loki, Promtail, and Grafana stack
- mock inference/event generation for controlled testing

### Thesis emphasis

The thesis focuses on:

- structured inference logging
- anomaly visibility in Grafana
- queryable event history in Loki
- latency and failure monitoring
- evaluation through controlled anomaly scenarios

### Supporting but secondary work

- real model integration
- dataset preparation
- detector benchmarking
- model architecture experimentation

These matter to the broader project, but they are not the main thesis claim.

---

## 3. Repository-Aligned Architecture

```text
PCB image / synthetic event source
        ↓
Inference or mock inference layer
        ↓
Structured AOI event payloads
        ↓
FastAPI backend
        ↓
SQLite persistence + JSONL logs
        ↓
Promtail → Loki → Grafana
        ↓
Operator review and monitoring
```

Actual implementation layers:

- `src/aoi/api/`: HTTP application surface
- `src/aoi/schema.py`: structured event contract
- `src/aoi/database.py`: persistence layer
- `src/aoi/log_manager.py`: JSONL event logging
- `src/aoi/mock_inference.py`: simulation path for controlled tests
- `web/`: operator-facing AOI workstation
- `deploy/`: observability stack configuration

---

## 4. Core System Modules

### 4.1 Review Workstation

The frontend provides the human-review layer for AOI runs. It supports run
navigation, PCB viewing, overlay inspection, defect review, and setup flow
operations.

### 4.2 Backend API

The backend operationalizes AI outputs by accepting structured event payloads,
persisting them, and exposing them to the review interface. This boundary is
important because it turns raw predictions into inspectable system records.

### 4.3 Event Schema

The event schema is the backbone of the monitoring design. It records:

- board identity
- component identity
- pass/fail result
- defect type
- confidence score
- inference latency
- optional overlay geometry
- operator review status

This schema supports both operational dashboards and post-event analysis.

### 4.4 Logging and Observability

Accepted events are written as structured JSON lines. Promtail ships them to
Loki, and Grafana visualizes:

- event volume
- failure counts
- distinct boards seen
- latency trends
- raw event streams

This is the core technical mechanism behind the thesis.

### 4.5 Mock Inference and Scenario Testing

The repository includes a synthetic inference path that allows the system to be
tested before the final detector is fully integrated. For the monitoring thesis,
this is valuable because it enables controlled experiments for:

- baseline traffic
- fail-rate spikes
- latency anomalies
- confidence degradation
- recovery after anomaly

---

## 5. Monitoring Value

The monitoring stack adds capabilities that a plain detector demo does not
provide:

- traceability of individual AOI events
- visibility into service latency and failure behavior
- board-level investigation using log queries
- repeatable anomaly demonstrations for thesis evaluation

This is the clearest differentiator between a model prototype and an operational
AI system.

---

## 6. Current Limitations

The present repository should not be described as a fully mature production AI
platform.

Known limits:

- inference is still partly represented by synthetic or mock flows
- alert rules and advanced dashboards are still under active refinement
- model provenance metadata is limited
- the real detector path is less mature than the monitoring path

These limits do not invalidate the thesis. They define its boundary.

---

## 7. Future Work

Future work can extend the platform in several directions:

- replace mock inference with a production detector
- attach model version and runtime metadata to every event
- expand Grafana dashboards and alert rules
- compare observed behavior across multiple inference backends
- add long-term retention and trend analysis

The key point is sequencing: the monitoring architecture is already a credible
thesis contribution even before the full production model stack is complete.
