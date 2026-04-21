# Pre-Program Setup: Implementation Checklist

This checklist tracks the implementation of the guided setup flow. Use this to ensure all components are built and verified before moving to the next phase.

## Phase 1: Guided Run Creation & Preparation
Goal: Eliminate the "empty state" dead-end by allowing operators to prepare a run manually.

### Backend Tasks
- [ ] **Database Schema Update**:
    - [ ] `model_name` column added to `inspection_runs`.
    - [ ] `setup_status` column added (`not_ready`, `in_progress`, `review_ready`).
- [ ] **Database Manager Methods**:
    - [ ] `create_run(pcb_id=None)`: Generate UUID, set default PCB ID, timestamp, and `SETUP` status.
    - [ ] `update_run(run_id, data)`: Support partial updates for `model_name` and `setup_status`.
- [ ] **API Endpoints**:
    - [ ] `POST /runs`: Trigger `create_run`.
    - [ ] `PATCH /runs/<run_id>`: Trigger `update_run`.
    - [ ] `GET /runs`: Ensure new setup fields are included in the response.

### Frontend Tasks
- [ ] **App State**:
    - [ ] Track `setupMode` (boolean) and `activeStep` (1-6).
    - [ ] Compute "Review Readiness" based on run metadata.
- [ ] **Setup UI Components**:
    - [ ] `SetupFlow` container: Replaces the main viewer when a run is incomplete.
    - [ ] `StepList`: Vertical progress indicator (1. Create -> 2. Upload -> 3. Model -> ...).
- [ ] **Step Implementation**:
    - [ ] **Step 1 (Create Run)**: Button to call `POST /runs`.
    - [ ] **Step 2 (Upload Scan)**: Integration of file upload to `POST /runs/<id>/images`.
    - [ ] **Step 3 (Enter Model)**: Form to update `model_name` via `PATCH /runs/<id>`.
    - [ ] **Step 6 (Continue)**: Final validation and switch to standard `Review Mode`.

---

## Phase 2: Automated Fiducial Detection
Goal: Add registration alignment to the setup flow.

- [ ] **Backend**: Implement `POST /runs/<id>/fiducials/detect` stub/logic.
- [ ] **Backend**: Implement `POST /runs/<id>/fiducials/confirm`.
- [ ] **Frontend**: Add `Step 4 (Find Fiducials)` card with detection trigger and manual confirm/adjust UI.

---

## Phase 3: Automated Barcode Detection
Goal: Add board identification to the setup flow.

- [ ] **Backend**: Implement `POST /runs/<id>/barcode/detect` stub/logic.
- [ ] **Backend**: Implement `POST /runs/<id>/barcode/confirm`.
- [ ] **Frontend**: Add `Step 5 (Find Barcode)` card showing detected region and decoded string.

---

## Success Criteria (Phase 1)
1. [ ] Start with an empty DB.
2. [ ] Click "Create Run" -> New run appears in sidebar.
3. [ ] Upload Image -> Image appears in setup preview.
4. [ ] Enter Model -> "Continue to Review" becomes active.
5. [ ] Click "Continue" -> App switches to standard defect review view.
