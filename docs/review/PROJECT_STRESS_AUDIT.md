# Project Stress Audit: "The Codex Debt"
**Date:** May 2, 2026
**Status:** Decoupling Complete (Phase 1)

## 1. Executive Summary
The project has successfully completed **Phase 1: Backend Decoupling.** The "God Object" has been dismantled, and the transport layer is now unified under FastAPI. The backend architecture is now stable, maintainable, and significantly more performant.

---

## 2. Backend Stress Points (REDUCED)

### 2.1 The "God Object" (`src/aoi/database.py`) - **RESOLVED**
`DatabaseManager` has been stripped of its business and vision logic.
*   **Outcome:** `DatabaseManager` is now focused strictly on CRUD operations and persistence.
*   **Extraction:** Vision logic moved to `VisionService`, and setup state management moved to `SetupService`.

### 2.2 Transport Redundancy - **RESOLVED**
*   **Outcome:** Legacy `service.py` has been removed. FastAPI is the single source of truth for the API.

### 2.3 Algorithmic Debt - **MITIGATED**
*   **Outcome:** Vision algorithms are isolated in `VisionService`, making them easy to swap for OpenCV or ML-based solutions in the future without touching the database or API layers.

---

## 3. Frontend Stress Points (CURRENT BOTTLENECK)

### 3.1 Component Monolith (`web/src/App.jsx`)
*   **Scale:** 2,266 lines in a single React file.
*   **Stress:** This is now the primary source of technical debt. State management and UI logic are tightly coupled, making the application fragile and difficult to extend.

### 3.2 Style Management (`web/src/App.css`)
*   **Stress:** Global CSS is hard to maintain and prone to regressions.

---

## 4. Refactoring Roadmap (Updated)

### Phase 1: Backend Decoupling (COMPLETED)
1.  [x] Decommission legacy `service.py`.
2.  [x] Extract `VisionService`.
3.  [x] Extract `SetupService`.
4.  [x] Maintain high test coverage (41+ tests passing).

### Phase 2: Frontend Decomposition (NEXT TARGET)
1.  **Extract Components:** Move `PcbViewer`, `SetupStepper`, `RunHistoryRail`, and `DefectList` into `/components`.
2.  **Logic Extraction:** Create custom hooks (e.g., `useRuns`, `useSetup`, `useDefects`) to handle data fetching and state.
3.  **Modernize Styling:** Introduce a more modular CSS strategy.

---

## 5. Conclusion
The backend is now in a "Senior Engineer" state. The focus must now shift to the frontend monolith to ensure the long-term health of the workstation UI.
