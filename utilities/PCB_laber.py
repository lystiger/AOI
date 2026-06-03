#!/usr/bin/env python3
"""
PCB board annotation tool for component-level labeling.

Run:
    python3 utilities/PCB_laber.py

Open:
    http://localhost:5000
"""

from __future__ import annotations

import base64
import json
import math
import re
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image, ImageFilter


WORKSPACE_DIR = Path("board_dataset")
IMAGE_DIR = WORKSPACE_DIR / "images"
ANNOTATION_DIR = WORKSPACE_DIR / "annotations"
EXPORT_DIR = WORKSPACE_DIR / "exports"
CROP_DIR = EXPORT_DIR / "crops"
YOLO_IMAGE_DIR = EXPORT_DIR / "yolo" / "images"
YOLO_LABEL_DIR = EXPORT_DIR / "yolo" / "labels"

COMPONENT_CLASSES = [
    "resistor",
    "capacitor",
    "connector",
    "ic",
    "led",
    "diode",
    "inductor",
    "transistor",
    "crystal",
    "switch",
    "button",
    "jumper",
    "test_point",
    "other",
]

CLASS_KEYS = {
    "1": "resistor",
    "2": "capacitor",
    "3": "connector",
    "4": "ic",
    "5": "led",
    "6": "diode",
    "7": "inductor",
    "8": "transistor",
    "9": "crystal",
    "q": "switch",
    "w": "button",
    "e": "jumper",
    "r": "test_point",
    "t": "other",
}

for path in (IMAGE_DIR, ANNOTATION_DIR, CROP_DIR, YOLO_IMAGE_DIR, YOLO_LABEL_DIR):
    path.mkdir(parents=True, exist_ok=True)


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    return slug or "item"


def _image_record(image_path: Path) -> dict[str, object]:
    annotation = _load_annotation(image_path.name)
    with Image.open(image_path) as image:
        width, height = image.size
    return {
        "id": image_path.name,
        "filename": image_path.name,
        "url": f"/image/{image_path.name}",
        "width": width,
        "height": height,
        "box_count": len(annotation["boxes"]),
        "updated_at": annotation["updated_at"],
    }


def _annotation_path(image_id: str) -> Path:
    return ANNOTATION_DIR / f"{image_id}.json"


def _default_annotation(image_id: str) -> dict[str, object]:
    return {
        "image_id": image_id,
        "boxes": [],
        "updated_at": "",
    }


def _load_annotation(image_id: str) -> dict[str, object]:
    path = _annotation_path(image_id)
    if not path.exists():
        return _default_annotation(image_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("boxes"), list):
        payload["boxes"] = []
    payload.setdefault("image_id", image_id)
    payload.setdefault("updated_at", "")
    return payload


def _save_annotation(image_id: str, payload: dict[str, object]) -> dict[str, object]:
    payload = {
        "image_id": image_id,
        "boxes": payload.get("boxes", []),
        "updated_at": payload.get("updated_at", ""),
    }
    _annotation_path(image_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _list_images() -> list[dict[str, object]]:
    records = [
        _image_record(image_path)
        for image_path in sorted(IMAGE_DIR.iterdir())
        if image_path.is_file() and image_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    ]
    records.sort(key=lambda item: str(item["filename"]).lower())
    return records


def _decode_data_url(image_data: str) -> tuple[bytes, str]:
    if "," not in image_data:
        raise ValueError("invalid data url")
    header, encoded = image_data.split(",", 1)
    if ";base64" not in header:
        raise ValueError("unsupported upload encoding")
    mime = header.split(":", 1)[-1].split(";", 1)[0].lower()
    if mime == "image/png":
        ext = ".png"
    elif mime == "image/webp":
        ext = ".webp"
    elif mime in {"image/jpeg", "image/jpg"}:
        ext = ".jpg"
    else:
        raise ValueError(f"unsupported image type: {mime}")
    return base64.b64decode(encoded), ext


def _import_image(filename: str, image_data: str) -> dict[str, object]:
    raw_bytes, ext = _decode_data_url(image_data)
    stem = _safe_slug(Path(filename).stem or "board")
    final_name = f"{stem}{ext}"
    candidate = IMAGE_DIR / final_name
    if candidate.exists():
        final_name = f"{stem}-{uuid.uuid4().hex[:8]}{ext}"
        candidate = IMAGE_DIR / final_name
    candidate.write_bytes(raw_bytes)
    return _image_record(candidate)


def _validate_box(box: dict[str, object]) -> dict[str, object]:
    class_name = str(box.get("class_name") or "").strip()
    if class_name not in COMPONENT_CLASSES:
        raise ValueError(f"unknown class_name: {class_name}")
    x = max(0.0, min(float(box.get("x", 0.0)), 1.0))
    y = max(0.0, min(float(box.get("y", 0.0)), 1.0))
    width = max(0.001, min(float(box.get("width", 0.001)), 1.0))
    height = max(0.001, min(float(box.get("height", 0.001)), 1.0))
    x = min(x, 1.0 - width)
    y = min(y, 1.0 - height)
    label = str(box.get("label") or class_name).strip() or class_name
    angle = _normalize_angle(float(box.get("angle", 0.0)))
    return {
        "id": str(box.get("id") or uuid.uuid4().hex),
        "class_name": class_name,
        "label": label,
        "x": round(x, 6),
        "y": round(y, 6),
        "width": round(width, 6),
        "height": round(height, 6),
        "angle": round(angle, 3),
    }


def _save_boxes(image_id: str, boxes: list[dict[str, object]]) -> dict[str, object]:
    payload = _save_annotation(
        image_id,
        {
            "boxes": [_validate_box(box) for box in boxes],
            "updated_at": uuid.uuid1().hex,
        },
    )
    return payload


def _yolo_line(box: dict[str, object]) -> str:
    class_index = COMPONENT_CLASSES.index(str(box["class_name"]))
    center_x = float(box["x"]) + (float(box["width"]) / 2.0)
    center_y = float(box["y"]) + (float(box["height"]) / 2.0)
    return (
        f"{class_index} "
        f"{center_x:.6f} "
        f"{center_y:.6f} "
        f"{float(box['width']):.6f} "
        f"{float(box['height']):.6f}"
    )


def _normalize_angle(angle: float) -> float:
    normalized = ((angle + 180.0) % 360.0) - 180.0
    if normalized >= 180.0:
        normalized -= 360.0
    if normalized < -180.0:
        normalized += 360.0
    return normalized


def _crop_box_from_image(image: Image.Image, box: dict[str, object]) -> Image.Image:
    image_width, image_height = image.size
    x0 = int(round(float(box["x"]) * image_width))
    y0 = int(round(float(box["y"]) * image_height))
    x1 = int(round((float(box["x"]) + float(box["width"])) * image_width))
    y1 = int(round((float(box["y"]) + float(box["height"])) * image_height))
    x0 = max(0, min(x0, image_width - 1))
    y0 = max(0, min(y0, image_height - 1))
    x1 = max(x0 + 1, min(x1, image_width))
    y1 = max(y0 + 1, min(y1, image_height))
    return image.crop((x0, y0, x1, y1))


def _estimate_angle_from_crop(crop: Image.Image) -> float:
    grayscale = crop.convert("L")
    edge_map = grayscale.filter(ImageFilter.FIND_EDGES)
    edge_values = list(edge_map.getdata())
    if not edge_values:
        return 0.0
    mean_value = sum(edge_values) / len(edge_values)
    variance = sum((value - mean_value) ** 2 for value in edge_values) / len(edge_values)
    threshold = max(24.0, mean_value + (variance**0.5))

    width, height = edge_map.size
    weighted_points: list[tuple[float, float, float]] = []
    for y in range(height):
        for x in range(width):
            strength = edge_map.getpixel((x, y))
            if strength >= threshold:
                weighted_points.append((float(x), float(y), float(strength)))

    if len(weighted_points) < 12:
        raw_values = list(grayscale.getdata())
        if not raw_values:
            return 0.0
        fallback_threshold = sum(raw_values) / len(raw_values)
        weighted_points = []
        for y in range(height):
            for x in range(width):
                value = grayscale.getpixel((x, y))
                distance = abs(float(value) - fallback_threshold)
                if distance >= 18:
                    weighted_points.append((float(x), float(y), distance))
        if len(weighted_points) < 12:
            return 0.0

    total_weight = sum(weight for _, _, weight in weighted_points)
    if total_weight <= 0:
        return 0.0

    mean_x = sum(x * weight for x, _, weight in weighted_points) / total_weight
    mean_y = sum(y * weight for _, y, weight in weighted_points) / total_weight
    cov_xx = sum(weight * ((x - mean_x) ** 2) for x, _, weight in weighted_points) / total_weight
    cov_yy = sum(weight * ((y - mean_y) ** 2) for _, y, weight in weighted_points) / total_weight
    cov_xy = sum(weight * (x - mean_x) * (y - mean_y) for x, y, weight in weighted_points) / total_weight

    if abs(cov_xy) < 1e-9 and abs(cov_xx - cov_yy) < 1e-9:
        return 0.0
    angle_radians = 0.5 * math.atan2(2.0 * cov_xy, cov_xx - cov_yy)
    angle_degrees = math.degrees(angle_radians)
    if angle_degrees >= 90.0:
        angle_degrees -= 180.0
    if angle_degrees < -90.0:
        angle_degrees += 180.0
    return round(angle_degrees, 3)


def _estimate_component_angle(image_id: str, box: dict[str, object]) -> float:
    image_path = IMAGE_DIR / image_id
    if not image_path.exists():
        raise FileNotFoundError("image not found")
    normalized_box = _validate_box(box)
    with Image.open(image_path) as image:
        crop = _crop_box_from_image(image.convert("RGB"), normalized_box)
    return _estimate_angle_from_crop(crop)


def _export_image(image_id: str) -> dict[str, object]:
    image_path = IMAGE_DIR / image_id
    if not image_path.exists():
        raise FileNotFoundError("image not found")
    annotation = _load_annotation(image_id)
    boxes = [_validate_box(box) for box in annotation["boxes"]]
    if not boxes:
        raise ValueError("no boxes to export")

    stem = image_path.stem
    yolo_image_path = YOLO_IMAGE_DIR / image_path.name
    yolo_label_path = YOLO_LABEL_DIR / f"{stem}.txt"
    yolo_image_path.write_bytes(image_path.read_bytes())
    yolo_label_path.write_text("\n".join(_yolo_line(box) for box in boxes) + "\n", encoding="utf-8")

    crop_root = CROP_DIR / stem
    crop_root.mkdir(parents=True, exist_ok=True)
    crop_count = 0

    with Image.open(image_path) as image:
        image = image.convert("RGB")
        for index, box in enumerate(boxes, start=1):
            crop = _crop_box_from_image(image, box)
            class_dir = crop_root / str(box["class_name"])
            raw_dir = class_dir / "raw"
            aligned_dir = class_dir / "aligned"
            raw_dir.mkdir(parents=True, exist_ok=True)
            aligned_dir.mkdir(parents=True, exist_ok=True)
            angle = float(box.get("angle", 0.0))
            crop_name = f"{index:04d}_{_safe_slug(str(box['label']))}_a{angle:+06.1f}.png"
            crop.save(raw_dir / crop_name, format="PNG")
            aligned_crop = crop.rotate(-angle, expand=True, fillcolor=(0, 0, 0))
            aligned_crop.save(aligned_dir / crop_name, format="PNG")
            crop_count += 1

    return {
        "image_id": image_id,
        "box_count": len(boxes),
        "crop_count": crop_count,
        "yolo_label_path": str(yolo_label_path),
        "crop_dir": str(crop_root),
    }


def _export_all_images() -> dict[str, object]:
    exported: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    for image in _list_images():
        image_id = str(image["id"])
        try:
            exported.append(_export_image(image_id))
        except ValueError as exc:
            skipped.append({"image_id": image_id, "reason": str(exc)})
    return {
        "exported_count": len(exported),
        "skipped_count": len(skipped),
        "exported": exported,
        "skipped": skipped,
    }


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>PCB Board Annotator</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: #10161f;
    color: #eef2f7;
    font-family: "Segoe UI", sans-serif;
  }
  .shell {
    display: grid;
    grid-template-columns: 340px 1fr 300px;
    height: 100vh;
  }
  .panel {
    overflow: auto;
    border-right: 1px solid #233246;
    background: #141d29;
    padding: 16px;
  }
  .panel.right {
    border-right: none;
    border-left: 1px solid #233246;
  }
  .section {
    margin-bottom: 18px;
    padding-bottom: 18px;
    border-bottom: 1px solid #233246;
  }
  .section:last-child {
    border-bottom: none;
  }
  h1 {
    margin: 0 0 8px;
    font-size: 20px;
  }
  h2 {
    margin: 0 0 10px;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #93a4ba;
  }
  .hint, .muted {
    color: #93a4ba;
    font-size: 12px;
    line-height: 1.5;
  }
  .toolbar, .row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  button, input, select {
    font: inherit;
  }
  button {
    border: 1px solid #355074;
    background: #1b2b3f;
    color: #eef2f7;
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
  }
  button.primary {
    background: #225a9c;
    border-color: #3d77bf;
  }
  button.danger {
    border-color: #8c4350;
    background: #4a2029;
  }
  button:disabled {
    opacity: 0.45;
    cursor: default;
  }
  input[type="file"] {
    display: none;
  }
  input[type="text"] {
    width: 100%;
    border: 1px solid #355074;
    background: #0f1722;
    color: #eef2f7;
    padding: 8px 10px;
    border-radius: 8px;
  }
  .canvas-wrap {
    position: relative;
    overflow: auto;
    background:
      linear-gradient(45deg, rgba(255,255,255,0.02) 25%, transparent 25%),
      linear-gradient(-45deg, rgba(255,255,255,0.02) 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, rgba(255,255,255,0.02) 75%),
      linear-gradient(-45deg, transparent 75%, rgba(255,255,255,0.02) 75%);
    background-size: 24px 24px;
    background-position: 0 0, 0 12px, 12px -12px, -12px 0;
  }
  .canvas-stage {
    position: relative;
    margin: 16px;
    display: inline-block;
  }
  #boardImage {
    display: block;
    max-width: none;
    user-select: none;
    -webkit-user-drag: none;
  }
  #overlay {
    position: absolute;
    inset: 0;
    cursor: crosshair;
  }
  .box {
    position: absolute;
    color: #fff;
    overflow: visible;
    cursor: move;
  }
  .box.selected .box-visual {
    box-shadow: 0 0 0 2px #f8c34a inset;
  }
  .box-visual {
    position: absolute;
    inset: 0;
    border: 2px solid var(--box-color, #54b2ff);
    background: color-mix(in srgb, var(--box-color, #54b2ff) 18%, transparent);
    overflow: visible;
    transform-origin: 50% 50%;
  }
  .box-label {
    position: absolute;
    top: 0;
    left: 0;
    font-size: 11px;
    padding: 2px 6px;
    background: rgba(0, 0, 0, 0.72);
    white-space: nowrap;
  }
  .angle-line {
    position: absolute;
    left: 50%;
    top: 50%;
    height: 2px;
    background: rgba(255, 255, 255, 0.92);
    transform-origin: 0 50%;
    pointer-events: none;
    box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.22);
  }
  .angle-line::after {
    content: "";
    position: absolute;
    right: -5px;
    top: 50%;
    width: 0;
    height: 0;
    border-left: 6px solid rgba(255, 255, 255, 0.92);
    border-top: 4px solid transparent;
    border-bottom: 4px solid transparent;
    transform: translateY(-50%);
  }
  .resize-handle {
    position: absolute;
    width: 10px;
    height: 10px;
    border: 1px solid rgba(255, 255, 255, 0.85);
    background: rgba(0, 0, 0, 0.82);
    border-radius: 999px;
  }
  .resize-handle.nw { top: -6px; left: -6px; cursor: nwse-resize; }
  .resize-handle.ne { top: -6px; right: -6px; cursor: nesw-resize; }
  .resize-handle.sw { bottom: -6px; left: -6px; cursor: nesw-resize; }
  .resize-handle.se { bottom: -6px; right: -6px; cursor: nwse-resize; }
  #overlay.rotate-mode .resize-handle {
    cursor: alias;
    background: rgba(34, 90, 156, 0.92);
    border-color: rgba(255, 255, 255, 0.92);
  }
  .image-list, .box-list, .class-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .image-item, .box-item, .class-item {
    border: 1px solid #233246;
    border-radius: 10px;
    padding: 10px;
    background: #111925;
    cursor: pointer;
  }
  .image-item.active, .box-item.active, .class-item.active {
    border-color: #54b2ff;
    background: #162438;
  }
  .class-key {
    display: inline-block;
    min-width: 22px;
    padding: 2px 5px;
    border-radius: 999px;
    background: #2a405d;
    color: #b4d2ff;
    text-align: center;
    margin-right: 8px;
    font-size: 11px;
  }
  .status {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    padding: 8px 12px;
    background: #0b1119;
    border-top: 1px solid #233246;
    color: #b5c8e0;
    font-size: 12px;
  }
  .metrics {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .metric {
    background: #0f1722;
    border: 1px solid #233246;
    border-radius: 10px;
    padding: 10px;
  }
  .metric .value {
    display: block;
    margin-top: 4px;
    font-size: 18px;
    color: #54b2ff;
    font-weight: 600;
  }
  .empty {
    color: #93a4ba;
    font-size: 13px;
    padding: 12px 0;
  }
</style>
</head>
<body>
<div class="shell">
  <aside class="panel">
    <div class="section">
      <h1>PCB Annotator</h1>
      <div class="hint">Board-level component labeling with persistent boxes, YOLO export, and automatic crop extraction.</div>
    </div>

    <div class="section">
      <h2>Import Board</h2>
      <div class="toolbar">
        <input id="fileInput" type="file" accept="image/*">
        <button class="primary" onclick="document.getElementById('fileInput').click()">Import Image</button>
        <button onclick="selectPreviousImage()" id="prevImageBtn">Prev</button>
        <button onclick="selectNextImage()" id="nextImageBtn">Next</button>
      </div>
      <div class="hint" style="margin-top:8px;">Imported images are stored in <code>board_dataset/images</code>.</div>
    </div>

    <div class="section">
      <h2>Boards</h2>
      <div id="imageList" class="image-list"></div>
    </div>

    <div class="section">
      <h2>Classes</h2>
      <div id="classList" class="class-list"></div>
    </div>
  </aside>

  <main class="canvas-wrap">
    <div class="section" style="padding:16px 16px 0; border-bottom:none;">
      <div class="toolbar">
        <button class="primary" onclick="saveAnnotations()" id="saveBtn">Save</button>
        <button onclick="exportCurrentImage()" id="exportBtn">Export YOLO + Crops</button>
        <button onclick="exportAllImages()" id="exportAllBtn">Export All</button>
        <button onclick="toggleRotateMode()" id="rotateModeBtn">Rotate Mode: Off</button>
        <button class="danger" onclick="deleteSelectedBox()" id="deleteBtn">Delete Box</button>
        <button onclick="duplicateSelectedBox()" id="duplicateBtn">Duplicate</button>
      </div>
      <div class="row" style="margin-top:10px;">
        <div class="muted">Zoom</div>
        <input id="zoomSlider" type="range" min="25" max="250" value="100" oninput="setZoom(this.value)">
        <div id="zoomText" class="muted">100%</div>
      </div>
    </div>
    <div id="canvasStage" class="canvas-stage" style="display:none;">
      <img id="boardImage" alt="Board">
      <div id="overlay"></div>
    </div>
    <div id="emptyState" class="empty" style="padding:24px;">Import or select a board image to start annotating.</div>
  </main>

  <aside class="panel right">
    <div class="section">
      <h2>Board Summary</h2>
      <div class="metrics">
        <div class="metric">Images<span class="value" id="metricImages">0</span></div>
        <div class="metric">Boxes<span class="value" id="metricBoxes">0</span></div>
      </div>
    </div>

    <div class="section">
      <h2>Selected Box</h2>
      <div id="selectionEmpty" class="empty">No box selected.</div>
      <div id="selectionEditor" style="display:none;">
        <div class="row" style="margin-bottom:8px;">
          <select id="selectedClass" onchange="updateSelectedBoxClass(this.value)" style="flex:1; border:1px solid #355074; background:#0f1722; color:#eef2f7; padding:8px 10px; border-radius:8px;"></select>
        </div>
        <div style="margin-bottom:8px;">
          <input id="selectedLabel" type="text" placeholder="Custom label" oninput="updateSelectedBoxLabel(this.value)">
        </div>
        <div class="row" style="margin-bottom:8px;">
          <input id="selectedAngle" type="text" placeholder="Angle" oninput="updateSelectedBoxAngle(this.value)">
          <button onclick="estimateSelectedBoxAngle()">Auto Angle</button>
        </div>
        <div class="hint">Drag a box to move it. Drag corner handles to resize, or rotate when rotate mode is on. Press R to toggle rotate mode. Arrow keys nudge the selected box. Hold Shift for larger movement. Press Delete to remove it.</div>
      </div>
    </div>

    <div class="section">
      <h2>Boxes</h2>
      <div id="boxList" class="box-list"></div>
    </div>
  </aside>
</div>

<div class="status" id="statusBar">Ready.</div>

<script>
const state = {
  classes: [],
  classKeys: {},
  images: [],
  selectedImageId: null,
  annotations: [],
  selectedClass: null,
  selectedBoxId: null,
  draftBox: null,
  draftStart: null,
  draftNormalized: null,
  isDrawing: false,
  interactionMode: null,
  interactionBoxId: null,
  interactionHandle: null,
  interactionStart: null,
  interactionBoxOriginal: null,
  rotateMode: false,
  zoomPercent: 100,
  imageWidth: 0,
  imageHeight: 0,
};

const boardImage = document.getElementById('boardImage');
const overlay = document.getElementById('overlay');
const stage = document.getElementById('canvasStage');
const emptyState = document.getElementById('emptyState');
const imageList = document.getElementById('imageList');
const boxList = document.getElementById('boxList');
const classList = document.getElementById('classList');
const statusBar = document.getElementById('statusBar');

function colorForClass(className) {
  const index = Math.max(0, state.classes.indexOf(className));
  const hue = (index * 37) % 360;
  return `hsl(${hue} 78% 62%)`;
}

function setStatus(message) {
  statusBar.textContent = message;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok || payload.status === 'error') {
    throw new Error(payload.message || 'Request failed');
  }
  return payload;
}

function updateSummary() {
  document.getElementById('metricImages').textContent = state.images.length;
  document.getElementById('metricBoxes').textContent = state.annotations.length;
}

function renderClassList() {
  classList.innerHTML = '';
  state.classes.forEach((className) => {
    const row = document.createElement('div');
    row.className = `class-item ${state.selectedClass === className ? 'active' : ''}`;
    const key = Object.entries(state.classKeys).find(([, value]) => value === className)?.[0] || '';
    row.innerHTML = `<span class="class-key">${key.toUpperCase()}</span>${className}`;
    row.onclick = () => {
      state.selectedClass = className;
      renderClassList();
      setStatus(`Selected class: ${className}`);
    };
    classList.appendChild(row);
  });
}

function renderImageList() {
  imageList.innerHTML = '';
  if (!state.images.length) {
    imageList.innerHTML = '<div class="empty">No images imported yet.</div>';
    return;
  }
  state.images.forEach((image) => {
    const item = document.createElement('div');
    item.className = `image-item ${state.selectedImageId === image.id ? 'active' : ''}`;
    item.innerHTML = `
      <div><strong>${image.filename}</strong></div>
      <div class="muted">${image.width}x${image.height} px</div>
      <div class="muted">${image.box_count} boxes</div>
    `;
    item.onclick = () => loadImage(image.id);
    imageList.appendChild(item);
  });
}

function renderBoxList() {
  boxList.innerHTML = '';
  if (!state.annotations.length) {
    boxList.innerHTML = '<div class="empty">No boxes on this image.</div>';
    return;
  }
  state.annotations.forEach((box, index) => {
    const item = document.createElement('div');
    item.className = `box-item ${state.selectedBoxId === box.id ? 'active' : ''}`;
    item.innerHTML = `
      <div><strong>${index + 1}. ${box.label}</strong></div>
      <div class="muted">${box.class_name}</div>
      <div class="muted">${box.width.toFixed(3)} x ${box.height.toFixed(3)} · ${Number(box.angle || 0).toFixed(1)}°</div>
    `;
    item.onclick = () => {
      state.selectedBoxId = box.id;
      renderBoxes();
    };
    boxList.appendChild(item);
  });
}

function updateSelectionEditor() {
  const editor = document.getElementById('selectionEditor');
  const empty = document.getElementById('selectionEmpty');
  const selected = state.annotations.find((box) => box.id === state.selectedBoxId);
  const classSelect = document.getElementById('selectedClass');
  classSelect.innerHTML = state.classes.map((className) => `<option value="${className}">${className}</option>`).join('');
  if (!selected) {
    editor.style.display = 'none';
    empty.style.display = 'block';
    return;
  }
  editor.style.display = 'block';
  empty.style.display = 'none';
  classSelect.value = selected.class_name;
  document.getElementById('selectedLabel').value = selected.label || '';
  document.getElementById('selectedAngle').value = Number(selected.angle || 0).toFixed(1);
}

function scaleBox(box) {
  const width = overlay.clientWidth || state.imageWidth;
  const height = overlay.clientHeight || state.imageHeight;
  return {
    left: box.x * width,
    top: box.y * height,
    width: box.width * width,
    height: box.height * height,
  };
}

function renderBoxes() {
  overlay.classList.toggle('rotate-mode', state.rotateMode);
  document.getElementById('rotateModeBtn').textContent = `Rotate Mode: ${state.rotateMode ? 'On' : 'Off'}`;
  overlay.innerHTML = '';
  state.annotations.forEach((box) => {
    const node = document.createElement('div');
    node.className = `box ${state.selectedBoxId === box.id ? 'selected' : ''}`;
    node.style.setProperty('--box-color', colorForClass(box.class_name));
    const scaled = scaleBox(box);
    node.style.left = `${scaled.left}px`;
    node.style.top = `${scaled.top}px`;
    node.style.width = `${scaled.width}px`;
    node.style.height = `${scaled.height}px`;
    const angle = Number(box.angle || 0);
    const angleLength = Math.max(16, Math.min(scaled.width, scaled.height) * 0.42);
    node.innerHTML = `
      <div class="box-visual" style="transform: rotate(${angle}deg);">
        <div class="box-label" style="transform: rotate(${-angle}deg); transform-origin: top left;">${box.label}</div>
        <div class="angle-line" style="width:${angleLength}px; transform: translateY(-50%);"></div>
        <div class="resize-handle nw" data-handle="nw" style="transform: rotate(${-angle}deg);"></div>
        <div class="resize-handle ne" data-handle="ne" style="transform: rotate(${-angle}deg);"></div>
        <div class="resize-handle sw" data-handle="sw" style="transform: rotate(${-angle}deg);"></div>
        <div class="resize-handle se" data-handle="se" style="transform: rotate(${-angle}deg);"></div>
      </div>
    `;
    node.onmousedown = (event) => {
      event.stopPropagation();
      state.selectedBoxId = box.id;
      const handle = event.target.dataset.handle;
      beginBoxInteraction(event, box.id, handle ? (state.rotateMode ? 'rotate' : 'resize') : 'move', handle || null);
      renderBoxes();
    };
    overlay.appendChild(node);
  });

  if (state.draftBox) {
    const draft = document.createElement('div');
    draft.className = 'box';
    draft.style.setProperty('--box-color', colorForClass(state.selectedClass || 'other'));
    draft.style.left = `${state.draftBox.left}px`;
    draft.style.top = `${state.draftBox.top}px`;
    draft.style.width = `${state.draftBox.width}px`;
    draft.style.height = `${state.draftBox.height}px`;
    overlay.appendChild(draft);
  }

  renderBoxList();
  updateSelectionEditor();
  updateSummary();
}

function setZoom(percent) {
  state.zoomPercent = Number(percent);
  const scale = state.zoomPercent / 100;
  boardImage.style.width = `${state.imageWidth * scale}px`;
  boardImage.style.height = `${state.imageHeight * scale}px`;
  overlay.style.width = `${state.imageWidth * scale}px`;
  overlay.style.height = `${state.imageHeight * scale}px`;
  document.getElementById('zoomText').textContent = `${state.zoomPercent}%`;
}

function findImageIndex() {
  return state.images.findIndex((image) => image.id === state.selectedImageId);
}

function selectPreviousImage() {
  const index = findImageIndex();
  if (index > 0) {
    loadImage(state.images[index - 1].id);
  }
}

function selectNextImage() {
  const index = findImageIndex();
  if (index !== -1 && index < state.images.length - 1) {
    loadImage(state.images[index + 1].id);
  }
}

function updateImageRecordBoxCount() {
  const image = state.images.find((item) => item.id === state.selectedImageId);
  if (image) {
    image.box_count = state.annotations.length;
  }
}

async function refreshState(preferredImageId = null) {
  const payload = await fetchJson('/state');
  state.classes = payload.classes;
  state.classKeys = payload.class_keys;
  state.images = payload.images;
  if (!state.selectedClass && state.classes.length) {
    state.selectedClass = state.classes[0];
  }
  renderClassList();
  renderImageList();

  const targetImageId =
    preferredImageId ||
    (state.selectedImageId && state.images.some((image) => image.id === state.selectedImageId) ? state.selectedImageId : null) ||
    state.images[0]?.id ||
    null;

  if (targetImageId) {
    await loadImage(targetImageId, true);
  } else {
    state.selectedImageId = null;
    state.annotations = [];
    state.selectedBoxId = null;
    stage.style.display = 'none';
    emptyState.style.display = 'block';
    updateSummary();
  }
}

async function loadImage(imageId, skipStateRefresh = false) {
  const payload = await fetchJson(`/annotations/${encodeURIComponent(imageId)}`);
  state.selectedImageId = imageId;
  state.annotations = payload.annotation.boxes || [];
  state.selectedBoxId = state.annotations[0]?.id || null;
  state.imageWidth = payload.image.width;
  state.imageHeight = payload.image.height;
  boardImage.onload = () => {
    stage.style.display = 'inline-block';
    emptyState.style.display = 'none';
    setZoom(state.zoomPercent);
    renderBoxes();
  };
  boardImage.src = payload.image.url;
  renderImageList();
  if (!skipStateRefresh) {
    updateImageRecordBoxCount();
  }
  setStatus(`Loaded ${payload.image.filename}`);
}

function pointerToNormalized(event) {
  const rect = overlay.getBoundingClientRect();
  const px = event.clientX - rect.left;
  const py = event.clientY - rect.top;
  return {
    x: Math.max(0, Math.min(px / rect.width, 1)),
    y: Math.max(0, Math.min(py / rect.height, 1)),
  };
}

function normalizedToDraftBox(start, end) {
  const x = Math.min(start.x, end.x);
  const y = Math.min(start.y, end.y);
  const width = Math.abs(start.x - end.x);
  const height = Math.abs(start.y - end.y);
  return { x, y, width, height };
}

function draftPixels(box) {
  return {
    left: box.x * overlay.clientWidth,
    top: box.y * overlay.clientHeight,
    width: box.width * overlay.clientWidth,
    height: box.height * overlay.clientHeight,
  };
}

function beginBoxInteraction(event, boxId, mode, handle) {
  const box = state.annotations.find((item) => item.id === boxId);
  if (!box) {
    return;
  }
  state.isDrawing = false;
  state.draftStart = null;
  state.draftBox = null;
  state.draftNormalized = null;
  state.interactionMode = mode;
  state.interactionBoxId = boxId;
  state.interactionHandle = handle;
  state.interactionStart = pointerToNormalized(event);
  state.interactionBoxOriginal = { ...box };
}

function toggleRotateMode() {
  state.rotateMode = !state.rotateMode;
  renderBoxes();
  setStatus(`Rotate mode ${state.rotateMode ? 'enabled' : 'disabled'}.`);
}

function clampBox(box) {
  const width = Math.min(Math.max(box.width, 0.001), 1);
  const height = Math.min(Math.max(box.height, 0.001), 1);
  return {
    ...box,
    x: Number(Math.min(Math.max(box.x, 0), 1 - width).toFixed(6)),
    y: Number(Math.min(Math.max(box.y, 0), 1 - height).toFixed(6)),
    width: Number(width.toFixed(6)),
    height: Number(height.toFixed(6)),
  };
}

function applyBoxInteraction(event) {
  const box = state.annotations.find((item) => item.id === state.interactionBoxId);
  if (!box || !state.interactionStart || !state.interactionBoxOriginal) {
    return;
  }
  const pointer = pointerToNormalized(event);
  const original = state.interactionBoxOriginal;
  const dx = pointer.x - state.interactionStart.x;
  const dy = pointer.y - state.interactionStart.y;

  if (state.interactionMode === 'move') {
    const next = clampBox({
      ...box,
      x: original.x + dx,
      y: original.y + dy,
      width: original.width,
      height: original.height,
    });
    Object.assign(box, next);
    return;
  }

  if (state.interactionMode === 'rotate') {
    const centerX = original.x + (original.width / 2);
    const centerY = original.y + (original.height / 2);
    const startAngle = Math.atan2(state.interactionStart.y - centerY, state.interactionStart.x - centerX);
    const currentAngle = Math.atan2(pointer.y - centerY, pointer.x - centerX);
    const deltaAngle = (currentAngle - startAngle) * (180 / Math.PI);
    let nextAngle = Number(original.angle || 0) + deltaAngle;
    nextAngle = ((nextAngle + 180) % 360 + 360) % 360 - 180;
    box.angle = Number(nextAngle.toFixed(3));
    return;
  }

  let x = original.x;
  let y = original.y;
  let width = original.width;
  let height = original.height;
  const handle = state.interactionHandle;
  if (handle.includes('e')) {
    width = original.width + dx;
  }
  if (handle.includes('s')) {
    height = original.height + dy;
  }
  if (handle.includes('w')) {
    x = original.x + dx;
    width = original.width - dx;
  }
  if (handle.includes('n')) {
    y = original.y + dy;
    height = original.height - dy;
  }
  if (width < 0.001) {
    if (handle.includes('w')) {
      x -= 0.001 - width;
    }
    width = 0.001;
  }
  if (height < 0.001) {
    if (handle.includes('n')) {
      y -= 0.001 - height;
    }
    height = 0.001;
  }
  const next = clampBox({ ...box, x, y, width, height });
  Object.assign(box, next);
}

overlay.addEventListener('mousedown', (event) => {
  if (event.target !== overlay || !state.selectedImageId) {
    return;
  }
  state.interactionMode = null;
  state.isDrawing = true;
  const start = pointerToNormalized(event);
  state.draftStart = start;
  state.draftBox = { left: 0, top: 0, width: 0, height: 0 };
  state.selectedBoxId = null;
  renderBoxes();
});

overlay.addEventListener('mousemove', (event) => {
  if (!state.isDrawing || !state.draftStart) {
    return;
  }
  const box = normalizedToDraftBox(state.draftStart, pointerToNormalized(event));
  state.draftNormalized = box;
  state.draftBox = draftPixels(box);
  renderBoxes();
});

window.addEventListener('mousemove', (event) => {
  if (state.interactionMode) {
    applyBoxInteraction(event);
    renderBoxes();
  }
});

window.addEventListener('mouseup', () => {
  if (state.interactionMode) {
    state.interactionMode = null;
    state.interactionBoxId = null;
    state.interactionHandle = null;
    state.interactionStart = null;
    state.interactionBoxOriginal = null;
    updateImageRecordBoxCount();
    renderBoxes();
    setStatus('Updated box geometry. Save when ready.');
    return;
  }
  if (!state.isDrawing || !state.draftNormalized) {
    state.isDrawing = false;
    state.draftStart = null;
    state.draftBox = null;
    state.draftNormalized = null;
    return;
  }
  const box = state.draftNormalized;
  state.isDrawing = false;
  state.draftStart = null;
  state.draftBox = null;
  state.draftNormalized = null;

  if (box.width < 0.003 || box.height < 0.003) {
    renderBoxes();
    return;
  }

  const className = state.selectedClass || state.classes[0];
  const newBox = {
    id: crypto.randomUUID(),
    class_name: className,
    label: className,
    x: Number(box.x.toFixed(6)),
    y: Number(box.y.toFixed(6)),
    width: Number(box.width.toFixed(6)),
    height: Number(box.height.toFixed(6)),
    angle: 0,
  };
  state.annotations.push(newBox);
  state.selectedBoxId = newBox.id;
  updateImageRecordBoxCount();
  renderBoxes();
  setStatus(`Added ${className} box. Save when ready.`);
  estimateBoxAngle(newBox.id, false);
});

function updateSelectedBoxClass(className) {
  const box = state.annotations.find((item) => item.id === state.selectedBoxId);
  if (!box) {
    return;
  }
  box.class_name = className;
  if (!box.label || state.classes.includes(box.label)) {
    box.label = className;
  }
  renderBoxes();
}

function updateSelectedBoxLabel(label) {
  const box = state.annotations.find((item) => item.id === state.selectedBoxId);
  if (!box) {
    return;
  }
  box.label = label.trim() || box.class_name;
  renderBoxes();
}

function updateSelectedBoxAngle(value) {
  const box = state.annotations.find((item) => item.id === state.selectedBoxId);
  if (!box) {
    return;
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return;
  }
  let angle = ((parsed + 180) % 360 + 360) % 360 - 180;
  if (angle === -180) {
    angle = 180;
  }
  box.angle = Number(angle.toFixed(3));
  renderBoxes();
}

async function estimateBoxAngle(boxId, announce = true) {
  const box = state.annotations.find((item) => item.id === boxId);
  if (!box || !state.selectedImageId) {
    return;
  }
  try {
    const payload = await fetchJson('/estimate-angle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image_id: state.selectedImageId,
        box,
      }),
    });
    box.angle = Number(payload.angle);
    renderBoxes();
    if (announce) {
      setStatus(`Estimated angle: ${box.angle.toFixed(1)}°`);
    }
  } catch (error) {
    if (announce) {
      setStatus(error.message);
    }
  }
}

async function estimateSelectedBoxAngle() {
  if (!state.selectedBoxId) {
    return;
  }
  await estimateBoxAngle(state.selectedBoxId, true);
}

function deleteSelectedBox() {
  if (!state.selectedBoxId) {
    return;
  }
  state.annotations = state.annotations.filter((box) => box.id !== state.selectedBoxId);
  state.selectedBoxId = state.annotations[0]?.id || null;
  updateImageRecordBoxCount();
  renderBoxes();
  setStatus('Deleted selected box.');
}

function duplicateSelectedBox() {
  const selected = state.annotations.find((box) => box.id === state.selectedBoxId);
  if (!selected) {
    return;
  }
  const next = {
    ...selected,
    id: crypto.randomUUID(),
    x: Number(Math.min(selected.x + 0.01, 1 - selected.width).toFixed(6)),
    y: Number(Math.min(selected.y + 0.01, 1 - selected.height).toFixed(6)),
  };
  state.annotations.push(next);
  state.selectedBoxId = next.id;
  updateImageRecordBoxCount();
  renderBoxes();
  setStatus('Duplicated selected box.');
}

async function saveAnnotations() {
  if (!state.selectedImageId) {
    return;
  }
  const payload = await fetchJson('/save-annotations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_id: state.selectedImageId,
      boxes: state.annotations,
    }),
  });
  state.annotations = payload.annotation.boxes;
  updateImageRecordBoxCount();
  renderBoxes();
  renderImageList();
  setStatus(`Saved ${state.annotations.length} boxes.`);
}

async function exportCurrentImage() {
  if (!state.selectedImageId) {
    return;
  }
  await saveAnnotations();
  const payload = await fetchJson('/export-image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_id: state.selectedImageId }),
  });
  setStatus(`Exported ${payload.crop_count} crops and YOLO labels for ${payload.image_id}.`);
}

async function exportAllImages() {
  if (state.selectedImageId) {
    await saveAnnotations();
  }
  const payload = await fetchJson('/export-all', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  setStatus(`Batch export complete: ${payload.exported_count} exported, ${payload.skipped_count} skipped.`);
}

document.getElementById('fileInput').addEventListener('change', async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const payload = await fetchJson('/import-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: file.name,
          image: reader.result,
        }),
      });
      await refreshState(payload.image.id);
      setStatus(`Imported ${payload.image.filename}`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      event.target.value = '';
    }
  };
  reader.readAsDataURL(file);
});

document.addEventListener('keydown', (event) => {
  if (event.target.tagName === 'INPUT' || event.target.tagName === 'SELECT') {
    return;
  }
  const key = event.key.toLowerCase();
  if (key === 'r') {
    toggleRotateMode();
    return;
  }
  if (state.classKeys[key]) {
    state.selectedClass = state.classKeys[key];
    renderClassList();
    setStatus(`Selected class: ${state.selectedClass}`);
    return;
  }
  if (key === 'delete' || key === 'backspace') {
    deleteSelectedBox();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && key === 's') {
    event.preventDefault();
    saveAnnotations();
    return;
  }
  const selected = state.annotations.find((box) => box.id === state.selectedBoxId);
  if (!selected) {
    return;
  }
  const step = event.shiftKey ? 0.01 : 0.0025;
  if (key === 'arrowleft') selected.x = Number(Math.max(0, selected.x - step).toFixed(6));
  if (key === 'arrowright') selected.x = Number(Math.min(1 - selected.width, selected.x + step).toFixed(6));
  if (key === 'arrowup') selected.y = Number(Math.max(0, selected.y - step).toFixed(6));
  if (key === 'arrowdown') selected.y = Number(Math.min(1 - selected.height, selected.y + step).toFixed(6));
  renderBoxes();
});

refreshState().catch((error) => setStatus(error.message));
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict[str, object], status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body) if body else {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))
            return

        if path == "/state":
            self._send_json(
                {
                    "status": "ok",
                    "classes": COMPONENT_CLASSES,
                    "class_keys": CLASS_KEYS,
                    "images": _list_images(),
                }
            )
            return

        if path.startswith("/annotations/"):
            image_id = unquote(path.removeprefix("/annotations/"))
            image_path = IMAGE_DIR / image_id
            if not image_path.exists():
                self._send_json({"status": "error", "message": "image not found"}, status_code=404)
                return
            annotation = _load_annotation(image_id)
            image = _image_record(image_path)
            self._send_json({"status": "ok", "image": image, "annotation": annotation})
            return

        if path.startswith("/image/"):
            image_id = unquote(path.removeprefix("/image/"))
            image_path = IMAGE_DIR / image_id
            if not image_path.exists() or not image_path.is_file():
                self.send_response(404)
                self.end_headers()
                return
            media_type = "image/png"
            suffix = image_path.suffix.lower()
            if suffix in {".jpg", ".jpeg"}:
                media_type = "image/jpeg"
            elif suffix == ".webp":
                media_type = "image/webp"
            elif suffix == ".bmp":
                media_type = "image/bmp"
            self.send_response(200)
            self.send_header("Content-Type", media_type)
            self.end_headers()
            self.wfile.write(image_path.read_bytes())
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._read_json()

            if path == "/import-image":
                filename = str(body.get("filename") or "").strip()
                image_data = str(body.get("image") or "")
                if not filename or not image_data:
                    raise ValueError("filename and image are required")
                image = _import_image(filename, image_data)
                self._send_json({"status": "ok", "image": image})
                return

            if path == "/save-annotations":
                image_id = str(body.get("image_id") or "").strip()
                boxes = body.get("boxes")
                if not image_id or not isinstance(boxes, list):
                    raise ValueError("image_id and boxes are required")
                if not (IMAGE_DIR / image_id).exists():
                    raise FileNotFoundError("image not found")
                annotation = _save_boxes(image_id, boxes)
                self._send_json({"status": "ok", "annotation": annotation})
                return

            if path == "/export-image":
                image_id = str(body.get("image_id") or "").strip()
                if not image_id:
                    raise ValueError("image_id is required")
                payload = _export_image(image_id)
                self._send_json({"status": "ok", **payload})
                return

            if path == "/estimate-angle":
                image_id = str(body.get("image_id") or "").strip()
                box = body.get("box")
                if not image_id or not isinstance(box, dict):
                    raise ValueError("image_id and box are required")
                angle = _estimate_component_angle(image_id, box)
                self._send_json({"status": "ok", "angle": angle})
                return

            if path == "/export-all":
                payload = _export_all_images()
                self._send_json({"status": "ok", **payload})
                return

            self._send_json({"status": "error", "message": "route not found"}, status_code=404)
        except FileNotFoundError as exc:
            self._send_json({"status": "error", "message": str(exc)}, status_code=404)
        except ValueError as exc:
            self._send_json({"status": "error", "message": str(exc)}, status_code=400)
        except Exception as exc:
            self._send_json({"status": "error", "message": str(exc)}, status_code=500)


if __name__ == "__main__":
    port = 5000
    server = HTTPServer(("localhost", port), Handler)
    print(
        f"""
╔══════════════════════════════════════════════╗
║        PCB Board Annotation Tool            ║
╠══════════════════════════════════════════════╣
║  Browser: http://localhost:{port:<18}║
║  Images:   ./board_dataset/images           ║
║  Labels:   ./board_dataset/annotations      ║
║  Exports:  ./board_dataset/exports          ║
╚══════════════════════════════════════════════╝
"""
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
