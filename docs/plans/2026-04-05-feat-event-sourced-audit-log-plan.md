---
title: "Event-Sourced Audit Log Service"
type: feat
status: draft
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-event-sourced-audit-log.md
feed_forward:
  risk: "The 'merge all payloads' approach for state reconstruction assumes callers pass partial-update payloads (patch semantics). If callers pass full state snapshots, the merge logic changes. This must be pinned down in the plan before implementation."
  verify_first: true
---

# feat: Event-Sourced Audit Log Service

## Enhancement Summary

**Deepened on:** 2026-04-05
**Research agents used:** solution-doc-searcher (prior lessons from job-queue, webhook-delivery, API key manager, URL health monitor, distributed task scheduler)

### Key Corrections From Research
- Timestamps must be normalized to `YYYY-MM-DD HH:MM:SS` at write time — do NOT store ISO8601 T-separator format
- Composite index required on `(entity_id, created_at)` AND `(entity_type, event_type, created_at)` for range query performance
- Projection state must be precomputed and stored — never replay on every projection read request
- Use `BEGIN IMMEDIATE` for all event insert + projection upsert operations (atomic write)

## What Must Not Change

1. **Append-only contract** — `events` table rows must never be UPDATEd or DELETEd under any circumstance
2. **Timestamp format** — all `created_at` values stored as `YYYY-MM-DD HH:MM:SS` (no T-separator, no timezone suffix)
3. **Projection consistency** — projections table must only be updated inside the same `BEGIN IMMEDIATE` transaction as the corresponding event insert
4. **Cursor pagination** — pagination uses event `id` as cursor (stable, monotonic integer), never offset-based
5. **SQLite WAL mode** — must be enabled on DB init for concurrent reads

## Prior Phase Risk

> "The 'merge all payloads' approach for state reconstruction assumes callers pass partial-update payloads (patch semantics). If callers pass full state snapshots, the merge logic changes. This must be pinned down in the plan before implementation."

**Resolution:** The API will document and enforce **patch semantics** — callers must pass partial-update payloads. The projection state is built by shallow-merging all payloads in ascending `id` order. The first task in Phase 1 is to write a test fixture that validates this merge behavior before any endpoint code is written. If a caller needs to replace state entirely, they pass a payload that overwrites the relevant keys.

**Verify first action:** Write `test_projection_merge()` in `tests/test_projection.py` before implementing any route.

## Smallest Safe Plan

### Phase 1: Database layer
**Files in scope:** `app/db.py`, `schema.sql`

- Create `schema.sql` with `events` and `projections` tables plus required indexes
- Create `app/db.py` with:
  - `get_db()` context manager (sqlite3 connection, WAL mode, row_factory)
  - `init_db()` to execute schema.sql
  - `append_event(entity_id, entity_type, event_type, payload_dict, actor=None)` — normalizes timestamp, runs `BEGIN IMMEDIATE`, inserts event, upserts projection (shallow merge), returns new event row
  - `get_projection(entity_id)` — SELECT from projections
  - `get_events(entity_id=None, entity_type=None, event_type=None, after_id=None, before=None, since=None, limit=50)` — builds query dynamically, returns (rows, next_cursor)

**Gate:** `test_db.py` passes — append, merge, cursor pagination all verified at the DB layer before routes are written.

### Phase 2: Flask routes
**Files in scope:** `app/routes.py`, `app/app.py`

- `POST /events` — accepts `{entity_id, entity_type, event_type, payload, actor}`, calls `append_event`, returns 201 with event JSON
- `GET /events` — query params: `entity_id`, `entity_type`, `event_type`, `since` (YYYY-MM-DD HH:MM:SS), `before` (same), `after` (cursor id), `limit` (default 50, max 200). Returns `{events: [...], next_cursor: id|null}`
- `GET /entities/<entity_id>/events` — shorthand for `/events?entity_id=<id>`, same pagination
- `GET /entities/<entity_id>/projection` — returns `{entity_id, entity_type, state, version, updated_at}` from projections table
- `GET /entities/<entity_id>/history` — replays full event stream for entity in ascending order, returns all events (no pagination — this is for reconstruction)

**Gate:** All 5 routes return correct HTTP status codes and response shapes per acceptance criteria.

### Phase 3: Entry point + tests
**Files in scope:** `app/__init__.py`, `run.py`, `tests/test_routes.py`, `tests/test_projection.py`

- Wire up Flask app, call `init_db()` on startup
- `tests/test_projection.py` — test projection merge logic (patch semantics, key overwrite, version increment)
- `tests/test_routes.py` — test all 5 routes with real SQLite (no mocks), covering happy path + edge cases (empty entity, cursor pagination boundary, time range filtering)

**Gate:** `pytest` passes with zero failures.

## Rejected Options

- **Option C (async projection worker):** Too complex for SQLite/Flask scope; projection can lag, risking stale audit reads. Synchronous write is correct here.
- **Option A (no projection table):** O(N) replay on every projection read is unacceptable for entities with large event histories.
- **Offset pagination:** Unstable under concurrent appends — a new event shifts all offsets. Cursor (id-based) is stable.
- **JSON validation per event_type:** Out of scope; free-form payload keeps the service generic. Callers own their schema.

## Risks And Unknowns

1. **Shallow merge semantics** — if a caller passes `{"status": "deleted"}` and a later event passes `{"status": "active", "name": "foo"}`, the name field appears. Callers must understand this. Documented in API contract; not enforced server-side.
2. **SQLite single-writer bottleneck** — under high write concurrency, `BEGIN IMMEDIATE` will serialize writes. Acceptable for this scope; would need Postgres for high-throughput.
3. **`since`/`before` time range with string comparison** — works correctly only if timestamps are consistently formatted as `YYYY-MM-DD HH:MM:SS`. Any deviation breaks range queries silently.
4. **`limit` upper bound** — must cap at 200 to prevent unbounded result sets; enforce server-side.

## Most Likely Way This Plan Is Wrong

The shallow-merge projection logic silently produces wrong state if callers mix patch and full-snapshot payloads. A caller who sends `{"state": {"all": "fields"}}` expecting a full replace will instead get merge-accumulated state. This is the #1 correctness risk. Mitigation: document the contract in the API response and in a `README.md`.

## Scope Creep Check

Compare against brainstorm: `docs/brainstorms/2026-04-05-event-sourced-audit-log.md`

Everything in this plan is in the brainstorm. Not included (and not in brainstorm):
- Authentication / API keys
- Event schema validation per type
- Snapshot/watermark optimization
- Background worker
- Multi-tenancy

## Acceptance Criteria

- [ ] `POST /events` with valid body returns 201 and JSON with `id`, `entity_id`, `entity_type`, `event_type`, `payload`, `actor`, `created_at`
- [ ] `POST /events` with missing required field (`entity_id`, `entity_type`, `event_type`, `payload`) returns 400
- [ ] `GET /events?entity_id=X` returns only events for entity X, ordered by `id` ascending
- [ ] `GET /events?since=2026-01-01 00:00:00&before=2026-12-31 23:59:59` returns events in that time range
- [ ] `GET /events?after=<id>&limit=10` returns at most 10 events with `id > after`, and `next_cursor` is null when no more events exist
- [ ] `GET /entities/<id>/projection` returns `{entity_id, entity_type, state, version, updated_at}` where `state` is the shallow-merged result of all payloads
- [ ] `GET /entities/<id>/projection` for unknown entity returns 404
- [ ] `GET /entities/<id>/history` returns all events for entity in ascending `id` order
- [ ] Appending 3 events to the same entity increments `version` to 3 and `state` reflects shallow merge of all 3 payloads
- [ ] `events` table has zero UPDATE or DELETE statements anywhere in the codebase (grep check)
- [ ] DB initialized with WAL mode (`PRAGMA journal_mode=WAL` confirmed on connection)

## Tests Or Checks

```bash
# Run all tests
pytest tests/ -v

# Grep to confirm no UPDATE/DELETE on events table
grep -rn "UPDATE events\|DELETE FROM events\|DELETE events" app/

# Confirm WAL mode is set
python -c "import sqlite3; c = sqlite3.connect('/tmp/test_audit.db'); c.execute('PRAGMA journal_mode=WAL'); print(c.execute('PRAGMA journal_mode').fetchone())"

# Manual smoke test (server running on :5000)
curl -s -X POST http://localhost:5000/events \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"user-1","entity_type":"user","event_type":"created","payload":{"name":"Alice","email":"a@example.com"}}' | python -m json.tool

curl -s http://localhost:5000/entities/user-1/projection | python -m json.tool
```

## Rollback Plan

This is a new project with no existing data. Rollback = delete the repo directory. No migrations to reverse, no shared state to unwind.

If deployed: drop the SQLite file. The service is stateless beyond the DB file. No external side effects.

## Claude Code Handoff Prompt

```text
Read docs/plans/2026-04-05-feat-event-sourced-audit-log-plan.md.

PREREQUISITE: Write tests/test_projection.py with test_projection_merge() FIRST
to validate patch-semantics shallow merge before implementing any routes.

Repos and files in scope:
  - schema.sql
  - app/db.py
  - app/routes.py
  - app/app.py
  - app/__init__.py
  - run.py
  - tests/test_db.py
  - tests/test_projection.py
  - tests/test_routes.py

Scope boundaries:
  - DO NOT add authentication, API keys, or multi-tenancy
  - DO NOT add event schema validation per event_type
  - DO NOT add snapshot/watermark optimization
  - DO NOT add a background projection worker
  - events table rows must NEVER be UPDATEd or DELETEd
  - All timestamps stored as 'YYYY-MM-DD HH:MM:SS' (no T, no Z)

Key corrections from plan review:
  [FILL IN after Codex review]

Acceptance criteria:
  - POST /events returns 201 with full event JSON
  - POST /events with missing required fields returns 400
  - GET /events supports entity_id, entity_type, event_type, since, before, after (cursor), limit filters
  - GET /entities/<id>/projection returns shallow-merged state at version N
  - GET /entities/<id>/projection for unknown entity returns 404
  - GET /entities/<id>/history returns all events ascending by id
  - version increments by 1 per event appended
  - WAL mode confirmed on DB init

Required checks:
  pytest tests/ -v
  grep -rn "UPDATE events\|DELETE FROM events" app/

Stop conditions:
  - If the shallow-merge behavior produces ambiguous results for any test case, stop and flag before proceeding
  - If SQLite WAL mode cannot be confirmed on the test DB, stop
```

## Sources

- Brainstorm: docs/brainstorms/2026-04-05-event-sourced-audit-log.md

## Feed-Forward

- **Hardest decision:** Pinning payload semantics as patch (partial update) rather than allowing callers to choose. A generic service would support both modes, but that doubles the projection logic complexity.
- **Rejected alternatives:** Full-snapshot payload mode (caller sends complete state each time) — rejected because it breaks the audit trail (you can't tell what changed); async projection worker — rejected for consistency reasons with SQLite.
- **Least confident:** The `GET /events` dynamic query builder (multiple optional filters combined with cursor pagination) is the most complex piece of code in this plan. Combining `since`, `before`, `entity_id`, `event_type`, and `after` filters correctly without SQL injection risk requires careful parameterization.
