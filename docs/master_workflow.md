# Master Workflow: The Self-Healing Loop

1. **Monitor**: AI agent continuously polls `Promtail` logs.
2. **Detect**: If `defect_type` > threshold, the system pauses the specific lane.
3. **Diagnose**: Agent runs `src/root_cause_analysis.py` (compares current board to `GOLD_DATA` library).
4. **Action**: 
   - If issue is drift: Update coordinate offset parameters.
   - If issue is component failure: Alert operator and route to rework.
5. **Report**: Append incident to `reports/monthly_performance.md`.

Order,Component,Purpose
1,Infrastructure (Docker),"Establish the ""Sink"" (Loki/Grafana)."
2,Logging Logic,Ensure log files are structured (JSON).
3,Mock Service,"Build the ""Shell"" to test the pipeline flow."
4,Validation Script,"Automate the ""Pass/Fail"" check of the logs."