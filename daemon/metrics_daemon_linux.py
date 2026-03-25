#!/usr/bin/env python3
"""
BCOM-C Linux Desktop Metrics Daemon
Serves GET /api/metrics for the Bob-AI Command & Control dashboard.

Collects local GPU/CPU/RAM telemetry on the Linux Desktop node and
serves it in the schema expected by bcom.js applyDashboard().

Usage:
    python3 metrics_daemon_linux.py [--port 8090]

Response schema:
    {
      "linux": {
        "cpu_pct":  0-100,
        "gpu_pct":  0-100,
        "gpu_temp": "51°C",
        "vram_pct": 0-100,
        "vram_gb":  "2.1 GB",
        "cpu_temp": 58.0,
        "ram_gb":   "12.4 GB",
        "uptime":   "3d 2h"
      }
    }
"""

import json
import subprocess
import time
import argparse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import psutil

# ── Configuration ────────────────────────────────────────────────────────────

PORT = 8090

# ── Metric collectors ────────────────────────────────────────────────────────

def _cpu_temp_c() -> float:
    """Return CPU temp (max across sensor zones), or 0."""
    try:
        temps = psutil.sensors_temperatures()
        for key in ("coretemp", "k10temp", "acpitz"):
            zones = temps.get(key, [])
            if zones:
                return round(max(z.current for z in zones), 1)
    except Exception:
        pass
    return 0.0


def _gpu_stats() -> dict:
    """
    Query nvidia-smi for GPU utilisation, temperature, and VRAM.
    Returns gpu_pct, gpu_temp, vram_pct, vram_gb with safe fallbacks.
    """
    result = {"gpu_pct": 0, "gpu_temp": "--", "vram_pct": 0, "vram_gb": "--"}
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0:
            parts = [p.strip() for p in out.stdout.strip().split(",")]
            if len(parts) >= 4:
                if parts[0] not in ("", "[N/A]", "N/A"):
                    result["gpu_pct"] = int(parts[0])
                if parts[1] not in ("", "[N/A]", "N/A"):
                    result["gpu_temp"] = f"{parts[1]}\u00b0C"
                used = int(parts[2]) if parts[2] not in ("", "[N/A]", "N/A") else 0
                total = int(parts[3]) if parts[3] not in ("", "[N/A]", "N/A") else 0
                if total > 0:
                    result["vram_pct"] = round((used / total) * 100, 1)
                    result["vram_gb"] = f"{used / 1024:.1f} GB"
    except Exception:
        pass
    return result


def _uptime_str(seconds: float) -> str:
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    return f"{days}d {hours}h"


def collect_metrics() -> dict:
    """Collect all local metrics for the Linux Desktop node."""
    cpu_pct = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    uptime_s = time.time() - psutil.boot_time()
    gpu = _gpu_stats()

    return {
        "cpu_pct":  round(cpu_pct, 1),
        "gpu_pct":  gpu["gpu_pct"],
        "gpu_temp": gpu["gpu_temp"],
        "vram_pct": gpu["vram_pct"],
        "vram_gb":  gpu["vram_gb"],
        "cpu_temp": _cpu_temp_c(),
        "ram_gb":   f"{mem.used / 1e9:.1f} GB",
        "uptime":   _uptime_str(uptime_s),
    }


# ── Metrics cache ────────────────────────────────────────────────────────────

_cache: dict = {}
_cache_lock = threading.Lock()


def _refresh_cache() -> None:
    linux = collect_metrics()
    with _cache_lock:
        _cache["linux"] = linux
        _cache["_ts"] = time.time()


def _poll_loop(interval: int = 5) -> None:
    while True:
        try:
            _refresh_cache()
        except Exception:
            pass
        time.sleep(interval)


# ── HTTP handler ─────────────────────────────────────────────────────────────

class MetricsHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path != "/api/metrics":
            self.send_response(404)
            self.end_headers()
            return

        with _cache_lock:
            payload = {k: v for k, v in _cache.items() if not k.startswith("_")}

        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass  # suppress per-request access logs


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BCOM-C Linux Desktop Metrics Daemon")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    print(f"BCOM-C Linux Metrics Daemon starting on port {args.port}")
    print(f"  Collecting: CPU, GPU, VRAM, RAM, temperature, uptime")

    # Populate cache before first HTTP request
    _refresh_cache()

    # Background polling thread
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()

    server = HTTPServer(("0.0.0.0", args.port), MetricsHandler)
    print(f"  Listening: http://0.0.0.0:{args.port}/api/metrics")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDaemon stopped.")


if __name__ == "__main__":
    main()
