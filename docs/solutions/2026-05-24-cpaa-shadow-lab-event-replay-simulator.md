---
title: "CPAA Shadow Lab Phase 0 — Event Replay Simulator"
date: 2026-05-24
category: event-sourcing
tags:
  - cpaa
  - shadow-lab
  - event-replay
  - flask
  - sqlite
  - projections
  - failure-injection
  - replay-clock
  - worktrees
problem_type: greenfield-build
components:
  - event-log
  - projection-handlers
  - replay-engine
  - dashboard
  - failure-injections
  - alert-system
severity: phase-0-prototype
status: complete
---

# CPAA Shadow Lab Phase 0 — Event Replay Simulator

## Problem

Building a standalone event-replay simulator for the CPAA (Claude-Powered Agentic Architecture) required implementing an event-sourced architecture in Flask that could replay a 4-hour charity gala timeline from synthetic telemetry, with bidirectional time travel (forward and backward), real-time dashboard visualization, and detection of 4 injected failure scenarios. The core challenge was making append-only event sourcing work with a replay clock that can move both forward and backward, while keeping projections consistent and the UI responsive.

This is Phase 0 of the CPAA architecture — it proves the event state model before any AI, MCP servers, or hardware are added.

## Investigation

The build drew on the existing `event-sourced-audit-log` solution doc for the append-only pattern, but the replay use case introduced requirements that pure audit logging doesn't face:

1. **Bidirectional projection consistency** — Audit logs only move forward. A replay simulator must support rewinding, which means projections must be rebuildable from scratch up to any arbitrary point in the timeline.

2. **Two classes of alerts** — Some alerts are triggered by specific events (e.g., a temperature breach fires an alert). Others are triggered by the *absence* of events (e.g., no heartbeat from a station for 60+ seconds). These require fundamentally different detection strategies.

3. **Thread-safe clock management** — Flask serves requests from multiple threads, but the replay clock is shared mutable state that the polling dashboard reads while control endpoints write.

4. **CWD-sensitive path resolution** — Flask's `static_folder` resolution interacts poorly with different working directories depending on how the app is launched.

5. **Development environment conflicts** — macOS AirPlay Receiver on port 5000, parallel Claude Code sessions switching git branches out from under each other.

## Root Cause

No single root cause — this was a greenfield build across 5 phases (Schema+Models, Generator, Flask+API, Dashboard UI, Failure Verification). The key architectural tension was between event sourcing's append-only invariant and the replay simulator's need to "unsee" events when rewinding. The correct approach: keep all events permanent but rebuild projections only up to the current replay cursor position.

Secondary issues traced to:

- **Double-counting projections**: `append_event` projected each event immediately on insert, but `advance_projections` re-projected the same events when advancing the clock. No clear single owner of "when does projection happen."
- **Station name loss**: `_ensure_station` created station rows using `station_id` as a fallback name, so after a rebuild cycle the human-readable names were replaced with IDs.
- **Static file 404s**: `os.path.abspath(__file__)` resolves relative to CWD, not the package.
- **Branch-switching**: Two Claude Code sessions sharing a git checkout caused constant branch reverts and file deletions.

## Solution

### Architecture: Append-Only Log + Rebuildable Projections

Six SQLite tables: `events` (append-only log), `station_state`, `financial_state`, `environment_state`, `active_alerts` (projection tables), `replay_meta` (projection cursor). All writes use `BEGIN IMMEDIATE` with `isolation_level=None`. Read functions never commit.

**Projection model:**
- 8 synchronous projection handlers registered in a dict, keyed by event type
- `advance_projections(db, t)` — reads cursor from `replay_meta`, projects events between cursor and `t`, updates cursor. Forward-only, incremental.
- `rebuild_projections_to(db, t)` — wipes all projection tables, replays all events up to `t` from scratch. Used for backward jumps.
- `rebuild_projections_to(db, None)` — clears everything. Used at replay start to prevent double-counting.

**Two alert models:**
- **Event-triggered**: Materialized in `active_alerts` by `system.alert.raised` / `system.alert.resolved` handlers. Survive rebuilds because they replay from the event log.
- **Absence-derived**: Computed at query time in `get_derived_state()` by checking `last_heartbeat` staleness and bid gap duration. Never stored.

### Replay Engine

Module-level dict + `threading.Lock` for replay state (stopped/playing/paused). `get_current_event_time()` calculates position from wall clock elapsed × speed. Speed changes re-anchor the time reference. Jump auto-pauses and triggers `rebuild_projections_to`.

### Key Fix Patterns

| Problem | Fix | Why It Works |
|---|---|---|
| Projection double-counting | `rebuild_projections_to(None)` at replay start | Clears projections from `append_event`'s inline path |
| Station names lost on rebuild | `_STATION_NAMES` lookup dict | Handlers use dict instead of falling back to station_id |
| `static_folder` CWD dependency | `Flask(__name__, static_folder='../static')` | Resolves relative to `root_path` (package dir), not CWD |
| Port 5000 conflict on macOS | Default to port 5050 | Avoids AirPlay Receiver which returns 403 |
| Branch switching across sessions | Git worktrees | Each session gets an independent working tree |
| Dark theme text contrast | Explicit `color` declarations in CSS | Don't rely on inheritance for text color on dark backgrounds |

### Failure Injections Verified

| Time | Injection | Verified Behavior |
|------|-----------|-------------------|
| 19:15-19:18 | Station 2 heartbeat drop | station_2 → unknown at 19:16:30, recovers by 19:19 |
| 19:45 | Ceviche Bar temp spike 8.2°C | temp_breach:station_1 critical alert, resolved by 19:56 |
| 20:00-20:15 | Network outage (zero events) | All 3 stations unknown at 20:02, recover by 20:16 |
| 20:30-20:50 | No bid events | auction_stall:global warning at 20:45, resolves by 21:00 |

### Build Stats

- **5 phases**, 6 commits, 22 files, 3,529 lines added
- **1,595 synthetic events** across 4-hour scenario
- **16 automated tests** (Phase A: 4, Phase B: 7, Phase E: 5)
- **Ultrareview result**: Clean — no bugs found in cpaa-shadow-lab code

## Prevention Strategies

### PS-1: Git Worktree Isolation for Concurrent Sessions

Before starting a second session on any repo, create a dedicated git worktree. Each session gets its own working directory with its own branch, so branch switches and file operations are fully isolated.

**Detection signal:** If `git status` shows unexpected changes or a different branch, another session is likely active. Stop and create a worktree.

### PS-2: Flask Static Path Resolution via root_path

Never use `os.path.abspath(__file__)` for locating static or template directories. Use relative paths from Flask's `root_path` or `pathlib.Path(__file__).resolve().parent`.

```python
app = Flask(__name__, static_folder='../static')  # CWD-independent
```

### PS-3: Projection Handlers Must Be Self-Contained

Every projection handler must carry all the data it needs. If `_ensure_station` creates a row with placeholder data, the event schema or handler is incomplete. Projection rebuild must produce identical output whether run against an empty or pre-populated database.

### PS-4: Default to Port 5050 on macOS

macOS Sonoma+ enables AirPlay Receiver on port 5000 by default. All Flask projects should default to port 5050 or 8080.

### PS-5: Explicit Text Color on Dark Backgrounds

Every CSS rule that sets a dark background must also set an explicit light text color. Never rely on inheritance.

### PS-6: Separate Data Loading from Projection Building

Data loading (inserting raw events) must never trigger projection side effects. The generator uses raw SQL inserts; projections are built exclusively by `advance_projections` during replay.

## Related Documentation

### Direct Precedents
- `docs/solutions/2026-04-05-event-sourced-audit-log.md` — Synchronous projection, cursor pagination, timestamp format
- `docs/solutions/2026-04-05-service-mesh-dashboard.md` — ON DELETE SET NULL for audit logs, dashboard UI patterns
- `docs/solutions/2026-05-22-brewops-21-agent-swarm-build.md` — Derived State as mandatory spec section

### Flask + SQLite Patterns
- `docs/solutions/2026-04-07-flask-swarm-acid-test.md` — Blueprint registration, app factory, Jinja2 inheritance
- `docs/solutions/2026-04-05-distributed-task-scheduler.md` — WAL mode + busy_timeout + BEGIN IMMEDIATE
- `docs/solutions/2026-05-23-client-intake-dashboard-15-agent-swarm-build.md` — Bootstrap 5 admin dashboard

### Worktree / Parallel Development
- `docs/solutions/2026-04-09-task-tracker-categories-swarm.md` — Agents in isolated git worktrees
- `docs/solutions/2026-04-09-compound-bash-instruction-refactor.md` — Forbidden bash patterns in worktrees

## Feed-Forward

- **Hardest decision:** Keeping Phase 0 as logical-time-only replay and honestly documenting what it does NOT prove (arrival-order bugs, burst handling). Codex caught the original plan claiming to test scenarios that pre-loaded data cannot exercise.
- **Rejected alternatives:** Client-side replay (skips server-side state model), background-thread insertion (Phase 1 scope), Postgres (overkill for sandbox).
- **Least confident:** Whether the absence-detection query-time pattern (heartbeat staleness, auction stall) will scale to Phase 1's larger datasets without caching. At 1,595 events it's <1ms per poll, but 10x more events at 10x speed may require optimization.
