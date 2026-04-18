# System Architecture: AI-Powered AOI Integration

## Data Flow
1. **PCB Acquisition**: AOI machine captures multi-angle images.
2. **Inference Engine**: `inference_service.py` processes raw image buffers via PyTorch/MediaPipe.
3. **Log Aggregator**: Results (pass/fail/confidence) are pushed to `Loki`.
4. **Dashboard Layer**: `Grafana` queries Loki for real-time visualization and historical trending.

## Component Map
- `src/camera_interface`: Manages physical sensor/AOI hardware communication.
- `src/ai_model`: Core inference logic (classifying component, lead, and solder).
- `src/log_manager`: Handles structured JSON logging for Promtail ingestion.