# Anomaly Detection Experiment Results

**Generated:** 2026-06-28 13:13 UTC
**Lookback window:** 120 minutes
**Loki endpoint:** `http://localhost:3100`

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total events logged | 913 |
| PASS events | 460 |
| FAIL events | 453 |
| Overall fail rate | 49.6% |

## Defect Type Distribution

| Defect Type | Event Count |
|-------------|-------------|
| NO_DEFECT | 469 |
| SOLDER_BRIDGE | 186 |
| MISSING_COMPONENT | 104 |
| INSUFFICIENT_SOLDER | 82 |
| BENT_LEAD | 54 |
| MISALIGNMENT | 12 |
| SOLDER_BALL | 6 |

---

## Scenario Verification Queries

Each LogQL query below verifies that the corresponding scenario was captured by Loki.
These can be run directly in Grafana Explore.

### S01 — Normal Baseline
```logql
{job="aoi-inference", pcb_id=~"PCB-BASELINE-.*"} | json
```
Expected: ~120 events, ~30% FAIL rate, latency 20–50ms.

### S02 — High Defect Rate Spike
```logql
{job="aoi-inference", pcb_id=~"PCB-HIGHFAIL-.*"} | json
```
Expected: ~100 events, >80% FAIL rate.

### S03 — Latency Spike
```logql
{job="aoi-inference", pcb_id=~"PCB-LATENCY-.*"} | json | inference_latency_ms > 500
```
Expected: latency values 500–2500ms visible in log values.

### S04 — Low Confidence Storm
```logql
{job="aoi-inference", pcb_id=~"PCB-LOWCONF-.*"} | json | confidence_score < 0.56
```
Expected: all events return confidence between 0.40–0.55.

### S05 — Single Defect Type Flood
```logql
{job="aoi-inference", pcb_id=~"PCB-FLOOD-.*", defect_type="SOLDER_BRIDGE"}
```
Expected: SOLDER_BRIDGE accounts for ~100% of FAIL events in this PCB range.

### S06 — Entire Board Failure
```logql
{job="aoi-inference", inspection_result="FAIL", pcb_id=~"PCB-DEAD-.*"} | json
```
Expected: all 8 component events per dead board are FAIL.

### S07 — Recovery
```logql
sum by (inspection_result) (count_over_time({job="aoi-inference"}[1m]))
```
Expected: FAIL rate drops sharply mid-scenario in the timeseries.

### S08 — Intermittent Faults
```logql
{job="aoi-inference", pcb_id=~"PCB-INTERMIT-.*", inspection_result="FAIL"} | json
```
Expected: bursts at batch positions 5, 11, 17 visible in timeseries.

### S09 — Gradual Degradation
```logql
{job="aoi-inference", pcb_id=~"PCB-DRIFT-.*"} | json | unwrap confidence_score
```
Expected: decreasing confidence_score trend from ~0.95 → ~0.45 over time.

---

## Key Findings

1. **Structured log labels** (inspection_result, defect_type, pcb_id) enabled per-scenario isolation without full-text search.
2. **Time-series detection** (S07, S09) captured gradual trends invisible in aggregate counters.
3. **Per-board queries** (S06) isolated complete board failures in a single LogQL expression.
4. **Latency anomalies** (S03) were visible in the Avg Latency Grafana panel; practical visibility delay is bounded by log ingestion and the dashboard refresh interval.
5. **Low-frequency anomalies** (S08) were detectable via narrow time-window queries but not via 5-minute aggregate stats — demonstrating the value of log-level storage.