# ADR-001: Vanilla HTML/CSS/JS — No Frontend Framework

**Status:** Accepted  
**Date:** 2025-12-04  
**Deciders:** Nicolas Myers

---

## Context

BCOM-C is a real-time operator dashboard for the Bob-AI pipeline, served as static files via Caddy. A decision was needed on whether to use a frontend framework (React, Vue, Svelte) or plain HTML/CSS/JS.

## Decision

Use vanilla HTML/CSS/JS with no build step, no bundler, and no framework.

## Rationale

- **Zero build overhead** — no npm install, no webpack, no vite. Files are edited and served as-is.
- **Direct Caddy serving** — Caddy mounts the directory read-only and serves it. A build step would require a CI rebuild on every change; with vanilla JS the file change is the deployment.
- **Sufficient capability** — The dashboard renders gauges, polls an API, and manages a WebSocket terminal. None of these require a reactive component tree.
- **Debuggability** — DevTools shows the actual source, not transpiled output. No source maps needed.
- **Longevity** — No dependency rot. The dashboard will run in five years without `npm audit fix`.

## Consequences

- No component reuse patterns (mitigated by shared `bcom.js` / `bcom.css`).
- No TypeScript type checking (mitigated by keeping logic simple and well-commented).
- Adding complex interactivity in the future may require revisiting this decision.
