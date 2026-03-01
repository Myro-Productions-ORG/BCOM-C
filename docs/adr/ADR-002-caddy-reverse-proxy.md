# ADR-002: Caddy as Reverse Proxy over Nginx

**Status:** Accepted  
**Date:** 2025-12-04  
**Deciders:** Nicolas Myers

---

## Context

The BCOM-C static site needs to be served over HTTP/HTTPS and must proxy `/api/*` requests to BobSpark-APIs on the DGX Spark (10.0.0.69:9010). A reverse proxy/web server was required.

## Decision

Use Caddy (v2) running in Docker, configured via `Caddyfile`.

## Rationale

- **Automatic HTTPS** — Caddy handles TLS certificate provisioning and renewal automatically, with no manual certbot cron jobs.
- **WebSocket proxying built-in** — Caddy upgrades HTTP→WebSocket for `/api/terminal/ws` transparently. Nginx requires explicit `proxy_set_header Upgrade` configuration.
- **Readable config** — A Caddyfile is 10–15 lines vs an equivalent nginx.conf at 40–60 lines.
- **Docker-native** — Single `caddy:2-alpine` image, no custom image needed.
- **`no-store` cache headers** — A single `header` directive handles cache-busting for all JS/CSS assets.

## Caddy Config (summary)

```
bcom.myroproductions.com {
    root * /app/bcom-c
    file_server
    reverse_proxy /api/* 10.0.0.69:9010
    header *.js Cache-Control "no-store, must-revalidate"
    header *.css Cache-Control "no-store, must-revalidate"
}
```

## Consequences

- Caddy is less common than Nginx in enterprise settings — new contributors may need to learn it.
- Caddy's Docker image adds ~50MB to the stack. Acceptable.
