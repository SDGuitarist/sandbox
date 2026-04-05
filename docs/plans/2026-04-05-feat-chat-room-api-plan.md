---
title: "Chat Room API"
type: feat
status: draft
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-chat-room-api.md
feed_forward:
  risk: "Under concurrent posts from the same user, two requests racing inside BEGIN IMMEDIATE on the rate_limits table may double-count if window reset and count increment are not fully atomic. Must verify BEGIN IMMEDIATE prevents this."
  verify_first: true
---

# feat: Chat Room API

## Enhancement Summary

**Deepened on:** 2026-04-05
**Research agents used:** solution-doc-searcher (api-key-manager, audit-log, job-queue, webhook-delivery, url-shortener)

### Key Corrections From Research
- Fixed-window rate limiting: window reset + count increment must be a single `BEGIN IMMEDIATE` transaction (api-key-manager lesson)
- Cursor pagination: `next_cursor = messages[limit-1]["id"]`; next call uses `id > cursor` (audit-log lesson — confirmed correct against off-by-one trap)
- Timestamps: `YYYY-MM-DD HH:MM:SS` at write time; validate at route layer with `datetime.strptime` for any timestamp inputs
- `db_path` through `current_app.config.get("DB_PATH")` not a module-level constant
- `get_db(immediate=True)` for all write operations needing atomicity

## What Must Not Change

1. **Rate limit atomicity** — window reset and count increment must be inside the same `BEGIN IMMEDIATE` transaction; no two-step approach
2. **Cursor stability** — pagination uses message `id` (autoincrement integer), never offset or timestamp
3. **Timestamp format** — all `created_at` values stored as `YYYY-MM-DD HH:MM:SS`
4. **WAL mode** — enabled on every connection
5. **Membership enforcement on POST** — only joined members may post messages; non-members get 403
6. **Reading is public** — `GET /rooms/<id>/messages` requires no membership check

## Prior Phase Risk

> "Under concurrent posts from the same user, two requests racing inside BEGIN IMMEDIATE on the rate_limits table may double-count if window reset and count increment are not fully atomic."

**Resolution:** Use the exact pattern from api-key-manager: inside `BEGIN IMMEDIATE`, read current row, check if window expired (if yes, reset count=0 and window_start=now), check count < MAX, increment. All in one transaction. The verify-first action is writing `tests/test_rate_limit.py` with a sequential test (not concurrent — SQLite serializes BEGIN IMMEDIATE) confirming: first 20 posts succeed, 21st returns 429, window reset after 60s restores count.

**Verify first action:** Write `tests/test_rate_limit.py` with `test_rate_limit_window_exhaustion()` and `test_rate_limit_window_reset()` before implementing any route.

## Smallest Safe Plan

### Phase 1: Database layer
**Files in scope:** `chat/schema.sql`, `chat/db.py`

- `chat/schema.sql`: rooms, memberships, messages, rate_limits tables + index on `messages(room_id, id)`
- `chat/db.py`:
  - `get_db(path=None, immediate=False)` — context manager, WAL, row_factory
  - `init_db(path=None)` — reads schema.sql via pathlib
  - `create_room(name, created_by, db_path=None)` → room dict or raises IntegrityError on duplicate name
  - `list_rooms(db_path=None)` → list of room dicts
  - `join_room(room_id, user_id, db_path=None)` → True (joined) or False (already member)
  - `leave_room(room_id, user_id, db_path=None)` → True (left) or False (was not member)
  - `is_member(room_id, user_id, db_path=None)` → bool
  - `post_message(room_id, user_id, content, db_path=None)` → message dict
  - `get_messages(room_id, after_id=None, limit=50, db_path=None)` → (list, next_cursor)
  - `check_rate_limit(user_id, window_seconds=60, max_count=20, db_path=None)` → True (allowed) or False (exceeded); increments counter atomically inside BEGIN IMMEDIATE

**Gate:** `tests/test_db.py` and `tests/test_rate_limit.py` pass — all DB functions verified before routes.

### Phase 2: Flask routes
**Files in scope:** `chat/routes.py`, `chat/app.py`, `chat/__init__.py`

- `POST /rooms` body: `{name, created_by}` → 201 + room JSON; 400 on missing fields; 409 on duplicate name
- `GET /rooms` → 200 + `{rooms: [...]}`
- `POST /rooms/<room_id>/join` body: `{user_id}` → 200 + `{joined: true/false}`; 404 if room not found
- `POST /rooms/<room_id>/leave` body: `{user_id}` → 200 + `{left: true/false}`; 404 if room not found
- `POST /rooms/<room_id>/messages` body: `{user_id, content}` → 201 + message JSON; 403 if not member; 429 if rate limited; 400 on missing fields
- `GET /rooms/<room_id>/messages` query: `after` (cursor id), `limit` (default 50, max 200) → 200 + `{messages: [...], next_cursor: id|null}`; 404 if room not found

**Gate:** All 6 routes return correct HTTP status codes and response shapes.

### Phase 3: Tests
**Files in scope:** `tests/test_rate_limit.py`, `tests/test_db.py`, `tests/test_routes.py`

- `tests/test_rate_limit.py` — verify-first: window exhaustion (20 allowed, 21st → 429 equivalent), window reset
- `tests/test_db.py` — all DB functions: create/list rooms, join/leave, post, get_messages cursor
- `tests/test_routes.py` — all 6 routes with real SQLite, happy path + edge cases

**Gate:** `pytest tests/ -v` passes with zero failures.

## Rejected Options

- **Timestamp cursor (Option B):** Not unique under concurrent inserts — two messages posted in the same second produce the same cursor, causing missed or duplicated messages
- **Offset pagination:** Unstable — a new message shifts all offsets; clients on page 2 will re-read or skip messages
- **WebSocket (Option C):** Out of scope for Flask + SQLite; no flask-socketio
- **Per-room rate limiting:** More complex schema; global per-user rate limit still prevents flooding
- **Separate poll + history endpoints:** Unnecessary — unified `GET /rooms/<id>/messages?after=<id>` handles both

## Risks And Unknowns

1. **Rate limit under concurrent load** — BEGIN IMMEDIATE serializes writes; under high concurrency the second writer waits up to `busy_timeout`. Acceptable for SQLite scope.
2. **Room name uniqueness** — enforced by UNIQUE constraint; catch `IntegrityError` in `create_room` and surface as 409
3. **Message content length** — no explicit limit in schema; add server-side validation (e.g., max 2000 chars) to prevent large row storage
4. **Rate limit row cleanup** — one row per user, upserted each time; O(users) table size, no cleanup needed

## Most Likely Way This Plan Is Wrong

The `check_rate_limit` function is the only place where two DB operations (read current state, write new state) must be atomic. If the `BEGIN IMMEDIATE` pattern is implemented incorrectly (e.g., called outside the context manager, or the window comparison uses the wrong time format), rate limiting will silently fail — either always allowing or always blocking. The verify-first test catches this.

## Scope Creep Check

Compare against brainstorm: `docs/brainstorms/2026-04-05-chat-room-api.md`

Everything in the plan matches the brainstorm. Not included (and not in brainstorm):
- Authentication / session tokens
- Room deletion
- Message editing or deletion
- WebSocket / push notifications
- Per-room rate limits
- Presence / typing indicators

## Acceptance Criteria

- [ ] `POST /rooms` with valid body returns 201 with room JSON (`id`, `name`, `created_by`, `created_at`)
- [ ] `POST /rooms` with duplicate name returns 409
- [ ] `GET /rooms` returns `{rooms: [...]}` with all rooms
- [ ] `POST /rooms/<id>/join` returns 200 with `{joined: true}` for new member, `{joined: false}` for existing
- [ ] `POST /rooms/<id>/leave` returns 200 with `{left: true}` for member, `{left: false}` for non-member
- [ ] `POST /rooms/<id>/messages` from a member returns 201 with message JSON
- [ ] `POST /rooms/<id>/messages` from a non-member returns 403
- [ ] `POST /rooms/<id>/messages` after 20 messages in current window returns 429
- [ ] `GET /rooms/<id>/messages` without `after` returns messages from beginning with cursor pagination
- [ ] `GET /rooms/<id>/messages?after=<id>` returns only messages with id > after
- [ ] `GET /rooms/<id>/messages` cursor pagination: no rows skipped or duplicated across pages
- [ ] `GET /rooms/<nonexistent>/messages` returns 404
- [ ] Message content > 2000 chars returns 400

## Tests Or Checks

```bash
pytest tests/ -v
grep -rn "UPDATE messages\|DELETE FROM messages" chat/
```

## Rollback Plan

New project, no existing data. Rollback = delete `chat/` directory and `tests/`. No migrations to reverse.

## Claude Code Handoff Prompt

```text
Read docs/plans/2026-04-05-feat-chat-room-api-plan.md.

PREREQUISITE: Write tests/test_rate_limit.py with test_rate_limit_window_exhaustion()
and test_rate_limit_window_reset() FIRST before implementing any routes.

Repos and files in scope:
  - chat/schema.sql
  - chat/db.py
  - chat/routes.py
  - chat/app.py
  - chat/__init__.py
  - run_chat.py
  - tests/test_rate_limit.py
  - tests/test_db.py (extend with chat tests)
  - tests/test_routes.py (extend with chat tests)

Scope boundaries:
  - DO NOT add authentication or session tokens
  - DO NOT add WebSocket support
  - DO NOT add room deletion or message editing
  - Messages table rows must NOT be UPDATEd or DELETEd
  - All timestamps stored as 'YYYY-MM-DD HH:MM:SS'

Acceptance criteria:
  - POST /rooms → 201 + room JSON; 409 on duplicate name
  - GET /rooms → {rooms: [...]}
  - POST /rooms/<id>/join → 200 + {joined: bool}
  - POST /rooms/<id>/leave → 200 + {left: bool}
  - POST /rooms/<id>/messages → 201 + message; 403 non-member; 429 rate limited
  - GET /rooms/<id>/messages → {messages: [...], next_cursor: id|null}; 404 unknown room
  - Message content > 2000 chars → 400

Required checks:
  pytest tests/ -v
  grep -rn "UPDATE messages\|DELETE FROM messages" chat/

Stop conditions:
  - If BEGIN IMMEDIATE does not correctly serialize rate limit check+increment, stop and flag
  - If cursor pagination skips rows in any test scenario, stop and flag
```

## Sources

- Brainstorm: docs/brainstorms/2026-04-05-chat-room-api.md

## Feed-Forward

- **Hardest decision:** Unified poll+history endpoint vs. separate endpoints. Chose unified — `GET /rooms/<id>/messages?after=<id>` is simpler and the cursor handles both use cases cleanly.
- **Rejected alternatives:** Timestamp cursors, offset pagination, WebSocket, per-room rate limits, separate poll/history endpoints.
- **Least confident:** The `check_rate_limit` atomicity under concurrent posts from the same user. The BEGIN IMMEDIATE pattern worked in api-key-manager, but that used a single-step rate limit; here the window-reset branch adds a conditional UPDATE that must stay inside the same transaction.
