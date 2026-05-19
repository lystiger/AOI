# Targeted Optimization: OpenCV for Fiducial Detection
**Date:** May 2, 2026
**Scope:** Internal refactor of `VisionService` to replace pure-Python image loops.

## 1. Current State Assessment
The current `VisionService` handles fiducial detection by downsampling images to a max dimension of 1000px and performing an HSV-based mask search followed by a manual BFS-based connected component extraction.
*   **Downsampling:** Already mitigates 12MP bottlenecks (src/aoi/vision_service.py:111).
*   **Bottleneck:** The Python-level iteration over the 1000px (1MP) mask and the manual BFS queue management for component labeling.
*   **Accuracy:** The current algorithm is functional but difficult to tune or extend for "Shape" recognition.

## 2. Refined Solution: Internal C++ Acceleration
We will integrate `opencv-python-headless` to replace the inner pixel-crunching loops while maintaining the current service interfaces.

### Refactoring Targets (Internal Only):
1.  **`_build_fiducial_candidate_mask`**: 
    *   **Current:** Iterates through pixels in Python.
    *   **OpenCV:** Use `cv2.inRange()` on the downsampled `numpy` array.
2.  **`_extract_mask_components`**:
    *   **Current:** Manual BFS queue and `list[bool]` visited map.
    *   **OpenCV:** Use `cv2.connectedComponentsWithStats()`.

## 3. Deployment & Packaging
*   **Dependencies:** Add `opencv-python-headless` and `numpy` to:
    *   `requirements.txt`
    *   `pyproject.toml`
*   **Verification:**
    *   **Regression Test:** Use existing fixtures in `tests/test_services.py` to ensure the number of detected candidates remains stable.
    *   **Performance:** Benchmark internal processing time (expected speedup is significant for the BFS phase, even at 1MP).

## 4. Constraint Checklist
*   [x] **DO NOT** change the `detect_fiducials(image_path)` method signature.
*   [x] **DO NOT** replace the `PIL` based file loading (keep boundary stable).
*   [x] **DO NOT** add CLAHE until regression tests for the base swap are passing.
