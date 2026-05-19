# Frontend Styling Refactor Plan
**Date:** May 19, 2026
**Status:** Planned
**Scope:** Refactor the frontend styling architecture after the React component/hook decomposition.

## 1. Objective
The frontend is no longer blocked by the old `App.jsx` monolith, but styling is still concentrated in a large global stylesheet. The next pass should improve maintainability, reduce regression risk, and tighten the visual system without doing a ground-up UI redesign.

## 2. Current State
### 2.1 What is already improved
* `web/src/App.jsx` is now a thin composition layer.
* Major UI areas already exist as separate components:
  * `RunRail`
  * `ReviewWorkspace`
  * `SetupFlow`
  * `PcbViewer`
  * `SettingsPanel`
* State and workflow logic have already been extracted into hooks.

### 2.2 What is still a bottleneck
* `web/src/App.css` is still a large global stylesheet and remains the main frontend maintenance risk.
* `web/src/index.css` still carries root-level defaults from an older dark theme direction, while `App.css` defines the current visual identity.
* Layout, component, and theme concerns are mixed together, which makes targeted edits slower and more fragile.

## 3. Refactor Goals
1. **Unify the visual system**
   * Choose one canonical theme baseline.
   * Remove stale or conflicting root theme assumptions.
   * Normalize tokens for spacing, radius, borders, and typography.

2. **Decompose styling by responsibility**
   * Split shell/layout rules from component-specific rules.
   * Group styles by feature area instead of keeping everything in one file.
   * Keep shared primitives separate from screen-level composition styles.

3. **Preserve the current product direction**
   * Keep the existing workstation/editorial-light feel unless a concrete UX problem requires redesign.
   * Improve polish and hierarchy without changing the workflow model.

4. **Reduce regression surface**
   * Keep class names stable where possible.
   * Prefer mechanical stylesheet moves before visual changes.
   * Verify desktop and mobile behavior after each styling slice.

## 4. Proposed CSS Structure
Target structure under `web/src/styles/`:

1. `tokens.css`
   * Theme variables
   * Typography variables
   * Global radius / spacing / elevation tokens

2. `base.css`
   * Reset-like rules
   * `html`, `body`, `#root`
   * Global element defaults

3. `layout.css`
   * `app-shell`
   * topbar shell
   * workspace grid
   * panel scaffolding

4. `components.css`
   * shared buttons
   * form fields
   * chips
   * cards
   * empty states

5. `run-rail.css`
   * rail layout
   * filter strip
   * run card grouping

6. `review-workspace.css`
   * review topbar
   * sidebar
   * defect list
   * review content framing

7. `setup-flow.css`
   * setup step list
   * setup panel
   * setup summary
   * setup-specific previews

8. `viewer.css`
   * PCB viewer
   * overlays
   * toolbar
   * zoom / selection / annotation presentation

This can be adjusted if the team prefers CSS modules later, but the first step should be decomposition without changing the styling model.

## 5. Execution Order
### Phase A: Stabilize Theme Foundations
* Move root tokens into a dedicated token file.
* Reconcile `index.css` and `App.css`.
* Remove outdated default dark-theme assumptions if they are no longer part of the intended experience.

### Phase B: Extract Shared Primitives
* Centralize button, field, chip, card, and utility patterns.
* Remove repeated sizing and spacing rules.

### Phase C: Split Feature Styles
* Move rail styles into their own file.
* Move review workspace styles into their own file.
* Move setup flow styles into their own file.
* Move viewer styles into their own file.

### Phase D: Visual Tightening
* Improve hierarchy, spacing rhythm, and density.
* Resolve any flat or noisy areas after the architecture is cleaner.
* Keep changes incremental and testable.

## 6. Non-Goals
* Do not redesign the application workflow.
* Do not rewrite components solely for cosmetic reasons.
* Do not introduce a CSS-in-JS stack during this pass.
* Do not add animation or decorative treatment unless it clearly improves usability.

## 7. Done Criteria
The styling refactor is complete when:

* `App.css` is no longer the primary styling monolith.
* Theme tokens have a single canonical source.
* Shared controls use consistent sizing and states.
* Major screens have isolated stylesheet ownership.
* The UI remains visually coherent on desktop and narrow widths.
* No workflow regressions are introduced in setup, review, run selection, or image viewing.

## 8. Recommendation
Proceed with a styling refactor, not a full redesign.

The current frontend is structurally good enough to keep and visually strong enough to refine. The right move is to clean the styling architecture first, then decide whether any specific screen needs deeper UX redesign after the code is easier to change.
