# Defense Day — Live Demo Plan

> **Thesis claim being demonstrated:** *When an AI inference service starts behaving
> abnormally in production, the Loki-stack logging/monitoring layer surfaces it on a
> dashboard and fires alerts.* Everything below exists to make that one sentence
> undeniable in front of the committee.

**Assumed slot:** ~15–20 min demo inside the defense. Each segment is modular — cut
Segment 5/6 first if you run short, expand the live-alert moment if you have time.

---

## 0. The single most important decision: don't run all 9 scenarios live

The full suite (`python -m experiments.runner`) is **~13 minutes** (9 scenarios ×
batches + 15 s gaps). That is far too long to watch in silence during a defense, and
alert `for:` windows add another 1–2 min. So the demo is **hybrid**:

- **Pre-run the full suite** before you walk in. That data becomes (a) the "thorough
  evaluation" material and (b) your fallback if anything breaks live.
- **Run a short 2–3 scenario subset live** (`S01 S02 S03`, ~3–4 min) as a background
  task while you talk through the frontend, so by the time you reach Grafana the alert
  is transitioning to **Firing** in real time. That live alert is the money shot.

The demo must **not depend on the live run succeeding** — the pre-run data is already
loaded in Loki/Grafana and can carry the entire story alone.

---

## 1. Pre-flight checklist (T-1 day, then again T-30 min)

**The night before / morning of:**
- [ ] `docker compose up -d --build` — confirm all 6 services up: `aoi-app`, `aoi-web`,
      `loki`, `promtail`, `grafana`, `aoi-mock-sender`.
- [ ] `curl http://localhost:8000/health` → 200.
- [ ] Run the **full suite once** to seed Loki and regenerate fresh evidence:
      `python -m experiments.runner` then
      `python -m experiments.report --output docs/experiments/anomaly_results.md`.
- [ ] Confirm the regenerated `docs/experiments/anomaly_results.md` has real query
      numbers (not empty / Loki errors).
- [ ] **Record a screen-capture video** of one clean full run end-to-end — ultimate fallback.
- [ ] Pre-seed the frontend with a good review run: one PCB scan uploaded, defects
      present, so the operator walkthrough has something rich to show.

**T-30 min (de-risk the room):**
- [ ] All 6 containers healthy again; do one throwaway `runner --scenarios S01` to confirm
      events flow end-to-end (frontend → POST /events → JSONL → Promtail → Loki → Grafana).
- [ ] Browser tabs pre-opened **in demo order**:
      1. Frontend `http://localhost:5173`
      2. Grafana dashboard `http://localhost:3000` (AOI Anomaly Detection) — already
         logged in (`admin`/`admin`), time range set to **Last 15 minutes**, auto-refresh **10s**.
      3. Grafana → Alerting → Alert rules.
      4. `docs/experiments/anomaly_results.md` rendered.
      5. (Fallback) `assets/readme/anomaly/` screenshots folder.
- [ ] Terminal ready with the live-run command typed but **not** entered, font size bumped.
- [ ] Disable OS notifications, screen sleep, Slack/email. Plug in power. Test the projector
      resolution — Grafana panels must be readable from the back row.
- [ ] Everything is **localhost only** — no network dependency. Say this out loud; it
      pre-empts "what if the wifi drops" anxiety.

---

## 2. Run-of-show (timing budget)

| # | Segment | Time | What's on screen | Backing asset |
|---|---------|------|------------------|---------------|
| 1 | Kick off live scenarios | 0:30 | Terminal — start `S01 S02 S03` | `experiments/runner.py` |
| 2 | Frontend / operator view | 4:00 | Review workstation | running app + seeded run |
| 3 | Grafana dashboard (live data) | 4:00 | AOI Anomaly Detection dashboard | live + pre-run data |
| 4 | **Alerts fire (live)** | 2:00 | Grafana Alerting — Pending→Firing | `aoi-alerts.yml` |
| 5 | Thorough evaluation (all 9) | 4:00 | Scenario→thesis map + Loki report | `anomaly_results.md`, screenshots |
| 6 | Reproducibility flourish | 1:00 | Regenerate report from Loki live | `experiments/report.py` |
|   | **Buffer / Q&A handoff** | ~2:00 | — | — |

---

## 3. Segment scripts (what to say + click)

### Segment 1 — Start the live run (30 s, do this FIRST)
Run it before the frontend tour so data accumulates and the alert `for:` window counts
down while you talk:
```bash
python -m experiments.runner --scenarios S01 S02 S03
```
> "I'm kicking off three anomaly scenarios now — a healthy baseline, a defect-rate
> spike, and a latency spike. They inject events into the live `POST /events` pipeline.
> Let's look at the operator's side while that runs in the background."

### Segment 2 — Frontend, the operator's world (4 min)
This is where inference events are *born*. Walk the operator flow:
1. **Run history rail** (left) → select a run.
2. **PCB viewer** — component overlays + defect overlays on the scan.
3. Click a **FAIL defect** → **Defect Inspector** (bottom-right): component ID, defect
   type, severity, **confidence score**, **inference latency (ms)**.
4. **Defect sidebar** — per-defect confidence + latency side by side.
5. **Zen Mode** — collapse rails, dim non-selected overlays, press `P`/`F` to confirm and
   auto-advance. Show the keyboard-shortcuts overlay (`?`).
6. **Topbar** live stats: runs, fail count, events.

> Key line: "Every one of these reviews emits a structured inference event —
> `pcb_id`, `component_id`, result, `defect_type`, `confidence_score`,
> `inference_latency_ms`. Those exact fields are what the monitoring stack consumes.
> The frontend produces the signal; now let's watch the stack catch it going wrong."

### Segment 3 — Grafana dashboard (4 min)
Switch to the **AOI Anomaly Detection** dashboard.
- **Three stat tiles** — fail rate %, avg confidence, P95 latency — should now be tinted
  red from the live S02/S03 data.
- **Trend panels** — Fail-Rate, Confidence, Latency, and Defect-Type Breakdown. Point at
  the S03 latency curve climbing ~250ms → 2000ms.
- Open one panel's query to show it's real LogQL, not a mock:
  `avg(avg_over_time({pcb_id=~"PCB-LATENCY-.*"} | json | unwrap inference_latency_ms [30s]))`.

> "A single screen answers *'is something wrong right now?'* before anyone reads a log
> line. Stat tiles answer the binary; the trends answer *'since when, getting better or
> worse?'*"

### Segment 4 — Alerts fire (2 min) — THE CORE CLAIM
Go to **Alerting → Alert rules**. Three provisioned rules: fail rate > 0.6, avg latency
> 500 ms, avg confidence < 0.6. With S02/S03 running, watch **high-defect-rate** and
**latency** transition **Pending → Firing**.

> "Dashboards are pull-based — someone has to be looking. Alerts are push-based; this is
> what turns *observability* into *monitoring*. Proving these rules reach **Firing**
> under a real anomaly is the central claim of the thesis — and there it is, live."

### Segment 5 — Thorough evaluation, all 9 scenarios (4 min)
Now broaden from the 3 live ones to the full evaluation using the **pre-run** data
(too long to run all live). Walk the scenario→thesis mapping:

| Scenario | Anomaly class | Detection mechanism | Result |
|---|---|---|---|
| S01 | Healthy baseline | label counts | control ~70/30 PASS/FAIL |
| S02 | Defect-rate spike | `fail_rate > 0.6` alert | >80% fail, **alert fired** |
| S03 | Latency spike | `avg_latency > 500ms` alert | 250→2000 ms, **alert fired** |
| S04 | Confidence collapse | `avg_confidence < 0.6` alert | pinned 0.47–0.50 |
| S05 | Systematic single fault | `defect_type` label filter | 100% `SOLDER_BRIDGE` |
| S06 | Board-level failure | `pcb_id` label filter | 3 boards × 8/8 fails |
| S07 | Fault → recovery | timeseries lifecycle | V-shaped recovery |
| S08 | Intermittent burst | narrow-window LogQL | isolated bursts |
| S09 | Gradual drift | trend over time | confidence 0.95 → 0.42 |

- Open `docs/experiments/anomaly_results.md` — emphasise it is **machine-generated from
  Loki**, every number is a query result, fully reproducible.
- Each scenario isolates its data by `pcb_id` prefix, so one Grafana time-range or the
  per-scenario screenshots show exactly one anomaly pattern with no cross-contamination.
- Call out the two academically interesting ones: **S08 intermittent** (why log-level
  storage beats counters — bursts that average out to "normal") and **S09 gradual drift**
  (catching a *trend*, not a threshold breach — production model-rot detection).

### Segment 6 — Reproducibility flourish (1 min, optional)
```bash
python -m experiments.report --output docs/experiments/anomaly_results.md
```
> "The evaluation isn't hand-written — it regenerates from live Loki right now. Runner →
> Loki → report is fully scripted and reproducible."

---

## 4. Contingency matrix (rehearse the fallbacks)

| If this breaks… | Fall back to | Pre-staged where |
|---|---|---|
| Live scenario run hangs/slow | Pre-run data already in Grafana — set time range to the pre-run window | dashboard time picker |
| Grafana/Loki won't come up | Static screenshots of every panel + alert state | `assets/readme/anomaly/`, `docs/pics/anomaly-screenshots/` |
| Frontend won't start | README review-workspace screenshots | `assets/readme/*.png` |
| Whole Docker stack dead | The recorded end-to-end video | (record during prep) |
| A LogQL panel returns empty | Show the committed report instead | `docs/experiments/anomaly_results.md` |

Golden rule: **never debug live in front of the committee.** If something is off, narrate
over the pre-staged asset and move on.

---

## 5. Anticipated committee questions

- **Why Loki, not Prometheus?** Logs vs metrics — Loki keeps log-level records with
  high-cardinality labels (`pcb_id`, `component_id`) so you can answer *"which physical
  board?"* (S06) and catch intermittent bursts (S08) that a pre-aggregated counter
  averages away.
- **Label cardinality explosion?** Labels are bounded (result, defect_type, pcb_id
  prefix); the high-cardinality detail lives in the log line and is parsed at query time
  with `| json | unwrap`, not as labels.
- **Mock inference & low mAP (0.13) — does that undermine the thesis?** No. The monitoring
  claim is orthogonal to model quality. Events are structured identically regardless of
  source; the mock sender is precisely what lets you inject *controlled, repeatable*
  anomalies to prove detection. Real-model integration is supporting future work.
- **How were the alert thresholds chosen?** Relative to the S01 baseline (the control),
  with `for:` debounce windows (1–2 min) to avoid flapping on single scrapes.
- **False positives / does S01 ever alert?** S01 baseline stays under threshold — that's
  why it's the control; show it never trips a rule.
- **Production-readiness / scale?** Honest boundary: this validates the detection
  pipeline end-to-end on a single-node stack; horizontal Loki + real inference backend is
  named future work.

---

## 6. Command appendix

```bash
# Bring up full stack
docker compose up -d --build
curl http://localhost:8000/health

# Live demo subset (run during Segment 1)
python -m experiments.runner --scenarios S01 S02 S03

# Full suite (run during PREP, ~13 min)
python -m experiments.runner

# Regenerate Loki-backed evaluation report
python -m experiments.report --output docs/experiments/anomaly_results.md

# Frontend (if not via compose)
cd web && npm run dev          # http://localhost:5173
```

Service URLs: API `:8000` · Frontend `:5173` · Grafana `:3000` (admin/admin) · Loki `:3100`
