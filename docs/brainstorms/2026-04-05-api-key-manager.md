---
title: "API Key Management Service"
date: 2026-04-05
status: complete
origin: "conversation"
---

# API Key Management Service — Brainstorm

## Problem
Services need a way to issue API keys to clients, enforce per-key rate limits (requests per minute/hour/day), validate keys on incoming requests via middleware, and track usage statistics. Currently this is often ad-hoc or repeated across projects.

## Context
- Stack: Python + Flask + SQLite (explicitly required)
- Prior art in this workspace: secrets.choice() for key gen, WAL+timeout for concurrency, return-secret-once pattern, atomic SQL counters
- "Validate keys as middleware" — Flask `before_request` hook checks the key on every request
- Rate limiting needs a sliding or fixed window counter — SQLite-backed is simplest
- Usage stats: per-key total requests, last-used timestamp, per-day counts

## Options for Rate Limiting Window

### Option A: Fixed window counter (reset at calendar boundary)
Store `request_count` + `window_start` per key. If `window_start` is in the current window, check count; otherwise reset. Simple but allows burst at window boundary (60 req at end of minute + 60 at start = 120 in 2 seconds).
- Pros: Simple, one row per key, no history table
- Cons: Burst at window reset

### Option B: Sliding window log (per-request timestamp log)
Store every request timestamp; count rows in the last N seconds. Accurate but expensive.
- Pros: Accurate sliding window
- Cons: Unbounded table growth; expensive COUNT query on every request

### Option C: Sliding window counter (two-bucket approximation)
Two counters: current window count + previous window count. Rate = previous * (remaining_fraction) + current. Good approximation without log table.
- Pros: More accurate than fixed, still O(1)
- Cons: More complex implementation; two DB columns per rate limit

## Decision for Rate Limiting
**Option A (fixed window)** — simplest, sufficient for this scope. Document the burst limitation. Use a `minute` window as default (configurable per key). Store `rate_limit_requests` (max), `rate_limit_window` (seconds), `window_count` (current period count), `window_start` (when current window began) on the api_keys row itself.

## Options for Key Format

### Option A: Random base62 (32 chars)
`secrets.choice()` over [a-zA-Z0-9], 32 chars = 62^32 ≈ 2^190 — unguessable.

### Option B: Prefixed key (e.g., `sk_live_<random>`)
Common pattern (Stripe, GitHub). Prefix identifies key type, easier to scan logs.

## Decision for Key Format
**Option B (prefixed)** — `ak_<32 random base62 chars>` where `ak_` = API key prefix. Makes keys easy to identify in logs. Total length = 35 chars.

## Data Model

### `api_keys` table
```
id               TEXT PRIMARY KEY  (UUID)
key_hash         TEXT UNIQUE       (SHA256 of the key — never store plaintext)
prefix           TEXT              (first 8 chars of key, for display/lookup hint)
name             TEXT              (human label, e.g., "Production client")
is_active        INTEGER DEFAULT 1
rate_limit_rpm   INTEGER DEFAULT 60   (requests per minute; 0 = unlimited)
window_count     INTEGER DEFAULT 0
window_start     TIMESTAMP
total_requests   INTEGER DEFAULT 0
last_used_at     TIMESTAMP
created_at       TIMESTAMP
expires_at       TIMESTAMP           (nullable; NULL = never expires)
```

Key is returned once at creation. Only `key_hash` is stored. `prefix` (first 8 chars) is stored for display.

### No separate usage_stats table for now
Embed `total_requests`, `last_used_at`, `window_count`, `window_start` directly on `api_keys`. Simpler, one-row update per request. If per-day breakdown is needed, add a separate `usage_log` table later.

## API Surface

- `POST /keys` — create API key (name, rate_limit_rpm, expires_at)
- `GET /keys` — list all keys (key_hash redacted, prefix shown)
- `GET /keys/<id>` — get key details
- `DELETE /keys/<id>` — revoke (soft delete: `is_active=0`)
- `POST /keys/validate` — validate a key + check rate limit + increment counter (used by middleware)
- `GET /keys/<id>/stats` — usage stats for a key

## Middleware Approach
Middleware (`before_request`) reads `Authorization: Bearer <key>` or `X-API-Key: <key>`, calls `POST /keys/validate` internally (or calls the DB directly if this is the same app), returns 401/429 as appropriate.

For this service: expose `POST /keys/validate` as an endpoint that external services call. The service itself doesn't wrap other routes — it IS the key management service, not a proxy. Middleware is a `before_request` demo route that shows how to integrate.

## Open Questions
- Hash algorithm for key storage: SHA-256 (fast, one-way, no need for bcrypt since API keys are already random and high-entropy)
- Rate limit window: per-minute as default, stored as `rate_limit_rpm` (requests per minute)
- Atomic rate limit check: use `UPDATE ... WHERE window_start = ? AND window_count < rate_limit_rpm` to atomically check-and-increment in one SQL statement

## Feed-Forward
- **Hardest decision:** Whether to include a separate usage log table for per-day stats, or embed everything in the key row. Chose embedded for simplicity — a `usage_log` table is a natural deferred item.
- **Rejected alternatives:** Sliding window log (unbounded table growth), two-bucket sliding window (complex for this scope), storing plaintext keys (never — always hash).
- **Least confident:** The atomic rate limit check via a single UPDATE — need to verify that SQLite's serialized writes make `UPDATE ... WHERE window_count < rate_limit_rpm` truly atomic (no TOCTOU between the count check and the increment). This is the same concurrency risk as the job-queue claim.
