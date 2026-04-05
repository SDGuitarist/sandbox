---
title: "Event-Sourced Audit Log Service"
date: 2026-04-05
status: complete
origin: "conversation"
---

# Event-Sourced Audit Log Service — Brainstorm

## Problem
We need an audit log service that records every change to entities as immutable events. Consumers need to:
1. Append events (write path — must never update or delete)
2. Reconstruct current state for any entity by replaying its event history
3. Query events by entity ID, event type, and/or time range with cursor pagination
4. Get a materialized "current state" projection without replaying every time

Without event sourcing, audit logs are typically an afterthought — a single `updated_at` field with no history. This service makes the event log the source of truth.

## Context
- Stack: Flask + SQLite
- SQLite constraints: single-writer, WAL mode for concurrent reads, no native JSON operators before 3.38
- Prior lessons learned (from solution docs):
  - Timestamps must be stored as `YYYY-MM-DD HH:MM:SS` — SQLite's `datetime()` rejects ISO8601 T-separators
  - Composite indexes on `(entity_id, event_type, created_at)` are required for range queries
  - Projections should store precomputed state, not replay on every request
  - BEGIN IMMEDIATE for atomic state updates inside transaction
- Event sourcing core contract: events are immutable, append-only, ordered by sequence number within an entity

## Options

### Option A: Single events table, no snapshot table
Every read replays the full event history from the `events` table. Projection endpoint replays in-memory and returns current state without persisting it.

**Pros:** Simplest schema, pure event sourcing, no sync issues between events and projections.  
**Cons:** O(N) replay on every projection read. For entities with thousands of events, this is a performance problem. No fast "current state" lookup.

### Option B: Events table + projections table (precomputed state)
`events` table is append-only. A separate `projections` table stores the latest materialized state per entity, updated atomically inside the same transaction as each event insert.

**Pros:** O(1) projection reads. Projection is always consistent with last event (same transaction). Range queries hit `events` table only. Clean separation of concerns.  
**Cons:** Slightly more complex write path (two INSERTs per event). Projections table schema is denormalized. If projection logic changes, need a backfill.

### Option C: Events table + async projection worker
Events are appended. A background worker reads the event stream and updates projections asynchronously (eventual consistency).

**Pros:** Decoupled, scalable write path.  
**Cons:** Projection can lag behind events. Adds complexity (background process, position tracking). For an audit log, stale projections are a correctness risk. Overkill for SQLite/Flask scope.

## Tradeoffs
| Concern | Option A | Option B | Option C |
|---|---|---|---|
| Projection read speed | O(N) — bad | O(1) — good | O(1) but stale |
| Write complexity | Simple | Moderate | High |
| Consistency | Strong | Strong | Eventual |
| Backfill on schema change | Easy (replay) | Manual backfill needed | Manual backfill needed |
| SQLite fit | Good | Good | Poor (background process) |

**What matters most:** Correctness (append-only guarantee), fast projection reads, and simplicity. Option B wins.

## Decision
**Option B: Events table + projections table, updated in the same transaction.**

- Projection is written atomically with the event — no lag, no staleness.
- The projection endpoint is O(1): `SELECT * FROM projections WHERE entity_id = ?`
- State reconstruction endpoint (`/entities/{id}/history`) replays the event stream.
- `BEGIN IMMEDIATE` wraps each event insert + projection upsert.

Schema sketch:
```sql
-- Append-only, never UPDATE or DELETE
CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id   TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    payload     TEXT NOT NULL,  -- JSON string
    actor       TEXT,           -- who triggered the event
    created_at  TEXT NOT NULL   -- 'YYYY-MM-DD HH:MM:SS'
);
CREATE INDEX idx_events_entity ON events(entity_id, created_at);
CREATE INDEX idx_events_type_time ON events(entity_type, event_type, created_at);

-- Materialized current state per entity
CREATE TABLE projections (
    entity_id   TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    state       TEXT NOT NULL,  -- JSON string
    version     INTEGER NOT NULL,  -- event count, for optimistic concurrency
    updated_at  TEXT NOT NULL
);
```

Pagination: cursor-based using `id` (stable, monotonic). `?after=<last_id>&limit=50`.

## Open Questions
1. Should `payload` be validated (schema per event_type) or free-form JSON? → Free-form for now; validation is a future concern.
2. What is "current state"? → Merge all event payloads in order (shallow merge). Caller defines what fields matter.
3. Snapshot optimization (store state every N events for fast replay)? → Not needed at this scale; defer.
4. Authentication/API keys? → Out of scope for this service; caller is trusted.
5. Should `entity_type` be an enum or free text? → Free text; no enforcement needed at DB level.

## Feed-Forward
- **Hardest decision:** Whether to make projections synchronous (same transaction) or async. Chose synchronous because SQLite's single-writer model makes async workers add complexity without benefit, and audit logs require strong consistency.
- **Rejected alternatives:** Option C (async worker) — too complex for this stack; Option A (no projection table) — O(N) replay makes the projection endpoint unacceptably slow for large entities.
- **Least confident:** The "merge all payloads" approach for state reconstruction assumes callers pass partial-update payloads (patch semantics). If callers pass full state snapshots, the merge logic changes. This must be pinned down in the plan before implementation.
