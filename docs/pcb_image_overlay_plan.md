# PCB Scan Image And Defect Overlay Implementation Plan

## Goal

Add run-level PCB scan images to the AOI workflow so an operator can open an inspection run, view the scanned board image, and see defect locations overlaid on that image.

This plan is intentionally scoped as an extension of the current system:

- keep the existing `inspection_runs` and `defect_logs` model
- add image metadata and defect coordinates around that model
- support a mock/demo image phase before real AOI scanner integration

## Problem Statement

The current UI and API expose inspection runs and defect rows, but they do not show the visual evidence behind those defects. That creates three gaps:

- operators must interpret failures from table data alone
- there is no fast visual confirmation path for false positives
- the frontend does not yet resemble a real AOI review workflow

The feature should solve those gaps without turning the current repo into a full image-processing platform in one step.

## Non-Goals

This plan does not assume the first release will:

- run computer vision directly in the browser
- generate synthetic PCB images as inspection evidence
- replace the existing runs table or defect detail view
- solve long-term image archival policy beyond basic local storage conventions

## Recommended Product Shape

The first useful product is:

1. open an inspection run
2. show one PCB scan image for that run
3. draw defect markers at known coordinates
4. link markers and defect rows both ways
5. keep the existing table-based workflow as a fallback

This is stronger than an AI-generated demo image because it preserves the core AOI idea: defects should point back to evidence.

## Current System Baseline

The current backend already has:

- `inspection_runs`: run header data such as `id`, `pcb_id`, `timestamp`, `model_version`, `status`
- `defect_logs`: per-event defect rows linked by `run_id`
- `GET /runs`
- `GET /runs/<run_id>`
- `GET /runs/<run_id>/defects`

The current system does not yet store:

- image file paths or image URLs
- image dimensions
- defect bounding boxes or point coordinates
- component-region metadata for image overlays

## Proposed Rollout

### Phase 1: Mock Image Support

Use static PCB scan images for a subset of runs and manually attach coordinates for defects.

Purpose:

- prove the UI workflow
- validate the API shape
- avoid blocking on scanner integration

Deliverables:

- image metadata attached to selected runs
- defect overlay coordinates for selected defect rows
- frontend image panel with clickable markers

### Phase 2: Real Run Image Association

Store real run image references produced by the AOI process and attach them to inspection runs at ingest time or shortly after.

Purpose:

- move from demo behavior to real operator evidence
- preserve current inspection history while expanding detail

Deliverables:

- stable storage location for scan images
- ingestion path for run-to-image mapping
- validation that each run references an expected image asset

### Phase 3: Multi-Image And Crop Support

Support more than one image per run when the AOI machine produces multiple views or crops.

Purpose:

- support realistic AOI capture patterns
- handle zoomed inspection regions without forcing one large board image

Deliverables:

- one-to-many run image model
- image selector in the frontend
- defect records linked to the correct source image

## Data Model Changes

### Option A: Minimal Schema Extension

Add columns directly to existing tables.

Suggested additions:

- `inspection_runs.image_path`
- `inspection_runs.image_width`
- `inspection_runs.image_height`
- `defect_logs.overlay_x`
- `defect_logs.overlay_y`
- `defect_logs.overlay_width`
- `defect_logs.overlay_height`

Pros:

- simple migration
- easy to ship in the current codebase

Cons:

- weak support for multi-image runs
- image metadata becomes cramped over time

### Option B: Recommended Schema Extension

Add a dedicated run-image table and keep overlay data on `defect_logs`.

Suggested tables:

#### `run_images`

- `id`
- `run_id`
- `image_path`
- `image_role`
- `image_width`
- `image_height`
- `sort_order`
- `created_at`

#### Additions to `defect_logs`

- `run_image_id`
- `overlay_x`
- `overlay_y`
- `overlay_width`
- `overlay_height`
- `overlay_shape`

Why this is the better direction:

- supports one or many images per run
- allows future image roles such as `full_board`, `crop`, `side_view`
- keeps the run header clean

## Coordinate Model

The overlay contract needs to be defined early. The safest choice is normalized image coordinates.

Recommended format:

- `overlay_x`: left position from `0.0` to `1.0`
- `overlay_y`: top position from `0.0` to `1.0`
- `overlay_width`: width from `0.0` to `1.0`
- `overlay_height`: height from `0.0` to `1.0`

Why normalized coordinates:

- frontend overlays scale cleanly with responsive image sizing
- avoids recalculating when source images have different pixel dimensions
- easier to validate across environments

Initial supported shape:

- rectangle

Later extensions:

- point marker
- polygon
- segmentation mask

## Storage Plan

### Near-Term

Store images on local disk in a predictable path, for example:

```text
data/images/<run_id>/<filename>
```

Serve those images through the AOI backend.

This keeps the first implementation simple and consistent with the current local SQLite and file-backed setup.

### Later

Move image storage behind object storage or a dedicated artifact service if image volume becomes large.

That step should be deferred until:

- image retention requirements are defined
- throughput is known
- the project outgrows local Docker volume storage

## API Changes

### Extend Run Detail Response

Add image information to `GET /runs/<run_id>`.

Suggested response shape:

```json
{
  "status": "ok",
  "run": {
    "id": "run-123",
    "pcb_id": "PCB-001",
    "timestamp": "2026-04-19T10:00:00Z",
    "status": "FAIL",
    "model_version": "v1",
    "event_count": 3,
    "images": [
      {
        "id": "img-1",
        "image_path": "/runs/run-123/images/board.png",
        "image_role": "full_board",
        "image_width": 2048,
        "image_height": 1536
      }
    ],
    "defect_logs": [
      {
        "id": 10,
        "component_id": "U002",
        "defect_type": "MISALIGNMENT",
        "severity": "major",
        "inspection_result": "FAIL",
        "overlay_shape": "rect",
        "overlay_x": 0.42,
        "overlay_y": 0.31,
        "overlay_width": 0.06,
        "overlay_height": 0.04,
        "run_image_id": "img-1"
      }
    ]
  }
}
```

### Add Image Delivery Route

Add a backend route that serves stored images safely.

Examples:

- `GET /runs/<run_id>/images/<image_id>`
- or a static file route with strict run scoping

Requirements:

- no arbitrary filesystem traversal
- clear not-found behavior
- content type derived safely

### Ingestion Strategy

Do not expand the original event payload immediately unless real image metadata is already available from the producer.

Safer first step:

- persist events as today
- attach image metadata in a second operation or fixture loader for demo runs

Later, if upstream AOI systems can provide image references reliably, extend the ingestion contract.

## Frontend Changes

### New Detail Panel Section

Keep the current runs list and defect table. Add an image viewer to the run detail view.

Recommended behavior:

- show the primary board image above or beside the defect table
- render overlay rectangles for each defect with coordinates
- hover marker highlights the matching row
- selecting a row highlights the matching marker

### Interaction Model

First release should support:

- fit-to-panel image view
- marker hover state
- marker click to focus defect row
- defect row click to focus marker

Second release can add:

- zoom
- pan
- image selector for multi-image runs
- filter to show only failing defects

### Empty State Behavior

If a run has no image:

- do not fail the run detail page
- show a clear “No scan image available for this run” state
- keep defect table functional

## Backend Work Breakdown

1. Add schema migration logic for image and overlay metadata.
2. Add read/write methods in `DatabaseManager` for run images and overlay fields.
3. Extend run detail serialization to include image metadata and overlay fields.
4. Add image-serving route with path validation.
5. Add seed or fixture support for mock images tied to selected runs.

## Frontend Work Breakdown

1. Extend the run detail fetch shape to accept `images` and overlay metadata.
2. Add a PCB image viewer component.
3. Render overlay markers using normalized coordinates.
4. Link row selection and marker selection.
5. Add empty and error states for missing image data.

## Testing Plan

### Backend

- migration tests for new tables or columns
- serialization tests for run detail with images
- image route tests for valid and invalid paths
- fixture tests for runs with and without image metadata

### Frontend

- render test for runs without images
- render test for runs with one image and multiple overlays
- interaction test for row-to-marker highlighting
- interaction test for marker-to-row highlighting

### Manual

- open a run with a mock image
- verify markers scale correctly when the browser width changes
- confirm filters still work on defect rows
- confirm missing-image runs degrade gracefully

## Risks And Decisions

### Risk: Coordinates Without A Stable Contract

If upstream systems provide inconsistent coordinate conventions, the overlay feature will look broken even if the UI is correct.

Decision:

- define one normalized coordinate contract before wiring real image ingestion

### Risk: One Image Per Run May Be Too Simple

Some AOI systems capture multiple images, crops, or angles.

Decision:

- prefer a `run_images` table over a single image path on `inspection_runs`

### Risk: Image Size And Performance

Large scanned images can slow page rendering and local Docker workflows.

Decision:

- first ship one display-size image per run
- defer deep zoom tiles or large-image optimization

### Risk: Mock Data Diverges From Real AOI Output

A demo path can become a dead end if the data contract is unrealistic.

Decision:

- keep mocks shaped like expected real data
- do not use AI-generated images as inspection evidence in the real workflow

## Recommended Milestone Order

### Milestone 1

Schema extension, mock images, one image per run, rectangle overlays, basic viewer.

### Milestone 2

Real image association from AOI output, safer image storage conventions, improved run detail API.

### Milestone 3

Multi-image runs, zoom/pan, richer annotation shapes.

## Definition Of Done For First Release

The first release should be considered complete when:

- at least one inspection run can display a PCB scan image
- at least one defect row renders a visible overlay on that image
- clicking the row and the marker syncs selection state
- runs without images still load correctly
- the backend serves image assets safely

## Recommendation

Implement this as a visual evidence layer on top of the current AOI run detail flow, not as a separate image application.

The most pragmatic path is:

1. add a `run_images` table
2. add normalized rectangle overlay fields
3. support mock images first
4. wire the UI interaction
5. integrate real scanner images only after the overlay contract is stable
