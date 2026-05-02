# Project Stress Audit: "The Codex Debt"
**Date:** May 2, 2026
**Status:** Updated (Legacy Transport Removed)

## 1. Executive Summary
The project has successfully completed the first major refactor: **Removal of the legacy transport layer.** The backend is now 100% FastAPI. This has reduced architectural cognitive load, but significant logic "stress" remains in the persistence layer.

---

## 2. Backend Stress Points

### 2.1 The "God Object" (`src/aoi/database.py`) - **CRITICAL**
`DatabaseManager` remains a 1,300-line catch-all.
*   **Architectural Leakage:** It still contains raw image processing logic (BFS, HSV masking).
*   **Risk:** High. The persistence layer should not be responsible for computer vision.
*   **Status:** Next target for refactoring.

### 2.2 Transport Redundancy - **RESOLVED**
*   **Status:** `service.py` has been deleted.
*   **Outcome:** Single source of truth for the API via FastAPI. CLI updated to use Uvicorn.

### 2.3 Algorithmic Debt
*   Vision algorithms are still procedural and coupled to the DB.

---

## 3. Frontend Stress Points (Unchanged)

### 3.1 Component Monolith (`web/src/App.jsx`)
*   **Scale:** 2,266 lines in a single React file.
*   **Risk:** Maintenance nightmare. Any UI change risks breaking global state.

---

## 4. Immediate Refactoring Roadmap

### Phase 1: Backend Decoupling (In Progress)
1.  [x] Decommission `service.py`.
2.  [ ] **Extract `VisionService`**: Port image processing to a dedicated class/module.
3.  [ ] **Extract `SetupService`**: Port setup state transitions out of the DB manager.

### Phase 2: Frontend Decomposition (Upcoming)
1.  Component Split into `/components`.
2.  Hook extraction for state and API logic.
