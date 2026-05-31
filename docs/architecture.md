# System Architecture: AI-Powered AOI Integration

## Data Flow
1. **PCB Acquisition**: AOI machine captures multi-angle images and uploads them via the FastAPI `/runs/{id}/images` endpoint.
2. **Setup Workflow**: Operators use the `SetupFlow` UI to configure model parameters, detect fiducials, and validate barcodes.
3. **Inference Engine**: External agents or the internal `VisionService` process raw images to identify defects.
4. **Persistence Layer**: `DatabaseManager` handles structured storage in SQLite, delegating business logic to specialized services.
5. **Review Dashboard**: A React-based tactical interface allows inspectors to review, zoom, and confirm defect logs.

## Component Map

### Backend (Python/FastAPI)
- `aoi.api`: FastAPI application defining the RESTful contract.
- `aoi.vision_service`: Isolated computer vision logic (masking, BFS component extraction, coordinate scoring).
- `aoi.setup_service`: State machine managing the transition from "Raw Scan" to "Review Ready."
- `aoi.database`: CRUD operations and SQLite schema management.
- `aoi.log_manager`: Structured JSON logging for observability (Loki/Grafana).

### Frontend (React/Vite)
- `hooks/`: Specialized state logic (e.g., `useRunData` for fetching, `useSetupActions` for transitions).
- `components/`: Modular UI units (e.g., `PcbViewer` for canvas interaction, `SetupFlow` for the wizard).
- `app/`: Global constants and utility functions.

## Design Trade-Offs

### SQLite as the Current Persistence Layer

The project currently uses SQLite as a deliberate implementation trade-off, not as a claim that it is the final production database.

Why SQLite is acceptable in the current stage:

- low operational overhead for a single-node development and prototype environment
- simple local setup with no external database service required
- easy file-based inspection, backup, and reset during rapid iteration
- sufficient for current workload patterns centered on setup, review, and event traceability

Known limitations:

- not designed for high-write concurrent production workloads across multiple application instances
- limited operational tooling compared with PostgreSQL for replication, failover, and access control
- schema migration and long-term analytics use cases will become harder as data volume and team size grow
- database locking behavior can become a bottleneck if ingestion and review traffic scale materially

Production implication:

- SQLite is acceptable for local deployment, development, demos, and early pilot workflows
- PostgreSQL should replace SQLite once the system requires multi-user concurrent writes, stronger operational guarantees, or horizontally scalable deployment

This boundary is intentional: the current architecture optimizes for delivery speed and local operability first, while leaving the persistence layer isolated enough to support a later migration.

## Proposed Architecture Modification

### Motivation

The next thesis-stage model change is to test whether attention improves PCB defect localization and component-focused detection.

Why this is technically justified:

- PCB defects are typically small relative to the full image
- defect regions are spatially sparse rather than uniformly distributed
- standard convolutions process all spatial regions with the same local filtering behavior
- attention modules can bias feature refinement toward informative channels and anomalous spatial regions

In this project context, that matters because AOI scenes contain large amounts of visually repetitive background:

- solder mask
- repeated passive components
- silkscreen markings
- dense but non-defective texture

An attention mechanism is therefore a reasonable architectural modification for improving signal allocation toward subtle or rare abnormal patterns.

### Proposed Model Variant

The proposed thesis modification is a CBAM-augmented YOLOv8 backbone.

Reference diagram:

- `docs/pics/cbam_yolov8_novel_arch.svg`

The diagram shows:

- standard YOLOv8 backbone on the left
- modified backbone on the right
- CBAM modules inserted after selected `C2f` blocks
- standard PANet neck and detection head retained

This is a good thesis design because it changes one meaningful architectural variable while keeping the rest of the detection pipeline stable.

### Why CBAM

CBAM is a practical choice because it combines:

- channel attention
- spatial attention

This lets the thesis test two related hypotheses:

1. Channel reweighting alone may improve discrimination between useful and noisy feature maps.
2. Full channel + spatial attention may further improve localization of sparse anomalies on the board surface.

### Experimental Design

The clean experiment plan is:

| Experiment | Model Variant | Purpose |
| --- | --- | --- |
| 1 | Baseline `YOLOv8s` | establish reference performance |
| 2 | `YOLOv8s + channel attention only` | isolate the benefit of channel reweighting |
| 3 | `YOLOv8s + full CBAM` | test the combined channel + spatial attention effect |

This three-row comparison is strong for an undergraduate thesis because:

- it is simple
- it is controlled
- it isolates architectural contribution
- it produces a defensible ablation rather than a single one-off modified model

### Evaluation Plan

Each experiment should be evaluated with the same:

- dataset split
- class taxonomy
- training schedule
- confidence/NMS policy
- hardware notes

The comparison table should report at minimum:

- mAP@50
- mAP@50-95
- precision
- recall
- per-class precision/recall/F1
- confusion matrix
- precision-recall curves
- inference latency

### Benchmarking Scope

For thesis clarity, two benchmark scopes must be separated:

1. Internal engineering benchmark

- compares baseline YOLOv8s vs channel attention vs full CBAM under the same local protocol
- valid for the current reduced-class AOI setup

2. Published benchmark comparison

- only valid if the dataset task definition, label space, and evaluation protocol match the original benchmark exactly

This distinction matters because the current project already uses a reduced taxonomy in some runs. That makes internal comparisons valid, but it prevents direct apples-to-apples claims against published SOTA on the original `pcb_wacv_2019` benchmark unless the protocol is matched.

### Thesis Value

This modification is appropriate thesis material because it contributes:

- a concrete model architecture change
- an interpretable motivation tied to PCB image characteristics
- a controlled ablation study
- measurable trade-offs between accuracy and latency

In short: the work is not just "train YOLO." It becomes a structured investigation of whether attention mechanisms improve PCB-focused visual inspection under constrained data conditions.

## Implementation Standards
- **Dark Mode First**: Industrial tactical aesthetic to reduce operator eye strain.
- **Monospaced Data**: All coordinates and IDs use monospaced fonts for precision alignment.
- **Service Isolation**: No business logic in the API routes or the Database manager.
