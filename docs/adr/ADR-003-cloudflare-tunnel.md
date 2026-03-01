# ADR-003: Cloudflare Tunnel for External HTTPS Access

**Status:** Accepted  
**Date:** 2025-12-04  
**Deciders:** Nicolas Myers

---

## Context

BCOM-C needs to be accessible at `bcom.myroproductions.com` from outside the local network. Options considered: port-forwarding on the router, a VPN (WireGuard/Tailscale), or a Cloudflare tunnel.

## Decision

Use `cloudflared` running as a Docker container (host network mode) to tunnel `bcom.myroproductions.com` → `http://localhost:80` (Caddy).

## Rationale

- **No port forwarding required** — The tunnel is an outbound connection from the Mac Mini to Cloudflare's edge. No router changes, no dynamic DNS.
- **Free tier sufficient** — Cloudflare Tunnel is free for personal/hobby use.
- **Automatic TLS at the edge** — Cloudflare terminates TLS; traffic from the edge to localhost is plain HTTP, which is fine on the loopback interface.
- **DDoS protection included** — Cloudflare sits in front of the origin automatically.
- **WebSocket support** — Cloudflare proxies WebSocket upgrades (`cf-cache-status: BYPASS`, `DYNAMIC` for WS connections).

## Config (`bcom-config.yml`)

```yaml
tunnel: <tunnel-id>
ingress:
  - hostname: bcom.myroproductions.com
    service: http://localhost:80
    originRequest:
      httpHostHeader: bcom.myroproductions.com
  - service: http_status:404
```

## Consequences

- External access depends on Cloudflare uptime (99.99% SLA).
- Mixed-content bug: WebSocket URL must use `wss://` (not `ws://`) when the page is served over HTTPS. Resolved in `bcom-terminal.js` by deriving the protocol from `window.location.protocol`.
- Cloudflare caches responses; `Cache-Control: no-store` headers are required on JS/CSS assets.
