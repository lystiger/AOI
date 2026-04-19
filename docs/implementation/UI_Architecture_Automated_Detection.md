# Architectural Decision: Automated Fiducial/Barcode Detection

## 1. Executive Summary
The decision to implement an automated search algorithm for fiducials and barcodes fundamentally shifts the user interface (UI) from **active manipulation** (manual placement) to **supervisory oversight** (validation). This change prioritizes speed, accuracy, and user efficiency.

## 2. Shift in UI Philosophy: "Management by Exception"
By delegating the detection task to an algorithm, the UI must transition its focus toward:
* **Transparency:** Clearly displaying what the system has found.
* **Confidence:** Communicating how certain the system is about its detections.
* **Correction:** Providing intuitive, low-friction paths for the user to override incorrect automated results.

## 3. Proposed UI/UX Implementation Strategies

### A. Pre-Validation & Confidence Visualization
* **Overlay System:** Use bounding boxes to highlight detected elements.
    * **Green:** High confidence (Auto-accepted).
    * **Yellow/Red:** Low confidence (Requires user review).
* **Confidence Scoring:** Display the algorithm's certainty score to allow the user to prioritize high-risk items.

### B. The Feedback Loop
* **One-Click Approval:** For high-confidence matches, provide a rapid confirmation path (e.g., a "Confirm All" or "Next" hotkey).
* **Manual Override Toggle:** If the algorithm fails, allow the user to switch seamlessly to manual mode to fix the specific error without resetting the entire workflow.

### C. Contextual Progress Tracking
* **Progress Mapping:** Use a persistent sidebar or progress bar to visualize the status of the entire job.
* **Error Highlighting:** Clearly flag indices that require attention, ensuring the user is never "lost" in the automated process.

## 4. Technical Considerations for UI/UX Performance
To maintain a professional, responsive feel:
* **Asynchronous Processing:** Run the search in the background to ensure the UI remains snappy.
* **Progressive Loading:** Update the UI as findings become available, rather than waiting for the entire batch to complete.
* **Defined Thresholds:**
    * **High ( >90%):** Auto-accept.
    * **Medium (60-90%):** Flag for user confirmation.
    * **Low ( <60%):** Immediate manual intervention required.

## 5. UI/UX Approach Comparison

| Approach | User's Primary Role | UI Complexity | Risk Profile |
| :--- | :--- | :--- | :--- |
| **Manual** | Precision placement | High | High (Fatigue/Error) |
| **Semi-Auto** | Assistive snapping | Moderate | Moderate |
| **Auto-Search** | **Validator/Approver** | **Low** | **Lowest** |

---
*Document generated to support the move to an algorithm-first workflow.*
