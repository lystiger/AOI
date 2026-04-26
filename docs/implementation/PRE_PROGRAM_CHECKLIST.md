# Pre-Program Setup: Current Status And Verification

This document is the current-state verification guide for the "Pre-Program" flow in this repository.

It replaces the older greenfield framing with a sharper question:

- what is already implemented
- what is currently mocked or simulated
- what still blocks production readiness

Use this document as the signoff surface for the setup workflow and as the handoff surface for the next milestone.

## Status Legend

- `Shipped`: implemented in the app and covered by code/tests
- `Partial`: implemented, but with known gaps in error handling or operator recovery
- `Mocked`: workflow exists, but core automation is synthetic
- `Missing`: expected by the product flow, not yet implemented

## Current Project Read

### What is real today

- Empty runs can be created from the UI and backend.
- A run can store a scan image and model name before any review data exists.
- Setup status is persisted and survives refresh/reload.
- Required fiducial and barcode steps can be toggled per run.
- A completed run can be forced back into setup when model requirements change.
- The UI already switches between setup mode and review mode.

### What is still mocked

- Fiducial detection returns generated overlay data, not computer-vision output.
- Barcode detection returns generated region and decoded value data, not decoder output.
- Detection endpoints behave like synchronous mock actions, not durable async jobs.

### What is not production-ready yet

- Detection failure handling is now present, but still heuristic and metadata-driven rather than vision-driven.
- Manual fiducial and barcode fallback is implemented, but the UI still uses numeric form entry instead of interactive placement.
- The checklist has more confidence than the automation layer deserves unless mocked behavior is called out explicitly.

## Phase 1: Guided Run Creation And Preparation

Goal: remove setup dead ends and provide a robust manual path into review.

### 1.1 Backend: Persistence And API

| Requirement | Verification Point | Status | Notes |
| :--- | :--- | :---: | :--- |
| Schema integrity for setup fields | `src/aoi/database.py` (`_initialize`) | `Shipped` | Setup columns exist and are exercised by tests. |
| Migration fallback for older databases | `src/aoi/database.py` | `Shipped` | Legacy column-add paths exist; keep regression coverage on upgraded DBs. |
| Run creation | `POST /runs` -> `src/aoi/service.py` (`_handle_create_run`) | `Shipped` | Empty setup run with generated PCB ID is covered in `tests/test_service.py`. |
| Run updates | `PATCH /runs/<run_id>` -> `src/aoi/service.py` (`_handle_patch_run`) | `Shipped` | Partial update path and missing-run handling are covered. |
| Model validation | `src/aoi/service.py` (`_handle_patch_run`) | `Shipped` | Rejects non-string and whitespace-only values. |
| Setup status transitions | `src/aoi/database.py` (`_calculate_setup_status`) | `Shipped` | `not_ready`, `in_progress`, and `review_ready` are all exercised. |

### 1.2 Frontend: Setup Orchestration

| Requirement | Verification Point | Status | Notes |
| :--- | :--- | :---: | :--- |
| Setup mode trigger | `web/src/App.jsx` (`showSetupMode`) | `Shipped` | Setup mode appears for incomplete runs and survives refresh via persisted selection. |
| Step progression | `web/src/App.jsx` (`setupSteps`) | `Shipped` | Sequential activation exists, with auto-focus on the next actionable step. |
| Backward navigation and revisit | `web/src/App.jsx` (`manualStepId`) | `Shipped` | Completed steps can be revisited without rebuilding the run. |
| Image upload | `web/src/App.jsx` (`handleImageUpload`) | `Shipped` | Success and invalid file handling are present. |
| Model saving | `web/src/App.jsx` (`handleSaveModel`) | `Partial` | Persistence works, but network-failure behavior should be treated as a UX hardening area. |
| Rework and revisit behavior | `src/aoi/database.py` (`update_run`) | `Shipped` | Model or requirement changes correctly reset dependent setup artifacts. |

## Phase 2: Fiducial Detection

Goal: alignment flow exists in product terms, but automation is still synthetic.

### 2.1 Detection Flow

| Requirement | Verification Point | Status | Notes |
| :--- | :--- | :---: | :--- |
| Detect endpoint exists | `POST /runs/<id>/fiducials/detect` | `Shipped` | Endpoint and status transitions are implemented. |
| Running/reviewable setup UI exists | `web/src/App.jsx` | `Shipped` | Review step, preview, and confirm CTA are present. |
| Detection data source is real CV output | `src/aoi/database.py` (`detect_fiducials`) | `Mocked` | Uses `_build_mock_fiducials(...)`, not image analysis. |
| Failure path | UI + backend detect flow | `Partial` | Failed detection is now represented explicitly, but the trigger is still heuristic rather than CV-driven. |
| Manual correction fallback | UI fiducial step | `Partial` | Operator can recover by entering numeric boxes manually, but interactive placement/editing is still missing. |
| Verification coverage | `tests/test_database.py`, `tests/test_service.py` | `Shipped` | Current tests verify state transitions, not real detection accuracy. |

## Phase 3: Barcode Detection

Goal: identification flow exists in product terms, but automation is still synthetic.

### 3.1 Validation Flow

| Requirement | Verification Point | Status | Notes |
| :--- | :--- | :---: | :--- |
| Detect endpoint exists | `POST /runs/<id>/barcode/detect` | `Shipped` | Endpoint and state transitions are implemented. |
| Needs-review flow exists | `web/src/App.jsx` | `Shipped` | Preview and confirm UI are present. |
| Detection/decoding data source is real | `src/aoi/database.py` (`detect_barcode`) | `Mocked` | Uses `_build_mock_barcode(...)`, not barcode localization/decoding. |
| Auto-complete on high confidence | Backend + UI | `Missing` | Current flow still routes through confirm. |
| Decode-failure/manual serial entry path | UI + backend | `Shipped` | Operator can recover with a manual decoded value and normalized barcode box. |
| Verification coverage | `tests/test_database.py`, `tests/test_service.py` | `Shipped` | Current tests verify workflow transitions, not real barcode robustness. |

## End-To-End Operator Stress Tests

These are the scenarios that matter most for signoff on the current workflow.

| Scenario | Status | Notes |
| :--- | :---: | :--- |
| Dirty exit: create run, upload scan, close browser, resume later | `Shipped` | Selection/setup persistence exists in the frontend. |
| Model swap after completion resets dependent setup | `Shipped` | Covered in database and service tests. |
| Bad upload stays in setup with an error | `Shipped` | Current upload path preserves setup mode on failure. |
| Delete selected run clears setup state cleanly | `Shipped` | Backend delete exists and UI handles the ghost-run case. |
| Continue-to-review remains locked while setup is incomplete | `Shipped` | Derived readiness gating is present in the UI. |
| Detection failure can be recovered manually | `Shipped` | Failed detection can now be completed via manual fiducial/barcode entry. |

## Recommended Next Milestone

The next milestone should not be "more setup UI." The workflow shell is already in place.

The next milestone should be:

### Milestone: Replace Mock Detection With Recoverable Real Detection

Scope:

- replace `_build_mock_fiducials(...)` with a real detection integration
- replace `_build_mock_barcode(...)` with a real localization/decode integration
- replace heuristic failure gates with actual image-analysis failure states such as "nothing found" and "decode failed"
- upgrade manual fiducial recovery from numeric entry to interactive placement/editing
- keep the manual barcode override, but back it with real localization/decode results when available
- keep the current setup-state machine and reuse the existing setup UI

Success criteria:

- setup remains usable even when automation fails
- setup can complete without synthetic data
- tests distinguish workflow-state coverage from detection-engine coverage

## Traceability

### Core backend logic

- `src/aoi/database.py`
- look for `_calculate_setup_status`
- look for `update_run`
- look for `detect_fiducials`
- look for `detect_barcode`

### Core backend routes

- `src/aoi/service.py`
- look for `_handle_create_run`
- look for `_handle_patch_run`
- look for `_handle_detect_fiducials`
- look for `_handle_detect_barcode`

### Core frontend logic

- `web/src/App.jsx`
- look for `setupSteps`
- look for `showSetupMode`
- look for `handleImageUpload`
- look for `handleSaveModel`

### Tests backing current status

- `tests/test_database.py`
- `tests/test_service.py`
