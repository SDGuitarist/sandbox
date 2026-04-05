---
title: "Flask URL Shortener API"
date: 2026-04-05
status: complete
origin: "conversation"
---

# Flask URL Shortener API — Brainstorm

## Problem
Developers and users need a way to turn long URLs into short, shareable links. The API must support creating short links, redirecting visitors to original URLs, and tracking how many times each link has been clicked.

## Context
- No existing codebase — greenfield project
- Stack: Python + Flask + SQLite (explicitly required)
- Must expose three endpoints: POST /shorten, GET /<code> (redirect), GET /stats/<code>
- SQLite is simple and sufficient for a single-server deployment
- Short codes must be unique; collisions must be handled

## Options

### Option A: Random base62 short codes (6 chars)
Generate a random 6-character string from [a-zA-Z0-9] (62^6 ≈ 56 billion combos). On collision, regenerate.
- Pros: Simple, unpredictable codes, no sequential enumeration
- Cons: Tiny collision chance grows with scale; retry loop needed

### Option B: Hash-based short codes (MD5/SHA truncated)
Hash the original URL, take first 6–8 chars of the hex digest.
- Pros: Deterministic — same URL always produces same code (dedup built-in)
- Cons: Hex-only (0-9a-f), shorter namespace; two URLs with same hash prefix collide

### Option C: Auto-increment ID encoded in base62
Use SQLite's autoincrement primary key, encode to base62.
- Pros: Zero collision risk, compact, deterministic
- Cons: Sequential — codes are guessable; slightly more complex encode/decode

## Tradeoffs
- **Uniqueness vs. simplicity:** Option A is simplest but needs a retry loop. Option C is collision-free but sequential.
- **Dedup vs. always-new:** Option B naturally deduplicates the same URL; Options A/C create a new code each time.
- **Click tracking:** A separate `clicks` table (log of each hit) is flexible but heavier. A simple `click_count` integer column on the links table is simpler and sufficient for this scope.

## Decision
**Option A (random base62, 6 chars)** with a retry-on-collision loop. It's the most natural URL shortener behavior, produces unguessable codes, and collisions at small scale are negligible. Use a single `links` table with a `click_count` column for stats — no separate clicks log needed for this scope.

Schema:
```
links(id INTEGER PK, original_url TEXT, short_code TEXT UNIQUE, click_count INTEGER DEFAULT 0, created_at TIMESTAMP)
```

Endpoints:
- `POST /shorten` — body `{"url": "..."}`, returns `{"short_code": "...", "short_url": "..."}`
- `GET /<code>` — 302 redirect to original URL, increments click_count
- `GET /stats/<code>` — returns `{"short_code": "...", "original_url": "...", "click_count": N, "created_at": "..."}`

## Open Questions
- Should 301 (permanent) or 302 (temporary) redirect be used? 302 is safer — allows click counting to keep working (browsers cache 301s and skip the server).
- Should duplicate URLs be detected and return the existing code? For now: no — always create a new code (simpler).
- Input validation: require `http://` or `https://` prefix? Yes — basic validation.

## Feed-Forward
- **Hardest decision:** 301 vs 302 redirect. Chose 302 so click counts remain accurate (browsers bypass server on 301 after first visit).
- **Rejected alternatives:** Hash-based codes (Option B) — hex-only namespace is smaller and offers no meaningful advantage here. Auto-increment (Option C) — sequential codes are guessable.
- **Least confident:** Thread safety of `click_count` increment in SQLite under concurrent requests. SQLite's write locking should handle it at small scale, but worth noting in the plan.
