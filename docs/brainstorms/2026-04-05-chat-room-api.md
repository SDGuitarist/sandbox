---
title: "Chat Room API"
date: 2026-04-05
status: complete
origin: "conversation"
---

# Chat Room API — Brainstorm

## Problem
Build a REST API for a multi-room chat system. Users need to:
1. Create and list rooms
2. Join and leave rooms (membership tracking)
3. Post messages to rooms they've joined
4. Poll for new messages efficiently using a cursor (long-poll or simple GET since last id)
5. List message history with cursor pagination
6. Be rate-limited per user using a fixed-window pattern (e.g., N messages per minute)

Without a cursor-based poll endpoint, clients must poll every message ever sent. Without rate limiting, a single user can flood a room.

## Context
- Stack: Flask + SQLite
- Same project as prior services — follow existing `get_db()` context manager pattern
- Prior lessons:
  - Cursor pagination: `id > cursor`, next_cursor = last returned row's id (audit-log lesson)
  - Fixed-window rate limiting: reset+increment must be atomic in `BEGIN IMMEDIATE` (api-key-manager lesson)
  - Timestamps as `YYYY-MM-DD HH:MM:SS` — ISO8601 T-separator breaks SQLite string comparison
  - WAL mode on every connection for concurrent reads
  - `db_path` through `current_app.config["DB_PATH"]` not a module-level constant

## Options

### Option A: Single messages table, cursor = message id, membership in separate table
`rooms` table + `memberships` table + `messages` table + `rate_limits` table.
Poll endpoint: `GET /rooms/<id>/messages?after=<last_id>` returns messages where `id > last_id`.
History: same endpoint with `limit` and cursor.

**Pros:** Simple schema. Cursor is the message `id` (autoincrement, monotonic, stable under concurrent inserts). Poll and history share the same endpoint. One endpoint for both cases, just different `limit` and `after` params.
**Cons:** No push — client must poll. Acceptable for this scope.

### Option B: Separate poll endpoint with timestamp cursor, history endpoint with offset
Poll: `GET /rooms/<id>/poll?since=<timestamp>` returns messages where `created_at > timestamp`.
History: `GET /rooms/<id>/history?page=2&limit=50` uses offset.

**Pros:** Timestamp cursors are human-readable. Offset pagination is familiar.
**Cons:** Timestamp cursors are not unique under concurrent inserts (two messages same second). Offset pagination is unstable — a new message shifts all offsets. Both flaws from prior lesson docs.

### Option C: WebSocket for push, REST for history
Real-time push via WebSocket, REST only for history.

**Pros:** True real-time.
**Cons:** Massively out of scope for Flask + SQLite. No WebSocket support in Flask without flask-socketio. Rejected immediately.

## Tradeoffs
| Concern | Option A | Option B | Option C |
|---|---|---|---|
| Poll stability | Stable (integer id) | Unstable (timestamp collisions) | N/A |
| History stability | Stable (cursor) | Unstable (offset) | Stable |
| Endpoint count | 1 (shared) | 2 | Many |
| Complexity | Low | Medium | High |
| SQLite fit | Excellent | Good | Poor |

**What matters most:** Correctness (no dropped/duplicate messages at cursor boundaries), simplicity, and consistency with prior service patterns.

## Decision
**Option A: Single endpoint, integer id cursor.**

Schema sketch:
```sql
CREATE TABLE rooms (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE memberships (
    room_id    INTEGER NOT NULL REFERENCES rooms(id),
    user_id    TEXT NOT NULL,
    joined_at  TEXT NOT NULL,
    PRIMARY KEY (room_id, user_id)
);

CREATE TABLE messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id    INTEGER NOT NULL REFERENCES rooms(id),
    user_id    TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_messages_room_id ON messages(room_id, id);

CREATE TABLE rate_limits (
    user_id      TEXT NOT NULL,
    window_start TEXT NOT NULL,
    count        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id)
);
```

Endpoints:
- `POST /rooms` — create room
- `GET /rooms` — list rooms
- `POST /rooms/<id>/join` — join room
- `POST /rooms/<id>/leave` — leave room
- `POST /rooms/<id>/messages` — post message (rate limited)
- `GET /rooms/<id>/messages` — poll/history: `?after=<id>&limit=50`

Rate limiting: `WINDOW_SECONDS = 60`, `MAX_MESSAGES = 20`. Inside `BEGIN IMMEDIATE`: check window expired → reset count + window_start; check count < MAX_MESSAGES → increment; else 429.

## Open Questions
1. Do non-members get a 403 on `GET /rooms/<id>/messages`? → No — reading is public. Only posting requires membership.
2. Should `leave` be idempotent (no error if not a member)? → Yes — DELETE FROM memberships WHERE ...; if rowcount=0, still 200.
3. Rate limit per user globally or per user per room? → Global per user (simpler, prevents room-hopping abuse).
4. Should `name` in rooms be case-sensitive? → Yes — store as-is, let UNIQUE constraint handle deduplication.
5. Should old rate_limits rows be cleaned up? → No — one row per user (upserted), O(users) table size, acceptable.

## Feed-Forward
- **Hardest decision:** Whether the poll and history endpoints should be the same route or separate. Chose unified — `GET /rooms/<id>/messages?after=<id>` serves both polling (caller tracks cursor) and history (no cursor = from beginning). This means `after=0` or omitting `after` returns from the start.
- **Rejected alternatives:** Timestamp cursors (not unique under concurrent inserts), offset pagination (unstable under concurrent inserts), WebSocket (out of scope), separate poll/history endpoints (unnecessary complexity).
- **Least confident:** The rate limit table has one row per user (upserted on each message post). Under concurrent posts from the same user, two requests racing inside `BEGIN IMMEDIATE` will serialize correctly — but the first one to get the lock will see `count=0` if they race on window reset. Need to verify that `BEGIN IMMEDIATE` inside `get_db(immediate=True)` actually prevents the second racer from double-counting. This is the same pattern as the API key manager and it worked there — but it's the highest-risk piece of this plan.
