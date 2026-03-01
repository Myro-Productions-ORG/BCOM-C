# ADR-004: xterm.js + PTY WebSocket for Remote Terminal

**Status:** Accepted  
**Date:** 2026-01-15  
**Deciders:** Nicolas Myers

---

## Context

BCOM-C needed an embedded interactive terminal connected to the DGX Spark, accessible from the browser. Options: SSH-in-browser (wetty/shellinabox), iframe to an external terminal, or a custom xterm.js + WebSocket implementation.

## Decision

Implement a custom terminal using **xterm.js v5.3.0** on the frontend and **ptyprocess** on the FastAPI backend, connected via a WebSocket at `/api/terminal/ws`.

## Rationale

- **Native look and feel** — xterm.js renders a proper terminal emulator (VT100/xterm escape codes, cursor, color, resize) in a `<canvas>` element. Iframe/shellinabox solutions look foreign in a dark ops dashboard.
- **Integrated in the dashboard** — No separate URL, no new tab. The terminal lives inside the BCOM-C layout alongside gauges and system stats.
- **Lightweight** — xterm.js (~600KB gzipped) is loaded lazily from CDN only when the SHELL tab is activated.
- **PTY (ptyprocess)** — A real pseudo-terminal means programs like `htop`, `vim`, and `nano` work correctly. A simple `subprocess.communicate()` pipe would break interactive programs.
- **WebSocket binary frames** — Keystrokes are sent as binary `Uint8Array`, PTY output is received as binary — efficient and avoids base64 overhead.

## Key Implementation Detail

```python
# CRITICAL: asyncio.get_running_loop() — NOT get_event_loop()
# In Python 3.10+, get_event_loop() inside an async function raises
# DeprecationWarning and returns the wrong loop, breaking add_reader().
loop = asyncio.get_running_loop()
loop.add_reader(proc.fd, _pty_readable)
```

## WebSocket URL Derivation

```javascript
// Derive protocol from page URL to avoid mixed-content block on HTTPS
function _wsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/api/terminal/ws`;
}
```

## Consequences

- xterm.js is loaded from CDN — requires internet access for first load (or self-host).
- PTY resize events must be forwarded from xterm's `onResize` to the backend via JSON frame `{type:"resize", cols, rows}`.
- The existing `switchTerm()` function on each page must be patched (`patchSwitchTerm()`) to handle the 'shell' tab without breaking the existing SPARK-BOB / LINUX-DSKTP tabs.
