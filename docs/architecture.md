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

## Implementation Standards
- **Dark Mode First**: Industrial tactical aesthetic to reduce operator eye strain.
- **Monospaced Data**: All coordinates and IDs use monospaced fonts for precision alignment.
- **Service Isolation**: No business logic in the API routes or the Database manager.
