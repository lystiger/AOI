# PCB Image Overlay Web Layout Specification

## Goal

Define the web UI layout for reviewing AOI inspection runs with a zoomable PCB image and clickable defect overlays.

This document is a UI specification for the feature planned in `docs/pcb_image_overlay_plan.md`.

## Design Intent

The PCB image should be the primary working surface.

The layout should support the real operator task:

1. open a run
2. identify failed defects quickly
3. jump to the defect visually
4. inspect the marked area
5. decide whether the call looks valid

This should feel like an AOI review console adapted for the web, not like a generic image gallery.

## Core Principles

- the board image is the main content, not a secondary attachment
- defect navigation should be driven by both image overlays and structured defect rows
- zoom and pan are necessary, but they should support defect review rather than replace it
- the interface should stay usable when a run has no image
- controls should be lighter than a desktop AOI machine UI

## Recommended Screen Structure

Use a three-part layout on desktop:

1. left panel: run context and defect list
2. main canvas: zoomable PCB image with overlays
3. top utility bar: image controls and quick navigation

### Desktop Layout

Suggested structure:

```text
+---------------------------------------------------------------+
| Header: Run title | status | image selector | zoom controls   |
+----------------------+----------------------------------------+
| Left panel           | Main image canvas                      |
|                      |                                        |
| Run summary          |  PCB image                             |
| Defect filters       |  bounding boxes / markers              |
| Defect list          |  selected-defect callout               |
| Selected detail      |                                        |
|                      |                                        |
+----------------------+----------------------------------------+
```

### Mobile / Narrow Layout

Use a stacked layout:

1. header and quick controls
2. image canvas
3. selected defect summary
4. defect list

On small screens, avoid showing a persistent side panel beside the image.

## Layout Regions

### 1. Header / Utility Bar

Purpose:

- identify the current run
- expose the minimum set of image controls
- give access to quick navigation

Recommended contents:

- run ID or PCB ID
- run status chip
- image selector if multiple images exist
- `Fit board`
- `Fit defect`
- zoom in
- zoom out
- reset view
- next defect
- previous defect

Controls that should be avoided in the first release:

- large floating icon stacks
- freeform drawing tools
- rotate image tools unless the source images actually require rotation

### 2. Left Panel

Purpose:

- keep structured inspection context visible
- provide fast, defect-driven navigation

Recommended sections:

#### Run Summary

Include:

- PCB ID
- timestamp
- status
- model version
- total event count
- fail count

#### Defect Filters

Include:

- defect type
- severity
- inspection result
- component search
- review status if that state exists later

#### Defect List

Each row should show:

- component ID
- defect type
- severity
- confidence score
- review state

Each row should support:

- click to focus the corresponding overlay
- hover to highlight the corresponding overlay

#### Selected Defect Detail

When a defect is selected, show:

- component ID
- defect type
- severity
- inspection result
- confidence score
- timestamp
- image name or view name

This section should be compact. The image remains the main inspection surface.

### 3. Main PCB Canvas

Purpose:

- present the board image as the central evidence view
- allow the operator to inspect the marked region closely

Behavior:

- image should fit the available canvas by default
- zoom should center on the pointer or selected defect
- pan should be enabled when zoomed in
- overlays should scale with the image
- the selected defect should remain visually distinct at all zoom levels

The canvas should support:

- mouse wheel zoom
- drag to pan
- click overlay to select defect
- keyboard navigation for next/previous defect if practical

## Overlay Design

### Overlay Types

First release should support:

- rectangle bounding boxes

Later releases may support:

- points
- polygons
- segmentation masks

### Overlay States

The overlays need more than one color if the user is expected to review them.

Recommended states:

- `default`: visible but not emphasized
- `hovered`: stronger outline
- `selected`: strongest outline and optional glow
- `confirmed`: stable success color
- `false_positive`: muted or alternate color
- `hidden_by_filter`: not rendered

### Visual Rules

- overlays must remain visible on dark and bright PCB areas
- selected overlays should use stronger stroke width, not only color
- small defects should have a minimum clickable target
- labels should not permanently clutter the board at full zoom-out

Recommended approach:

- draw boxes at all times
- show labels only for hovered or selected overlays

## Selection And Navigation Model

Selection must be synchronized across all views.

### Defect Row -> Canvas

When the user clicks a defect row:

- that defect becomes selected
- the image pans or zooms to bring the defect into focus
- the overlay becomes visually emphasized
- the selected defect detail updates

### Canvas -> Defect Row

When the user clicks an overlay:

- that defect becomes selected
- the list scrolls to the matching row if needed
- the selected defect detail updates

### Keyboard / Sequential Navigation

Support:

- next defect
- previous defect

These actions should move in the currently filtered order.

This matters because operators often work defect-by-defect, not board-by-board manually.

## Zoom And Pan Behavior

This is the part that can make the feature feel professional or frustrating.

### Default View

On initial load:

- fit the full board within the canvas
- center the image
- render all visible overlays

### Zoom Controls

Required:

- mouse wheel or trackpad pinch zoom
- button zoom in
- button zoom out
- reset view
- fit selected defect

Recommended:

- animated transition when jumping to a defect

Avoid:

- over-smooth animation that slows defect review

### Pan Controls

Required:

- click-and-drag pan when zoomed in

Recommended:

- constrain panning enough that the user cannot lose the board entirely

### Minimap

A minimap is not mandatory for the first release, but becomes useful if:

- images are very large
- the user often zooms deeply
- multi-image runs are introduced

If added later, it should show:

- current viewport rectangle
- selected defect location

## Empty And Fallback States

### No Image For Run

If a run does not have an image:

- show a neutral placeholder in the canvas
- explain that no scan image is available
- keep the defect list usable

Do not make the whole run detail page look broken.

### No Defects Match Filters

If filters remove all visible defects:

- keep the image visible
- hide filtered overlays
- show a clear message in the list area

### Image Failed To Load

If the image path exists in metadata but cannot be loaded:

- show an error state in the canvas
- keep the defect list visible
- avoid clearing the whole run detail panel

## Recommended First-Release Scope

The first release should stay tight.

Include:

- one primary image per run
- rectangle overlays
- click row to focus overlay
- click overlay to focus row
- zoom in/out
- drag to pan
- fit board
- fit selected defect
- selected defect detail card
- no-image fallback state

Defer:

- annotation editing
- overlay drawing tools
- review comments
- multiple synchronized panes
- advanced AOI machine controls

## Styling Direction

The UI should look like an operations tool, not a marketing dashboard.

Recommended direction:

- dark or neutral canvas area around the PCB image
- high-contrast overlay colors
- compact information density in the left panel
- clear chips for status and severity
- restrained motion

Avoid:

- oversized cards
- decorative gradients on the inspection surface
- visual noise that competes with overlays

## Data Contract Needed By The UI

The UI expects, at minimum:

- run metadata
- one or more image records
- defect records
- image ID linked from each defect
- normalized overlay coordinates
- optional overlay shape

Example frontend shape:

```json
{
  "run": {
    "id": "run-123",
    "pcb_id": "PCB-001",
    "status": "FAIL",
    "images": [
      {
        "id": "img-1",
        "image_path": "/runs/run-123/images/board.png",
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
        "run_image_id": "img-1",
        "overlay_shape": "rect",
        "overlay_x": 0.42,
        "overlay_y": 0.31,
        "overlay_width": 0.06,
        "overlay_height": 0.04
      }
    ]
  }
}
```

## Acceptance Criteria

The layout is acceptable for the first implementation when:

- the user can open a run and immediately see the board image
- the user can zoom and pan without losing overlay alignment
- clicking a defect row focuses the corresponding image region
- clicking a bounding box focuses the corresponding defect row
- the selected defect is clearly distinguishable from all others
- the UI remains usable when no image is available

## Recommendation

Build the web layout around a synchronized defect list and image canvas.

The desktop AOI reference image is useful as a workflow reference, but the web implementation should simplify it:

- fewer controls
- stronger selection behavior
- clearer list-to-image synchronization
- more emphasis on the selected defect than on general tooling
