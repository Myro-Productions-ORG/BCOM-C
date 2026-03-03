# ADR-007: URL-Param Routed Detail Pages

**Status:** Accepted
**Date:** 2026-03-01
**Deciders:** Nicolas Myers

---

## Context

BCOM-C is a single-level dashboard where every view is a full page or a panel within a page. As run history grows, users need to drill into individual runs to inspect the full event chain, live stream, and token stats — information that is too dense to surface inline in the Generation Feed.

Options considered:
1. **Inline expand** — expand a feed item in-place (already done partially with EXPAND button, insufficient for full detail)
2. **Modal/drawer overlay** — JS overlay injected into the existing page
3. **Separate page with URL query param** — `pages/datagen-run.html?id=<run_id>`

## Decision

Use **separate HTML pages with `?id=` query params** for all drill-down detail views.

- Detail pages live in `pages/` alongside primary pages
- The entity ID is passed via `?id=` in the query string
- The page reads `new URLSearchParams(window.location.search).get('id')` on init
- All API fetches are keyed off that ID
- Back navigation uses `history.back()` with a fallback to the parent page

## Rationale

- Consistent with ADR-001 (vanilla JS, no framework) — no router library needed
- URL is shareable and bookmarkable: `bcom.myroproductions.com/pages/datagen-run.html?id=abc123`
- Avoids complex modal state management in already-busy dashboard pages
- Browser back/forward works natively
- Each detail page can be built and tested independently

## Consequences

- Every entity type needing a detail view gets its own `pages/<entity>-detail.html`
- Primary pages link to detail pages via `href="<detail>.html?id=<id>"` — no JS navigation needed
- `datagen-run.html` establishes the canonical pattern: hero stats → live panel (if running) → full event chain
- SSE is opened on the detail page independently if the run is still active (complements ADR-006)
