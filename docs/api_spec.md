# API Specification: Inference & Log Schema

## Log JSON Format (Target for `src/log_manager`)
```json
{
  "timestamp": "ISO8601",
  "pcb_id": "string",
  "component_id": "string",
  "inspection_result": "PASS|FAIL",
  "defect_type": "string",
  "confidence_score": 0.00,
  "inference_latency_ms": 0
}