# Data Retention & Training Policy

## 1. Data Classification
- **GOLD_DATA (Keep Forever)**: Verified "Pass" boards with high confidence scores. Used as the baseline.
- **ERROR_SAMPLES (High Priority)**: Boards with "Fail" status (confirmed by human/manual check). These are the only samples used for retraining the ML classifiers.
- **FALSE_CALLS (Archive for 30 Days)**: Results flagged by AI but deemed "Pass" by the operator. These are used to update the `bias_correction` threshold.

## 2. Automated Maintenance
- **Monthly**: Run `src/clean_archive.py`.
- **Logic**: 
    - Compress `FALSE_CALLS` older than 30 days.
    - Export `ERROR_SAMPLES` to the training server for model versioning.
    - Purge raw images older than 6 months unless they are part of a failure analysis case.