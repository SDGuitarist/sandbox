---
title: "Chat Room API"
date: 2026-04-05
tags: [chat, rate-limiting, flask, sqlite, pagination, membership]
module: chat-room-api
lesson: "Merge rate-limit check and message insert into a single BEGIN IMMEDIATE transaction to eliminate the TOCTOU gap; executescript() in init_db must bypass get_db() because it issues an implicit COMMIT."
origin_plan: docs/plans/2026-04-05-feat-chat-room-api-plan.md
origin_brainstorm: docs/brainstorms/2026-04-05-chat-room-api.md
---

# Chat Room API

## Problem

Build a Flask + SQLite REST API for multi-room chat: create/list rooms, join/leave (membership), post messages with fixed-window per-user rate limiting, and poll/list messages with cursor pagination.

## Solution

- `rooms`, `memberships`, `messages`, `rate_limits` tables in SQLite with WAL mode
- 6 Flask routes: `POST/GET /rooms`, `POST /rooms/<id>/join`, `POST /rooms/<id>/leave`, `POST/GET /rooms/<id>/messages`
- `rate_limit_and_post()` combines rate-limit check + message insert in a single `BEGIN IMMEDIATE` transaction — eliminates TOCTOU gap
- Cursor pagination: `id > after_id`, `next_cursor = messages[limit-1]["id"]`
- `init_db()` uses a raw connection (not `get_db`) to avoid `executescript` implicit COMMIT footgun
- Input validation: max-length on `name` (100), `user_id` (64), `content` (2000); whitespace-only rejection

## Why This Approach

- **Integer id cursor over timestamp cursor:** Timestamps are not unique under concurrent inserts. Integer autoincrement IDs are monotonic and collision-free.
- **Offset pagination rejected:** Unstable under concurrent inserts — new messages shift all offsets, causing skips and re-reads.
- **Unified poll+history endpoint:** `GET /rooms/<id>/messages?after=<id>` handles both polling (caller advances cursor) and history (no cursor = from start). Separate endpoints add complexity with no benefit.
- **Global per-user rate limit over per-room:** Simpler schema (one row per user), prevents room-hopping abuse, and still achieves flood prevention goal.

## Risk Resolution

> **Flagged risk:** "Under concurrent posts from the same user, two requests racing inside BEGIN IMMEDIATE on the rate_limits table may double-count if window reset and count increment are not fully atomic."

> **What actually happened:** The `check_rate_limit()` function was correctly atomic internally, but the route called it separately from `post_message()`, creating a TOCTOU gap between the two independent transactions. Two concurrent requests could both pass `check_rate_limit` before either inserted a message. Review caught this.

> **Lesson learned:** Per-function atomicity is not enough — the route-level sequence of check-then-act must also be in one transaction. Merge `check_rate_limit` and `post_message` into `rate_limit_and_post()` with a single `BEGIN IMMEDIATE`. The plan's verify-first test only covered sequential calls; TOCTOU gaps require the caller to also be atomic.

## Key Decisions

| Decision | Choice | Reason |
|---|---|---|
| Cursor type | Integer message id | Monotonic, no collision, stable under concurrent inserts |
| Rate limit + insert | Single BEGIN IMMEDIATE (`rate_limit_and_post`) | Eliminates TOCTOU between check and act |
| init_db connection | Raw sqlite3.connect, not get_db | executescript() issues implicit COMMIT, bypassing context manager |
| Reading messages | Public (no membership check) | Audit/history use cases; membership only required for posting |
| join_room duplicate detection | Pre-check membership before INSERT | Distinguishes FK violation (nonexistent room) from duplicate member |

## Gotchas

1. **TOCTOU in rate limiting:** Calling `check_rate_limit()` then `post_message()` as two separate transactions creates a race window. Use `rate_limit_and_post()` which wraps both in one `BEGIN IMMEDIATE`.

2. **`executescript()` implicit COMMIT:** Calling `conn.executescript(schema)` inside a `get_db` context silently commits and releases any pending transaction. Always use a raw connection for `init_db` — never route through `get_db`.

3. **Cursor off-by-one (correct pattern):** `next_cursor = messages[limit-1]["id"]` is correct. The next call uses `id > cursor`, which starts after the last returned row. Using `messages[limit]["id"]` (the first un-returned row) would skip that row on the next page.

4. **`user_id` whitespace validation:** `str(body["user_id"]).strip()` then empty check — a user_id of `"   "` passes key-presence checks but must be rejected explicitly.

5. **`join_room` FK vs duplicate distinction:** Check `SELECT 1 FROM memberships WHERE room_id=? AND user_id=?` first; if found, return False (already member). Then INSERT — if it raises IntegrityError, it's a FK violation (nonexistent room), not a duplicate. Without the pre-check, both cases return False and callers can't distinguish them.

6. **`Retry-After` header on 429:** Include `Retry-After: <window_seconds>` so clients know when to retry without polling.
