#!/usr/bin/env python3
"""
PCB Component Labeling Tool
- Chạy: python3 pcb_labeler.py
- Mở browser: http://localhost:5000
- Click + kéo để crop component, gõ label để lưu
"""

import os
import json
import base64
import shutil
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import io

# ── Cấu hình ──────────────────────────────────────────────
OUTPUT_DIR = Path("dataset")
CLASSES = {
    "o": "ok",
    "s": "shift",
    "m": "missing",
    "t": "tombstone",
    "w": "wrong_part",
    "p": "polarity",
    "f": "solder_fail",
}
# ──────────────────────────────────────────────────────────

# Tạo thư mục output
for cls in CLASSES.values():
    (OUTPUT_DIR / "train" / cls).mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "val" / cls).mkdir(parents=True, exist_ok=True)

# Counter cho mỗi class
counters = {cls: len(list((OUTPUT_DIR / "train" / cls).glob("*.jpg"))) 
            for cls in CLASSES.values()}

HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>PCB Labeler</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #1a1a2e; color: #eee; font-family: 'Segoe UI', sans-serif; }
  
  .header {
    background: #16213e;
    padding: 12px 20px;
    display: flex;
    align-items: center;
    gap: 20px;
    border-bottom: 2px solid #0f3460;
  }
  .header h1 { font-size: 18px; color: #e94560; }
  
  .main { display: flex; height: calc(100vh - 56px); }
  
  .sidebar {
    width: 260px;
    background: #16213e;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow-y: auto;
    border-right: 1px solid #0f3460;
  }
  
  .canvas-area {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: auto;
    padding: 16px;
    position: relative;
  }
  
  #canvas {
    cursor: crosshair;
    border: 2px solid #0f3460;
    max-width: 100%;
    image-rendering: pixelated;
  }
  
  .section-title {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #888;
    margin-bottom: 4px;
  }
  
  .upload-btn {
    background: #e94560;
    color: white;
    border: none;
    padding: 10px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    width: 100%;
    font-weight: bold;
  }
  .upload-btn:hover { background: #c73652; }
  
  .class-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }
  
  .class-btn {
    padding: 8px 6px;
    border: 2px solid #333;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    text-align: center;
    background: #0f3460;
    color: #eee;
    transition: all 0.15s;
  }
  .class-btn:hover { border-color: #e94560; transform: scale(1.03); }
  .class-btn.active { border-color: #4ecca3; background: #1a5a4a; color: #4ecca3; }
  .class-btn .key {
    display: inline-block;
    background: #333;
    border-radius: 3px;
    padding: 1px 5px;
    font-size: 10px;
    font-weight: bold;
    margin-right: 4px;
    color: #ffd700;
  }
  
  .stats {
    background: #0f3460;
    border-radius: 8px;
    padding: 10px;
  }
  .stat-row {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    padding: 2px 0;
    border-bottom: 1px solid #1a3a6a;
  }
  .stat-row:last-child { border: none; }
  .stat-count { color: #4ecca3; font-weight: bold; }
  
  .controls { display: flex; flex-direction: column; gap: 6px; }
  .btn {
    padding: 8px;
    border: 1px solid #333;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    background: #0f3460;
    color: #eee;
    text-align: center;
  }
  .btn:hover { background: #1a4a8a; }
  .btn.danger { border-color: #e94560; }
  .btn.danger:hover { background: #4a1a2a; }
  
  .info-box {
    background: #0a2040;
    border: 1px solid #1a4a8a;
    border-radius: 8px;
    padding: 10px;
    font-size: 11px;
    line-height: 1.8;
    color: #aaa;
  }
  .info-box b { color: #4ecca3; }
  
  .status-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #0f3460;
    padding: 6px 16px;
    font-size: 12px;
    color: #4ecca3;
    border-top: 1px solid #1a4a8a;
    z-index: 100;
  }
  
  #overlay {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
    border-radius: 8px;
  }
  
  .save-popup {
    background: #16213e;
    border: 2px solid #4ecca3;
    border-radius: 12px;
    padding: 24px 32px;
    text-align: center;
    min-width: 280px;
  }
  .save-popup h3 { color: #4ecca3; margin-bottom: 12px; }
  .save-popup .preview {
    width: 200px;
    height: 150px;
    object-fit: contain;
    border: 1px solid #333;
    background: #000;
    margin: 10px auto;
    display: block;
  }
  .save-popup .label-buttons {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-top: 12px;
  }
  .save-popup .lbl-btn {
    padding: 8px;
    border: 1px solid #333;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    background: #0f3460;
    color: #eee;
  }
  .save-popup .lbl-btn:hover { background: #1a5a4a; border-color: #4ecca3; }
  .save-popup .cancel-btn {
    margin-top: 10px;
    padding: 6px 20px;
    background: #333;
    border: none;
    border-radius: 6px;
    color: #aaa;
    cursor: pointer;
    font-size: 12px;
  }
  
  .toast {
    position: fixed;
    top: 20px;
    right: 20px;
    background: #4ecca3;
    color: #000;
    padding: 10px 20px;
    border-radius: 8px;
    font-weight: bold;
    font-size: 14px;
    z-index: 999;
    opacity: 0;
    transition: opacity 0.3s;
    pointer-events: none;
  }
  .toast.show { opacity: 1; }
  
  .no-image {
    color: #555;
    text-align: center;
    font-size: 14px;
  }
  .no-image .icon { font-size: 48px; margin-bottom: 12px; }
</style>
</head>
<body>

<div class="header">
  <h1>🔬 PCB Component Labeler</h1>
  <span style="color:#888; font-size:13px;">Kéo để crop → chọn label → lưu tự động</span>
</div>

<div class="main">
  <div class="sidebar">
    <!-- Upload -->
    <div>
      <div class="section-title">Ảnh PCB</div>
      <input type="file" id="fileInput" accept="image/*" style="display:none">
      <button class="upload-btn" onclick="document.getElementById('fileInput').click()">
        📁 Mở ảnh PCB
      </button>
      <div id="filename" style="font-size:11px; color:#888; margin-top:6px; word-break:break-all;"></div>
    </div>
    
    <!-- Classes -->
    <div>
      <div class="section-title">Phím tắt / Label</div>
      <div class="class-grid">
        <div class="class-btn" data-key="o" onclick="selectClass('ok','o')">
          <span class="key">O</span>OK
        </div>
        <div class="class-btn" data-key="s" onclick="selectClass('shift','s')">
          <span class="key">S</span>Shift
        </div>
        <div class="class-btn" data-key="m" onclick="selectClass('missing','m')">
          <span class="key">M</span>Missing
        </div>
        <div class="class-btn" data-key="t" onclick="selectClass('tombstone','t')">
          <span class="key">T</span>Tombstone
        </div>
        <div class="class-btn" data-key="w" onclick="selectClass('wrong_part','w')">
          <span class="key">W</span>Wrong Part
        </div>
        <div class="class-btn" data-key="p" onclick="selectClass('polarity','p')">
          <span class="key">P</span>Polarity
        </div>
        <div class="class-btn" data-key="f" onclick="selectClass('solder_fail','f')">
          <span class="key">F</span>Solder Fail
        </div>
      </div>
    </div>

    <!-- Stats -->
    <div>
      <div class="section-title">Số ảnh đã lưu</div>
      <div class="stats" id="stats">
        <div class="stat-row"><span>ok</span><span class="stat-count" id="cnt-ok">0</span></div>
        <div class="stat-row"><span>shift</span><span class="stat-count" id="cnt-shift">0</span></div>
        <div class="stat-row"><span>missing</span><span class="stat-count" id="cnt-missing">0</span></div>
        <div class="stat-row"><span>tombstone</span><span class="stat-count" id="cnt-tombstone">0</span></div>
        <div class="stat-row"><span>wrong_part</span><span class="stat-count" id="cnt-wrong_part">0</span></div>
        <div class="stat-row"><span>polarity</span><span class="stat-count" id="cnt-polarity">0</span></div>
        <div class="stat-row"><span>solder_fail</span><span class="stat-count" id="cnt-solder_fail">0</span></div>
        <div class="stat-row" style="border-top:1px solid #4ecca3; margin-top:4px; padding-top:4px;">
          <span><b>Total</b></span><span class="stat-count" id="cnt-total">0</span>
        </div>
      </div>
    </div>
    
    <!-- Controls -->
    <div class="controls">
      <div class="section-title">Thao tác</div>
      <div class="btn" onclick="undoLast()">↩ Undo ảnh cuối (U)</div>
      <div class="btn danger" onclick="clearCanvas()">✕ Xóa vùng chọn (Esc)</div>
    </div>
    
    <!-- Shortcuts -->
    <div class="info-box">
      <b>Hướng dẫn:</b><br>
      1. Mở ảnh PCB<br>
      2. Click + kéo để chọn component<br>
      3. Nhấn phím tắt hoặc click label<br>
      4. Ảnh tự lưu vào <b>dataset/</b><br><br>
      <b>Phím tắt:</b><br>
      O=ok · S=shift · M=missing<br>
      T=tombstone · W=wrong · P=polarity<br>
      F=solder_fail · U=undo · Esc=cancel
    </div>
  </div>
  
  <div class="canvas-area" id="canvasArea">
    <div class="no-image" id="noImage">
      <div class="icon">🖼️</div>
      Mở ảnh PCB để bắt đầu label
    </div>
    <canvas id="canvas" style="display:none"></canvas>
    
    <!-- Save popup -->
    <div id="overlay" style="display:none;">
      <div class="save-popup">
        <h3>Chọn label cho component này</h3>
        <img id="cropPreview" class="preview" src="">
        <div class="label-buttons">
          <div class="lbl-btn" onclick="saveWithLabel('ok')">✅ OK</div>
          <div class="lbl-btn" onclick="saveWithLabel('shift')">↔ Shift</div>
          <div class="lbl-btn" onclick="saveWithLabel('missing')">❌ Missing</div>
          <div class="lbl-btn" onclick="saveWithLabel('tombstone')">⬆ Tombstone</div>
          <div class="lbl-btn" onclick="saveWithLabel('wrong_part')">❓ Wrong Part</div>
          <div class="lbl-btn" onclick="saveWithLabel('polarity')">🔄 Polarity</div>
          <div class="lbl-btn" onclick="saveWithLabel('solder_fail')">💧 Solder Fail</div>
        </div>
        <button class="cancel-btn" onclick="cancelCrop()">Hủy (Esc)</button>
      </div>
    </div>
  </div>
</div>

<div class="status-bar" id="statusBar">Mở ảnh PCB để bắt đầu...</div>
<div class="toast" id="toast"></div>

<script>
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
let img = null;
let isDrawing = false;
let startX, startY, endX, endY;
let currentCrop = null;
let selectedClass = null;
let counters = {};
let lastSaved = null;
let scale = 1;

// Load file
document.getElementById('fileInput').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  document.getElementById('filename').textContent = file.name;
  const reader = new FileReader();
  reader.onload = ev => {
    img = new Image();
    img.onload = () => {
      // Fit to screen
      const maxW = document.getElementById('canvasArea').clientWidth - 40;
      const maxH = document.getElementById('canvasArea').clientHeight - 40;
      scale = Math.min(1, maxW / img.width, maxH / img.height);
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      document.getElementById('noImage').style.display = 'none';
      canvas.style.display = 'block';
      setStatus(`Ảnh: ${img.width}x${img.height}px | Scale: ${Math.round(scale*100)}% | Kéo để chọn component`);
    };
    img.src = ev.target.result;
  };
  reader.readAsDataURL(file);
});

// Mouse events
canvas.addEventListener('mousedown', e => {
  if (!img) return;
  isDrawing = true;
  const r = canvas.getBoundingClientRect();
  startX = e.clientX - r.left;
  startY = e.clientY - r.top;
  endX = startX; endY = startY;
});

canvas.addEventListener('mousemove', e => {
  if (!isDrawing) return;
  const r = canvas.getBoundingClientRect();
  endX = e.clientX - r.left;
  endY = e.clientY - r.top;
  redraw();
  // Draw selection box
  ctx.strokeStyle = '#4ecca3';
  ctx.lineWidth = 2;
  ctx.setLineDash([5, 3]);
  ctx.strokeRect(startX, startY, endX - startX, endY - startY);
  ctx.fillStyle = 'rgba(78, 204, 163, 0.1)';
  ctx.fillRect(startX, startY, endX - startX, endY - startY);
});

canvas.addEventListener('mouseup', e => {
  if (!isDrawing) return;
  isDrawing = false;
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  if (w < 10 || h < 10) return; // Bỏ qua click quá nhỏ
  
  // Lấy crop từ ảnh gốc
  const x0 = Math.min(startX, endX) / scale;
  const y0 = Math.min(startY, endY) / scale;
  const cw = w / scale;
  const ch = h / scale;
  
  const tmpCanvas = document.createElement('canvas');
  tmpCanvas.width = cw; tmpCanvas.height = ch;
  const tmpCtx = tmpCanvas.getContext('2d');
  tmpCtx.drawImage(img, x0, y0, cw, ch, 0, 0, cw, ch);
  currentCrop = tmpCanvas.toDataURL('image/jpeg', 0.95);
  
  // Nếu đã chọn class → lưu ngay
  if (selectedClass) {
    saveWithLabel(selectedClass);
    return;
  }
  
  // Hiện popup chọn label
  document.getElementById('cropPreview').src = currentCrop;
  document.getElementById('overlay').style.display = 'flex';
  setStatus('Chọn label cho component...');
});

// Select class
function selectClass(cls, key) {
  selectedClass = cls;
  document.querySelectorAll('.class-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`.class-btn[data-key="${key}"]`).classList.add('active');
  setStatus(`Class đang chọn: ${cls.toUpperCase()} | Kéo để crop component`);
}

// Save crop
function saveWithLabel(label) {
  if (!currentCrop) return;
  document.getElementById('overlay').style.display = 'none';
  
  fetch('/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({image: currentCrop, label: label})
  })
  .then(r => r.json())
  .then(data => {
    lastSaved = {label, filename: data.filename};
    counters[label] = (counters[label] || 0) + 1;
    updateStats();
    showToast(`✅ Đã lưu: ${label} #${counters[label]}`);
    setStatus(`Lưu thành công: ${data.filename}`);
    currentCrop = null;
    redraw();
  });
}

function cancelCrop() {
  document.getElementById('overlay').style.display = 'none';
  currentCrop = null;
  redraw();
  setStatus('Đã hủy. Kéo để chọn component khác.');
}

// Undo
function undoLast() {
  if (!lastSaved) return;
  fetch('/undo', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({filename: lastSaved.filename, label: lastSaved.label})
  })
  .then(r => r.json())
  .then(data => {
    counters[lastSaved.label] = Math.max(0, (counters[lastSaved.label] || 1) - 1);
    updateStats();
    showToast(`↩ Đã undo: ${lastSaved.label}`);
    lastSaved = null;
  });
}

function clearCanvas() {
  document.getElementById('overlay').style.display = 'none';
  currentCrop = null;
  isDrawing = false;
  redraw();
  setStatus('Đã xóa. Kéo để chọn component mới.');
}

function redraw() {
  if (!img) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
}

function updateStats() {
  const classes = ['ok','shift','missing','tombstone','wrong_part','polarity','solder_fail'];
  let total = 0;
  classes.forEach(cls => {
    const cnt = counters[cls] || 0;
    const el = document.getElementById(`cnt-${cls}`);
    if (el) el.textContent = cnt;
    total += cnt;
  });
  document.getElementById('cnt-total').textContent = total;
}

// Load initial counts
fetch('/counts').then(r => r.json()).then(data => {
  counters = data;
  updateStats();
});

function setStatus(msg) {
  document.getElementById('statusBar').textContent = msg;
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2000);
}

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  const key = e.key.toLowerCase();
  const keyMap = {o:'ok',s:'shift',m:'missing',t:'tombstone',w:'wrong_part',p:'polarity',f:'solder_fail'};
  
  if (document.getElementById('overlay').style.display !== 'none') {
    if (key === 'escape') { cancelCrop(); return; }
    if (keyMap[key]) { saveWithLabel(keyMap[key]); return; }
  }
  
  if (key === 'escape') { clearCanvas(); return; }
  if (key === 'u') { undoLast(); return; }
  if (keyMap[key]) { selectClass(keyMap[key], key); return; }
});
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass  # Tắt log

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif path == '/counts':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(counters).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = json.loads(self.rfile.read(length))
        path = urlparse(self.path).path

        if path == '/save':
            label = body['label']
            img_data = body['image'].split(',')[1]
            img_bytes = base64.b64decode(img_data)
            
            counters[label] = counters.get(label, 0) + 1
            cnt = counters[label]
            
            # 80% train, 20% val
            split = 'train' if cnt % 5 != 0 else 'val'
            filename = f"{label}_{cnt:04d}.jpg"
            save_path = OUTPUT_DIR / split / label / filename
            
            with open(save_path, 'wb') as f:
                f.write(img_bytes)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'filename': str(save_path),
                'count': cnt
            }).encode())

        elif path == '/undo':
            label = body['label']
            filename = body['filename']
            try:
                os.remove(filename)
                if label in counters and counters[label] > 0:
                    counters[label] -= 1
                result = {'ok': True}
            except Exception as e:
                result = {'ok': False, 'error': str(e)}
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())


if __name__ == '__main__':
    port = 5000
    server = HTTPServer(('localhost', port), Handler)
    print(f"""
╔══════════════════════════════════════════╗
║      PCB Component Labeling Tool         ║
╠══════════════════════════════════════════╣
║  Mở browser: http://localhost:{port}       ║
║  Ảnh lưu vào: ./dataset/                ║
║  Dừng: Ctrl+C                           ║
╚══════════════════════════════════════════╝
    """)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng. Dataset lưu tại ./dataset/")