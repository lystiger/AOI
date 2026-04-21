# Pre-Program Setup: Verification Checklist

This document is the authoritative source for verifying the "Pre-Program" setup flow. It links directly to implementation and defines the rigor required for production readiness.

## Phase 1: Guided Run Creation & Preparation
Goal: Eliminate "empty state" dead-ends and provide a robust manual setup path.

### 1.1 Backend: Persistence & API
| Requirement | Verification Point (Code/Route) | Happy Path | Negative/Edge Path |
| :--- | :--- | :---: | :---: |
| **Schema Integrity** | `src/aoi/database.py` (`_initialize`) | [x] Columns exist | [ ] Migration fallback |
| **Run Creation** | `POST /runs` -> `src/aoi/service.py` (`_handle_create_run`) | [x] UUID + Default PCB ID | [x] Invalid JSON payload |
| **Run Updates** | `PATCH /runs/<run_id>` -> `src/aoi/service.py` (`_handle_patch_run`) | [x] Partial updates | [x] 404 on missing run |
| **Model Validation**| `src/aoi/service.py` (`_handle_patch_run`) | [x] Non-empty string | [x] Whitespace-only names |
| **Setup Status** | `src/aoi/database.py` (`_calculate_setup_status`) | [x] Transition to `review_ready` | [x] Premature readiness blocked |

### 1.2 Frontend: Setup Orchestration
| Requirement | Verification Point (Code) | Happy Path | Negative/Edge Path |
| :--- | :--- | :---: | :---: |
| **Setup Mode Trigger**| `web/src/App.jsx` (`showSetupMode`) | [x] Show for `SETUP` runs | [x] Persistence after refresh |
| **Step Progression** | `web/src/App.jsx` (`setupSteps`) | [x] Sequential activation | [ ] Backward nav logic |
| **Image Upload** | `web/src/App.jsx` (`handleImageUpload`) | [x] Success previews image | [x] Bad type stays in setup with error |
| **Model Saving** | `web/src/App.jsx` (`handleSaveModel`) | [x] Persistence on success | [ ] Network failure handling |
| **Rework/Revisit** | `src/aoi/database.py` (`update_run`), `web/src/App.jsx` (`showSetupMode`) | [x] Edit completed steps | [x] Invalidation of children |

---

## Phase 2: Automated Fiducial Detection
Goal: Registration alignment with manual correction.

### 2.1 Detection Flow
- [x] **Trigger**: `POST /runs/<id>/fiducials/detect` returns `200 OK`.
- [x] **State `running`**: UI shows spinner/progress in the Fiducial step card.
- [x] **State `needs_review`**: UI renders detected boxes with confidence scores.
- [ ] **Negative Path**: Detection finds 0 fiducials -> State moves to `failed` -> UI offers manual placement.
- [x] **Verification**: `src/aoi/database.py` (`fiducial_status` transitions).

---

## Phase 3: Automated Barcode Detection
Goal: Board identification and serial mapping.

### 3.1 Validation Flow
- [x] **Trigger**: `POST /runs/<id>/barcode/detect` returns `200 OK`.
- [ ] **State `done`**: High-confidence decode automatically marks step complete.
- [x] **State `needs_review`**: Low-confidence decode or multiple barcodes found.
- [ ] **Negative Path**: Decode failure -> UI allows manual serial entry.
- [x] **Verification**: `src/aoi/database.py` (`barcode_status` transitions).

---

## End-to-End Robustness Scenarios (The "Operator Stress Test")
Verify these multi-step behaviors before signing off on Phase 1:

1. [ ] **The "Dirty Exit"**: Create run, upload scan, close browser. Re-open -> Setup should resume at Step 3.
2. [x] **The "Model Swap"**: Complete setup -> Go back to Step 3 -> Change model. Dependent steps (Fiducials/Barcode) should reset to `ready` or `blocked`.
3. [x] **The "Bad Upload"**: Upload a corrupted or non-image file. System must show error message and remain in Step 2.
4. [x] **The "Ghost Run"**: Delete a run while it is selected in setup mode. UI must gracefully clear and return to empty Step 1.
5. [x] **The "Readiness Lock"**: Attempt to "Continue to Review" while a required step is still `ready` (not `done`). Button must be disabled.

---

## Traceability Links
- **Logic**: `src/aoi/database.py` -> Look for `_calculate_setup_status`
- **Logic**: `src/aoi/database.py` -> Look for `update_run` for model-change and requirement-toggle resets
- **UI**: `web/src/App.jsx` -> Look for `const setupSteps = useMemo(...)`, `const showSetupMode = ...`, `handleImageUpload`, and the localStorage-backed selected run state
- **Tests**: `tests/test_database.py`, `tests/test_service.py`
