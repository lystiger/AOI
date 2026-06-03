# Frontend UI/UX Bug Report

**Date:** 2026-06-03  
**Reviewer:** Claude (UI/UX audit)  
**Scope:** `web/src/` — React components, CSS, hooks

---

## BUG-001 · Floating Inspector Nearly Invisible by Default

**Severity:** High  
**File:** `web/src/styles/viewer.css:253`

```css
.floating-inspector {
  opacity: var(--ghost-opacity, 0.2);
}
```

The CSS fallback for `--ghost-opacity` is `0.2`, which makes the inspector almost completely transparent on first load. Operators inspecting defects will miss the component ID, defect type, severity, and confidence panel entirely unless they know to hover over the bottom-right corner.

**Steps to reproduce:**
1. Select a run with FAIL defects.
2. Click any defect overlay on the PCB viewer.
3. Floating inspector appears but is nearly invisible.

**Expected:** Inspector is readable at default state (≥ 0.8 opacity).  
**Actual:** Inspector renders at 20% opacity.

**Fix:**
```css
.floating-inspector {
  opacity: var(--ghost-opacity, 0.85);
}
```
Or raise the default value in `useWorkspacePrefs` so `hudGhostOpacity` initialises to `0.85`.

---

## BUG-002 · Delete Run Has No Confirmation Guard

**Severity:** High  
**File:** `web/src/components/ReviewWorkspace.jsx:159-165`

```jsx
<button
  type="button"
  className="ghost-button delete-button"
  onClick={handleDeleteRun}
  disabled={!selectedRunId || isDeletingRun}
>
```

The Delete Run button fires `handleDeleteRun` immediately on click with no confirmation dialog. In a production AOI environment, accidentally deleting a run that contains 20+ annotated defect records is unrecoverable.

**Steps to reproduce:**
1. Select any run from the History rail.
2. Click "Delete Run" — run is deleted with no warning.

**Expected:** Confirmation dialog before deletion.  
**Actual:** Run is deleted immediately.

**Fix:**
```jsx
onClick={() => {
  if (window.confirm(`Delete run ${selectedRun?.pcb_id}? This cannot be undone.`)) {
    handleDeleteRun()
  }
}}
```
Or wire up a custom modal component for consistency with the design system.

---

## BUG-003 · Inference Latency Never Shown in the UI

**Severity:** Medium  
**Files:** `web/src/components/shared.jsx:57-84`, `web/src/components/ReviewWorkspace.jsx:367-392`

`inference_latency_ms` is stored on every defect event and present in `logs/inference.jsonl`, but it is never rendered. The `DefectListItem` and the floating `Defect Inspector` panel both omit it. Operators and engineers have no way to identify slow inference runs without reading raw JSON logs.

**Fix — add latency chip to `DefectListItem` in `shared.jsx`:**
```jsx
<span className="defect-confidence">{defect.inference_latency_ms}ms</span>
```

**Fix — add latency row to `inspector-grid` in `ReviewWorkspace.jsx`:**
```jsx
<div className="inspector-item">
  <span className="eyebrow">Latency</span>
  <strong>{selectedDefect.inference_latency_ms ?? '—'}ms</strong>
</div>
```

---

## BUG-004 · Sidebar Collapse Has No CSS Transition

**Severity:** Low  
**File:** `web/src/styles/review-workspace.css:69-74`

```css
.review-shell.sidebar-collapsed {
  grid-template-columns: 0px 1fr;
}
```

The `run-rail` collapse in `layout.css:17` uses `transition: grid-template-columns 250ms cubic-bezier(0.4, 0, 0.2, 1)`, but the review sidebar collapse has no equivalent transition. The sidebar disappears abruptly when toggled.

**Fix:**
```css
.review-shell {
  transition: grid-template-columns 250ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

## BUG-005 · Defect Stepper Buttons Have No Accessible Labels or Position Indicator

**Severity:** Medium  
**File:** `web/src/components/ReviewWorkspace.jsx:168-176`

```jsx
<button type="button" className="ghost-button review-nav-button" onClick={() => stepDefect(-1)}>
  &lt;
</button>
<button type="button" className="ghost-button review-nav-button" onClick={() => stepDefect(1)}>
  &gt;
</button>
```

Both buttons render as raw `<` and `>` characters with no `aria-label`, no tooltip, and no positional feedback (e.g. "3 / 12"). The affordance of "step through defects" is undiscoverable for new operators and inaccessible to screen readers.

**Fix:**
```jsx
<button
  type="button"
  aria-label="Previous defect"
  className="ghost-button review-nav-button"
  onClick={() => stepDefect(-1)}
>
  ‹
</button>
<span className="stepper-position">{currentIndex + 1} / {visibleDefects.length}</span>
<button
  type="button"
  aria-label="Next defect"
  className="ghost-button review-nav-button"
  onClick={() => stepDefect(1)}
>
  ›
</button>
```

---

## BUG-006 · No Feedback While Inference Runs After Upload

**Severity:** Medium  
**File:** `web/src/components/ReviewWorkspace.jsx:151-158`

```jsx
<button
  className={`ghost-button upload-button ${isUploading ? 'loading' : ''}`}
  onClick={openImagePicker}
  disabled={isUploading || !selectedRunId}
>
  {isUploading ? 'Uploading Scan...' : 'Upload PCB Scan'}
</button>
```

The upload state covers file transfer only. Once the image is saved, the button reverts to "Upload PCB Scan" but inference may still be executing server-side. The operator sees no indication that analysis is in progress and may assume the scan was rejected or failed.

**Expected:** A transient "Analyzing..." state or run-level status indicator while inference events are being generated.  
**Actual:** UI goes idle immediately after file upload completes.

**Fix:** Poll run status after upload and show a transient "Analyzing…" label until at least one inference event arrives, or until a timeout.

---

## BUG-007 · `review-topbar` Stacks Too Tall at 1280px Breakpoint

**Severity:** Medium  
**File:** `web/src/styles/review-workspace.css:251-259`

```css
@media (max-width: 1280px) {
  .review-topbar {
    flex-direction: column;
  }
  .review-controls {
    width: 100%;
    justify-content: space-between;
  }
}
```

At 1280px (common laptop resolution), the topbar stacks `review-context` and `review-controls` into two full-width rows. With five or more action elements in `review-controls` (`Edit Setup`, `Surface` selector, `Upload PCB Scan`, `Delete Run`, `< >`), the header can reach 100–120px tall, significantly squishing the PCB viewer canvas below it.

**Fix:** Collapse secondary actions (`Delete Run`, stepper) into a `⋯` overflow menu at this breakpoint, keeping only `Upload PCB Scan` and the surface selector visible.

---

## BUG-008 · Keyboard Shortcuts Are Undiscoverable

**Severity:** Low  
**File:** `web/src/components/PcbViewer.jsx:104-160`

Zen Mode activates `P` (Confirmed Pass) and `F` (Confirmed Fail) review bindings. The viewer also responds to arrow keys for pan, `+`/`-` for zoom, and `0` to reset. None of these are documented in the UI. The only hint is a small "Arrows to pan" stat chip in the viewer toolbar, which disappears if keyboard navigation is disabled.

**Fix:** Add a `?` icon button in the viewer toolbar that opens a keybindings legend overlay. Alternatively, show a brief tooltip on Zen Mode entry listing the `P` and `F` bindings.

---

## Summary

| ID | Title | Severity | File |
|---|---|---|---|
| BUG-001 | Inspector invisible at default opacity | High | viewer.css:253 |
| BUG-002 | Delete Run: no confirmation | High | ReviewWorkspace.jsx:159 |
| BUG-003 | Inference latency not shown in UI | Medium | shared.jsx, ReviewWorkspace.jsx |
| BUG-004 | Sidebar collapse has no transition | Low | review-workspace.css:69 |
| BUG-005 | Stepper buttons: no aria-label or position | Medium | ReviewWorkspace.jsx:168 |
| BUG-006 | No feedback while inference runs post-upload | Medium | ReviewWorkspace.jsx:151 |
| BUG-007 | Topbar stacks too tall at 1280px | Medium | review-workspace.css:251 |
| BUG-008 | Keyboard shortcuts undiscoverable | Low | PcbViewer.jsx:104 |
