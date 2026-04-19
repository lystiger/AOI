import json
import requests
import os

BASE_URL = "http://localhost:8000"
MOCK_IMAGE_PATH = "web/public/mock/pcb-example.png"

def test_ingestion():
    # 1. Create a Run with some events
    print("--- Step 1: Creating Run ---")
    payload = {
        "events": [
            {
                "pcb_id": "TEST-PROD-99",
                "component_id": "U001",
                "inspection_result": "FAIL",
                "defect_type": "SOLDER_BRIDGE",
                "confidence_score": 0.92,
                "inference_latency_ms": 45,
                "overlay_x": 0.2,
                "overlay_y": 0.2,
                "overlay_width": 0.1,
                "overlay_height": 0.1,
                "overlay_shape": "rect"
            }
        ]
    }
    
    resp = requests.post(f"{BASE_URL}/events", json=payload)
    if resp.status_code != 202:
        print(f"Failed to create run: {resp.text}")
        return
    
    data = resp.json()
    run_id = data["run_id"]
    print(f"Created Run ID: {run_id}")

    # 2. Upload the Image
    print("\n--- Step 2: Uploading Image ---")
    if not os.path.exists(MOCK_IMAGE_PATH):
        print(f"Error: {MOCK_IMAGE_PATH} not found. Please run from project root.")
        return

    with open(MOCK_IMAGE_PATH, "rb") as f:
        img_data = f.read()

    headers = {"Content-Type": "image/png"}
    img_resp = requests.post(f"{BASE_URL}/runs/{run_id}/images", data=img_data, headers=headers)
    
    if img_resp.status_code == 201:
        img_info = img_resp.json()
        print(f"Success! Image ID: {img_info['image_id']}")
        print(f"View this run at: http://localhost:5173 (Refresh the page)")
    else:
        print(f"Failed to upload image: {img_resp.text}")

if __name__ == "__main__":
    test_ingestion()
