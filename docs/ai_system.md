# AOI Industrial AI System
## PCB Defect Detection, Review, and Monitoring Platform

Author: Lys  
Target environment: Industrial AOI workflow / PCB inspection  
Document role: Thesis-stage system overview aligned to the current repository

---

## 1. System Overview

This project implements an AI-assisted AOI (Automated Optical Inspection) workflow for PCB defect detection and operator review. The system is intended to demonstrate how an industrial inspection pipeline can be extended with:

- AI-based defect detection
- structured inference logging
- backend-served inspection data
- review-oriented frontend visualization
- a path toward benchmarking and future model experimentation

The current repository already contains an end-to-end software skeleton for this workflow: a FastAPI backend, a React frontend workstation, domain models for runs and events, and a mock inference/event pipeline. The thesis objective at this stage is not to describe a generic future platform, but to document the implemented system architecture and the remaining steps required to replace mock inference with a real model pipeline.

---

## 2. Thesis Scope at the Current Stage

At this stage of the thesis, the project should be understood as an **AOI review and logging platform with AI integration points already defined**, rather than as a completed production AI stack.

### Implemented now

- Review workstation frontend for browsing runs, reviewing defects, and inspecting PCB images
- FastAPI backend with run, event, and review endpoints
- Domain schema for defect events, confidence scores, overlays, and operator review state
- Mock inference/event ingestion flow for simulating AOI activity
- Persistent logging/storage layer for runs and inspection events

### Partially implemented / integration stage

- Real AI inference replacing mock event generation
- richer inference provenance and model metadata
- run-level analytics surfaced directly in the frontend
- benchmark-ready experiment reporting

### Future work

- dataset management and training pipelines inside this repository
- comparative model benchmarking across multiple architectures
- deployment optimization such as ONNX or TensorRT
- live camera feeds, edge deployment, and multi-line industrial rollout

---

## 3. Current Repository-Aligned Architecture

The current system architecture in this repository is:

```text
PCB image / simulated event source
        ↓
Mock inference or future AI inference service
        ↓
Structured defect event payloads
        ↓
FastAPI backend
        ↓
Run + event persistence
        ↓
React review workstation
        ↓
Operator review / monitoring
```

### Actual project structure

```text
AOI/
├── docs/
├── src/aoi/
│   ├── api/
│   ├── database.py
│   ├── log_manager.py
│   ├── mock_inference.py
│   ├── schema.py
│   ├── setup_service.py
│   └── vision_service.py
└── web/
    ├── src/components/
    ├── src/hooks/
    ├── src/styles/
    └── package.json
```

This matters for the thesis: the implemented system is currently a Python package plus a separate React web client. It is not yet organized as a large multi-service MLOps monorepo, and the document should not imply otherwise.

---

## 4. Implemented System Modules

## 4.1 Frontend Review Workstation

Purpose:
Provide an operator-facing AOI review interface for inspecting runs, selecting defects, viewing defect overlays, and reviewing detection outcomes.

Current characteristics:

- React frontend under `web/`
- JSX + CSS styling, not TypeScript/Tailwind at present
- review workspace with run browser, defect list, PCB viewer, setup flow, and workspace top bar
- existing support for overlay rendering, zoom/pan, defect selection, and operator review actions

Role in the thesis:
This module demonstrates the human-review layer of the AI-enhanced AOI workflow, which is a critical distinction from a pure offline detector.

## 4.2 Backend API Layer

Purpose:
Expose run, event, and review data to the frontend and act as the integration boundary between inference output and the operator workstation.

Current characteristics:

- FastAPI application under `src/aoi/api/`
- routes for health, runs, and events
- request validation through Pydantic models
- defect review update flow for operator confirmation

Role in the thesis:
This layer demonstrates how AI outputs are operationalized into inspectable system records instead of staying as isolated notebook results.

## 4.3 Event and Run Data Model

Purpose:
Represent AOI detections as structured events that can be persisted, visualized, and reviewed.

Current characteristics:

- run creation and update request models
- event payload schema with:
  - `pcb_id`
  - `component_id`
  - `inspection_result`
  - `defect_type`
  - `confidence_score`
  - `inference_latency_ms`
  - normalized overlay coordinates:
    - `overlay_x`
    - `overlay_y`
    - `overlay_width`
    - `overlay_height`
  - operator review state
- image metadata associated with runs

Role in the thesis:
This is the core contract that connects detection results, logging, and visualization. It is one of the strongest implemented parts of the current project.

## 4.4 Mock Inference / Simulation Layer

Purpose:
Provide a controlled stand-in for AI predictions while the real model pipeline is still being integrated.

Current characteristics:

- mock inference/event flow already present in the backend package
- allows frontend and backend behavior to be developed before the full model stack is ready

Role in the thesis:
This supports staged system development, but it must be clearly labeled as simulation rather than final AI inference.

## 4.5 Storage and Logging Layer

Purpose:
Persist run history, defect records, and review actions.

Current characteristics:

- local persistence/logging utilities already present in the Python package
- supports the current review workstation and event history behavior

Role in the thesis:
This demonstrates traceability, which is essential for an industrial AI system and more defensible than a detector that only returns transient predictions.

---

## 5. Data Flow and API Contract

The system currently revolves around structured AOI events rather than raw model internals.

### Inference event payload

The implemented event model already supports the following data:

```json
{
  "timestamp": "2026-04-19T10:36:44Z",
  "pcb_id": "PCB-001",
  "component_id": "R42",
  "inspection_result": "FAIL",
  "defect_type": "solder_bridge",
  "confidence_score": 0.94,
  "inference_latency_ms": 14,
  "overlay_x": 0.34,
  "overlay_y": 0.51,
  "overlay_width": 0.08,
  "overlay_height": 0.04,
  "operator_review": "NONE"
}
```

### Data flow interpretation

1. A PCB image or simulated inspection input produces a detection event.
2. The backend validates and stores the event against a run.
3. The frontend retrieves run detail and associated defect logs.
4. The operator reviews the defects on the PCB canvas and updates review state.

This contract is already suitable for a thesis demonstration because it captures:

- defect class
- confidence
- latency
- localization
- review traceability

What is still missing for the final AI stage is richer provenance, such as:

- model identifier
- model version/hash
- backend/runtime type
- aggregate run-level inference statistics

---

## 6. Model Training and Inference Scope

The project vision includes both training and inference, but the current repository is more mature on the inference logging and review side than on the in-repo training side.

### Realistic thesis scope

For this thesis stage, the most defensible scope is:

- one practical baseline detector integrated into the system
- structured inference output routed through the backend
- frontend review and logging of model predictions
- optional comparison against one additional baseline model if time allows

### Recommended model scope

Do not present the project as if it already supports a broad model zoo unless that is actually implemented. A tighter and more credible scope would be:

- Primary model: `YOLOv8` or another object-detection baseline suited to PCB defect localization
- Optional comparison model: one secondary baseline for benchmark comparison

### What should remain future work

- multiple advanced architectures at once
- full experiment management platform
- large-scale MLOps orchestration
- production deployment optimization

This framing keeps the thesis rigorous and prevents the documented scope from exceeding the implemented system.

---

## 7. Evaluation and Benchmark Plan

The benchmarking section should support the thesis, but it should be framed as an evaluation plan tied to the implemented system.

### Primary evaluation dimensions

- detection quality
  - precision
  - recall
  - F1 score
  - mAP
- runtime behavior
  - inference latency
  - throughput / FPS
- operational usefulness
  - review visibility in the frontend
  - run/event traceability
  - defect localization clarity

### Benchmark objective

The benchmark is not only to find the most accurate model, but to identify the model and system configuration that best supports an industrial AOI review workflow.

### Thesis-friendly outputs

- model comparison table
- example detections with overlays
- inference latency summary
- run/event log screenshots
- operator review workflow demonstration

---

## 8. Current Limitations

The current repository still has clear limitations that should be stated directly.

- inference is still partially represented by mock or simulated flows
- the frontend improvement plan for provenance, event streaming, and richer confidence visualization is not fully implemented yet
- model training and dataset management are not yet fully represented as first-class repository modules
- the repository structure is still a development-stage application layout rather than a finalized industrial deployment layout
- benchmarking outputs are not yet fully integrated into the dashboard layer

These are acceptable limitations for a thesis-stage system as long as they are described honestly and the implemented pipeline is demonstrated clearly.

---

## 9. Final Thesis Positioning

The strongest position for this project is:

This thesis presents an AI-assisted AOI review platform for PCB defect detection that already implements the software pathway from structured inspection events to backend logging and operator-facing review. The final integration stage is the replacement of mock inference with a real trained model and the addition of stronger inference provenance, benchmarking evidence, and analytics surfaces.

That claim is stronger and more defensible than presenting the current repository as a fully completed industrial AI platform.

---

## 10. Near-Term Completion Priorities

To move from the current repository state to a strong thesis demonstration, the next priorities should be:

1. Integrate one real defect detection model into the event pipeline.
2. Add inference provenance fields and display them in the frontend.
3. Improve event log visibility and confidence-oriented review behavior.
4. Produce benchmark outputs for the selected model scope.
5. Document the implemented architecture, limitations, and results with evidence from the running system.

---

## 11. Summary

The AOI project already contains the essential skeleton of an AI-enabled inspection system:

- backend API
- event schema
- persistence/logging
- review workstation frontend
- simulated AOI event flow

The final thesis value will come from showing that this skeleton can be connected to a real model pipeline and used as a credible operator-facing industrial inspection workflow, not merely as a UI mockup or a standalone detector.
