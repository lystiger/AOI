# AOI Review Workstation — Frontend Improvement Spec

> Thesis context: AI Logging & Inference System for PCB Defect Detection  
> Current stack observed: React-based dark-theme dashboard  
> Each item is tagged with its status and dependency profile.

**Status tags**
- `ALREADY EXISTS` — component/data is present, no new work needed
- `ENHANCE` — extend or polish what's already there
- `FRONTEND ONLY` — no backend changes required
- `BACKEND DEPENDENCY` — requires new or modified API fields

---

## Priority 1 — Inference Metadata & Provenance

**The core thesis differentiator. This is what separates an AI logging system from a generic review tool.**

The run detail view (`RUN-083B1D8E`) already shows a timestamp and fail count. Extend it with inference provenance.

| Item | Status |
|---|---|
| Collapsible **Inference Info** section below the run header | `ENHANCE` |
| `Model ID` field — e.g. `pcb-yolo-v3.2.1` | `BACKEND DEPENDENCY` |
| `Model version hash` — short SHA, e.g. `a3f9c12` | `BACKEND DEPENDENCY` |
| `Inference backend` — `CUDA / CPU / ONNX` | `BACKEND DEPENDENCY` |
| `Avg latency (ms)` per-image inference time | `BACKEND DEPENDENCY` |
| `Images processed` — total scan count for this run | `BACKEND DEPENDENCY` |
| `Throughput (fps)` — derived from latency, can be computed frontend | `ENHANCE` |
| `LIVE` animated badge when a run is in-progress | `FRONTEND ONLY` |

### Run object schema additions
```json
{
  "model_id": "pcb-yolo-v3.2.1",
  "model_hash": "a3f9c12",
  "inference_backend": "CUDA",
  "avg_latency_ms": 14.3,
  "images_processed": 48,
  "status": "complete"
}
```

---

## Priority 2 — Event Log Integration

**The `EVENTS` counter already exists in the top bar. Wire it to a real log.**

| Item | Status |
|---|---|
| `EVENTS N` badge in top bar | `ALREADY EXISTS` |
| Event log drawer (slide-in panel) triggered by clicking `EVENTS` | `ENHANCE` |
| Log entry fields: ISO timestamp, event type, payload summary | `BACKEND DEPENDENCY` |
| Event types: `RUN_STARTED` / `DEFECT_DETECTED` / `RUN_COMPLETED` / `MODEL_LOADED` / `ERROR` | `BACKEND DEPENDENCY` |
| Color-code entries by type (amber = defect, red = error, green = complete) | `FRONTEND ONLY` |
| Live streaming via WebSocket or SSE; fallback to 2s polling | `BACKEND DEPENDENCY` |
| Badge pulse animation when new events arrive | `FRONTEND ONLY` |

### Log entry schema
```json
{
  "event_id": "uuid",
  "timestamp": "2026-04-19T10:36:44Z",
  "type": "DEFECT_DETECTED",
  "payload": {
    "defect_id": "abc",
    "component": "C5",
    "confidence": 0.87
  }
}
```

---

## Priority 3 — Confidence Filtering & Presentation Polish

**Confidence data likely exists on defect objects already. Surface it.**

| Item | Status |
|---|---|
| Confidence score on each defect card — pill with color scale | `ENHANCE` |
| Color scale: green ≥ 85%, yellow 60–84%, red < 60% | `FRONTEND ONLY` |
| Confidence threshold slider in Defect Filters panel (0–100%, default 50%) | `ENHANCE` |
| Slider filters the defect queue in real time, composable with existing filters | `FRONTEND ONLY` |
| Run summary line extended with mean confidence — e.g. `0 fail defects · avg confidence: —` | `ENHANCE` |
| Aggregate confidence score per run in the history sidebar | `BACKEND DEPENDENCY` |

> All filter logic (confidence threshold + component + type + severity + result) should apply as AND composition. Check existing filter reducer before adding new state.

---

## Priority 4 — Defect List Enrichment

**The defect list component already exists. Upgrade its populated state.**

| Item | Status |
|---|---|
| Defect card layout — component ID, type label, severity badge, result, confidence, timestamp | `ENHANCE` |
| Cropped PCB thumbnail (64×64px) at defect overlay location per card | `ENHANCE` |
| Card selection highlights corresponding canvas overlay and triggers Center Defect | `ENHANCE` |
| Defect count chip on section header (the `0` badge already exists — make reactive) | `ALREADY EXISTS` |
| Empty state: keep existing copy, add icon + "Reset Filters" shortcut | `ENHANCE` |

### Defect card data shape

Use the current frontend field names from the existing run detail payload. If the backend later adopts a nested bounding-box object, add a mapping layer instead of changing every consumer at once.

```json
{
  "id": "uuid",
  "component_id": "R42",
  "defect_type": "solder_bridge",
  "severity": "major",
  "inspection_result": "FAIL",
  "confidence_score": 0.94,
  "overlay_x": 0.34,
  "overlay_y": 0.51,
  "overlay_width": 0.08,
  "overlay_height": 0.04,
  "timestamp": "2026-04-19T10:36:50Z"
}
```

---

## Priority 4b — Canvas Overlay Upgrade *(demo-critical)*

**Note: Lower implementation priority than §4, but should be featured prominently in any thesis demo or defense.**

The canvas pan/zoom already works. Extend it with defect annotations.

| Item | Status |
|---|---|
| Bounding box drawn over PCB image at defect coordinates | `ENHANCE` |
| Color-coded by severity: red = fail, yellow = warn, green = pass | `FRONTEND ONLY` |
| Label chip above each box: `{component_id} · {defect_type}` | `FRONTEND ONLY` |
| Crosshair/reticle animation on "Center Defect" | `ENHANCE` |
| Overlay count badge updates reactively | `ALREADY EXISTS` |
| Overlays scale and translate correctly with zoom | `ALREADY EXISTS` |

> Overlay coordinates are already normalized (0–1). Continue treating them as normalized viewport-relative values; if a future API introduces a bounding-box object, map it to `overlay_x`, `overlay_y`, `overlay_width`, and `overlay_height` at the boundary.

---

## Priority 5 — Inline Stats *(optional)*

**Nice-to-have for the thesis demo. Skip if timeline is tight — Grafana covers this.**

| Item | Status |
|---|---|
| Stats tab added next to `ACTIVE REVIEW SURFACE` / `SETUP` | `ENHANCE` |
| Defect breakdown donut by type | `FRONTEND ONLY` |
| Severity distribution bar (fail / warn / pass counts) | `FRONTEND ONLY` |
| Confidence histogram (10 buckets, 0–100%) | `FRONTEND ONLY` |
| Run duration | `BACKEND DEPENDENCY` |
| Images scanned | `ENHANCE` |
| Live update if run is in progress | `FRONTEND ONLY` |

> No charting dependency is currently installed in `web/package.json`. Check existing deps first; if charts are still worth adding, prefer a small library and keep this section optional.

---

## Out of Scope (deferred)

These are valid product improvements but not thesis-relevant. Implement after defense if at all.

- PCB thumbnail in run browser sidebar cards
- Keyboard navigation shortcuts
- Model/inference config in Setup form
- Accessibility (`aria-label`) pass on icon buttons

---

## Notes for Codex

- Implement priorities in order: **1 → 2 → 3 → 4 → 4b**
- Each priority is independently committable — do not bundle across sections
- All new filter logic composes with existing filters using AND; check the current filter reducer before adding state
- Payload alignment: prefer the current frontend field names (`overlay_x`, `overlay_y`, `overlay_width`, `overlay_height`, `component_id`, `defect_type`, `confidence_score`, `timestamp`) unless the API contract is intentionally migrated
- Normalization: overlay coordinates are 0–1 relative to image dimensions and should stay normalized through the view layer
- Do not add new dependencies without checking `package.json` first
