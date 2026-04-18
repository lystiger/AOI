# Database Schema Overview

## 1. PostgreSQL (Relational)
- `components`: {id, part_number, ref_designator, tolerance_xy}
- `inspection_runs`: {id, pcb_id, timestamp, model_version, status}
- `defect_logs`: {id, run_id, component_id, defect_type, severity}

## 2. Redis (Cache)
- Key: `offset:{pcb_id}:{component_id}`
- Value: `{x_offset, y_offset, rotation}`

## 3. Loki (Time-Series Logs)
- Stream: `{app="aoi_inference", level="info"}`