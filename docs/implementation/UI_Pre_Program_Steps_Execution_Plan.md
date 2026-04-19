# Execution Plan: Pre-Program Setup Flow

## 1. Purpose

This document converts the product direction from:

- [UI_Architecture_Automated_Detection.md](/home/lystiger/projects/AOI/docs/implementation/UI_Architecture_Automated_Detection.md)
- [UI_Pre_Program_Steps_Implementation.md](/home/lystiger/projects/AOI/docs/implementation/UI_Pre_Program_Steps_Implementation.md)

into an implementation plan for this repository.

It focuses on:

- frontend components and rendering rules
- backend endpoints and storage changes
- state transitions
- phased delivery

## 2. Current Repository Baseline

### Frontend

The current web app already supports:

- listing runs from `GET /runs`
- loading run detail from `GET /runs/<run_id>`
- uploading a run image to `POST /runs/<run_id>/images`
- browsing defects and image overlays for a selected run

The current UI is review-first, not setup-first.

### Backend

The current backend already has:

- `inspection_runs`
- `defect_logs`
- `run_images`
- `POST /events`
- `GET /runs`
- `GET /runs/<run_id>`
- `POST /runs/<run_id>/images`

The current backend does not yet support:

- creating an empty run directly from the UI
- storing setup-progress state
- assigning a model name independently of event ingestion
- fiducial/barcode setup job state

## 3. Implementation Goal

When the operator opens the app with no ready run, the main panel should switch into setup mode and guide the user through:

1. Create Run
2. Upload PCB Scan
3. Enter Model Name
4. Find Fiducial Marks if required
5. Find Barcode if required
6. Continue to Review

This must work even when the database is empty.

## 4. Recommended Delivery Strategy

Implement this in three phases.

### Phase 1

Ship the minimum non-dead-end workflow:

- Create Run
- Upload PCB Scan
- Enter Model Name
- Continue to Review

### Phase 2

Add fiducial setup:

- detection job state
- result review
- manual override path

### Phase 3

Add barcode setup:

- detection and decode state
- result review
- manual override path

This order is important. Phase 1 solves the dead end. Phases 2 and 3 add automation on top of a usable workflow.

## 5. Frontend Plan

### 5.1 New UI Modes

Add two major modes to the main review panel:

- `setup mode`
- `review mode`

Recommended rule:

- show `setup mode` when the selected run is incomplete
- show `review mode` when the run is review-ready

Interim fallback:

- if there is no run selected, show `setup mode`

### 5.2 New Component Structure

Add these frontend components under `web/src/`:

- `SetupFlow`
- `SetupStepList`
- `SetupStepCard`
- `SetupStepPanel`
- `RunSetupSummary`
- `CreateRunStep`
- `UploadScanStep`
- `ModelAssignmentStep`
- `FiducialSetupStep`
- `BarcodeSetupStep`
- `ReviewReadyStep`

This can start as a single-file implementation inside `App.jsx` if speed matters, but the target structure should separate step UI from the review viewer.

### 5.3 Recommended App State Additions

Add frontend state for:

- `setupStepId`
- `isCreatingRun`
- `isSavingModel`
- `runSetupStatus`
- `runModelName`
- `requiresFiducials`
- `requiresBarcode`
- `fiducialStatus`
- `barcodeStatus`

Initial derived state can be computed from the run payload until the backend returns richer setup metadata.

### 5.4 Rendering Rules

#### History Rail

Keep the History rail, but change the empty-state copy to support setup mode.

If no runs exist:

- show `Create Run` CTA in the rail or main setup panel

If runs exist:

- selecting a run should open setup mode or review mode depending on completion

#### Main Panel

If no selected run:

- render setup mode with Step 1 active

If selected run exists but has no image:

- render setup mode with Step 2 active

If selected run has image but no model:

- render setup mode with Step 3 active

If selected run is setup-complete:

- render review mode

### 5.5 Step Status Model

Each step should expose:

- `id`
- `label`
- `status`
- `required`
- `active`
- `description`

Recommended statuses:

- `not_started`
- `blocked`
- `ready`
- `running`
- `needs_review`
- `done`
- `failed`
- `skipped`
- `not_required`

### 5.6 Step Computation Logic

For Phase 1:

- Step 1 `Create Run`
  - `done` if `selectedRunId` exists
  - `ready` if no selected run

- Step 2 `Upload PCB Scan`
  - `blocked` if no selected run
  - `done` if `selectedRun.images.length > 0`
  - `ready` otherwise

- Step 3 `Enter Model Name`
  - `blocked` if no selected run
  - `done` if `selectedRun.model_name` or equivalent exists
  - `ready` otherwise

- Step 4 `Find Fiducials`
  - `not_required` until model rules say required

- Step 5 `Find Barcode`
  - `not_required` until model rules say required

- Step 6 `Continue to Review`
  - `ready` when all required previous steps are `done`
  - `blocked` otherwise

### 5.7 UX Behaviors

#### Create Run

The primary CTA in empty state should be `Create Run`.

On success:

- prepend new run into the run list
- select it automatically
- activate Step 2

#### Upload Scan

The upload control should exist inside the step panel.

The topbar upload button can remain as a shortcut, but setup mode must provide the primary flow.

#### Model Assignment

Phase 1 should support a simple text field and save action.

If model rules do not yet exist, use a default policy:

- `requires_fiducials = false`
- `requires_barcode = false`

Later, replace this with catalog-backed rules.

#### Continue to Review

This CTA should switch the main panel back to the existing viewer/review layout.

If review mode is just a frontend decision in Phase 1, that is acceptable. Backend run status can be added later.

## 6. Backend Plan

### 6.1 New Endpoints

Add the following endpoints.

#### `POST /runs`

Purpose:

- create an empty run directly from the UI

Suggested request body:

```json
{
  "pcb_id": "optional-string"
}
```

Suggested response:

```json
{
  "status": "ok",
  "run": {
    "id": "uuid",
    "pcb_id": "RUN-20260419-001",
    "timestamp": "2026-04-19T12:00:00+00:00",
    "status": "SETUP",
    "model_name": null,
    "setup_status": "not_ready"
  }
}
```

Notes:

- if `pcb_id` is omitted, generate one server-side
- this is the critical endpoint that removes the dead end

#### `PATCH /runs/<run_id>`

Purpose:

- update run-level setup fields without event ingestion

Suggested request body:

```json
{
  "model_name": "ABC-BOARD-V2"
}
```

Phase 1 scope:

- support `model_name`
- optionally support `status`

Later scope:

- support setup fields like `requires_fiducials`, `requires_barcode`, `setup_status`

#### Future endpoints for Phase 2 and 3

- `POST /runs/<run_id>/fiducials/detect`
- `POST /runs/<run_id>/fiducials/confirm`
- `POST /runs/<run_id>/barcode/detect`
- `POST /runs/<run_id>/barcode/confirm`

These should not block Phase 1.

### 6.2 Database Changes

Extend `inspection_runs` with setup-oriented fields.

Recommended columns:

- `model_name TEXT`
- `setup_status TEXT NOT NULL DEFAULT 'not_ready'`
- `requires_fiducials INTEGER`
- `requires_barcode INTEGER`
- `fiducial_status TEXT`
- `barcode_status TEXT`

If keeping schema changes smaller in Phase 1, the minimum useful addition is:

- `model_name TEXT`
- `setup_status TEXT NOT NULL DEFAULT 'not_ready'`

### 6.3 DatabaseManager Methods

Add methods to `DatabaseManager`:

- `create_run(...)`
- `update_run(...)`
- `list_runs(...)` should include setup fields
- `fetch_run(...)` should include setup fields

Suggested method responsibilities:

#### `create_run`

- generate run ID
- generate default `pcb_id` if omitted
- set timestamp
- set `status = 'SETUP'`
- set `setup_status = 'not_ready'`
- insert row
- return run payload

#### `update_run`

- allow partial updates
- validate supported fields
- recompute `setup_status` if enough data exists

### 6.4 Service Layer Changes

In `src/aoi/service.py`:

- add `POST /runs`
- add `PATCH /runs/<run_id>`
- update `GET /runs` and `GET /runs/<run_id>` serialization to include new setup fields

Keep the existing routes unchanged to avoid breaking the current frontend.

## 7. Run State Model

Add a clear separation between:

- inspection outcome status
- setup completion status

Do not overload one field for both concerns.

Recommended interpretation:

- `status`
  - current inspection or run lifecycle value such as `SETUP`, `PASS`, `FAIL`
- `setup_status`
  - `not_ready`
  - `in_progress`
  - `review_ready`

Phase 1 can use a simpler rule:

- new run starts as `SETUP`
- after required steps complete, set `setup_status = 'review_ready'`

## 8. Detailed Phase Plan

### Phase 1 Tasks

#### Backend

1. Add `model_name` and `setup_status` columns to `inspection_runs`
2. Add `DatabaseManager.create_run`
3. Add `DatabaseManager.update_run`
4. Add `POST /runs`
5. Add `PATCH /runs/<run_id>`
6. Extend run serializers for list/detail responses

#### Frontend

1. Add setup-mode state computation
2. Add step-list rendering in the main panel
3. Add `Create Run` action wired to `POST /runs`
4. Reuse existing image upload flow inside the step panel
5. Add model-name form wired to `PATCH /runs/<run_id>`
6. Add `Continue to Review` action
7. Keep the current review viewer as the destination state

#### Validation

Test these paths:

- empty database -> create run -> upload image -> save model -> review mode
- existing run without image -> setup mode opens at Step 2
- existing run with image but no model -> setup mode opens at Step 3
- existing review-ready run -> review mode opens directly

### Phase 2 Tasks

#### Backend

1. Add fiducial status fields if not already present
2. Add fiducial detection route(s)
3. Store detection results and confirmation state

#### Frontend

1. Add fiducial step card and step panel
2. Render overlays and confidence state
3. Add confirm/retry/manual override actions

### Phase 3 Tasks

#### Backend

1. Add barcode status fields if not already present
2. Add barcode detect/decode route(s)
3. Store decoded value and review state

#### Frontend

1. Add barcode step card and step panel
2. Render barcode region and decoded value
3. Add confirm/retry/manual override actions

## 9. Risks And Design Constraints

### Risk 1: Mixing Setup And Review Concerns

If setup logic is scattered into the existing review viewer, the code will become hard to reason about.

Recommendation:

- isolate setup-mode rendering from review-mode rendering

### Risk 2: Overloading `status`

If `status` is used for both inspection result and setup progress, the model will become ambiguous.

Recommendation:

- keep `setup_status` separate

### Risk 3: Frontend-Only Setup State

If review readiness only exists in the frontend, later automation steps will be harder to coordinate.

Recommendation:

- accept derived frontend logic in early Phase 1 if needed
- move to explicit backend fields before Phase 2

### Risk 4: Optional-Step Timing

If model rules are not defined yet, optional steps will behave unpredictably.

Recommendation:

- Phase 1 should default optional steps to `not_required`
- Phase 2 and 3 should introduce model-driven requirements

## 10. Recommended File-Level Change List

### Backend

- `src/aoi/database.py`
  - add columns
  - add run creation/update methods
  - extend fetch/list queries

- `src/aoi/service.py`
  - add `POST /runs`
  - add `PATCH /runs/<run_id>`
  - include setup fields in responses

- `src/aoi/schema.py`
  - add request/response helpers if needed for run create/update payload validation

- `tests/test_database.py`
  - add run creation/update coverage

- `tests/test_service.py`
  - add endpoint coverage for `POST /runs` and `PATCH /runs/<run_id>`

### Frontend

- `web/src/App.jsx`
  - add setup-mode orchestration
  - add create-run flow
  - add model-name save flow
  - switch between setup and review modes

- `web/src/App.css`
  - add setup-step layout styles

If the setup UI grows, split `App.jsx` into component files after Phase 1 stabilization.

## 11. Success Criteria

Phase 1 is successful when:

- the app is usable from an empty database
- a user can create a run without external ingestion
- a user can upload a PCB scan to that run
- a user can save a model name
- the UI can transition into review mode without hidden prerequisites

Phase 2 and 3 are successful when:

- optional detection steps only appear when required
- the automated detection behavior follows the approval/correction model from the architecture document

## 12. Final Recommendation

Implement Phase 1 immediately.

The current dead-end is not a styling problem. It is a missing product path. The smallest correct fix is to make run creation and run preparation first-class actions in the UI and backend.

After that, integrate automated fiducial and barcode detection as conditional setup steps instead of isolated features.
