---
title: "Event-Sourced Audit Log Service"
date: 2026-04-05
tags: [event-sourcing, audit-log, flask, sqlite, pagination, projections]
module: audit-log
lesson: "Synchronous projection upsert inside BEGIN IMMEDIATE is simpler and safer than async workers for SQLite; cursor pagination with id > cursor correctly avoids the off-by-one trap a naive 'next page id' approach creates."
origin_plan: docs/plans/2026-04-05-feat-event-sourced-audit-log-plan.md
origin_brainstorm: docs/brainstorms/2026-04-05-event-sourced-audit-log.md
---

# Event-Sourced Audit Log Service

## Problem

Build a Flask + SQLite service where every change to an entity is recorded as an immutable event. Consumers need: append-only write path, state reconstruction from events, range+type queries with pagination, and an O(1) current-state projection endpoint.

## Solution

- `events` table: append-only, autoincrement `id`, composite indexes on `(entity_id, created_at)` and `(entity_type, event_type, created_at)`
- `projections` table: one row per entity, updated atomically inside the same `BEGIN IMMEDIATE` transaction as the event insert
- 5 Flask routes: `POST /events`, `GET /events` (filters + cursor pagination), `GET /entities/<id>/events`, `GET /entities/<id>/projection`, `GET /entities/<id>/history`
- Timestamps stored as `YYYY-MM-DD HH:MM:SS` (never ISO8601 T-separator)
- `get_db(immediate=True)` context manager handles WAL mode, row_factory, commit/rollback uniformly

## Why This Approach

- **Async projection worker (Option C) rejected:** SQLite's single-writer model makes async workers add complexity with no throughput benefit; projection staleness is a correctness risk for audit logs
- **No projection table (Option A) rejected:** O(N) replay on every projection read is unacceptable for entities with large event histories
- **Offset pagination rejected:** Unstable under concurrent appends; cursor (id > last_id) is stable and monotonic

## Risk Resolution

> **Flagged risk:** "The 'merge all payloads' approach for state reconstruction assumes callers pass partial-update payloads (patch semantics). If callers pass full state snapshots, the merge logic changes."
>
> **What actually happened:** Risk was resolved at plan time by pinning the contract to patch semantics. `test_projection_merge_patch_semantics` was written first (verify-first step), confirming shallow merge behavior before any route was implemented. The docstring in `append_event` explicitly documents the patch contract. No ambiguity surfaced during implementation.
>
> **Lesson learned:** Pinning payload semantics (patch vs. full-snapshot) in the plan — not during coding — eliminates the entire class of ambiguity. The verify-first test is the enforcement mechanism. Write it before any endpoint code.

## Key Decisions

| Decision | Choice | Reason |
|---|---|---|
| Projection timing | Synchronous, same transaction | No staleness; BEGIN IMMEDIATE serializes writer anyway |
| Cursor type | event.id (autoincrement integer) | Stable, monotonic; immune to gaps or concurrent inserts |
| Payload merge | Shallow merge (patch semantics) | Preserves audit trail; callers can see per-key changes |
| Timestamp format | `YYYY-MM-DD HH:MM:SS` | SQLite datetime() rejects T-separators; string comparison works on this format |

## Gotchas

1. **Cursor off-by-one trap:** `next_cursor = events[limit - 1]["id"]` is correct (last row of current page). A review suggested using `events[limit]["id"]` (first row of next page) but this causes the last row of the fetched extra-row to be silently skipped. The `id > cursor` condition correctly means "start after the last returned row."

2. **schema.sql must use pathlib relative to `__file__`**, not `open("schema.sql")` — the latter breaks if the process is not started from the repo root. Use: `SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"`

3. **`since`/`before` filters must be validated** at the route layer with `datetime.strptime(val, "%Y-%m-%d %H:%M:%S")` — passing an ISO8601 T-separator string silently produces wrong results because SQLite string comparison doesn't normalize formats.

4. **`actor` field must be cast to `str`** in the route before storing, or integer actors create type inconsistency in API responses.

5. **`append_event` must use `get_db(immediate=True)`** — not a raw `sqlite3.connect` — so WAL mode and connection settings stay consistent with all other DB functions.
