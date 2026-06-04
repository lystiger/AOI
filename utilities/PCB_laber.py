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
    cursor: default;
    background:
      linear-gradient(45deg, rgba(255,255,255,0.02) 25%, transparent 25%),
      linear-gradient(-45deg, rgba(255,255,255,0.02) 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, rgba(255,255,255,0.02) 75%),
      linear-gradient(-45deg, transparent 75%, rgba(255,255,255,0.02) 75%);
    background-size: 24px 24px;
    background-position: 0 0, 0 12px, 12px -12px, -12px 0;
  }
  .canvas-wrap.pan-ready,
  .canvas-wrap.panning {
    cursor: grab;
  }
  .canvas-wrap.panning {
    cursor: grabbing;
  }
  .canvas-stage {
    position: relative;
    margin: 16px;
    display: inline-block;
  }
  .minimap {
    position: absolute;
    right: 18px;
    bottom: 18px;
    z-index: 30;
    border: 1px solid #355074;
    border-radius: 12px;
    background: rgba(11, 17, 25, 0.9);
    padding: 8px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
    user-select: none;
  }
  .minimap.hidden {
    display: none;
  }
  .minimap-header {
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #93a4ba;
    margin-bottom: 6px;
  }
  .minimap-stage {
    position: relative;
    overflow: hidden;
    border-radius: 8px;
    background: #0f1722;
    cursor: pointer;
  }
  .minimap-stage img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: fill;
    opacity: 0.9;
    pointer-events: none;
  }
  .minimap-viewport {
    position: absolute;
    border: 2px solid #54b2ff;
    background: rgba(84, 178, 255, 0.14);
    box-shadow: 0 0 0 1px rgba(12, 17, 26, 0.6) inset;
    pointer-events: none;
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
  .edge-handle {
    position: absolute;
    background: rgba(0, 0, 0, 0.82);
    border: 1px solid rgba(255, 255, 255, 0.82);
    border-radius: 999px;
  }
  .edge-handle.n, .edge-handle.s {
    left: 50%;
    width: 18px;
    height: 8px;
    transform: translateX(-50%);
  }
  .edge-handle.e, .edge-handle.w {
    top: 50%;
    width: 8px;
    height: 18px;
    transform: translateY(-50%);
  }
  .edge-handle.n { top: -5px; cursor: ns-resize; }
  .edge-handle.s { bottom: -5px; cursor: ns-resize; }
  .edge-handle.e { right: -5px; cursor: ew-resize; }
  .edge-handle.w { left: -5px; cursor: ew-resize; }
  .rotation-stem {
    position: absolute;
    left: 50%;
    top: -22px;
    width: 2px;
    height: 16px;
    background: rgba(255, 255, 255, 0.78);
    transform: translateX(-50%);
    pointer-events: none;
  }
  .rotation-handle {
    position: absolute;
    left: 50%;
    top: -32px;
    width: 12px;
    height: 12px;
    border-radius: 999px;
    background: rgba(34, 90, 156, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.92);
    cursor: grab;
    transform: translateX(-50%);
  }
  .box.hidden-box {
    opacity: 0.18;
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
        <button onclick="copySelectedBoxes()" id="copyBtn">Copy</button>
        <button onclick="pasteBoxes()" id="pasteBtn">Paste</button>
        <button onclick="bringSelectionForward()" id="bringForwardBtn">Bring Forward</button>
        <button onclick="sendSelectionBackward()" id="sendBackwardBtn">Send Backward</button>
        <button onclick="showOnlySelected()" id="onlySelectedBtn">Only Selected</button>
        <button onclick="hideSelectedBoxes()" id="hideSelectedBtn">Hide Selected</button>
        <button onclick="showAllBoxes()" id="showAllBtn">Show All</button>
        <button class="danger" onclick="deleteSelectedBox()" id="deleteBtn">Delete Box</button>
        <button onclick="duplicateSelectedBox()" id="duplicateBtn">Duplicate</button>
      </div>
      <div class="row" style="margin-top:10px;">
        <button onclick="fitToScreen()" id="fitBtn">Fit</button>
        <button onclick="zoomToActualSize()" id="actualSizeBtn">100%</button>
        <button onclick="resetView()" id="resetViewBtn">Reset View</button>
        <div class="muted">Zoom</div>
        <input id="zoomSlider" type="range" min="25" max="250" value="100" oninput="setZoom(this.value)">
        <div id="zoomText" class="muted">100%</div>
      </div>
    </div>
    <div id="canvasStage" class="canvas-stage" style="display:none;">
      <img id="boardImage" alt="Board">
      <div id="overlay"></div>
    </div>
    <div id="minimap" class="minimap hidden">
      <div class="minimap-header">Overview</div>
      <div id="minimapStage" class="minimap-stage">
        <img id="minimapImage" alt="Board overview">
        <div id="minimapViewport" class="minimap-viewport"></div>
      </div>
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
        <div class="hint">Drag a box to move it. Use corners or edge handles to resize. Use the top rotation handle to rotate. Rotation snaps to 45° unless Alt is held. Hold Shift while resizing to lock aspect ratio. Ctrl/Cmd-click adds to the selection. Arrow keys nudge selection, Alt is fine and Shift is coarse. Use mouse wheel to zoom and Space-drag or middle-drag to pan.</div>
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
  selectedBoxIds: [],
  draftBox: null,
  draftStart: null,
  draftNormalized: null,
  isDrawing: false,
  interactionMode: null,
  interactionBoxId: null,
  interactionHandle: null,
  interactionStart: null,
  interactionBoxOriginal: null,
  isPanning: false,
  panStartX: 0,
  panStartY: 0,
  panScrollLeft: 0,
  panScrollTop: 0,
  spacePressed: false,
  zoomPercent: 100,
  imageWidth: 0,
  imageHeight: 0,
  viewStateByImageId: {},
  zoomAnimationFrame: null,
  minimapDragging: false,
  clipboardBoxes: [],
  hiddenBoxIds: [],
  visibilityMode: 'all',
  interactionSelectionBounds: null,
};

const boardImage = document.getElementById('boardImage');
const overlay = document.getElementById('overlay');
const stage = document.getElementById('canvasStage');
const emptyState = document.getElementById('emptyState');
const canvasWrap = document.querySelector('.canvas-wrap');
const imageList = document.getElementById('imageList');
const boxList = document.getElementById('boxList');
const classList = document.getElementById('classList');
const statusBar = document.getElementById('statusBar');
const minimap = document.getElementById('minimap');
const minimapStage = document.getElementById('minimapStage');
const minimapImage = document.getElementById('minimapImage');
const minimapViewport = document.getElementById('minimapViewport');

function colorForClass(className) {
  const index = Math.max(0, state.classes.indexOf(className));
  const hue = (index * 37) % 360;
  return `hsl(${hue} 78% 62%)`;
}

function setStatus(message) {
  statusBar.textContent = message;
}

function viewCenterPoint() {
  const rect = canvasWrap.getBoundingClientRect()
  return {
    x: rect.width / 2,
    y: rect.height / 2,
  }
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

function getSelectedBoxes() {
  return state.annotations.filter((box) => state.selectedBoxIds.includes(box.id));
}

function getPrimarySelectedBox() {
  return state.annotations.find((box) => box.id === state.selectedBoxId) || null;
}

function setSelectedBoxIds(ids) {
  const uniqueIds = [...new Set(ids)].filter((id) => state.annotations.some((box) => box.id === id));
  state.selectedBoxIds = uniqueIds;
  state.selectedBoxId = uniqueIds[0] || null;
}

function toggleSelectedBoxId(id) {
  if (state.selectedBoxIds.includes(id)) {
    setSelectedBoxIds(state.selectedBoxIds.filter((item) => item !== id));
  } else {
    setSelectedBoxIds([...state.selectedBoxIds, id]);
  }
}

function clearSelection() {
  setSelectedBoxIds([]);
}

function getVisibleAnnotations() {
  return state.annotations.filter((box) => {
    if (state.hiddenBoxIds.includes(box.id)) {
      return false;
    }
    if (state.visibilityMode === 'onlySelected') {
      return state.selectedBoxIds.includes(box.id);
    }
    return true;
  });
}

function selectionBounds(boxes = getSelectedBoxes()) {
  if (!boxes.length) {
    return null;
  }
  const left = Math.min(...boxes.map((box) => box.x));
  const top = Math.min(...boxes.map((box) => box.y));
  const right = Math.max(...boxes.map((box) => box.x + box.width));
  const bottom = Math.max(...boxes.map((box) => box.y + box.height));
  return {
    x: left,
    y: top,
    width: right - left,
    height: bottom - top,
    centerX: left + ((right - left) / 2),
    centerY: top + ((bottom - top) / 2),
  };
}

function normalizeAngle(value) {
  let angle = ((Number(value) + 180) % 360 + 360) % 360 - 180;
  if (angle === -180) {
    angle = 180;
  }
  return Number(angle.toFixed(3));
}

function snapAngle(angle, enabled = true) {
  if (!enabled) {
    return normalizeAngle(angle);
  }
  return normalizeAngle(Math.round(angle / 45) * 45);
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
    item.className = `box-item ${state.selectedBoxIds.includes(box.id) ? 'active' : ''}`;
    item.style.opacity = state.hiddenBoxIds.includes(box.id) ? '0.45' : '1';
    item.innerHTML = `
      <div><strong>${index + 1}. ${box.label}</strong></div>
      <div class="muted">${box.class_name}</div>
      <div class="muted">${box.width.toFixed(3)} x ${box.height.toFixed(3)} · ${Number(box.angle || 0).toFixed(1)}°</div>
    `;
    item.onclick = (event) => {
      if (event.ctrlKey || event.metaKey) {
        toggleSelectedBoxId(box.id);
      } else {
        setSelectedBoxIds([box.id]);
      }
      renderBoxes();
    };
    boxList.appendChild(item);
  });
}

function updateSelectionEditor() {
  const editor = document.getElementById('selectionEditor');
  const empty = document.getElementById('selectionEmpty');
  const selected = getPrimarySelectedBox();
  const selectedCount = state.selectedBoxIds.length;
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
  const labelInput = document.getElementById('selectedLabel');
  const angleInput = document.getElementById('selectedAngle');
  labelInput.disabled = selectedCount !== 1;
  angleInput.disabled = selectedCount !== 1;
  document.getElementById('selectionEmpty').textContent = 'No box selected.';
  labelInput.value = selectedCount === 1 ? (selected.label || '') : '';
  angleInput.value = selectedCount === 1 ? Number(selected.angle || 0).toFixed(1) : '';
  labelInput.placeholder = selectedCount === 1 ? 'Custom label' : `${selectedCount} boxes selected`;
  angleInput.placeholder = selectedCount === 1 ? 'Angle' : 'Single-select to edit angle';
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
  canvasWrap.classList.toggle('pan-ready', state.spacePressed && !state.isPanning);
  canvasWrap.classList.toggle('panning', state.isPanning);
  overlay.innerHTML = '';
  getVisibleAnnotations().forEach((box) => {
    const node = document.createElement('div');
    node.className = `box ${state.selectedBoxIds.includes(box.id) ? 'selected' : ''}`;
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
        <div class="edge-handle n" data-handle="n"></div>
        <div class="edge-handle e" data-handle="e"></div>
        <div class="edge-handle s" data-handle="s"></div>
        <div class="edge-handle w" data-handle="w"></div>
        <div class="rotation-stem"></div>
        <div class="rotation-handle" data-handle="rotate"></div>
      </div>
    `;
    node.onmousedown = (event) => {
      event.stopPropagation();
      if (event.ctrlKey || event.metaKey) {
        toggleSelectedBoxId(box.id);
      } else if (!state.selectedBoxIds.includes(box.id)) {
        setSelectedBoxIds([box.id]);
      }
      const handle = event.target.dataset.handle;
      const mode = handle === 'rotate' ? 'rotate' : (handle ? 'resize' : 'move');
      beginBoxInteraction(event, box.id, mode, handle || null);
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
  renderMinimap();
}

function currentContentFocus(focusPoint) {
  if (!focusPoint) {
    return null
  }
  const scale = state.zoomPercent / 100
  return {
    x: (canvasWrap.scrollLeft + focusPoint.x) / Math.max(scale, 0.0001),
    y: (canvasWrap.scrollTop + focusPoint.y) / Math.max(scale, 0.0001),
  }
}

function applyZoom(percent, focusPoint = null, contentFocus = null) {
  const nextPercent = Math.max(25, Math.min(250, Number(percent)));
  state.zoomPercent = nextPercent;
  const scale = state.zoomPercent / 100;
  boardImage.style.width = `${state.imageWidth * scale}px`;
  boardImage.style.height = `${state.imageHeight * scale}px`;
  overlay.style.width = `${state.imageWidth * scale}px`;
  overlay.style.height = `${state.imageHeight * scale}px`;
  document.getElementById('zoomSlider').value = String(state.zoomPercent);
  document.getElementById('zoomText').textContent = `${state.zoomPercent}%`;

  if (focusPoint && contentFocus) {
    requestAnimationFrame(() => {
      canvasWrap.scrollLeft = Math.max(0, (contentFocus.x * scale) - focusPoint.x);
      canvasWrap.scrollTop = Math.max(0, (contentFocus.y * scale) - focusPoint.y);
      persistCurrentViewState();
      renderMinimap();
    });
  } else {
    persistCurrentViewState();
    renderMinimap();
  }
}

function animateZoom(percent, focusPoint = null, duration = 140) {
  if (state.zoomAnimationFrame !== null) {
    cancelAnimationFrame(state.zoomAnimationFrame)
    state.zoomAnimationFrame = null
  }
  const startZoom = state.zoomPercent
  const targetZoom = Math.max(25, Math.min(250, Number(percent)))
  if (Math.abs(targetZoom - startZoom) < 0.01) {
    applyZoom(targetZoom, focusPoint, currentContentFocus(focusPoint))
    return
  }
  const contentFocus = currentContentFocus(focusPoint)
  const startTime = performance.now()
  const easeOutCubic = (t) => 1 - ((1 - t) ** 3)
  const step = (now) => {
    const progress = Math.min(1, (now - startTime) / duration)
    const eased = easeOutCubic(progress)
    const nextZoom = startZoom + ((targetZoom - startZoom) * eased)
    applyZoom(nextZoom, focusPoint, contentFocus)
    if (progress < 1) {
      state.zoomAnimationFrame = requestAnimationFrame(step)
    } else {
      state.zoomAnimationFrame = null
      applyZoom(targetZoom, focusPoint, contentFocus)
    }
  }
  state.zoomAnimationFrame = requestAnimationFrame(step)
}

function setZoom(percent, focusPoint = null) {
  animateZoom(percent, focusPoint)
}

function calculateFitZoom() {
  if (!state.imageWidth || !state.imageHeight) {
    return 100
  }
  const horizontalPadding = 48
  const verticalPadding = 84
  const availableWidth = Math.max(120, canvasWrap.clientWidth - horizontalPadding)
  const availableHeight = Math.max(120, canvasWrap.clientHeight - verticalPadding)
  const fitRatio = Math.min(availableWidth / state.imageWidth, availableHeight / state.imageHeight)
  return Math.max(25, Math.min(250, Math.floor(fitRatio * 100)))
}

function centerViewport() {
  const width = overlay.clientWidth
  const height = overlay.clientHeight
  canvasWrap.scrollLeft = Math.max(0, (width - canvasWrap.clientWidth) / 2)
  canvasWrap.scrollTop = Math.max(0, (height - canvasWrap.clientHeight) / 2)
  persistCurrentViewState()
  renderMinimap()
}

function fitToScreen() {
  if (!state.selectedImageId) {
    return
  }
  applyZoom(calculateFitZoom())
  requestAnimationFrame(centerViewport)
}

function zoomToActualSize() {
  if (!state.selectedImageId) {
    return
  }
  animateZoom(100, viewCenterPoint())
}

function resetView() {
  if (!state.selectedImageId) {
    return
  }
  delete state.viewStateByImageId[state.selectedImageId]
  fitToScreen()
  setStatus('View reset.')
}

function findImageIndex() {
  return state.images.findIndex((image) => image.id === state.selectedImageId);
}

function selectPreviousImage() {
  const index = findImageIndex();
  if (index > 0) {
    persistCurrentViewState()
    loadImage(state.images[index - 1].id);
  }
}

function selectNextImage() {
  const index = findImageIndex();
  if (index !== -1 && index < state.images.length - 1) {
    persistCurrentViewState()
    loadImage(state.images[index + 1].id);
  }
}

function persistCurrentViewState() {
  if (!state.selectedImageId || stage.style.display === 'none') {
    return
  }
  state.viewStateByImageId[state.selectedImageId] = {
    zoomPercent: state.zoomPercent,
    scrollLeft: canvasWrap.scrollLeft,
    scrollTop: canvasWrap.scrollTop,
  }
}

function restoreViewState(imageId) {
  const saved = state.viewStateByImageId[imageId]
  if (!saved) {
    fitToScreen()
    return
  }
  applyZoom(saved.zoomPercent)
  requestAnimationFrame(() => {
    canvasWrap.scrollLeft = saved.scrollLeft
    canvasWrap.scrollTop = saved.scrollTop
    renderMinimap()
  })
}

function renderMinimap() {
  if (!state.selectedImageId || stage.style.display === 'none' || !state.imageWidth || !state.imageHeight) {
    minimap.classList.add('hidden')
    return
  }
  minimap.classList.remove('hidden')
  minimapImage.src = boardImage.src
  const maxWidth = 210
  const maxHeight = 140
  const scale = Math.min(maxWidth / state.imageWidth, maxHeight / state.imageHeight)
  const width = Math.max(80, Math.round(state.imageWidth * scale))
  const height = Math.max(60, Math.round(state.imageHeight * scale))
  minimapStage.style.width = `${width}px`
  minimapStage.style.height = `${height}px`
  const viewportWidth = Math.max(10, (canvasWrap.clientWidth / Math.max(overlay.clientWidth, 1)) * width)
  const viewportHeight = Math.max(10, (canvasWrap.clientHeight / Math.max(overlay.clientHeight, 1)) * height)
  const viewportLeft = (canvasWrap.scrollLeft / Math.max(overlay.clientWidth, 1)) * width
  const viewportTop = (canvasWrap.scrollTop / Math.max(overlay.clientHeight, 1)) * height
  minimapViewport.style.width = `${Math.min(width, viewportWidth)}px`
  minimapViewport.style.height = `${Math.min(height, viewportHeight)}px`
  minimapViewport.style.left = `${Math.min(width - viewportWidth, viewportLeft)}px`
  minimapViewport.style.top = `${Math.min(height - viewportHeight, viewportTop)}px`
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
    clearSelection();
    stage.style.display = 'none';
    emptyState.style.display = 'block';
    updateSummary();
  }
}

async function loadImage(imageId, skipStateRefresh = false) {
  persistCurrentViewState()
  const payload = await fetchJson(`/annotations/${encodeURIComponent(imageId)}`);
  state.selectedImageId = imageId;
  state.annotations = payload.annotation.boxes || [];
  setSelectedBoxIds(state.annotations[0] ? [state.annotations[0].id] : []);
  state.hiddenBoxIds = [];
  state.visibilityMode = 'all';
  state.imageWidth = payload.image.width;
  state.imageHeight = payload.image.height;
  boardImage.onload = () => {
    stage.style.display = 'inline-block';
    emptyState.style.display = 'none';
    restoreViewState(imageId);
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
  if (!state.selectedBoxIds.includes(boxId)) {
    setSelectedBoxIds([boxId]);
  }
  state.isDrawing = false;
  state.draftStart = null;
  state.draftBox = null;
  state.draftNormalized = null;
  state.interactionMode = mode;
  state.interactionBoxId = boxId;
  state.interactionHandle = handle;
  state.interactionStart = pointerToNormalized(event);
  state.interactionBoxOriginal = Object.fromEntries(
    getSelectedBoxes().map((selectedBox) => [selectedBox.id, { ...selectedBox }]),
  );
  state.interactionSelectionBounds = selectionBounds(Object.values(state.interactionBoxOriginal));
}

function beginPan(event) {
  state.isPanning = true;
  state.isDrawing = false;
  state.draftStart = null;
  state.draftBox = null;
  state.draftNormalized = null;
  state.interactionMode = null;
  state.panStartX = event.clientX;
  state.panStartY = event.clientY;
  state.panScrollLeft = canvasWrap.scrollLeft;
  state.panScrollTop = canvasWrap.scrollTop;
  renderBoxes();
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
  if (!box || !state.interactionStart || !state.interactionBoxOriginal || !state.interactionSelectionBounds) {
    return;
  }
  const pointer = pointerToNormalized(event);
  const original = state.interactionBoxOriginal[state.interactionBoxId];
  const originalSelection = state.interactionSelectionBounds;
  const dx = pointer.x - state.interactionStart.x;
  const dy = pointer.y - state.interactionStart.y;
  const selectedIds = Object.keys(state.interactionBoxOriginal);

  if (state.interactionMode === 'move') {
    selectedIds.forEach((id) => {
      const target = state.annotations.find((item) => item.id === id);
      const baseline = state.interactionBoxOriginal[id];
      if (!target || !baseline) {
        return;
      }
      Object.assign(target, clampBox({
        ...target,
        x: baseline.x + dx,
        y: baseline.y + dy,
        width: baseline.width,
        height: baseline.height,
      }));
    });
    return;
  }

  if (state.interactionMode === 'rotate') {
    const centerX = originalSelection.centerX;
    const centerY = originalSelection.centerY;
    const startAngle = Math.atan2(state.interactionStart.y - centerY, state.interactionStart.x - centerX);
    const currentAngle = Math.atan2(pointer.y - centerY, pointer.x - centerX);
    const deltaAngle = snapAngle((currentAngle - startAngle) * (180 / Math.PI), !event.altKey);
    const radians = deltaAngle * (Math.PI / 180);
    const cos = Math.cos(radians);
    const sin = Math.sin(radians);
    selectedIds.forEach((id) => {
      const target = state.annotations.find((item) => item.id === id);
      const baseline = state.interactionBoxOriginal[id];
      if (!target || !baseline) {
        return;
      }
      const boxCenterX = baseline.x + (baseline.width / 2);
      const boxCenterY = baseline.y + (baseline.height / 2);
      const relX = boxCenterX - centerX;
      const relY = boxCenterY - centerY;
      const rotatedCenterX = centerX + (relX * cos) - (relY * sin);
      const rotatedCenterY = centerY + (relX * sin) + (relY * cos);
      Object.assign(target, clampBox({
        ...target,
        x: rotatedCenterX - (baseline.width / 2),
        y: rotatedCenterY - (baseline.height / 2),
        width: baseline.width,
        height: baseline.height,
        angle: normalizeAngle(Number(baseline.angle || 0) + deltaAngle),
      }));
    });
    return;
  }

  let x = originalSelection.x;
  let y = originalSelection.y;
  let width = originalSelection.width;
  let height = originalSelection.height;
  const handle = state.interactionHandle;
  if (handle.includes('e')) {
    width = originalSelection.width + dx;
  }
  if (handle.includes('s')) {
    height = originalSelection.height + dy;
  }
  if (handle.includes('w')) {
    x = originalSelection.x + dx;
    width = originalSelection.width - dx;
  }
  if (handle.includes('n')) {
    y = originalSelection.y + dy;
    height = originalSelection.height - dy;
  }
  if (event.shiftKey) {
    const aspect = originalSelection.width / Math.max(originalSelection.height, 0.0001);
    if (handle === 'n' || handle === 's') {
      width = height * aspect;
      x = originalSelection.centerX - (width / 2);
    } else if (handle === 'e' || handle === 'w') {
      height = width / aspect;
      y = originalSelection.centerY - (height / 2);
    } else {
      const size = Math.max(width, height * aspect);
      width = size;
      height = size / aspect;
      if (handle.includes('w')) {
        x = originalSelection.x + originalSelection.width - width;
      }
      if (handle.includes('n')) {
        y = originalSelection.y + originalSelection.height - height;
      }
    }
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
  selectedIds.forEach((id) => {
    const target = state.annotations.find((item) => item.id === id);
    const baseline = state.interactionBoxOriginal[id];
    if (!target || !baseline) {
      return;
    }
    const relLeft = (baseline.x - originalSelection.x) / Math.max(originalSelection.width, 0.0001);
    const relTop = (baseline.y - originalSelection.y) / Math.max(originalSelection.height, 0.0001);
    const relWidth = baseline.width / Math.max(originalSelection.width, 0.0001);
    const relHeight = baseline.height / Math.max(originalSelection.height, 0.0001);
    Object.assign(target, clampBox({
      ...target,
      x: x + (relLeft * width),
      y: y + (relTop * height),
      width: Math.max(0.001, relWidth * width),
      height: Math.max(0.001, relHeight * height),
      angle: baseline.angle,
    }));
  });
}

overlay.addEventListener('mousedown', (event) => {
  if ((event.button === 1 || (event.button === 0 && state.spacePressed)) && state.selectedImageId) {
    event.preventDefault();
    beginPan(event);
    return;
  }
  if (event.target !== overlay || !state.selectedImageId) {
    return;
  }
  state.interactionMode = null;
  state.isDrawing = true;
  const start = pointerToNormalized(event);
  state.draftStart = start;
  state.draftBox = { left: 0, top: 0, width: 0, height: 0 };
  clearSelection();
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
  if (state.isPanning) {
    canvasWrap.scrollLeft = state.panScrollLeft - (event.clientX - state.panStartX);
    canvasWrap.scrollTop = state.panScrollTop - (event.clientY - state.panStartY);
    return;
  }
  if (state.interactionMode) {
    applyBoxInteraction(event);
    renderBoxes();
  }
});

window.addEventListener('mouseup', () => {
  if (state.isPanning) {
    state.isPanning = false;
    renderBoxes();
    return;
  }
  if (state.interactionMode) {
    state.interactionMode = null;
    state.interactionBoxId = null;
    state.interactionHandle = null;
    state.interactionStart = null;
    state.interactionBoxOriginal = null;
    state.interactionSelectionBounds = null;
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
  setSelectedBoxIds([newBox.id]);
  updateImageRecordBoxCount();
  renderBoxes();
  setStatus(`Added ${className} box. Save when ready.`);
  estimateBoxAngle(newBox.id, false);
});

canvasWrap.addEventListener('mousedown', (event) => {
  if (!state.selectedImageId) {
    return;
  }
  if (event.button === 1 || (event.button === 0 && state.spacePressed)) {
    event.preventDefault();
    beginPan(event);
  }
});

canvasWrap.addEventListener('wheel', (event) => {
  if (!state.selectedImageId || stage.style.display === 'none') {
    return;
  }
  event.preventDefault();
  const rect = canvasWrap.getBoundingClientRect();
  const focusPoint = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  };
  const direction = event.deltaY < 0 ? 1 : -1;
  const step = event.shiftKey ? 20 : 10;
  setZoom(state.zoomPercent + (direction * step), focusPoint);
}, { passive: false });

canvasWrap.addEventListener('dblclick', (event) => {
  if (!state.selectedImageId || stage.style.display === 'none') {
    return
  }
  const rect = canvasWrap.getBoundingClientRect()
  const focusPoint = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
  animateZoom(Math.min(250, state.zoomPercent + 35), focusPoint, 170)
})

canvasWrap.addEventListener('scroll', () => {
  persistCurrentViewState()
  renderMinimap()
})

function moveViewportFromMinimap(event) {
  if (!state.selectedImageId || !state.imageWidth || !state.imageHeight) {
    return
  }
  const rect = minimapStage.getBoundingClientRect()
  const x = Math.max(0, Math.min(event.clientX - rect.left, rect.width))
  const y = Math.max(0, Math.min(event.clientY - rect.top, rect.height))
  const contentX = (x / rect.width) * overlay.clientWidth
  const contentY = (y / rect.height) * overlay.clientHeight
  canvasWrap.scrollLeft = Math.max(0, contentX - (canvasWrap.clientWidth / 2))
  canvasWrap.scrollTop = Math.max(0, contentY - (canvasWrap.clientHeight / 2))
  persistCurrentViewState()
  renderMinimap()
}

minimapStage.addEventListener('mousedown', (event) => {
  event.preventDefault()
  state.minimapDragging = true
  moveViewportFromMinimap(event)
})

function updateSelectedBoxClass(className) {
  const boxes = getSelectedBoxes();
  if (!boxes.length) {
    return;
  }
  boxes.forEach((box) => {
    box.class_name = className;
    if (!box.label || state.classes.includes(box.label)) {
      box.label = className;
    }
  });
  renderBoxes();
}

function updateSelectedBoxLabel(label) {
  const box = getPrimarySelectedBox();
  if (!box) {
    return;
  }
  box.label = label.trim() || box.class_name;
  renderBoxes();
}

function updateSelectedBoxAngle(value) {
  const box = getPrimarySelectedBox();
  if (!box) {
    return;
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return;
  }
  box.angle = normalizeAngle(parsed);
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
  if (!state.selectedBoxId || state.selectedBoxIds.length !== 1) {
    return;
  }
  await estimateBoxAngle(state.selectedBoxId, true);
}

function deleteSelectedBox() {
  if (!state.selectedBoxIds.length) {
    return;
  }
  state.annotations = state.annotations.filter((box) => !state.selectedBoxIds.includes(box.id));
  state.hiddenBoxIds = state.hiddenBoxIds.filter((id) => !state.selectedBoxIds.includes(id));
  setSelectedBoxIds(state.annotations[0] ? [state.annotations[0].id] : []);
  updateImageRecordBoxCount();
  renderBoxes();
  setStatus('Deleted selected boxes.');
}

function duplicateSelectedBox() {
  const selected = getSelectedBoxes();
  if (!selected.length) {
    return;
  }
  const nextIds = [];
  selected.forEach((box) => {
    const next = {
      ...box,
      id: crypto.randomUUID(),
      x: Number(Math.min(box.x + 0.01, 1 - box.width).toFixed(6)),
      y: Number(Math.min(box.y + 0.01, 1 - box.height).toFixed(6)),
    };
    state.annotations.push(next);
    nextIds.push(next.id);
  });
  setSelectedBoxIds(nextIds);
  updateImageRecordBoxCount();
  renderBoxes();
  setStatus('Duplicated selected boxes.');
}

function copySelectedBoxes() {
  const selected = getSelectedBoxes();
  if (!selected.length) {
    return;
  }
  state.clipboardBoxes = selected.map((box) => ({ ...box }));
  setStatus(`Copied ${selected.length} box${selected.length === 1 ? '' : 'es'}.`);
}

function pasteBoxes() {
  if (!state.clipboardBoxes.length) {
    return;
  }
  const nextIds = [];
  state.clipboardBoxes.forEach((box, index) => {
    const offset = 0.01 + (index * 0.002);
    const next = {
      ...box,
      id: crypto.randomUUID(),
      x: Number(Math.min(box.x + offset, 1 - box.width).toFixed(6)),
      y: Number(Math.min(box.y + offset, 1 - box.height).toFixed(6)),
    };
    state.annotations.push(next);
    nextIds.push(next.id);
  });
  setSelectedBoxIds(nextIds);
  updateImageRecordBoxCount();
  renderBoxes();
  setStatus(`Pasted ${nextIds.length} box${nextIds.length === 1 ? '' : 'es'}.`);
}

function bringSelectionForward() {
  if (!state.selectedBoxIds.length) {
    return;
  }
  for (let index = state.annotations.length - 2; index >= 0; index -= 1) {
    if (state.selectedBoxIds.includes(state.annotations[index].id) && !state.selectedBoxIds.includes(state.annotations[index + 1].id)) {
      const current = state.annotations[index];
      state.annotations[index] = state.annotations[index + 1];
      state.annotations[index + 1] = current;
    }
  }
  renderBoxes();
  setStatus('Moved selection forward.');
}

function sendSelectionBackward() {
  if (!state.selectedBoxIds.length) {
    return;
  }
  for (let index = 1; index < state.annotations.length; index += 1) {
    if (state.selectedBoxIds.includes(state.annotations[index].id) && !state.selectedBoxIds.includes(state.annotations[index - 1].id)) {
      const current = state.annotations[index];
      state.annotations[index] = state.annotations[index - 1];
      state.annotations[index - 1] = current;
    }
  }
  renderBoxes();
  setStatus('Moved selection backward.');
}

function showOnlySelected() {
  if (!state.selectedBoxIds.length) {
    return;
  }
  state.visibilityMode = 'onlySelected';
  renderBoxes();
  setStatus('Showing only selected boxes.');
}

function hideSelectedBoxes() {
  if (!state.selectedBoxIds.length) {
    return;
  }
  state.hiddenBoxIds = [...new Set([...state.hiddenBoxIds, ...state.selectedBoxIds])];
  clearSelection();
  state.visibilityMode = 'all';
  renderBoxes();
  setStatus('Hid selected boxes temporarily.');
}

function showAllBoxes() {
  state.hiddenBoxIds = [];
  state.visibilityMode = 'all';
  renderBoxes();
  setStatus('Showing all boxes.');
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
  if (key === ' ') {
    if (!state.spacePressed) {
      event.preventDefault();
      state.spacePressed = true;
      renderBoxes();
    }
    return;
  }
  if ((event.ctrlKey || event.metaKey) && key === '0') {
    event.preventDefault();
    resetView();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && key === 'c') {
    event.preventDefault();
    copySelectedBoxes();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && key === 'v') {
    event.preventDefault();
    pasteBoxes();
    return;
  }
  if (key === '+' || key === '=') {
    event.preventDefault();
    animateZoom(state.zoomPercent + 15, viewCenterPoint(), 120);
    return;
  }
  if (key === '-' || key === '_') {
    event.preventDefault();
    animateZoom(state.zoomPercent - 15, viewCenterPoint(), 120);
    return;
  }
  if (key === '[' || key === 'pageup') {
    event.preventDefault();
    selectPreviousImage();
    return;
  }
  if (key === ']' || key === 'pagedown') {
    event.preventDefault();
    selectNextImage();
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
  const selected = getSelectedBoxes();
  if (!selected.length) {
    return;
  }
  const step = event.altKey ? 0.001 : (event.shiftKey ? 0.01 : 0.0025);
  let moved = false;
  selected.forEach((box) => {
    if (key === 'arrowleft') {
      box.x = Number(Math.max(0, box.x - step).toFixed(6));
      moved = true;
    }
    if (key === 'arrowright') {
      box.x = Number(Math.min(1 - box.width, box.x + step).toFixed(6));
      moved = true;
    }
    if (key === 'arrowup') {
      box.y = Number(Math.max(0, box.y - step).toFixed(6));
      moved = true;
    }
    if (key === 'arrowdown') {
      box.y = Number(Math.min(1 - box.height, box.y + step).toFixed(6));
      moved = true;
    }
  });
  if (moved) {
    renderBoxes();
  }
});

document.addEventListener('keyup', (event) => {
  if (event.key === ' ') {
    state.spacePressed = false;
    if (!state.isPanning) {
      renderBoxes();
    }
  }
});

window.addEventListener('mousemove', (event) => {
  if (state.minimapDragging) {
    moveViewportFromMinimap(event)
  }
})

window.addEventListener('mouseup', () => {
  if (state.minimapDragging) {
    state.minimapDragging = false
  }
})

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
