# Implementation Priorities

This document defines what should be built first, what should be deferred, and how the current documentation should be interpreted during implementation.

## Purpose

The existing documents describe the target system architecture and future direction of the project. They are not all equal in implementation priority. Some features are required to establish a working AOI logging and monitoring pipeline, while others should remain placeholders until the core system is stable.

This file is the implementation guide for Codex.

## Priority Rule

When there is a conflict between ambition and feasibility, build the smallest working system first.

The implementation order is:

1. Logging pipeline
2. Structured schemas and storage
3. Monitoring and querying
4. Validation and test coverage
5. Simulated automation hooks
6. Advanced self-healing behavior
7. Model retraining workflow

## Phase 1: Must Build Now

These are the minimum components required for the first usable version of the system.

### 1. Structured Inference Logging
- Implement a consistent JSON log schema based on `docs/api_spec.md`.
- Every inference event must produce one machine-readable record.
- Required fields should include timestamp, pcb identifier, component identifier, result, defect type, confidence, and latency.

### 2. Log Ingestion Pipeline
- Build the path from inference output to log collection.
- Ensure logs are written in a format that Promtail can scrape reliably.
- Ensure Loki receives searchable records without manual transformation.

### 3. Basic Monitoring
- Expose logs in Grafana.
- Support filtering by board, component, defect type, and result.
- Provide a minimal dashboard for inspection history and error review.

### 4. Core Data Model
- Create the first stable relational schema for components, runs, and defect logs.
- Keep Redis optional unless offset caching is actively needed in code.
- Treat Loki as log storage, not as the primary source of relational truth.

### 5. Testable Local Workflow
- Make the system runnable without AOI hardware by using mock inference input.
- Support generation of sample logs for integration testing.
- Ensure the logging pipeline can be validated end-to-end in development.

## Phase 2: Build After Core Stability

These features are important, but should not block the first implementation.

### 1. Defect Classification Expansion
- Extend support for IPC-aligned defect labels from `docs/defects.md`.
- Validate taxonomy mapping after the core pipeline is stable.

### 2. Data Retention Automation
- Add archive and cleanup scripts after real data flow exists.
- Do not overdesign retention logic before sample volume and storage patterns are known.

### 3. Troubleshooting Utilities
- Implement operator-facing recovery helpers only after the error surface is understood from real logs.
- Initial error codes may be stubbed or documented before full automation exists.

## Phase 3: Defer or Simulate

These features should be treated as future work or placeholders unless explicitly requested.

### 1. Self-Healing Loop
- Automatic drift correction
- Lane pause and compensation logic
- Root cause analysis agents

These ideas are valid architectural goals, but they should not be implemented as production behavior until the core pipeline proves reliable.

### 2. Model Retraining Workflow
- Dataset export
- False-call feedback loop
- Bias correction updates

Retraining logic depends on stable data collection and review procedures. It should remain separate from the first delivery.

### 3. Real AOI Hardware Control
- Camera control
- Sensor recovery
- Lighting calibration
- Direct machine actuation

Unless hardware APIs are available and verified, these should be mocked behind interfaces.

## Interpretation Notes

The documents in `docs/` should be read with the following assumptions:

- `architecture.md` and `api_spec.md` define the initial system boundary.
- `database.md` defines a starting schema, not a finalized production database.
- `master_workflow.md` contains long-term automation goals, not all immediate requirements.
- `data_retention_policy.md` and `troubleshooting_manual.md` describe operational intent and can be partially stubbed.
- `contract.md` describes project ambition and context, but implementation should still be incremental.

## Coding Guidance for Codex

During implementation, prefer the following:

- Build modules that can run locally with mocks.
- Keep interfaces explicit and narrow.
- Separate logging, storage, and automation concerns.
- Avoid hard-coding assumptions about AOI hardware vendors.
- Mark unimplemented advanced behaviors clearly rather than faking full support.

## Immediate Output Expected

The first meaningful milestone should deliver:

- A mock or real inference service that emits structured JSON logs
- A log ingestion path into Loki
- A minimal Grafana dashboard
- A basic database schema for runs and defects
- End-to-end tests for logging and ingestion

If this milestone is working, the project is ready for iterative expansion.
