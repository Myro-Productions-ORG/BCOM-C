# ADR-005: Self-Hosted GitHub Actions Runners for Multi-Machine Deployment

**Status:** Accepted  
**Date:** 2026-03-01  
**Deciders:** Nicolas Myers

---

## Context

BCOM-C needs to be kept in sync across multiple machines on the local network: the DGX Spark (primary inference node), the M4 Pro Mac Mini (dev/reference), and the Linux desktop. A CI/CD mechanism was needed that triggers on every push to GitHub.

## Decision

Run self-hosted GitHub Actions runners on each machine. On `push` to `main`, a workflow fires three parallel jobs — one per machine — each doing `git pull origin main` on their local mirror.

## Rationale

- **GitHub Actions is already in use** for the repository — no new CI service needed.
- **Self-hosted runners allow LAN pull** — The runner on each machine does the `git pull` locally. No SSH from GitHub into the network, no firewall changes.
- **Parallel jobs** — All three machines sync simultaneously; the push-to-live latency is under 10 seconds.
- **Labels for targeting** — Each runner is labeled (`dgx`, `m4pro`, `linux-desktop`) so jobs can be precisely targeted.
- **User-level systemd / launchd** — No root required. Linux machines use `systemctl --user`; macOS uses launchd `LaunchAgents`. Both are enabled at boot via linger/RunAtLoad.

## Runner Summary

| Machine | IP | OS | Runner Name | Labels |
|---|---|---|---|---|
| DGX Spark | 10.0.0.69 | Ubuntu 24.04 arm64 | dgx-spark | self-hosted, dgx, arm64 |
| M4 Pro | 10.0.0.210 | macOS arm64 | m4pro | self-hosted, m4pro, arm64, macos |
| Linux Desktop | 10.0.0.10 | Debian x86_64 | linux-desktop | self-hosted, linux-desktop, x64, linux |

## Workflow (`.github/workflows/deploy.yml`)

```yaml
jobs:
  sync-dgx:
    runs-on: [self-hosted, dgx, arm64]
    steps:
      - run: git -C /home/nmyers/Projects/BCOM-C pull origin main

  sync-m4pro:
    runs-on: [self-hosted, m4pro, arm64]
    steps:
      - run: git -C /Users/myro-pro/Projects/BCOM-C pull origin main

  sync-linux:
    runs-on: [self-hosted, linux-desktop, x64]
    steps:
      - run: git -C /home/myroproductions/Projects/BCOM-C pull origin main
```

## Consequences

- Runners must be online when a push happens. If a machine is offline, that job fails (does not block the others).
- Registration tokens are single-use and expire. Re-registering requires generating a new token via `gh api`.
- The `loginctl enable-linger` flag must be set on Linux machines so user services survive logout.
