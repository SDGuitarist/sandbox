# Deepening Applied -- Run 052

**Date:** 2026-05-21
**Agents:** 4 (best-practices, learnings, framework-docs, repo-research)

## Changes Merged

### From best-practices-researcher (Flask SQLite patterns)
1. **P0 FIXED:** Added `isolation_level=None` to `sqlite3.connect()` in `get_db()`.
   Without this, `BEGIN IMMEDIATE` crashes with "cannot start a transaction within
   a transaction" due to Python's implicit transaction management.
2. **P1 FIXED:** Removed `PRAGMA journal_mode=WAL` from `get_db()`. WAL mode is
   persistent (per-database, not per-connection) and only needs to be set in
   `init_db()`.
3. **P0 FIXED:** Added WAL mode return value check in `init_db()` to fail loudly
   if WAL mode cannot be enabled.

### From repo-research-analyst (repo conventions)
4. **HIGH FIXED:** Extracted `get_db()`/`close_db()` to `app/db.py` (matches all
   prior Flask apps: gigsheet, venueconnect, etc.).
5. **HIGH FIXED:** Added `instance_relative_config=True` and instance path for
   database storage (matches prior apps).
6. **MEDIUM FIXED:** Added `SECRET_KEY_BLOCKLIST` production guard.
7. **MEDIUM FIXED:** Added `@app.after_request` security headers (X-Content-Type-Options,
   X-Frame-Options, Referrer-Policy).
8. **MEDIUM FIXED:** Added `CSRFError` handler (flash friendly message instead of raw 400).
9. **LOW FIXED:** Added `SESSION_COOKIE_HTTPONLY` and `SESSION_COOKIE_SAMESITE` config.
10. **MEDIUM FIXED:** Extracted Jinja filters to `app/filters.py` with
    `register_filters(app)` pattern.

### From learnings-researcher
- No contradictions found. Plan is green. Added pragma-per-connection emphasis
  to Coordinated Behaviors #9.

### From framework-docs-researcher (Flask 3.x)
- Zero runtime-blocking findings. All patterns correct for Flask 3.x.

## Agent Count Correction

Plan originally said 34 agents but the assignment table only listed 29. Fixed
frontmatter `agent_count` to 29.

## Coordinated Behaviors Updated

- #8 (Database Connection Pattern): Rewrote to document `isolation_level=None`
  consequences. All write routes must use explicit `conn.execute("BEGIN")` +
  `conn.commit()`.
- #9 (SQLite PRAGMAs): Split into per-connection (foreign_keys, busy_timeout)
  and per-database (WAL). Emphasized "Do NOT create additional sqlite3.connect()".

## File Assignment Updated

Core agent files expanded: added `app/db.py` and `app/filters.py`.
Swarm Assignment table updated to match.
