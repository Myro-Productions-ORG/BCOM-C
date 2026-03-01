# BCOM-C Session Log

---

## Session — 2026-03-01

**Built:**
- Live Generation Stream: `pages/data-gen.html` — SSE worker cards with tok/s EMA, pulse-glow animation, batch submit 1–18 workers via real `POST /api/runs`
- Generation Feed: `pages/data-gen.html` — polls `GET /api/runs?limit=50`, shows completed run history with best-snippet extraction; immediate update on `stream_end`
- Expand Event Chain: `pages/data-gen.html` — EXPAND button now renders full `node_update` event chain with agent labels instead of unclamping useless 200-char snippet
- Gap Report update: `bcom_gap_report.html` — reflected P1 #1 (Live Stream) and pipeline finetune fix as DONE; added session counter card

**Fixed:**
- `pipeline.html` finetune banner: replaced fake simulation with real `GET /api/finetune/` polling
- Pulse animation on worker cards: changed from subtle border fade to full `box-shadow` glow (1.6s cycle)
- EXPAND button: was a no-op (200-char snippets never overflow 100px box); now shows full event chain

**ADRs:**
- ADR-006: SSE live generation stream + feed via BobSpark-APIs run endpoints (`docs/adr/ADR-006-sse-live-generation-stream.md`)

**Decisions:**
- Use SSE (EventSource) over polling for live worker stream — already server-side implemented, lower latency
- Build generation feed on `GET /api/runs` + `GET /api/runs/{id}` — no dedicated datagen feed endpoint exists in BobSpark-APIs
- tok/s via EMA (α=0.3) on cumulative `tokens_out` delta, gated at dt > 100ms
- Stagger multi-worker launches 300ms apart to avoid API hammering
- Snippet extraction priority: last non-supervisor/system/finish node → any node → last status message

**Plugins created:**
- `bcom-git-workflow.plugin` — `/ship` command: enforces branch → ADR → commit → push → PR flow
- `bobspark-apis-ref.plugin` — passive skill: loads all endpoint schemas + SSE event types + DB schema into context
- `bcom-spark-sync.plugin` — `/sync` and `/restart` commands for scp deploys and service restarts
- `bcom-session-tracker.plugin` — `/gap-update` and `/session-log` commands for progress tracking

**Pending (gap list):**
- P1 #3: Datagen Run Detail Page — new page `/datagen-run?id=…` with full live monitoring
- P1 #4: Coordinator Job System — multi-node job dispatch, add/remove/pause/resume nodes
- P1 #5: Datasets Page — hero stats + filterable table + slide-out + provenance chain
- P2: Datagen Analytics Charts (5× Chart.js), Service Queue panel, Models/Leaderboard page
- P2: Pipeline Training Loss charts, Iteration History table
- Update gap report after each completed P1 item

---
