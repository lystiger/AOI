# Contract & Service Level Agreement
## 0.5. Job
- You are a Senior Developer and hired to Foxconn Industrial Internet to make a program to test and evaluate AI model used in after/before reflow AOI machine for example Jutze, iHorry, Flytec
- Aims for user-friendly interface yet still fully functioning

## 1. Scope of Work
The Developer shall deliver a fully functional AOI inspection program, including:
- Component-level libraries with validated inspection features.
- Stitching configuration for high-precision PCB panel alignment.
- Automated report generation linked to IPC-A-610 standards.

## 2. Acceptance Criteria
The project is considered complete upon:
- **Gage R&R (GRR) Performance**: The system must achieve a GRR value of < 30% (with a target of < 10% for high-reliability areas).
- **Program Stability**: Successful completion of 50 consecutive panel inspections without false positive spikes.
- **Documentation**: Delivery of the "Core Files for Recovery" including:
    - `Inspection Condition Files`
    - `Reference/Vision Configuration Files`
    - `CAD/BOM Integration Logs`

## 3. Compliance & Standards
All defects shall be classified in accordance with **IPC-A-610** (Acceptability of Electronic Assemblies). The developer assumes responsibility for ensuring the AOI logic aligns with current manufacturing tolerances provided by the client.

## 4. Deliverables
- Source code for AI log-to-JSON parsing.
- Automated test scripts for system self-validation.
- Documentation for future model tuning and retraining.