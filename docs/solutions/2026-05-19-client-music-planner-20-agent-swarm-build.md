---
title: "Client Music Planner: 20-Agent Swarm Build"
date: 2026-05-19
category: swarm-builds
tags: [flask, sqlite, swarm, 20-agents, token-auth, drag-and-drop, portal, two-sided]
module: client-music-planner
run: "048"
agents: 20
grade_pending: true
---

# Client Music Planner: 20-Agent Swarm Build (Run 048)

## Problem

Build a two-sided portal where musicians manage their repertoire and create shareable event portals for wedding/event clients. Clients browse, build playlists with drag-and-drop, flag must-play/do-not-play songs, submit song requests, and approve timelines -- all via a token-based URL with no login required. Target: biggest autopilot swarm to date (20 agents, exceeding run 047's 16).

## Solution

Flask + SQLite + Jinja2 + Bootstrap 5 + SortableJS. 20-agent vertical blueprint split with zero merge conflicts. 75 files, ~5,600 lines of code. Full autopilot pipeline: brainstorm -> plan (deepened with 5 research agents) -> spec consistency check -> 20-agent parallel swarm -> assembly merge -> smoke test -> test suite -> 5-agent review -> P1 fixes -> compound.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total agents | 20 |
| Total files | 75 |
| Total lines | ~5,600 |
| Merge conflicts | 0 |
| Assembly fixes | 1 (portal_playlist + repertoire_import rewrite) |
| Contract check failures | 23 (all fixed in 1 assembly-fix pass) |
| Smoke test | 11/11 PASS |
| Test suite | 81/81 PASS |
| Review agents | 5 (security, performance, python, learnings, flow-trace) |
| P1 findings | 4 (all fixed) |
| P2 findings | ~14 (documented, deferred) |
| P3 findings | ~16 (documented, deferred) |
| Prior run comparison | Run 046: 15 agents/B grade, Run 047: 16 agents/A grade |

## Architecture

### Blueprint Vertical Split (20 Agents)

| Agent | Blueprint | Files | Notes |
|-------|-----------|-------|-------|
| core-infra | -- | 10 | App factory, db, models, decorators, filters, schema |
| auth | auth | 4 | Login, register, logout |
| layout-static | -- | 4 | base.html, navbar, flash, CSS |
| repertoire | repertoire | 5 | Song CRUD |
| repertoire-import | repertoire_import | 4 | CSV bulk import with preview |
| events | events | 5 | Event CRUD, token gen, archive |
| event-dashboard | event_dashboard | 3 | Musician views client selections |
| event-export | event_export | 3 | Setlist export (print + CSV) |
| portal-browse | portal_browse | 4 | Client browses repertoire |
| portal-playlist | portal_playlist | 3 | Playlist builder with DnD |
| portal-flags | portal_flags | 2 | Must-play/do-not-play AJAX |
| portal-requests | portal_requests | 3 | Song requests |
| portal-approve | portal_approve | 3 | Approval flow |
| portal-layout | -- | 3 | Portal base template, nav, CSS |
| dashboard | dashboard | 3 | Musician home page |
| api-playlist | api_playlist | 2 | JSON reorder endpoint |
| api-filters | api_filters | 2 | JSON filter endpoint |
| static-assets | -- | 4 | SortableJS, playlist/filter/flag JS |
| tests | -- | 7 | Pytest suite (81 tests) |
| seed-data | -- | 1 | Demo data script |

### Novel Pattern: Token-Based Portal Access

This is the first sandbox build to use token-based URL access (no login required for clients). The pattern:

1. Musician creates event -> `secrets.token_urlsafe(32)` generates portal token
2. Client visits `/portal/<token>` -> `@require_portal_token` decorator validates token, sets `g.portal_event` and `g.portal_is_approved`
3. All 6 portal blueprints depend on `g.portal_event` (set by decorator) -- never re-query
4. Write routes stack `@require_portal_writable` which checks `g.portal_is_approved`
5. After approval, all client writes are blocked (server-side, not just UI)

**Security characteristics:**
- 256-bit random tokens (not derived from user data -- FC19 does not apply)
- 404 for invalid/archived tokens (no information leak)
- `Referrer-Policy: no-referrer` header prevents token leakage
- Token rotation via "Regenerate Link" button

**What worked:** The decorator pattern cleanly separates token validation from route logic. All 6 portal agents used `g.portal_event` consistently (after assembly fix).

**What didn't work initially:** The portal_playlist agent ignored `g.portal_event` and re-queried the event, used wrong column names (`musician_id` vs `user_id`), bypassed model functions, and forgot `db.commit()`. This was caught by the spec contract checker and fully rewritten in the assembly fix.

## Assembly Fix Details

The spec contract checker found 23 failures concentrated in 2 agents:

**portal_playlist (13 failures):**
- Hardcoded `url_prefix='/portal'` in Blueprint constructor (double-prefix `/portal/portal/...`)
- Bypassed all model functions, did direct SQL with wrong column names
- Zero `db.commit()` calls on any write path (silent data loss)
- Referenced nonexistent `portal_landing` blueprint
- Used wrong Jinja block name (`portal_content` vs `content`)
- Used `item_id` form field instead of spec's `song_id`

**repertoire_import (5 failures):**
- Exported `repertoire_import_bp` instead of `bp` (ImportError at startup)
- No `@login_required` on any route
- Called nonexistent `bulk_insert_repertoire` instead of `bulk_create_songs`
- No `get_db(immediate=True)` or `db.commit()` on write path

**Root cause:** Both agents diverged significantly from the spec. portal_playlist appears to have generated code from its understanding of the feature rather than reading the spec's Cross-Boundary Wiring code blocks. repertoire_import had a naming mismatch in its `__init__.py` that cascaded.

**Fix:** Single assembly-fix agent pass rewrote both modules per spec. All 23 failures resolved.

## Review Findings

### P1s Fixed (4)

1. **Bare `except Exception` in portal_playlist** -- Caught all errors including DB corruption, connection failures, and programming bugs, then told the user "Song is already in your playlist." Fixed to catch `sqlite3.IntegrityError` specifically.

2. **Raw exception leakage in repertoire_import** -- `flash(f"Import failed: {e}", "error")` exposed internal error messages (file paths, schema details) to users. Fixed to generic message.

3. **CSS class mismatch: move buttons dead** -- Template used `btn-move-up`/`btn-move-down` but JS queried `.move-up`/`.move-down`. Move buttons (WCAG 2.5.7 accessibility alternative to drag) were permanently non-functional. Found by flow-trace reviewer (cross-file bug invisible to single-file review).

4. **Energy validation range inconsistency** -- Import accepted energy 0-10 but schema CHECK constraint is 1-5. Would produce invalid data that passes import validation but violates DB constraints.

### Notable P2s (Deferred)

- Double DB connection on every portal request (decorator opens + route opens)
- Row-by-row UPDATE/INSERT instead of executemany
- Check-then-act race conditions across separate connections
- No rate limiting on login or portal endpoints
- innerHTML XSS risk in showToast (currently safe but latent)
- List instead of set for playlist_ids lookup (O(n) -> O(1) fix)
- Missing composite index on song(user_id, energy)

## Risk Resolution (Feed-Forward Chain)

**Brainstorm risk:** "Token-based access is novel territory. The @require_portal_token decorator is the critical security boundary."

**What happened:** The decorator itself was implemented correctly by core-infra. But 1 of 6 portal agents (portal_playlist) ignored it entirely and re-queried the event with wrong column names. The spec contract checker caught this before any runtime testing.

**Lesson:** For novel patterns, the decorator/shared-code implementation is not the risk -- the risk is agents not USING it. The spec must include explicit code blocks showing how to call `g.portal_event` (which it did), but agents can still ignore them if they generate code from feature description instead of reading the spec. The assembly fix rate for novel patterns is higher than for established patterns.

**Brainstorm risk 2:** "Drag-and-drop reorder persistence (SortableJS -> /api/playlist/reorder -> batch UPDATE)"

**What happened:** The data flow itself was correct (SortableJS config, JSON POST, validation, UPDATE). But the CSS class mismatch between template and JS was a cross-file bug that only the flow-trace reviewer caught. Single-file reviewers (security, python, performance) all missed it because each file was internally correct.

**Lesson:** Flow-trace review is mandatory for any feature involving HTML + JS + Python (3+ file trace). The flow-trace reviewer found the only P1 that other reviewers missed.

## Lessons for Future Builds

### New Patterns Validated

1. **20-agent vertical split produces zero merge conflicts** -- Extends the pattern from 15 (run 046) and 16 (run 047). Blueprint-scoped file ownership with no shared files works at 20-agent scale.

2. **Token-based portal access** -- `@require_portal_token` + `@require_portal_writable` decorator pair is the correct pattern for shareable-link auth. All portal agents must use `g.portal_event` (not re-query).

3. **SortableJS + JSON API + batch UPDATE** -- The drag-and-drop reorder flow works when prescribed in the Cross-Boundary Wiring section with exact code blocks. The `data-item-id` attribute, `toArray()`, and `update_playlist_positions` must all use the same ID type (playlist_item.id, not song_id).

4. **CSV import with preview** -- Temp file + UUID pattern works for multi-step import flows. Must validate UUID format to prevent path traversal.

### Patterns to Improve

1. **Portal decorator should pass DB connection** -- The current pattern opens a connection in the decorator (to validate token) and then routes open their own connection. This doubles connection overhead. Future builds should either pass the connection through `g` or use Flask's request-scoped connection pattern.

2. **Use executemany for batch operations** -- `bulk_create_songs` and `update_playlist_positions` both loop with individual SQL statements. `executemany` reduces Python-to-C round trips.

3. **Flow-trace reviewer is non-negotiable** -- Found the only P1 that 4 other reviewers missed (CSS class mismatch). Must be included in every swarm review.

4. **Assembly fix rate: 1/20 agents needed rewrite** -- 5% agent failure rate is acceptable for a 20-agent build, but the failures were severe (23 contract violations in one agent). The portal_playlist agent appears to have ignored the spec entirely. Potential mitigation: include the exact route handler code in the agent brief (not just references to the spec).

## Spec Quality

- **Spec length:** ~1,880 lines (deepened with 5 research agents)
- **Spec consistency check:** FAIL on first pass (1 CSV column name mismatch: `key` vs `musical_key`). Fixed and would have caused silent data loss on every import.
- **Template Render Context section:** ~170 lines covering all render_template calls. This section prevented variable name mismatches in 18/20 agents (portal_playlist was the exception).
- **Cross-Boundary Wiring section:** ~230 lines with exact code blocks for all cross-agent flows. Effective for agents that read it.

## Prevention

1. For novel decorator patterns: include "CRITICAL: use `g.portal_event` exactly as named" in agent briefs
2. For cross-file flows: always run flow-trace-reviewer in review phase
3. For CSV imports: validate column names against model function parameter names in spec consistency check
4. For 20+ agent builds: budget for 1-2 assembly fix passes (5-10% agent failure rate is normal)
