# BCOM-C Dashboard

**Bob-AI Command & Control — v0.1**

Operator dashboard for the Bob-AI Pipeline / Data Jet system. Monitors live telemetry from the DGX Spark and Linux desktop nodes, and provides system controls for model management.

---

## Structure

```
BCOM-C-Dashboard/
├── index.html              # Main dashboard (SPARK-BOB + LINUX-DSKTP panels)
├── assets/
│   ├── css/bcom.css        # Shared styles — color variables, gauges, layout
│   └── js/bcom.js          # Shared JS — polling engine, gauge/temp renderers, clock
└── pages/
    ├── data-gen.html       # Synthetic data pipeline controls (standby)
    ├── pipeline.html       # Ingest / transform / inference routing (standby)
    ├── resources.html      # Model registry, storage, compute allocation (standby)
    └── reports.html        # Run logs, performance history, export (standby)
```

---

## Dashboard Panels

**SPARK-BOB** — DGX Spark node
- CPU load gauge
- GPU load gauge
- VRAM used gauge
- CPU temperature bar (safe < 70°C / warn 70–90°C / danger > 90°C)
- Metrics: VRAM GB, GPU temp, uptime

**LINUX-DSKTP** — Linux desktop node
- CPU load gauge
- GPU load gauge
- CPU temperature bar (safe < 70°C / warn 70–85°C / danger > 85°C)
- Metrics: RAM GB, uptime

---

## Action Bar

| Button | Function |
|---|---|
| RESTART VLLM | Restart vLLM inference server |
| RESTART LLM | Restart base LLM process |
| DOWNLOAD MODEL | Pull model from registry |
| ASK ADVISOR | Query the AI advisor module |

---

## Connecting a Live Data Source

The polling engine is built and ready. To activate live telemetry:

1. Open `index.html`
2. Uncomment and set the API base URL:
   ```js
   BCOM.apiBase = 'http://YOUR_SERVER:PORT';
   ```
3. The dashboard will immediately begin polling `/api/metrics` every 5 seconds.

### Expected API Response — `GET /api/metrics`

```json
{
  "spark": {
    "cpu_pct":  68,
    "gpu_pct":  74,
    "vram_pct": 55,
    "vram_gb":  "44.2 GB",
    "gpu_temp": "72°C",
    "cpu_temp": 78,
    "uptime":   "2d 14h"
  },
  "linux": {
    "cpu_pct":  42,
    "gpu_pct":  31,
    "cpu_temp": 65,
    "ram_gb":   "28.1 GB",
    "uptime":   "5d 3h"
  }
}
```

All fields are optional — missing keys render as `--` without errors.

### Poll behavior

- Polls every 5 seconds (configurable via `BCOM.pollInterval`)
- Logs "Live telemetry active" on first successful connection
- On disconnect: logs one error, suppresses duplicates until reconnected
- No API configured: silent standby — no errors, no polling

---

## Tech Stack

- Vanilla HTML / CSS / JS — no framework, no build step
- SVG circular gauges with `stroke-dasharray` animation
- CSS custom properties for theming
- `clamp()` + `aspect-ratio` for fluid responsive scaling

---

## Deployment Notes

- Designed to be containerized alongside the Bob-AI stack
- Serve as a static site (nginx, Caddy, or any static host)
- API polling uses `fetch()` with `cache: 'no-store'` — works across origins if CORS is enabled on the metrics endpoint
- SSH key for this repo is scoped to the BCOM-C deployment environment

---

*BOB-AI // BCOM-C v0.1*
