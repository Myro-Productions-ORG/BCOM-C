# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

BCOM-C (Bob-AI Command & Control) is a vanilla HTML/CSS/JS operator dashboard for monitoring the Bob-AI pipeline running on the DGX Spark and Linux desktop nodes. No framework, no build step — edit and it's live.

**Live URL:** https://bcom.myroproductions.com

## Tech Stack

- **Frontend:** Vanilla HTML/CSS/JS — no framework, no bundler
- **Terminal:** xterm.js v5.3.0 + FitAddon (CDN-loaded)
- **Reverse proxy:** Caddy v2 (Docker) on M4 Pro, nginx in container
- **External access:** Cloudflare Tunnel → `bcom.myroproductions.com`
- **Backend API:** BobSpark-APIs (FastAPI, DGX Spark port 9010)
- **Metrics daemon:** `daemon/metrics_daemon.py` — Python, runs on DGX Spark port 8090
- **CI/CD:** GitHub Actions self-hosted runners (3 nodes in parallel on push to `main`)

## Deployment Nodes

| Machine | IP | Runner label | Repo path |
|---|---|---|---|
| DGX Spark | 10.0.0.69 | `dgx` | `/home/nmyers/Projects/BCOM-C` |
| M4 Pro (this machine) | 10.0.0.210 | `m4pro` | `/Users/myro-pro/Projects/BCOM-C` — **NOTE: wrong path, actual path is `/Volumes/DevDrive-M4Pro/Projects/BCOM-C`** |
| Linux Desktop | 10.0.0.10 | `linux-desktop` | `/home/myroproductions/Projects/BCOM-C` |

Push to `main` → GitHub Actions syncs all three nodes automatically via `git pull`.

Files on M4 Pro are served by Caddy directly from `/Volumes/DevDrive/Projects/websites/BCOM-C` (per docker-compose volume mount — may need updating).

## Structure

```
index.html                  # Main dashboard (SPARK-BOB + LINUX-DSKTP + SHELL tabs)
index_p2_additions.html     # P2 feature additions (merged into main)
pages/
  ├── orchestrator.html     # AI orchestration control
  ├── data-gen.html         # Synthetic data pipeline controls
  ├── datagen-run.html      # Individual datagen run detail
  ├── datasets.html         # Dataset registry
  ├── pipeline.html         # Ingest/transform/inference routing + finetune job status
  ├── coordinator.html      # Job coordinator
  ├── models.html           # Model registry
  ├── evals.html            # Evaluation runs
  ├── deploy.html           # Deployment controls
  ├── monitor.html          # Live monitoring
  ├── analytics.html        # Analytics charts
  ├── resources.html        # Compute/storage allocation
  ├── reports.html          # Run logs and history
  └── settings.html         # Appearance / theme editor (localStorage persistence)
assets/
  ├── css/bcom.css          # Shared styles — color vars, gauges, layout
  ├── js/bcom.js            # Shared JS — polling engine, gauge renderers, clock
  └── js/bcom-terminal.js   # xterm.js terminal — WebSocket PTY, tab wiring
daemon/
  ├── metrics_daemon.py     # Python HTTP server — collects local GPU/CPU metrics + SSH remote
  └── start.sh              # Daemon launch script
docs/adr/                   # Architecture Decision Records (ADR-001 through ADR-005)
.github/workflows/deploy.yml # Multi-node CI/CD
```

## API Endpoints

**BobSpark-APIs** (FastAPI, DGX Spark, port 9010 — proxied through Caddy as `/api/`):
- `GET /api/metrics` — GPU/CPU/VRAM telemetry for both nodes (polled every 5s)
- `GET /api/jobs/` — Live training job status (polled every 5s on pipeline.html)
- `POST /api/finetune/start` — Start a finetune job `{epochs, batch_size, lr}`
- `GET /api/finetune/` — List recent finetune jobs

**Metrics daemon** (`daemon/metrics_daemon.py`, port 8090 on DGX Spark):
```
GET /api/metrics → {"spark": {cpu_pct, gpu_pct, vram_pct, vram_gb, gpu_temp, cpu_temp, uptime}, "linux": {...}}
```
VRAM uses per-process GPU memory sum (workaround for GB10 unified memory — `nvidia-smi` reports `[N/A]` for standard VRAM query).

## Key Patterns

- **No build step** — all JS is inline or loaded via `<script src>`. Changes are immediately live after `git pull` on the server.
- **Polling engine** — `bcom.js` drives all live data via `setInterval` fetches. Missing API fields render as `--` without errors.
- **Terminal** — WebSocket PTY at `wss://bcom.myroproductions.com/api/terminal/ws`. Implemented in `bcom-terminal.js`, wired to the SHELL tab present on every page.
- **Theme/settings** — `settings.html` manages appearance via `localStorage`. Pure sync — no async/await.
- **Progress log format** — Training scripts emit `PROGRESS chunk X/Y: Z%` lines; `jobs/service.py` on BobSpark-APIs parses these for live job percentage.

## Running Locally

No build required. Serve any static file server from the repo root:

```bash
# Quick local preview
python3 -m http.server 8080

# Or via Docker (matches production nginx config)
docker compose up
# → http://localhost:3500
```

The Docker container (nginx) serves files from `/Volumes/DevDrive/Projects/websites/BCOM-C` via volume mount — update `docker-compose.yml` if your local path differs.

## ADR References

- ADR-001: Vanilla JS (no framework) — keep it that way
- ADR-002: Caddy reverse proxy
- ADR-003: Cloudflare Tunnel for HTTPS/WSS
- ADR-004: xterm.js + PTY WebSocket
- ADR-005: Self-hosted CI/CD runners
