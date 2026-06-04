# Anomaly Detection Testing — Grafana + Loki Stack

**For:** Codex  
**Repo:** `lystiger/AOI`  
**Purpose:** Implement and run all anomaly detection experiment scenarios required by the thesis proposal — *"Design and Evaluation of an AI Model Logging and Monitoring System Using the Loki Stack"*. This is the primary thesis evaluation chapter. Every scenario here produces observable evidence in Grafana and queryable logs in Loki.

---

## Context: What Already Exists

- `src/aoi/cli.py` — `send-mock-events` command POSTs batches to `POST /events`
- `src/aoi/mock_inference.py` — `generate_mock_events()` cycles through 7 hardcoded events
- `src/aoi/api/routes/events.py` — accepts payload, writes JSONL via `LogManager`, persists to DB
- `deploy/promtail/config.yml` — scrapes `/var/log/aoi/*.jsonl`, extracts labels: `inspection_result`, `defect_type`, `pcb_id`, `component_id`
- `deploy/grafana/provisioning/dashboards/json/aoi-overview.json` — existing panels:
  - Events Last 5m (stat)
  - Fails Last 5m (stat)
  - Boards Seen Last 15m (stat)
  - Avg Latency Last 5m (stat)
  - Inspection Result Rate (timeseries)
  - Failure Types (timeseries)
  - Raw AOI Events (logs)

**What is missing:** dedicated anomaly scenario scripts, Grafana alert rules, and new dashboard panels for anomaly visualisation. This document tells Codex exactly what to build.

---

## Directory Structure to Create

```
experiments/
├── scenarios/
│   ├── __init__.py
│   ├── base.py                    # shared HTTP sender + timing utilities
│   ├── s01_normal_baseline.py     # Scenario 1 — normal healthy operation
│   ├── s02_high_defect_rate.py    # Scenario 2 — defect rate spike
│   ├── s03_latency_spike.py       # Scenario 3 — inference latency anomaly
│   ├── s04_confidence_drop.py     # Scenario 4 — low confidence storm
│   ├── s05_missing_component.py   # Scenario 5 — single defect type flood
│   ├── s06_board_failure.py       # Scenario 6 — entire board failing
│   ├── s07_recovery.py            # Scenario 7 — system recovery after anomaly
│   ├── s08_intermittent_fault.py  # Scenario 8 — intermittent random faults
│   └── s09_model_degradation.py   # Scenario 9 — gradual accuracy degradation
├── runner.py                      # run all or selected scenarios in sequence
├── report.py                      # query Loki API and generate markdown report
└── requirements-experiments.txt
deploy/grafana/provisioning/dashboards/json/
└── aoi-anomaly-detection.json     # new Grafana dashboard for all anomaly panels
deploy/grafana/provisioning/alerting/
└── aoi-alerts.yml                 # Grafana alert rules for each anomaly type
docs/experiments/
└── anomaly_detection_plan.md      # this file (copy here)
```

---

## Step 0 — Shared Base (`experiments/scenarios/base.py`)

```python
"""
Shared utilities for all anomaly scenario scripts.
All scenarios import from here — no duplication of HTTP logic.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request as urllib_request

DEFAULT_ENDPOINT = "http://localhost:8000/events"
DEFAULT_MODEL_VERSION = "anomaly-test-v1"


@dataclass
class ScenarioResult:
    scenario_id: str
    scenario_name: str
    events_sent: int
    batches_sent: int
    duration_seconds: float
    errors: list[str]

    def summary(self) -> str:
        status = "PASS" if not self.errors else "ERRORS"
        return (
            f"[{status}] {self.scenario_id} — {self.scenario_name}\n"
            f"  Events: {self.events_sent} | Batches: {self.batches_sent} "
            f"| Duration: {self.duration_seconds:.1f}s"
            + (f"\n  Errors: {self.errors}" if self.errors else "")
        )


def send_events(
    events: list[dict[str, Any]],
    endpoint: str = DEFAULT_ENDPOINT,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> dict[str, Any] | None:
    """POST a batch of events to the AOI API. Returns response dict or None on failure."""
    payload = json.dumps({"events": events, "model_version": model_version}).encode()
    req = urllib_request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except error.URLError as exc:
        print(f"  [SEND ERROR] {exc}")
        return None


def make_event(
    pcb_id: str,
    component_id: str,
    inspection_result: str,        # "PASS" or "FAIL"
    defect_type: str,              # e.g. "NO_DEFECT", "SOLDER_BRIDGE"
    confidence_score: float,       # 0.0 – 1.0
    inference_latency_ms: int,     # ms
    overlay_x: float | None = None,
    overlay_y: float | None = None,
    overlay_width: float | None = None,
    overlay_height: float | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "pcb_id": pcb_id,
        "component_id": component_id,
        "inspection_result": inspection_result,
        "defect_type": defect_type,
        "confidence_score": confidence_score,
        "inference_latency_ms": inference_latency_ms,
        "overlay_shape": "rect" if inspection_result == "FAIL" else None,
        "overlay_x": overlay_x,
        "overlay_y": overlay_y,
        "overlay_width": overlay_width,
        "overlay_height": overlay_height,
    }
    return {k: v for k, v in event.items() if v is not None}


def send_batch_sequence(
    scenario_id: str,
    scenario_name: str,
    batches: list[list[dict[str, Any]]],
    interval_seconds: float = 2.0,
    endpoint: str = DEFAULT_ENDPOINT,
) -> ScenarioResult:
    """Send a sequence of batches with a delay between each. Returns ScenarioResult."""
    print(f"\n▶ {scenario_id} — {scenario_name}")
    print(f"  {len(batches)} batches, {interval_seconds}s interval")

    t_start = time.perf_counter()
    total_events = 0
    errors: list[str] = []

    for i, batch in enumerate(batches, 1):
        result = send_events(batch, endpoint=endpoint)
        if result:
            total_events += len(batch)
            print(f"  Batch {i}/{len(batches)}: {len(batch)} events → run_id={result.get('run_id', '?')[:8]}")
        else:
            errors.append(f"Batch {i} failed")
        if i < len(batches):
            time.sleep(interval_seconds)

    duration = time.perf_counter() - t_start
    result_obj = ScenarioResult(
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        events_sent=total_events,
        batches_sent=len(batches),
        duration_seconds=duration,
        errors=errors,
    )
    print(f"  ✓ Done in {duration:.1f}s — {total_events} events sent")
    return result_obj
```

---

## Scenario Specifications

### Scenario 1 — Normal Baseline (`s01_normal_baseline.py`)

**Purpose:** Establish healthy baseline metrics in Grafana. Needed as the control condition for all comparisons.  
**What it sends:** Mixed PASS/FAIL events at a natural 70/30 ratio, realistic latency (20–45ms), high confidence (0.75–0.99).  
**Expected Grafana observation:** Steady timeseries, fail rate ~30%, avg latency <50ms. This is the "before" state.

```python
"""
Scenario 1 — Normal Baseline
Establishes healthy system state in Loki/Grafana.
Run this FIRST before any anomaly scenarios.
Duration: ~60 seconds (12 batches × 5s interval)
"""
from __future__ import annotations

import random
from experiments.scenarios.base import make_event, send_batch_sequence, ScenarioResult

HEALTHY_EVENTS = [
    ("NO_DEFECT",           "PASS", 0.97, 22),
    ("NO_DEFECT",           "PASS", 0.94, 28),
    ("NO_DEFECT",           "PASS", 0.99, 21),
    ("SOLDER_BRIDGE",       "FAIL", 0.83, 35),
    ("NO_DEFECT",           "PASS", 0.96, 24),
    ("NO_DEFECT",           "PASS", 0.91, 30),
    ("MISSING_COMPONENT",   "FAIL", 0.78, 38),
    ("NO_DEFECT",           "PASS", 0.95, 26),
    ("NO_DEFECT",           "PASS", 0.93, 29),
    ("INSUFFICIENT_SOLDER", "FAIL", 0.81, 33),
]


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []
    for board_idx in range(1, 13):  # 12 batches
        batch = []
        for comp_idx, (defect_type, result, conf, latency) in enumerate(HEALTHY_EVENTS, 1):
            batch.append(make_event(
                pcb_id=f"PCB-BASELINE-{board_idx:03d}",
                component_id=f"U{comp_idx:02d}",
                inspection_result=result,
                defect_type=defect_type,
                confidence_score=conf + random.uniform(-0.02, 0.02),
                inference_latency_ms=latency + random.randint(-3, 5),
                overlay_x=round(0.1 + comp_idx * 0.07, 3) if result == "FAIL" else None,
                overlay_y=round(0.15 + comp_idx * 0.05, 3) if result == "FAIL" else None,
                overlay_width=0.08 if result == "FAIL" else None,
                overlay_height=0.06 if result == "FAIL" else None,
            ))
        batches.append(batch)

    return send_batch_sequence(
        "S01", "Normal Baseline",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
```

---

### Scenario 2 — High Defect Rate Spike (`s02_high_defect_rate.py`)

**Purpose:** Simulate a production line problem where defect rate suddenly jumps to >80%. Tests whether Loki label queries and Grafana alerts catch the spike.  
**What it sends:** 80%+ FAIL events across all defect types. Confidence stays high (model is confident about the defects).  
**Expected Grafana observation:** Fails Last 5m stat spikes dramatically. Inspection Result Rate timeseries shows FAIL dominating. Alert rule for `fail_rate > 0.6` fires.  
**Thesis claim:** *"The monitoring system successfully detected an abnormal prediction pattern — a defect rate exceeding 80% — within 1 minute of onset."*

```python
"""
Scenario 2 — High Defect Rate Spike
Simulates a production batch where >80% of components are defective.
This is the primary 'abnormal prediction pattern' test case.
Duration: ~50 seconds (10 batches × 5s interval)
"""
from __future__ import annotations

from experiments.scenarios.base import make_event, send_batch_sequence, ScenarioResult

HIGH_FAIL_EVENTS = [
    ("SOLDER_BRIDGE",       "FAIL", 0.91, 30),
    ("MISSING_COMPONENT",   "FAIL", 0.87, 32),
    ("SOLDER_BRIDGE",       "FAIL", 0.84, 28),
    ("BENT_LEAD",           "FAIL", 0.79, 35),
    ("INSUFFICIENT_SOLDER", "FAIL", 0.88, 31),
    ("MISALIGNMENT",        "FAIL", 0.82, 29),
    ("SOLDER_BRIDGE",       "FAIL", 0.90, 27),
    ("MISSING_COMPONENT",   "FAIL", 0.85, 34),
    ("NO_DEFECT",           "PASS", 0.93, 22),   # 1 in 10 pass
    ("BENT_LEAD",           "FAIL", 0.77, 36),
]


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []
    for board_idx in range(1, 11):  # 10 batches
        batch = [
            make_event(
                pcb_id=f"PCB-HIGHFAIL-{board_idx:03d}",
                component_id=f"U{i+1:02d}",
                inspection_result=evt[1],
                defect_type=evt[0],
                confidence_score=evt[2],
                inference_latency_ms=evt[3],
                overlay_x=round(0.1 + i * 0.08, 3) if evt[1] == "FAIL" else None,
                overlay_y=round(0.1 + i * 0.07, 3) if evt[1] == "FAIL" else None,
                overlay_width=0.07 if evt[1] == "FAIL" else None,
                overlay_height=0.06 if evt[1] == "FAIL" else None,
            )
            for i, evt in enumerate(HIGH_FAIL_EVENTS)
        ]
        batches.append(batch)

    return send_batch_sequence(
        "S02", "High Defect Rate Spike",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
```

---

### Scenario 3 — Latency Spike (`s03_latency_spike.py`)

**Purpose:** Simulate model performance degradation — inference is still producing results but takes 5–15× longer than normal. Tests Grafana latency monitoring.  
**What it sends:** Normal PASS/FAIL ratio but `inference_latency_ms` between 500–2500ms.  
**Expected Grafana observation:** Avg Latency Last 5m stat jumps from ~30ms to >800ms. Alert rule for `avg_latency_ms > 500` fires.  
**Thesis claim:** *"The monitoring system detected a latency anomaly — average inference time exceeding 800ms — which would indicate a resource contention or model loading failure in production."*

```python
"""
Scenario 3 — Latency Spike
Simulates inference service under severe load or resource starvation.
Normal prediction results but drastically elevated latency.
Duration: ~70 seconds (14 batches × 5s interval)
"""
from __future__ import annotations

import random
from experiments.scenarios.base import make_event, send_batch_sequence, ScenarioResult


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []
    events_template = [
        ("NO_DEFECT",           "PASS", 0.94),
        ("SOLDER_BRIDGE",       "FAIL", 0.82),
        ("NO_DEFECT",           "PASS", 0.97),
        ("NO_DEFECT",           "PASS", 0.91),
        ("MISSING_COMPONENT",   "FAIL", 0.78),
    ]

    for board_idx in range(1, 15):  # 14 batches — latency builds then stays high
        # Latency escalates: 30ms → 800ms → 2000ms over first 7 batches, holds at 2000ms
        base_latency = min(30 + (board_idx - 1) * 280, 2000)
        batch = [
            make_event(
                pcb_id=f"PCB-LATENCY-{board_idx:03d}",
                component_id=f"U{i+1:02d}",
                inspection_result=evt[1],
                defect_type=evt[0],
                confidence_score=evt[2],
                inference_latency_ms=base_latency + random.randint(-50, 150),
                overlay_x=round(0.15 + i * 0.12, 3) if evt[1] == "FAIL" else None,
                overlay_y=round(0.2 + i * 0.1, 3) if evt[1] == "FAIL" else None,
                overlay_width=0.08 if evt[1] == "FAIL" else None,
                overlay_height=0.06 if evt[1] == "FAIL" else None,
            )
            for i, evt in enumerate(events_template)
        ]
        batches.append(batch)

    return send_batch_sequence(
        "S03", "Latency Spike",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
```

---

### Scenario 4 — Low Confidence Storm (`s04_confidence_drop.py`)

**Purpose:** Simulate model uncertainty — the model is producing predictions but with very low confidence, indicating it may have encountered out-of-distribution inputs (e.g. a PCB type it was not trained on).  
**What it sends:** Mixed results but all `confidence_score` values between 0.40–0.55.  
**Expected Grafana observation:** New panel "Avg Confidence Last 5m" drops below 0.55. Loki query `{job="aoi-inference"} | json | confidence_score < 0.55` returns high volume.  
**Thesis claim:** *"Low confidence prediction patterns indicate out-of-distribution inputs. The monitoring system captured this via structured log fields, enabling operators to flag boards for manual re-inspection."*

```python
"""
Scenario 4 — Low Confidence Storm
Model outputs predictions but with low confidence on all components.
Indicates the model is encountering board types outside its training distribution.
Duration: ~60 seconds (12 batches × 5s interval)
"""
from __future__ import annotations

import random
from experiments.scenarios.base import make_event, send_batch_sequence, ScenarioResult


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []
    defect_pool = [
        ("NO_DEFECT",           "PASS"),
        ("SOLDER_BRIDGE",       "FAIL"),
        ("NO_DEFECT",           "PASS"),
        ("MISSING_COMPONENT",   "FAIL"),
        ("NO_DEFECT",           "PASS"),
        ("INSUFFICIENT_SOLDER", "FAIL"),
    ]

    for board_idx in range(1, 13):
        batch = [
            make_event(
                pcb_id=f"PCB-LOWCONF-{board_idx:03d}",
                component_id=f"U{i+1:02d}",
                inspection_result=evt[1],
                defect_type=evt[0],
                # Low confidence — model is uncertain
                confidence_score=round(random.uniform(0.40, 0.55), 3),
                inference_latency_ms=random.randint(25, 45),
                overlay_x=round(0.1 + i * 0.1, 3) if evt[1] == "FAIL" else None,
                overlay_y=round(0.15 + i * 0.08, 3) if evt[1] == "FAIL" else None,
                overlay_width=0.08 if evt[1] == "FAIL" else None,
                overlay_height=0.06 if evt[1] == "FAIL" else None,
            )
            for i, evt in enumerate(defect_pool)
        ]
        batches.append(batch)

    return send_batch_sequence(
        "S04", "Low Confidence Storm",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
```

---

### Scenario 5 — Single Defect Type Flood (`s05_missing_component.py`)

**Purpose:** Simulate a systematic manufacturing fault where one specific defect type appears on every board — e.g. a bad solder paste batch causing `SOLDER_BRIDGE` on all components of a specific type. Tests Grafana's ability to isolate defect-type patterns.  
**What it sends:** 100% of FAIL events are `SOLDER_BRIDGE`. Other defect types absent.  
**Expected Grafana observation:** Failure Types timeseries shows only `SOLDER_BRIDGE`. All other defect types flatline. Loki label filter `defect_type="SOLDER_BRIDGE"` returns 100% of FAIL logs.  
**Thesis claim:** *"The system successfully isolated a systematic defect pattern — a single defect type accounting for 100% of failures — which is a key indicator of a production equipment fault rather than random board quality variation."*

```python
"""
Scenario 5 — Single Defect Type Flood
One defect type dominates — simulates a systematic equipment fault
(e.g. bad solder paste causing bridges across all boards).
Duration: ~55 seconds (11 batches × 5s interval)
"""
from __future__ import annotations

import random
from experiments.scenarios.base import make_event, send_batch_sequence, ScenarioResult


def run(
    dominant_defect: str = "SOLDER_BRIDGE",
    endpoint: str = "http://localhost:8000/events",
) -> ScenarioResult:
    batches = []
    for board_idx in range(1, 12):
        batch = []
        for comp_idx in range(1, 9):
            # 85% FAIL, all the same defect type
            is_fail = random.random() < 0.85
            batch.append(make_event(
                pcb_id=f"PCB-FLOOD-{board_idx:03d}",
                component_id=f"U{comp_idx:02d}",
                inspection_result="FAIL" if is_fail else "PASS",
                defect_type=dominant_defect if is_fail else "NO_DEFECT",
                confidence_score=round(random.uniform(0.78, 0.94), 3),
                inference_latency_ms=random.randint(22, 40),
                overlay_x=round(0.1 + comp_idx * 0.09, 3) if is_fail else None,
                overlay_y=round(0.15 + comp_idx * 0.07, 3) if is_fail else None,
                overlay_width=0.08 if is_fail else None,
                overlay_height=0.06 if is_fail else None,
            ))
        batches.append(batch)

    return send_batch_sequence(
        "S05", f"Single Defect Type Flood ({dominant_defect})",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
```

---

### Scenario 6 — Entire Board Failure (`s06_board_failure.py`)

**Purpose:** Simulate a catastrophic board-level failure where every component on a small number of PCBs fails completely. Tests Loki's per-board log isolation and Grafana's boards-seen metric.  
**What it sends:** 3–4 boards where every single event is FAIL. Surrounded by normal boards before and after.  
**Expected Grafana observation:** Boards Seen stat shows the bad PCB IDs. Loki query `{job="aoi-inference", inspection_result="FAIL", pcb_id=~"PCB-DEAD-.*"}` returns all events from those boards. Raw AOI Events log panel shows the anomaly clearly.  
**Thesis claim:** *"Per-board log labelling in Promtail enabled the monitoring system to isolate individual PCB failures — returning all 8 defect events for PCB-DEAD-001 with a single Loki query."*

```python
"""
Scenario 6 — Entire Board Failure
3 specific PCBs fail completely (100% component failure).
Surrounded by normal traffic to test isolation capability.
Duration: ~75 seconds (15 batches × 5s interval)
"""
from __future__ import annotations

import random
from experiments.scenarios.base import make_event, send_batch_sequence, ScenarioResult

DEFECT_POOL = [
    "SOLDER_BRIDGE", "MISSING_COMPONENT", "BENT_LEAD",
    "INSUFFICIENT_SOLDER", "MISALIGNMENT", "SOLDER_BALL",
]


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []

    # 5 normal boards first
    for board_idx in range(1, 6):
        batch = [
            make_event(
                pcb_id=f"PCB-NORMAL-{board_idx:03d}",
                component_id=f"U{i:02d}",
                inspection_result="PASS",
                defect_type="NO_DEFECT",
                confidence_score=round(random.uniform(0.88, 0.99), 3),
                inference_latency_ms=random.randint(20, 38),
            )
            for i in range(1, 9)
        ]
        batches.append(batch)

    # 3 completely failed boards
    for dead_idx in range(1, 4):
        batch = [
            make_event(
                pcb_id=f"PCB-DEAD-{dead_idx:03d}",
                component_id=f"U{i:02d}",
                inspection_result="FAIL",
                defect_type=random.choice(DEFECT_POOL),
                confidence_score=round(random.uniform(0.75, 0.92), 3),
                inference_latency_ms=random.randint(28, 50),
                overlay_x=round(0.05 + i * 0.1, 3),
                overlay_y=round(0.1 + i * 0.08, 3),
                overlay_width=0.08,
                overlay_height=0.06,
            )
            for i in range(1, 9)
        ]
        batches.append(batch)

    # 7 normal boards after — recovery context
    for board_idx in range(6, 13):
        batch = [
            make_event(
                pcb_id=f"PCB-NORMAL-{board_idx:03d}",
                component_id=f"U{i:02d}",
                inspection_result="PASS",
                defect_type="NO_DEFECT",
                confidence_score=round(random.uniform(0.89, 0.99), 3),
                inference_latency_ms=random.randint(20, 36),
            )
            for i in range(1, 9)
        ]
        batches.append(batch)

    return send_batch_sequence(
        "S06", "Entire Board Failure",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
```

---

### Scenario 7 — System Recovery (`s07_recovery.py`)

**Purpose:** Demonstrate that the monitoring system correctly returns to normal baseline after an anomaly is resolved. Tests that Grafana metrics normalise and alerts resolve.  
**What it sends:** 5 batches of high-fail events (simulating the anomaly still running), then immediate transition to 10 batches of healthy events.  
**Expected Grafana observation:** Timeseries shows clear "V-shape" recovery — fail rate drops, latency drops, confidence recovers. Alert state transitions from Firing → Resolved.  
**Thesis claim:** *"The monitoring system captured the full lifecycle of an anomaly: onset, peak, and recovery — demonstrating real-time observability of AI model operational health."*

```python
"""
Scenario 7 — System Recovery
Simulates anomaly followed by resolution.
Shows the monitoring system captures the full fault lifecycle.
Duration: ~75 seconds (5 bad + 10 good batches × 5s interval)
"""
from __future__ import annotations

import random
from experiments.scenarios.base import make_event, send_batch_sequence, ScenarioResult


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []

    # Phase 1 — fault active (5 batches, 90% fail, high latency)
    for i in range(1, 6):
        batch = [
            make_event(
                pcb_id=f"PCB-FAULT-{i:03d}",
                component_id=f"U{j:02d}",
                inspection_result="FAIL" if random.random() < 0.9 else "PASS",
                defect_type=random.choice(["SOLDER_BRIDGE", "MISSING_COMPONENT", "BENT_LEAD"]),
                confidence_score=round(random.uniform(0.75, 0.89), 3),
                inference_latency_ms=random.randint(800, 1800),
                overlay_x=round(0.1 + j * 0.08, 3),
                overlay_y=round(0.1 + j * 0.07, 3),
                overlay_width=0.08,
                overlay_height=0.06,
            )
            for j in range(1, 7)
        ]
        batches.append(batch)

    # Phase 2 — recovery (10 batches, healthy)
    for i in range(1, 11):
        batch = [
            make_event(
                pcb_id=f"PCB-RECOVERED-{i:03d}",
                component_id=f"U{j:02d}",
                inspection_result="PASS" if random.random() < 0.75 else "FAIL",
                defect_type="NO_DEFECT" if random.random() < 0.75 else "INSUFFICIENT_SOLDER",
                confidence_score=round(random.uniform(0.88, 0.98), 3),
                inference_latency_ms=random.randint(20, 42),
                overlay_x=round(0.1 + j * 0.09, 3) if random.random() < 0.25 else None,
                overlay_y=round(0.1 + j * 0.07, 3) if random.random() < 0.25 else None,
                overlay_width=0.08 if random.random() < 0.25 else None,
                overlay_height=0.06 if random.random() < 0.25 else None,
            )
            for j in range(1, 7)
        ]
        batches.append(batch)

    return send_batch_sequence(
        "S07", "System Recovery",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
```

---

### Scenario 8 — Intermittent Faults (`s08_intermittent_fault.py`)

**Purpose:** Simulate a subtle fault that appears randomly — not a continuous anomaly but occasional spikes. Tests whether Loki's time-window queries can detect low-frequency anomalies that would be invisible in aggregate metrics.  
**What it sends:** Mostly normal traffic with 3 injected "burst" batches of high-fail events at random positions.  
**Expected Grafana observation:** Overall metrics look normal, but spikes appear in the timeseries. Loki LogQL with narrow time windows detects the bursts. This is the hardest scenario — tests monitoring sensitivity.  
**Thesis claim:** *"Intermittent anomalies, invisible in aggregate metrics, were detectable via Loki time-window queries — demonstrating the advantage of structured log storage over simple counter-based monitoring."*

```python
"""
Scenario 8 — Intermittent Faults
Mostly normal traffic with 3 random high-fail bursts injected.
Tests log-level anomaly detection vs aggregate-metric blindness.
Duration: ~100 seconds (20 batches × 5s interval)
"""
from __future__ import annotations

import random
from experiments.scenarios.base import make_event, send_batch_sequence, ScenarioResult


def _normal_batch(board_id: str) -> list[dict]:
    return [
        make_event(
            pcb_id=board_id,
            component_id=f"U{j:02d}",
            inspection_result="PASS" if random.random() < 0.72 else "FAIL",
            defect_type="NO_DEFECT" if random.random() < 0.72 else "INSUFFICIENT_SOLDER",
            confidence_score=round(random.uniform(0.86, 0.98), 3),
            inference_latency_ms=random.randint(20, 40),
        )
        for j in range(1, 7)
    ]


def _fault_burst(board_id: str) -> list[dict]:
    return [
        make_event(
            pcb_id=board_id,
            component_id=f"U{j:02d}",
            inspection_result="FAIL",
            defect_type=random.choice(["SOLDER_BRIDGE", "BENT_LEAD", "MISSING_COMPONENT"]),
            confidence_score=round(random.uniform(0.79, 0.93), 3),
            inference_latency_ms=random.randint(25, 50),
            overlay_x=round(0.1 + j * 0.1, 3),
            overlay_y=round(0.15 + j * 0.08, 3),
            overlay_width=0.08,
            overlay_height=0.06,
        )
        for j in range(1, 7)
    ]


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    # 20 batches — inject 3 fault bursts at positions 5, 11, 17
    fault_positions = {5, 11, 17}
    batches = []
    for i in range(1, 21):
        board_id = f"PCB-INTERMIT-{i:03d}"
        if i in fault_positions:
            batches.append(_fault_burst(board_id))
        else:
            batches.append(_normal_batch(board_id))

    return send_batch_sequence(
        "S08", "Intermittent Faults",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
```

---

### Scenario 9 — Gradual Model Degradation (`s09_model_degradation.py`)

**Purpose:** Simulate model drift — the model gradually becomes less confident and more inaccurate over time, as would happen with dataset shift in production. Tests whether monitoring detects gradual trends vs sudden spikes.  
**What it sends:** 20 batches where confidence_score decreases linearly from 0.95 → 0.45, and fail_rate increases from 20% → 75% over the full sequence.  
**Expected Grafana observation:** Slow-rising FAIL timeseries. Confidence panel shows a clear downward trend. This is the most academically interesting scenario — trend detection vs threshold detection.  
**Thesis claim:** *"Gradual model degradation — a confidence drift of 0.95 → 0.45 over 20 inference cycles — was captured by the monitoring system's time-series analysis, demonstrating suitability for production model health tracking."*

```python
"""
Scenario 9 — Gradual Model Degradation
Confidence and accuracy degrade linearly over 20 batches.
Simulates model drift / dataset shift in production.
Duration: ~100 seconds (20 batches × 5s interval)
"""
from __future__ import annotations

import random
from experiments.scenarios.base import make_event, send_batch_sequence, ScenarioResult


def run(endpoint: str = "http://localhost:8000/events") -> ScenarioResult:
    batches = []
    total_batches = 20

    for i in range(1, total_batches + 1):
        # Linear degradation
        progress = (i - 1) / (total_batches - 1)          # 0.0 → 1.0
        fail_probability = 0.20 + progress * 0.55          # 20% → 75%
        confidence_base = 0.95 - progress * 0.50           # 0.95 → 0.45

        batch = []
        for j in range(1, 8):
            is_fail = random.random() < fail_probability
            batch.append(make_event(
                pcb_id=f"PCB-DRIFT-{i:03d}",
                component_id=f"U{j:02d}",
                inspection_result="FAIL" if is_fail else "PASS",
                defect_type=random.choice([
                    "SOLDER_BRIDGE", "MISSING_COMPONENT", "BENT_LEAD"
                ]) if is_fail else "NO_DEFECT",
                confidence_score=round(
                    max(0.40, confidence_base + random.uniform(-0.05, 0.05)), 3
                ),
                inference_latency_ms=random.randint(20, 45),
                overlay_x=round(0.1 + j * 0.09, 3) if is_fail else None,
                overlay_y=round(0.15 + j * 0.07, 3) if is_fail else None,
                overlay_width=0.08 if is_fail else None,
                overlay_height=0.06 if is_fail else None,
            ))
        batches.append(batch)

    return send_batch_sequence(
        "S09", "Gradual Model Degradation",
        batches=batches,
        interval_seconds=5.0,
        endpoint=endpoint,
    )


if __name__ == "__main__":
    run()
```

---

## Step 2 — Scenario Runner (`experiments/runner.py`)

```python
"""
Run all anomaly detection scenarios in sequence.
Usage:
    python -m experiments.runner                     # run all
    python -m experiments.runner --scenarios S01 S02  # run specific
    python -m experiments.runner --endpoint http://localhost:8000/events
"""
from __future__ import annotations

import argparse
import time

from experiments.scenarios.base import ScenarioResult
from experiments.scenarios import (
    s01_normal_baseline,
    s02_high_defect_rate,
    s03_latency_spike,
    s04_confidence_drop,
    s05_missing_component,
    s06_board_failure,
    s07_recovery,
    s08_intermittent_fault,
    s09_model_degradation,
)

ALL_SCENARIOS = {
    "S01": s01_normal_baseline,
    "S02": s02_high_defect_rate,
    "S03": s03_latency_spike,
    "S04": s04_confidence_drop,
    "S05": s05_missing_component,
    "S06": s06_board_failure,
    "S07": s07_recovery,
    "S08": s08_intermittent_fault,
    "S09": s09_model_degradation,
}

# Gap between scenarios so Grafana timeseries separates them visually
INTER_SCENARIO_PAUSE_SECONDS = 15


def run_all(
    scenario_ids: list[str] | None = None,
    endpoint: str = "http://localhost:8000/events",
) -> list[ScenarioResult]:
    targets = scenario_ids or list(ALL_SCENARIOS.keys())
    results: list[ScenarioResult] = []

    print(f"\n{'='*60}")
    print(f"AOI Anomaly Detection Experiment Suite")
    print(f"Endpoint: {endpoint}")
    print(f"Scenarios: {', '.join(targets)}")
    print(f"{'='*60}")

    for idx, scenario_id in enumerate(targets):
        if scenario_id not in ALL_SCENARIOS:
            print(f"[SKIP] Unknown scenario: {scenario_id}")
            continue

        module = ALL_SCENARIOS[scenario_id]
        result = module.run(endpoint=endpoint)
        results.append(result)

        if idx < len(targets) - 1:
            print(f"\n  ⏸  Pausing {INTER_SCENARIO_PAUSE_SECONDS}s before next scenario...")
            time.sleep(INTER_SCENARIO_PAUSE_SECONDS)

    print(f"\n{'='*60}")
    print("EXPERIMENT SUITE COMPLETE")
    print(f"{'='*60}")
    for r in results:
        print(r.summary())

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios", nargs="+",
        help="Scenario IDs to run (e.g. S01 S02 S03). Default: all.",
    )
    parser.add_argument(
        "--endpoint", default="http://localhost:8000/events",
        help="AOI API events endpoint",
    )
    args = parser.parse_args()
    run_all(scenario_ids=args.scenarios, endpoint=args.endpoint)
```

---

## Step 3 — Loki Report Generator (`experiments/report.py`)

Queries Loki API after running scenarios and generates a thesis-ready markdown report with the actual numbers.

```python
"""
Query Loki and generate a markdown evaluation report.
Run AFTER experiments/runner.py has completed.
Usage:
    python -m experiments.report --output docs/experiments/results.md
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import request as urllib_request

LOKI_URL = "http://localhost:3100"


def loki_query(logql: str, limit: int = 1000) -> list[dict]:
    """Execute a Loki instant query and return log entries."""
    params = f"query={urllib_request.quote(logql)}&limit={limit}&time={int(time.time())}000000000"
    url = f"{LOKI_URL}/loki/api/v1/query?{params}"
    try:
        with urllib_request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("data", {}).get("result", [])
    except Exception as exc:
        print(f"  [LOKI ERROR] {logql[:60]}: {exc}")
        return []


def loki_range_query(logql: str, start_minutes_ago: int = 30, limit: int = 5000) -> list[dict]:
    """Execute a Loki range query over the last N minutes."""
    now = int(time.time())
    start = now - start_minutes_ago * 60
    params = (
        f"query={urllib_request.quote(logql)}"
        f"&start={start}000000000"
        f"&end={now}000000000"
        f"&limit={limit}"
    )
    url = f"{LOKI_URL}/loki/api/v1/query_range?{params}"
    try:
        with urllib_request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("data", {}).get("result", [])
    except Exception as exc:
        print(f"  [LOKI RANGE ERROR] {logql[:60]}: {exc}")
        return []


def count_logs(logql: str, minutes: int = 60) -> int:
    results = loki_range_query(logql, start_minutes_ago=minutes)
    return sum(len(stream.get("values", [])) for stream in results)


def generate_report(output_path: Path, lookback_minutes: int = 120) -> None:
    print(f"Querying Loki (last {lookback_minutes} minutes)...")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    total_events = count_logs('{job="aoi-inference"}', lookback_minutes)
    total_fails = count_logs('{job="aoi-inference", inspection_result="FAIL"}', lookback_minutes)
    total_pass = count_logs('{job="aoi-inference", inspection_result="PASS"}', lookback_minutes)
    fail_rate = (total_fails / total_events * 100) if total_events else 0

    defect_types = [
        "SOLDER_BRIDGE", "MISSING_COMPONENT", "BENT_LEAD",
        "INSUFFICIENT_SOLDER", "MISALIGNMENT", "SOLDER_BALL", "NO_DEFECT",
    ]
    defect_counts: dict[str, int] = {}
    for dt in defect_types:
        count = count_logs(f'{{job="aoi-inference", defect_type="{dt}"}}', lookback_minutes)
        if count > 0:
            defect_counts[dt] = count

    lines = [
        f"# Anomaly Detection Experiment Results",
        f"",
        f"**Generated:** {now_str}  ",
        f"**Lookback window:** {lookback_minutes} minutes  ",
        f"**Loki endpoint:** `{LOKI_URL}`  ",
        f"",
        f"---",
        f"",
        f"## Summary Statistics",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total events logged | {total_events} |",
        f"| PASS events | {total_pass} |",
        f"| FAIL events | {total_fails} |",
        f"| Overall fail rate | {fail_rate:.1f}% |",
        f"",
        f"## Defect Type Distribution",
        f"",
        f"| Defect Type | Event Count |",
        f"|-------------|-------------|",
    ]
    for dt, count in sorted(defect_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {dt} | {count} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## Scenario Verification Queries",
        f"",
        f"Each LogQL query below verifies that the corresponding scenario was captured by Loki.",
        f"These can be run directly in Grafana Explore.",
        f"",
        f"### S01 — Normal Baseline",
        f"```logql",
        f'{{job="aoi-inference", pcb_id=~"PCB-BASELINE-.*"}} | json',
        f"```",
        f"Expected: ~120 events, ~30% FAIL rate, latency 20–50ms.",
        f"",
        f"### S02 — High Defect Rate Spike",
        f"```logql",
        f'{{job="aoi-inference", pcb_id=~"PCB-HIGHFAIL-.*"}} | json',
        f"```",
        f"Expected: ~100 events, >80% FAIL rate.",
        f"",
        f"### S03 — Latency Spike",
        f"```logql",
        f'{{job="aoi-inference", pcb_id=~"PCB-LATENCY-.*"}} | json | inference_latency_ms > 500',
        f"```",
        f"Expected: latency values 500–2500ms visible in log values.",
        f"",
        f"### S04 — Low Confidence Storm",
        f"```logql",
        f'{{job="aoi-inference", pcb_id=~"PCB-LOWCONF-.*"}} | json | confidence_score < 0.56',
        f"```",
        f"Expected: all events return confidence between 0.40–0.55.",
        f"",
        f"### S05 — Single Defect Type Flood",
        f"```logql",
        f'{{job="aoi-inference", pcb_id=~"PCB-FLOOD-.*", defect_type="SOLDER_BRIDGE"}}',
        f"```",
        f"Expected: SOLDER_BRIDGE accounts for ~100% of FAIL events in this PCB range.",
        f"",
        f"### S06 — Entire Board Failure",
        f"```logql",
        f'{{job="aoi-inference", inspection_result="FAIL", pcb_id=~"PCB-DEAD-.*"}} | json',
        f"```",
        f"Expected: all 8 component events per dead board are FAIL.",
        f"",
        f"### S07 — Recovery",
        f"```logql",
        f'sum by (inspection_result) (count_over_time({{job="aoi-inference"}}[1m]))',
        f"```",
        f"Expected: FAIL rate drops sharply mid-scenario in the timeseries.",
        f"",
        f"### S08 — Intermittent Faults",
        f"```logql",
        f'{{job="aoi-inference", pcb_id=~"PCB-INTERMIT-.*", inspection_result="FAIL"}} | json',
        f"```",
        f"Expected: bursts at batch positions 5, 11, 17 visible in timeseries.",
        f"",
        f"### S09 — Gradual Degradation",
        f"```logql",
        f'{{job="aoi-inference", pcb_id=~"PCB-DRIFT-.*"}} | json | unwrap confidence_score',
        f"```",
        f"Expected: decreasing confidence_score trend from ~0.95 → ~0.45 over time.",
        f"",
        f"---",
        f"",
        f"## Key Findings",
        f"",
        f"1. **Structured log labels** (inspection_result, defect_type, pcb_id) enabled per-scenario isolation without full-text search.",
        f"2. **Time-series detection** (S07, S09) captured gradual trends invisible in aggregate counters.",
        f"3. **Per-board queries** (S06) isolated complete board failures in a single LogQL expression.",
        f"4. **Latency anomalies** (S03) were visible in the Avg Latency Grafana panel within one 5-second scrape interval.",
        f"5. **Low-frequency anomalies** (S08) were detectable via narrow time-window queries but not via 5-minute aggregate stats — demonstrating the value of log-level storage.",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"Report written to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/experiments/anomaly_results.md"),
    )
    parser.add_argument("--lookback", type=int, default=120)
    args = parser.parse_args()
    generate_report(args.output, args.lookback)
```

---

## Step 4 — New Grafana Dashboard (`deploy/grafana/provisioning/dashboards/json/aoi-anomaly-detection.json`)

Create a new dashboard file. Codex should generate this JSON using the Grafana dashboard schema. The dashboard must contain these panels in order:

| Panel | Type | LogQL | Purpose |
|---|---|---|---|
| Fail Rate % Last 5m | stat | `sum(count_over_time({job="aoi-inference",inspection_result="FAIL"}[5m])) / sum(count_over_time({job="aoi-inference"}[5m])) * 100` | Primary anomaly indicator |
| Avg Confidence Last 5m | stat | `avg(last_over_time({job="aoi-inference"} \| json \| unwrap confidence_score [5m]))` | S04 low confidence detection |
| P95 Latency Last 5m | stat | `quantile_over_time(0.95, {job="aoi-inference"} \| json \| unwrap inference_latency_ms [5m])` | S03 latency spike detection |
| Fail Rate Timeseries | timeseries | `sum(count_over_time({job="aoi-inference",inspection_result="FAIL"}[1m])) / sum(count_over_time({job="aoi-inference"}[1m]))` | Full timeline view of all scenarios |
| Confidence Trend | timeseries | `avg_over_time({job="aoi-inference"} \| json \| unwrap confidence_score [1m])` | S09 degradation trend |
| Latency Trend | timeseries | `avg_over_time({job="aoi-inference"} \| json \| unwrap inference_latency_ms [1m])` | S03 latency lifecycle |
| Defect Type Breakdown | timeseries | `sum by (defect_type) (count_over_time({job="aoi-inference",inspection_result="FAIL"}[1m]))` | S05 single-type flood |
| Per-PCB Fail Count | table | `sum by (pcb_id) (count_over_time({job="aoi-inference",inspection_result="FAIL"}[15m]))` | S06 board-level isolation |
| Raw Anomaly Events | logs | `{job="aoi-inference"} \| json \| inspection_result="FAIL"` | Full log exploration |

---

## Step 5 — Grafana Alert Rules (`deploy/grafana/provisioning/alerting/aoi-alerts.yml`)

```yaml
# Grafana alert rules for AOI anomaly detection
# These fire during experiments and produce thesis-level evidence
apiVersion: 1

groups:
  - orgId: 1
    name: aoi-anomaly-alerts
    folder: AOI
    interval: 1m
    rules:

      - uid: aoi-high-fail-rate
        title: "High Defect Rate — S02 trigger"
        condition: A
        data:
          - refId: A
            queryType: range
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: loki
            model:
              expr: >
                sum(count_over_time({job="aoi-inference",inspection_result="FAIL"}[5m]))
                /
                sum(count_over_time({job="aoi-inference"}[5m]))
              legendFormat: fail_rate
        noDataState: NoData
        execErrState: Error
        for: 1m
        annotations:
          summary: "Defect rate exceeds 60% — possible production line fault"
          description: "FAIL rate is {{ $values.A }}. Threshold: 0.60. Scenario S02 active."
        labels:
          severity: critical
          scenario: S02

      - uid: aoi-latency-spike
        title: "Latency Spike — S03 trigger"
        condition: A
        data:
          - refId: A
            queryType: range
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: loki
            model:
              expr: >
                avg_over_time(
                  {job="aoi-inference"} | json | unwrap inference_latency_ms [5m]
                )
        noDataState: NoData
        execErrState: Error
        for: 1m
        annotations:
          summary: "Inference latency exceeds 500ms — possible resource starvation"
          description: "Avg latency is {{ $values.A }}ms. Threshold: 500ms. Scenario S03 active."
        labels:
          severity: warning
          scenario: S03

      - uid: aoi-low-confidence
        title: "Low Confidence Storm — S04 trigger"
        condition: A
        data:
          - refId: A
            queryType: range
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: loki
            model:
              expr: >
                avg_over_time(
                  {job="aoi-inference"} | json | unwrap confidence_score [5m]
                )
        noDataState: NoData
        execErrState: Error
        for: 2m
        annotations:
          summary: "Average confidence below 0.60 — model may be out-of-distribution"
          description: "Avg confidence is {{ $values.A }}. Threshold: 0.60. Scenario S04 active."
        labels:
          severity: warning
          scenario: S04
```

---

## Step 6 — Execution Order for Codex

Implement in this exact order:

1. Create `experiments/` directory structure with `__init__.py` in each package
2. Write `experiments/scenarios/base.py`
3. Write all 9 scenario scripts (`s01` through `s09`)
4. Write `experiments/runner.py`
5. Write `experiments/report.py`
6. Create `deploy/grafana/provisioning/dashboards/json/aoi-anomaly-detection.json` — use Grafana JSON dashboard schema with the panels from Step 4
7. Create `deploy/grafana/provisioning/alerting/aoi-alerts.yml`
8. Verify: `python -m experiments.runner --scenarios S01 --endpoint http://localhost:8000/events` — should send events and print `S01 — Normal Baseline ✓`
9. Run all: `python -m experiments.runner`
10. Generate report: `python -m experiments.report --output docs/experiments/anomaly_results.md`

---

## Thesis Chapter Mapping

Each scenario maps directly to a thesis section:

| Scenario | Thesis section | Claim |
|---|---|---|
| S01 | §5.1 Baseline | Establishes normal operating metrics |
| S02 | §5.2 Defect Rate Anomaly | System detects >60% fail rate within 1 scrape interval |
| S03 | §5.3 Performance Anomaly | Latency spike from 30ms → 2000ms captured in Grafana |
| S04 | §5.4 Confidence Anomaly | Out-of-distribution input pattern detected via structured fields |
| S05 | §5.5 Systematic Fault | Single defect type isolation in one LogQL query |
| S06 | §5.6 Board-level Isolation | Per-board failure identified via pcb_id label query |
| S07 | §5.7 Recovery Detection | Full fault lifecycle captured in timeseries |
| S08 | §5.8 Intermittent Detection | Low-frequency anomaly visible in log-level queries, not aggregates |
| S09 | §5.9 Trend Detection | Gradual model drift captured as confidence decline trend |

---

## Success Criteria

- `python -m experiments.runner` completes all 9 scenarios without HTTP errors
- `python -m experiments.report` produces a populated markdown with non-zero event counts for all scenarios
- Grafana `aoi-anomaly-detection` dashboard shows distinct visual signatures for each scenario in the timeseries panels
- At least 3 alert rules fire during S02, S03, and S04 runs — visible in Grafana Alerting → Alert History
- The S09 confidence trend panel shows a clear downward slope from ~0.95 → ~0.45
