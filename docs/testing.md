# Testing Protocol

## Phase 1: Unit Testing (Inference)
- Verify `inference_service.py` returns consistent predictions for a static input.

## Phase 2: Integration Testing (Logging)
- Script: Generate 100 dummy inferences.
- Assertion: Query Loki API to ensure 100 entries exist with status "success".

## Phase 3: Performance Stress Test
- Loop: Execute 10 inferences per second.
- Check: Monitor Grafana for latency spikes or dropped log lines.