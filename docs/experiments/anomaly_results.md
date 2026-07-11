# Anomaly Detection Experiment Results

**Generated:** 2026-07-11 13:27 UTC
**Lookback window:** 120 minutes
**Loki endpoint:** `http://localhost:3100`

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total events logged | 731 |
| PASS events | 240 |
| FAIL events | 491 |
| Overall fail rate | 67.2% |

## Defect Type Distribution

| Defect Type | Event Count |
|-------------|-------------|
| NO_DEFECT | 240 |
| MOUSE_BITE | 82 |
| SPUR | 70 |
| CONDUCTOR_SCRATCH | 66 |
| BASE_MATERIAL_FOREIGN_OBJECT | 62 |
| HOLE_BREAKOUT | 56 |
| OPEN_CIRCUIT | 54 |
| SPURIOUS_COPPER | 45 |
| CONDUCTOR_FOREIGN_OBJECT | 36 |
| BOARD_FAILURE | 16 |
| SHORT | 4 |

---

## Scenario Verification Queries

Each LogQL query below verifies that the corresponding scenario was captured by Loki.
These can be run directly in Grafana Explore.

### S01 — Normal Baseline (real model, clean board crops)
```logql
{job="aoi-inference", pcb_id=~"PCB-BASELINE-.*"} | json
```
Expected: PASS-dominated (~85–90% PASS); the few FAILs are real model false positives.

### S02 — High Defect Rate Spike (real defective boards)
```logql
{job="aoi-inference", pcb_id=~"PCB-HIGHFAIL-.*"} | json
```
Expected: ~100% FAIL with real DsPCBSD+ defect classes (SPUR, SHORT, ...).

### S03 — Latency Spike (real predictions, injected latency)
```logql
{job="aoi-inference", pcb_id=~"PCB-LATENCY-.*"} | json | inference_latency_ms > 500
```
Expected: latency values escalating to ~2000ms; predictions themselves are real.

### S04 — Low Confidence Storm (real model on degraded boards)
```logql
{job="aoi-inference", pcb_id=~"PCB-LOWCONF-.*"} | json | confidence_score < 0.70
```
Expected: lower mean detection confidence than S02 plus some missed defects.

### S05 — Single Defect Type Flood (real, one dominant class)
```logql
{job="aoi-inference", pcb_id=~"PCB-FLOOD-.*"} | json
```
Expected: one DsPCBSD+ defect class accounts for ~100% of the FAIL events.

### S06 — Entire Board Failure (corrupt scans)
```logql
{job="aoi-inference", defect_type="BOARD_FAILURE", pcb_id=~"PCB-DEAD-.*"} | json
```
Expected: BOARD_FAILURE events for unreadable scans, isolated amid normal traffic.

### S07 — Recovery
```logql
sum by (inspection_result) (count_over_time({job="aoi-inference"}[1m]))
```
Expected: FAIL rate drops sharply mid-scenario in the timeseries.

### S08 — Intermittent Faults
```logql
sum(count_over_time({job="aoi-inference", pcb_id=~"PCB-INTERMIT-.*", inspection_result="FAIL"}[30s]))
```
Expected: three tall FAIL spikes (boards 0005/0011/0017) above a near-zero baseline; occasional single-event blips are real model false positives.

### S09 — Model Degradation / Drift (baseline -> under-trained)
```logql
sum by (model_version) (count_over_time({job="aoi-inference", pcb_id=~"PCB-DRIFT-.*", inspection_result="FAIL"}[30s]))
```
Expected: on identical defective boards the under-trained model (`yolov8s-dspcbsd-epoch0`) emits far fewer FAILs than `yolov8s-dspcbsd-baseline` (missed defects) — a sharp drop at the phase boundary. Swap the metric to `unwrap confidence_score` to also see the confidence dip.

---

## Key Findings

1. **Structured log labels** (inspection_result, defect_type, pcb_id) enabled per-scenario isolation without full-text search.
2. **Time-series detection** (S07, S09) captured gradual trends invisible in aggregate counters.
3. **Per-board queries** (S06) isolated complete board failures in a single LogQL expression.
4. **Latency anomalies** (S03) were visible in the Avg Latency Grafana panel; practical visibility delay is bounded by log ingestion and the dashboard refresh interval.
5. **Low-frequency anomalies** (S08) were detectable via narrow time-window queries but not via 5-minute aggregate stats — demonstrating the value of log-level storage.