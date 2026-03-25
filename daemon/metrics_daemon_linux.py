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
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

import psutil

# ── Configuration ────────────────────────────────────────────────────────────

PORT = 8090
OLLAMA_URL = "http://localhost:11434"

# Notable processes to track (command substrings → display names)
TRACKED_PROCESSES = {
    "ollama":           "Ollama",
    "init_agent.js":    "Mindcraft Agent",
    "minecraft":        "Minecraft",
    "fabric-server":    "Minecraft Server",
    "vault":            "Vault",
    "chroma":           "ChromaDB",
    "bob-stt":          "Bob STT",
    "node_exporter":    "Node Exporter",
    "ttyd":             "TTYD",
    "Runner.Listener":  "GH Actions Runner",
}

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


def _ollama_get(path: str):
    """GET a JSON endpoint from the local Ollama server."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}{path}")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def collect_ollama_models() -> list:
    """Return list of all Ollama models (installed)."""
    data = _ollama_get("/api/tags")
    if not data:
        return []
    return [
        {
            "name": m["name"],
            "parameter_size": m.get("details", {}).get("parameter_size", "--"),
            "quantization": m.get("details", {}).get("quantization_level", "--"),
            "family": m.get("details", {}).get("family", "--"),
            "size_gb": round(m.get("size", 0) / 1e9, 1),
        }
        for m in data.get("models", [])
    ]


def collect_ollama_running() -> list:
    """Return list of currently loaded/running Ollama models."""
    data = _ollama_get("/api/ps")
    if not data:
        return []
    return [
        {
            "name": m["name"],
            "parameter_size": m.get("details", {}).get("parameter_size", "--"),
            "quantization": m.get("details", {}).get("quantization_level", "--"),
            "vram_gb": round(m.get("size_vram", 0) / 1e9, 1),
            "context_length": m.get("context_length", 0),
            "expires_at": m.get("expires_at", ""),
        }
        for m in data.get("models", [])
    ]


def collect_processes() -> list:
    """Return notable running processes with resource usage."""
    results = []
    seen_labels = {}
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cpu_percent",
                                      "memory_info", "create_time"]):
        try:
            info = proc.info
            cmdline = " ".join(info.get("cmdline") or [])
            pname = info.get("name", "")
            full = f"{pname} {cmdline}"

            for substr, label in TRACKED_PROCESSES.items():
                if substr.lower() in full.lower():
                    # For Mindcraft agents, extract the agent name
                    display = label
                    if substr == "init_agent.js" and info.get("cmdline"):
                        args = info["cmdline"]
                        for i, a in enumerate(args):
                            if "init_agent.js" in a and i + 1 < len(args):
                                display = f"Mindcraft: {args[i+1]}"
                                break

                    key = display
                    mem_mb = round((info.get("memory_info") or
                                    psutil._common.pmem(0,0,0,0,0,0,0)).rss / 1e6)
                    uptime_s = time.time() - (info.get("create_time") or time.time())

                    # Keep the one using the most memory if duplicated
                    if key not in seen_labels or mem_mb > seen_labels[key]["mem_mb"]:
                        seen_labels[key] = {
                            "name": display,
                            "pid": info["pid"],
                            "mem_mb": mem_mb,
                            "uptime": _uptime_str(uptime_s),
                            "status": "running",
                        }
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return sorted(seen_labels.values(), key=lambda x: x["mem_mb"], reverse=True)


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
    models = collect_ollama_models()
    running = collect_ollama_running()
    processes = collect_processes()
    with _cache_lock:
        _cache["linux"] = linux
        _cache["ollama_models"] = models
        _cache["ollama_running"] = running
        _cache["processes"] = processes
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

    def _json_response(self, payload: dict | list):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        with _cache_lock:
            cache = dict(_cache)

        if self.path == "/api/metrics":
            self._json_response({
                k: v for k, v in cache.items() if not k.startswith("_")
            })
        elif self.path == "/api/models/":
            # Ollama models in same format as BobSpark-APIs /api/models/
            models = cache.get("ollama_models", [])
            self._json_response({"models": [
                {
                    "name": m["name"],
                    "details": {
                        "parameter_size": m["parameter_size"],
                        "quantization_level": m["quantization"],
                        "family": m["family"],
                    },
                    "size_gb": m["size_gb"],
                }
                for m in models
            ]})
        elif self.path == "/api/ollama/ps":
            self._json_response({"models": cache.get("ollama_running", [])})
        elif self.path == "/api/processes/":
            self._json_response({"processes": cache.get("processes", [])})
        else:
            self.send_response(404)
            self.end_headers()

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
