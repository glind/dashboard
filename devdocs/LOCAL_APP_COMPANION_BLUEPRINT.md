# Local App Companion Blueprint

## Vision

Build a standalone companion platform that can launch, monitor, and open any local web app that follows a standard startup contract based on `ops/startup.sh`.

Primary goals:
- One reusable launcher for many local services
- Lightweight Mac-first UX (menu bar + optional widget + WebKit window)
- Consistent app metadata (name, icon, README description, health endpoint)
- Reliable start/stop/health/uptime reporting

---

## Brand Direction

## Recommended Product Name

Buildly Launchpad

Why this works:
- Ties cleanly to existing Buildly ecosystem language
- Signals startup/launcher behavior immediately
- Works for both technical and non-technical users

## Alternate Name Options

- Buildly Dock
- Buildly Local Hub
- Buildly Service Deck
- OpsShelf
- Startup Deck

## Suggested Tagline

Run and monitor local web apps with one click.

## Positioning

Buildly Launchpad is a local service launcher and control center for teams running many Python and web-based tools on development machines.

---

## Separate Repo Strategy

Create a dedicated repository so this becomes a reusable product, not tied to a single dashboard codebase.

Suggested repo name:
- buildly-launchpad

Suggested visibility:
- Private initially, then public after packaging and docs are stable

Suggested license:
- Apache-2.0 if you want broad reuse
- BSL if you want a delayed-open model similar to your dashboard

---

## High-Level Architecture

1. Companion Core Service
- Local API server on loopback only, for example `127.0.0.1:6410`
- Owns process orchestration and health checks
- Reads app catalog and runtime state

2. Mac Host UI
- Menu bar app with quick controls
- Optional WebKit window for full app catalog management
- Optional desktop widget for summary and quick actions

3. App Catalog
- Registry of managed services
- Includes metadata and commands

4. Runtime Tracker
- Tracks state for each app: running, pid, url, port, started_at, uptime
- Persists to runtime files for crash recovery and fast reload

5. Plugin/Adapter Layer
- Starts with shell adapter for `ops/startup.sh`
- Later support docker-compose, npm scripts, uvicorn, etc.

---

## Standard Service Contract

Each managed service must provide:

1. Required file
- `ops/startup.sh`

2. Required commands
- `./ops/startup.sh start`
- `./ops/startup.sh stop`
- `./ops/startup.sh status`
- Optional: `./ops/startup.sh restart`

3. Health endpoint
- Default: `/health`
- Must return non-5xx when healthy

4. Runtime state output
- Preferred output file: `data/runtime.json`
- Minimum fields:
  - `name`
  - `status`
  - `pid`
  - `port`
  - `url`
  - `started_at`

Example runtime payload:

```json
{
  "name": "Founder Dashboard",
  "status": "running",
  "pid": 12345,
  "port": 8008,
  "url": "http://127.0.0.1:8008",
  "started_at": "2026-05-26T12:30:00Z"
}
```

This contract allows Launchpad to handle dynamic ports while preserving a stable control plane.

---

## Catalog Schema

Suggested catalog file:
- `.launchpad/services.yaml`

Example:

```yaml
version: 1
services:
  - id: founder-dashboard
    name: Founder Dashboard
    root_path: /Users/you/Projects/me/dashboard
    startup_script: ops/startup.sh
    health:
      path: /health
      timeout_seconds: 2
      retries: 10
    metadata:
      readme_path: README.md
      icon_paths:
        - assets/images/icon-192.png
        - assets/images/icon.png
      tags: [python, fastapi, pwa]
```

---

## Metadata Extraction Rules

For each service card:

1. Display name
- `name` in catalog
- Fallback to folder name

2. Description
- First paragraph under first H1 in README
- Fallback to static description in catalog

3. Logo
- First existing path from `icon_paths`
- Fallback to generic icon by framework type

4. Stats
- Uptime from `started_at`
- PID and port from runtime state
- Optional CPU and memory via `psutil`

---

## UX Surfaces

## Menu Bar (Primary)
- Running count badge
- Start/Stop/Restart/Open actions per app
- Last error summary

## WebKit Window (Secondary)
- Full app cards
- Search and filters
- Logs preview
- Edit service metadata

## Widget (Tertiary)
- Small status tiles
- Open and restart quick actions
- Snapshot-oriented, not full orchestrator

Note: Widget should trigger companion actions, not run shell scripts directly.

---

## Security Baseline

- Bind local API to loopback only
- Enforce root path allowlist
- No arbitrary command entry from UI by default
- Require explicit user confirmation for first app registration
- Sanitize log output surfaced in UI

---

## Suggested Repo Structure

```text
buildly-launchpad/
  apps/
    macos/
      LaunchpadApp/           # Swift menu bar + WebKit UI + widget extension
  companion/
    api/                      # FastAPI or lightweight Python API
    orchestrator/             # start/stop/status adapters
    registry/                 # catalog parsing and validation
    telemetry/                # uptime, process stats, events
  contracts/
    startup-contract.md
    service-catalog.schema.yaml
  examples/
    services.yaml
    runtime.json
  docs/
    architecture.md
    setup-macos.md
    onboarding-services.md
  scripts/
    bootstrap-repo.sh
```

---

## Phased Delivery Plan

Phase 1: Core companion and catalog
- Parse catalog
- Start/stop/status using `ops/startup.sh`
- Health checks and uptime

Phase 2: Mac menu bar app
- Service list, actions, status chips
- Open app URL in default browser or embedded WebKit

Phase 3: Widget and polish
- Status widgets
- Restart/open intents
- Better branding and onboarding flow

Phase 4: Multi-runtime adapters
- Add Docker and Node adapters
- Shared contract test suite

---

## Migration Path from Existing Dashboard Repo

1. Extract generic server-manager logic currently in `src/utils/server_manager.py`
2. Keep dashboard-specific APIs in dashboard repo
3. Move generic orchestration into new launchpad repo
4. Add launchpad adapter in dashboard service catalog entry

This avoids duplicated process-control logic and makes the launcher reusable across projects.

---

## Definition of Done for v1

- Register at least 3 local services using only `ops/startup.sh`
- Start/stop/restart works from companion UI
- Dynamic port changes resolve to current live URL
- README description and icon auto-populate service cards
- Uptime and pid shown accurately
- macOS menu bar app and WebKit window shipped
