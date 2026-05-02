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

## Implementation Standards
- **Dark Mode First**: Industrial tactical aesthetic to reduce operator eye strain.
- **Monospaced Data**: All coordinates and IDs use monospaced fonts for precision alignment.
- **Service Isolation**: No business logic in the API routes or the Database manager.
