# PCB Image Overlay Web Layout Specification

## Goal

Define a web layout for AOI review that keeps the PCB image, defect list, and run navigation visible with minimal scrolling.

This document updates the earlier layout direction into a workstation-style screen.

## Core Decision

The review screen should not behave like a dashboard page.

It should behave like an operator workstation:

- thin global header
- compact run rail
- compact defect rail
- large image canvas
- almost no vertical travel before the user can inspect a defect

## Problem With The Earlier Skeleton

The earlier version had the right building blocks, but it still stacked too much content vertically:

- hero area
- summary cards
- run history panel
- review cards
- image viewer

That makes the user scroll before the core inspection loop is even visible.

## Revised First-Screen Rule

On desktop, the first screen should show all of the following at once:

- current run identity
- defect list
- PCB image
- zoom controls
- defect navigation controls

If any of those are below the fold by default, the layout is wrong for this workflow.

## Recommended Desktop Structure

```text
+------------------------------------------------------------------+
| Thin top bar: title | run counts | API/Grafana links             |
+------------------------+-----------------------------------------+
| Run rail               | Review workspace                        |
|                        |                                         |
| Run filters            | Run line + image selector + prev/next   |
| Run history            |-----------------------------------------|
|                        | Defect rail        | Large PCB canvas   |
|                        | filters            | overlays           |
|                        | defect list        | zoom / pan         |
|                        | compact inspector  |                    |
+------------------------+-----------------------------------------+
```

## Layout Regions

### 1. Thin Top Bar

Purpose:

- identify the screen
- show small summary counts
- expose links to API and Grafana

Do not place large descriptive copy here.

Recommended content:

- title
- run count
- fail-run count
- event count
- API link
- Grafana link

### 2. Run Rail

Purpose:

- support switching runs quickly
- keep run filtering available without taking over the page

Contents:

- compact run filters
- scrollable run history list

Rules:

- visually dense
- independently scrollable
- no large cards

### 3. Review Top Bar

Purpose:

- identify the active run
- expose the minimum set of review controls

Contents:

- PCB ID
- status chip
- timestamp
- fail defect count
- image selector
- previous defect
- next defect

This should be a thin control bar inside the review workspace, not a large header block.

### 4. Defect Rail

Purpose:

- drive navigation through the image
- keep filters and selected-defect context nearby

Contents:

- compact defect filters
- scrollable defect list
- compact inspector for the selected defect

Rules:

- this rail must not push the image downward
- the defect list should take most of the rail height
- selected-defect detail should be compact, not a large summary section

### 5. Main PCB Canvas

Purpose:

- present the visual evidence as the primary inspection surface

Behavior:

- full board visible by default
- overlays visible immediately
- zoom with wheel or buttons
- pan when zoomed
- click box to select defect
- double click or command action to fit selected defect

The canvas should dominate the workspace visually.

## Interaction Model

### Row To Canvas

When the user clicks a defect row:

- select that defect
- highlight its overlay
- keep the image visible

Optional but recommended:

- allow a stronger focus action that zooms to the defect

### Canvas To Row

When the user clicks an overlay:

- select that defect
- synchronize the defect list
- update the compact inspector

### Sequential Review

The screen must support:

- previous defect
- next defect

These should move through the currently filtered defect order.

## Controls To Keep

- fit board
- fit defect
- zoom in
- zoom out
- previous defect
- next defect
- image selector if multiple images exist

## Controls To Avoid In The First Release

- large floating toolbars
- freeform drawing tools
- rotate tools unless the source images require them
- dashboard-style summary blocks on this screen

## Density Guidance

This UI should be denser than the previous skeleton.

Recommended:

- short labels
- compact chips
- compact filters
- scrollable rails
- fewer decorative surfaces

Avoid:

- oversized cards
- large marketing copy
- multiple large summary sections
- duplicated run metadata in several places

## Mobile / Narrow Layout

On narrow screens, stack the regions in this order:

1. thin top bar
2. review top bar
3. image canvas
4. defect list
5. compact inspector
6. run rail

On mobile, the image still comes before the long lists.

## First Release Scope

Include:

- compact workstation shell
- one primary image per run
- rectangle overlays
- run rail
- defect rail
- large PCB canvas
- compact inspector
- no-image fallback state

Defer:

- annotation editing
- review comments
- multiple synchronized image panes
- advanced AOI machine controls

## Acceptance Criteria

The layout is acceptable when:

- the image is visible immediately on desktop without scrolling
- the defect list is visible immediately on desktop without scrolling
- the user can move between defects without losing context
- the run rail, defect rail, and image canvas each remain usable independently
- the screen feels like a review workstation rather than a long reporting page

## Recommendation

Build the AOI review UI as a compact workstation with three active zones:

- run rail
- defect rail
- image canvas

That is the right structure for fast defect validation and it avoids the biggest problem in the earlier version: too much vertical scrolling before the actual inspection task begins.
