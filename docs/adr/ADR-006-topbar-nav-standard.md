# ADR-006: Topbar as the Canonical Navigation Pattern

**Status:** Accepted
**Date:** 2026-03-01
**Deciders:** Nicolas Myers

---

## Context

During the P2 build session, new pages were scaffolded using a `<nav class="bcom-nav">` component with an expanded link set (COORDINATOR, DATASETS, ANALYTICS, MODELS, EVALS, MONITOR, DEPLOY). This deviated from the original navigation pattern established in `index.html` and the early `pages/` pages, which use a `<div class="topbar">` structure styled by `bcom.css`.

The two patterns coexisted silently — P2 pages with `bcom-nav` would render with undefined styles (the class has no rules in `bcom.css`) and navigate to stale or wrong hrefs, causing users to be dropped back to the dashboard or a broken page when clicking nav buttons.

A full site audit confirmed 8 of 14 pages in `pages/` were using `bcom-nav`, and 3 of the topbar pages had incorrect href targets (linking to `coordinator.html` and `datasets.html` instead of `orchestrator.html`).

## Decision

The `topbar` div pattern is the **sole, canonical navigation structure** for all BCOM-C pages. `bcom-nav` is not a supported component and must not appear in any page.

The standard main-nav link set (fixed across all pages) is:

| Label | Href (from `pages/`) |
|---|---|
| DASHBOARD | `../index.html` |
| DATA GEN | `data-gen.html` |
| PIPELINE | `pipeline.html` |
| RESOURCES | `resources.html` |
| REPORTS | `reports.html` |
| ORCHESTRATOR | `orchestrator.html` |
| ⚙ (settings) | `settings.html` |

Pages not represented in the main nav (coordinator, datasets, analytics, evals, models, monitor, deploy, datagen-run) still use the full topbar with no active button — they are sub-pages reachable from their parent section, not from the top nav.

Each page sets `class="nav-btn active"` on exactly the link matching its own href.

## Rationale

- **Single source of style** — `topbar`, `topbar-title`, `topbar-right`, `nav-btn`, `nav-btn active`, `cog-btn`, and `timestamp` are all defined in `bcom.css`. No page-level nav CSS is needed.
- **Consistent UX** — users always see the same 6 primary destinations regardless of which page they are on.
- **Avoids ghost pages in nav** — COORDINATOR, DATASETS, EVALS, MODELS, MONITOR, DEPLOY are internal/secondary pages. Surfacing them in the primary nav cluttered the bar and created dead links during development.
- **Eliminates undefined-variable fallback** — `bcom-nav` had no CSS rules, so P2 pages rendered with browser-default unstyled navigation.

## Consequences

- All new pages **must** copy the topbar block from `reports.html` and update the `active` class to their own link. No new nav patterns are permitted.
- Secondary pages (coordinator, datasets, etc.) are navigated to via in-page links from their parent section page, not from the topbar.
- If the main nav set ever changes (new top-level section added), **all** pages must be updated — a find-replace across `pages/*.html` is the mechanism since there is no shared template include.
