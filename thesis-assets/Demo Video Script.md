# AOI Demo Video Script (~1 minute)

**What it shows:** an operator runs a real AI inspection in the AOI workstation, and
that inference is captured, monitored, and query-able through the observability stack
(FastAPI → JSONL → Promtail → Loki → Grafana). That is the thesis claim, end to end.

**Format:** two full-screen Chrome tabs (no split-screen — the AOI workspace looks best
full-width). Tab 1 = AOI, Tab 2 = Grafana.

---

## Before you hit record (pre-flight)

Run these from the repo root (`~/projects/AOI`). Do all of this **off camera**.

1. **Start the full stack with AI enabled** (the `demo` profile adds the inference sidecar):
   ```bash
   docker compose --profile demo up -d
   ```
   Wait until healthy:
   ```bash
   curl -s localhost:8000/health && curl -s localhost:8001/health
   ```

2. **Seed the anomaly history** so Grafana already tells a story (baseline → spike →
   latency → recovery). ~5 minutes; let it finish before recording:
   ```bash
   ./venv/bin/python -m experiments.runner --scenarios S01 S02 S03 S07
   ```
   (Or `python -m experiments.runner` for all 9 — richer dashboard, ~8–10 min.)

   > ⚠️ Loki has **no persistence volume**, so its data is wiped if the container
   > restarts. Seed **right before** recording and don't `restart`/`down` Loki after.

3. **Warm up the model** so the on-camera click is instant (the *first* inference loads
   the weights and is slow — you don't want that lag on video). Do one throwaway
   inspection through the UI now, or:
   ```bash
   # create a run, upload a board, inspect — then delete it in the UI
   ```
   Board images to use: `ml/data/dspcbsd_plus/test/images/` (the model's home turf).

4. **Pre-stage the AOI run** you'll film: in Tab 1 (http://localhost:5173) create a run,
   upload a board, enter a model name, **Continue To Review** — so on camera your very
   first click is **Run Inspection**.

5. **Set up Tab 2** (Grafana, http://localhost:3000, `admin` / `admin`): open the
   **AOI Anomaly Detection** dashboard, set the time range to **Last 15 minutes**,
   refresh **5s**. Leave it on this tab.

---

## The 60-second script (shot list)

| Time | Tab | You do | You say |
|---|---|---|---|
| **0–20s** | **AOI** | Click **Run Inspection**. Defect boxes appear. Hover a defect to open the inspector. | "This is the AOI review workstation. I upload a board, and when I run an inspection the trained model runs on the scan — here it's flagged a defect, with its type, confidence, and inference latency." |
| **20–35s** | **Grafana › Anomaly Detection** | Switch tabs. Point at the fail-rate spike + recovery on the timeseries, then the latency panel. | "Every inference is logged and shipped to Grafana in real time. Here's an elevated fail-rate episode and its recovery, alongside inference latency — this is monitoring the AI's behaviour, not just the app's." |
| **35–50s** | **Grafana › (same dashboard, Logs panel)** | Scroll to the live **Logs** panel; the inspection you just ran is in the stream. | "And every event is here as structured data — including the inspection I just ran a moment ago." |
| **50–60s** | **Grafana › Explore** | Left nav → **Explore** → Loki → paste the query below → **Run query**. | "I can also interrogate it ad hoc — for example, every failed inspection across the line." |

**Exact Explore query** (verified against the live stack):
```logql
{job="aoi-inference"} | json | inspection_result="FAIL"
```
Handy variants:
```logql
{job="aoi-inference"} | json | defect_type="MOUSE_BITE"
{job="aoi-inference"} | json | line_format "{{.pcb_id}} {{.defect_type}} {{.confidence_score}}"
```

---

## Which ending to use

Keep it to **one** closer so you don't rush:

- Thesis emphasis on **anomaly detection** → end on the **dashboard** spike/recovery (steps
  20–35s); drop the Explore beat. *(Recommended — reads instantly on camera.)*
- Thesis emphasis on **observability / queryability** → end on **Explore** (50–60s).

---

## If something looks off

| Symptom | Cause → fix |
|---|---|
| Run Inspection shows *"inference service unavailable"* (503) | You started the lean stack. Use `docker compose --profile demo up -d`. |
| First Run Inspection is slow / laggy on camera | Model wasn't warmed up. Do one throwaway inspection off camera first (pre-flight step 3). |
| Grafana panels empty | Time range doesn't cover the seed, or Loki was restarted after seeding. Set range to *Last 15 minutes* and re-seed. |
| Explore returns nothing | Confirm the label: `{job="aoi-inference"}` (that's the Promtail job label). Re-seed if the window is stale. |

---

## URLs & credentials

| Surface | URL |
|---|---|
| AOI workstation | http://localhost:5173 |
| Grafana | http://localhost:3000 — `admin` / `admin` |
| API health | http://localhost:8000/health |
| Inference sidecar health | http://localhost:8001/health |
