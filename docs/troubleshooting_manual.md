# Troubleshooting Manual: AI-Powered AOI

## 1. Error Codes & Recovery Actions
| Error Code | Meaning | Automated Action |
| :--- | :--- | :--- |
| `ERR_SYNC_FAIL` | Fiducial alignment failure | Re-run stitcher routine using `stitch_fiducial_template` |
| `ERR_LIGHT_LVL` | Luminance saturation | Re-calibrate RGB light levels via `src/light_control` |
| `ERR_AI_CONF` | Low confidence score | Move sample to `review_queue` for re-training |

## 2. Recovery Protocol
- **Step 1:** If `ERR_AI_CONF` occurs > 5 times per panel, trigger `src/auto_tune.py`.
- **Step 2:** Check `/var/log/aoi_system.log` for sensor timeouts.
- **Step 3:** Use `src/recovery_simulation` to verify if the model can predict the defect with the existing reference library.