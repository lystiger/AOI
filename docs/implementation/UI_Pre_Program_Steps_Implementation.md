# UI Implementation: Pre-Program Setup Flow

## 1. Purpose

This document defines the operator-facing setup flow that must happen before normal AOI review can begin.

It complements [UI_Architecture_Automated_Detection.md](/home/lystiger/projects/AOI/docs/implementation/UI_Architecture_Automated_Detection.md) by answering a different question:

- the automated-detection document explains how the UI should behave when the system is finding fiducials or barcodes
- this document explains how the user enters the workflow from an empty or partially configured state

The goal is to remove dead-end states and replace them with a clear, ordered setup sequence.

## 2. Core Product Decision

The UI should not start with an empty review screen and expect the user to understand hidden dependencies such as runs, scan upload requirements, or optional detection steps.

Instead, the UI should present a guided setup flow from top to bottom.

Recommended sequence:

1. Create Run
2. Upload PCB Scan
3. Enter Model Name
4. Find Fiducial Marks if required
5. Find Barcode if required
6. Continue to Review

This flow should be shown as a persistent step list in the main panel when a run is not yet fully prepared.

## 3. UI Philosophy

The pre-program flow should follow four rules:

- **Ordered:** The user should know what happens first, second, and next.
- **Stateful:** Every step should show whether it is not started, ready, running, done, blocked, failed, or skipped.
- **Conditional:** Optional steps should only appear when the selected product requires them.
- **Recoverable:** The user must be able to revisit completed steps without restarting the whole run.

This keeps the product usable in both empty-start and rework cases.

## 4. Layout Recommendation

When no run is ready for inspection, replace the blank viewer experience with a setup workspace containing:

- a vertical numbered step rail in the main content area
- a detail panel for the currently active step
- a summary/status area showing current run, model, scan status, and validation results

Suggested visual structure:

| Left | Center | Right |
| :--- | :--- | :--- |
| Step list | Active step content | Run summary / validation state |

If the product should remain visually simple, the right column can be merged into the center panel.

## 5. Step Definitions

### Step 1: Create Run

#### Purpose

Create the working record that all later actions attach to.

#### Why it must come first

The current system is run-centric:

- uploaded scans belong to a run
- defect review belongs to a run
- model assignment belongs to a run

Without a run, the rest of the workflow has no stable target.

#### User action

The operator clicks `Create Run`.

#### Expected system behavior

- create a new run ID
- set initial status such as `setup` or `pending`
- automatically select the new run
- move focus to Step 2

#### UI state examples

- `Not started`: no run exists
- `Done`: run created and selected
- `Failed`: backend creation failed

#### Notes

This step must be extremely lightweight. Do not ask for too much information here.

### Step 2: Upload PCB Scan

#### Purpose

Attach the board image that later setup and inspection steps operate on.

#### Why it comes before detection

Fiducial search and barcode search depend on having a scan image.

#### User action

The operator uploads one PCB scan image for the current run.

#### Expected system behavior

- store the image under the selected run
- read image dimensions and metadata
- render the uploaded image immediately
- unlock the next step

#### UI state examples

- `Blocked`: no run selected
- `Ready`: run exists, waiting for file
- `Done`: image uploaded and visible
- `Failed`: upload error or unsupported file

#### Notes

If multi-image runs are needed later, that can extend this step without changing the basic workflow.

### Step 3: Enter Model Name

#### Purpose

Assign the product or model context that determines which setup rules apply.

#### Why it should happen before optional detection steps

The model is the cleanest place to decide:

- whether fiducials are required
- whether barcode detection is required
- what templates or thresholds should be used

#### User action

The operator enters or selects the model name.

#### Expected system behavior

- save the model to the run
- load model-level setup rules if available
- evaluate which later steps are required
- mark optional steps as `Required` or `Not required`

#### UI state examples

- `Ready`: scan exists and model not yet assigned
- `Done`: model saved successfully
- `Failed`: unknown model or validation failure

#### Notes

If the product catalog exists, use search or dropdown selection rather than free text only.

### Step 4: Find Fiducial Marks

#### Purpose

Locate fiducial reference points used for board alignment.

#### Condition

Only show this step if the selected model requires fiducials.

#### User action

The operator starts detection, reviews results, and confirms or corrects them.

#### Expected system behavior

- run automated fiducial detection asynchronously
- show overlays and confidence states on the scan
- auto-accept high-confidence results if policy allows
- require confirmation or manual correction for uncertain results

#### UI state examples

- `Not required`: model does not use fiducials
- `Ready`: model requires fiducials and scan is available
- `Running`: search in progress
- `Needs review`: detections found but require user confirmation
- `Done`: fiducials confirmed
- `Failed`: no valid fiducials found

#### Notes

This step should follow the automated-detection architecture:

- high confidence: transparent and quick approval
- medium confidence: explicit review
- low confidence: manual correction path

### Step 5: Find Barcode

#### Purpose

Locate and validate the barcode if the product uses one.

#### Condition

Only show this step if the selected model requires barcode handling.

#### User action

The operator starts search, validates the detected barcode region and decoded value, then confirms.

#### Expected system behavior

- run barcode detection and decode in the background
- show the detected barcode box and decoded data
- flag uncertain or unreadable results
- allow manual override if detection fails

#### UI state examples

- `Not required`: model does not use barcode setup
- `Ready`: model requires barcode and scan is available
- `Running`: detection in progress
- `Needs review`: region or decode requires confirmation
- `Done`: barcode confirmed
- `Failed`: no barcode found or decode failed

#### Notes

Barcode detection should not block the entire run forever. It should provide a controlled exception path when products are damaged or labels are missing.

### Step 6: Continue to Review

#### Purpose

Transition the user from setup into normal inspection or review mode.

#### User action

The operator clicks `Continue to Review`.

#### Expected system behavior

- confirm all required setup steps are complete
- change run state from setup to review-ready
- open the standard inspection/review layout

#### UI state examples

- `Blocked`: one or more required steps incomplete
- `Ready`: all required steps complete
- `Done`: run is now reviewable

## 6. State Model

Each step should use a consistent state machine.

Recommended statuses:

- `Not started`
- `Blocked`
- `Ready`
- `Running`
- `Needs review`
- `Done`
- `Failed`
- `Skipped`
- `Not required`

These states should be visible in both the step list and the active-step panel.

## 7. Transition Rules

The workflow should enforce simple dependencies:

- `Create Run` must complete before any other step
- `Upload PCB Scan` requires a run
- `Enter Model Name` requires a run and should preferably happen after scan upload
- `Find Fiducial Marks` requires scan upload and a model that needs fiducials
- `Find Barcode` requires scan upload and a model that needs barcode handling
- `Continue to Review` requires all mandatory prior steps to be complete

The UI should allow backward navigation, but it should not silently invalidate dependent steps. If a user changes the model after confirming fiducials or barcode, the system should mark those dependent steps as stale and require reconfirmation.

## 8. Active Step Behavior

The active step panel should always answer:

- what this step is for
- what the user must do now
- what the system is doing
- what blocks the next step

Each step panel should contain:

- a short title
- one-sentence purpose text
- main action button
- current status
- error or warning text if relevant
- next-step consequence

Example:

- Title: `Step 2. Upload PCB Scan`
- Status: `Ready`
- Guidance: `Upload one board image for this run. Detection cannot start until an image is attached.`

## 9. Relationship To Automated Detection

The automated-detection architecture is approved as the behavior inside Steps 4 and 5.

That means:

- the pre-program flow defines when fiducial or barcode detection happens
- the automated-detection document defines how those steps should behave during execution

This separation is important. Without the pre-program flow, the product still has dead-end entry states. Without the automated-detection behavior, the product still has high-friction detection steps.

Both documents are needed.

## 10. Implementation Guidance

### Frontend

Recommended frontend additions:

- a `setup mode` when the selected run is incomplete
- a reusable step component with numbered badges and status chips
- conditional rendering for required versus optional steps
- a step-detail panel that changes with the selected step

### Backend

Recommended backend support:

- endpoint to create a run directly from the UI
- run status fields for setup progress
- fields for model name, fiducial confirmation state, barcode confirmation state
- endpoints or jobs for automated fiducial and barcode detection

### Data model

Likely run-level fields:

- `setup_status`
- `model_name`
- `requires_fiducials`
- `requires_barcode`
- `fiducial_status`
- `barcode_status`

This can be implemented incrementally. The first version does not need every field if derived state is sufficient.

## 11. Recommended First Release Scope

To reduce risk, implement the flow in phases.

### Phase 1

- Create Run
- Upload PCB Scan
- Enter Model Name
- Continue to Review

### Phase 2

- Add fiducial step with automated detection and manual override

### Phase 3

- Add barcode step with automated detection and manual override

This sequence avoids overbuilding before the basic setup workflow is proven.

## 12. Final Recommendation

Approve the automated-detection direction, but do not ship it as a standalone UI change.

The product needs a pre-program setup flow so operators can move from an empty system to a review-ready run without guessing hidden dependencies.

The correct structure is:

1. guided setup flow first
2. automated validation inside the conditional detection steps
3. standard AOI review after required setup is complete

That gives the user a coherent path instead of a blank workspace with disabled controls.
