# Smoke Test Report

**Plan:** film-production-pm-plan.md
**Tested:** 2026-06-02T10:08:04

## App Startup

- **Command:** `.venv/bin/python test_smoke.py` (Flask test client, no HTTP server needed)
- **Status:** started (app loaded successfully via `create_app()`)
- **Time to ready:** immediate (in-process test client)

## Root Cause: Database Init / In-Memory Incompatibility

The smoke test sets `DATABASE=:memory:` and calls `create_app()`, which triggers `init_app()`. The `init_db()` function opens its own `sqlite3.connect(':memory:')` connection, runs the schema and seeds data, then closes it. That connection is destroyed immediately. When each Flask request arrives, `get_db()` opens a **new** `:memory:` connection — blank, no tables. Every authenticated route therefore fails with `sqlite3.OperationalError: no such table: users`.

This is a classic in-memory SQLite pitfall: each `sqlite3.connect(':memory:')` call is a fresh, empty database. The init connection and the request connection are different objects and do not share data.

## Route Results

Phase 1 — Public routes (no auth/DB required):

| # | Method | Path | Expected | Actual | Status |
|---|--------|------|----------|--------|--------|
| 1 | GET | /auth/login | 200 | 200 | PASS |
| 2 | GET | /auth/register | 200 | 200 | PASS |
| 3 | GET | / | 302 (→ login) | 302 | PASS |

Phase 2a — Auth with CSRF:

| # | Method | Path | Expected | Actual | Status |
|---|--------|------|----------|--------|--------|
| 4 | GET | /auth/login | CSRF token in form | found | PASS |
| 5 | POST | /auth/login | 302 (redirect) | 500 | FAIL |
| 6 | session | session['user_id'] set | set | not set | FAIL |

Phase 2b — Authenticated root:

| # | Method | Path | Expected | Actual | Status |
|---|--------|------|----------|--------|--------|
| 7 | GET | / | 200 or 302 | 302 | PASS |

Phase 3 — Project-scoped routes (project_id=1, requires login session):

| # | Method | Path | Expected | Actual | Status |
|---|--------|------|----------|--------|--------|
| 8 | GET | /scenes/1 | 200 | 302 | FAIL |
| 9 | GET | /cast/1 | 200 | 302 | FAIL |
| 10 | GET | /crew/1 | 200 | 302 | FAIL |
| 11 | GET | /departments/1 | 200 | 302 | FAIL |
| 12 | GET | /locations/1 | 200 | 302 | FAIL |
| 13 | GET | /schedule/1 | 200 | 302 | FAIL |
| 14 | GET | /call-sheets/1 | 200 | 302 | FAIL |
| 15 | GET | /budget/1 | 200 | 302 | FAIL |
| 16 | GET | /expenses/1 | 200 | 302 | FAIL |
| 17 | GET | /reports/1 | 200 | 302 | FAIL |

Phase 4 — Security headers:

| # | Method | Path | Expected | Actual | Status |
|---|--------|------|----------|--------|--------|
| 18 | GET | /auth/login | CSP has cdn.jsdelivr.net | present | PASS |

## Failure Analysis

**Root failure (test 5):** `POST /auth/login` returns 500 with traceback:
```
sqlite3.OperationalError: no such table: users
  File "app/models/auth_models.py", line 35, in authenticate
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
```

**Cascade failures (tests 6, 8-17):** All downstream failures cascade from test 5. Because login fails, no session is established. All project-scoped routes require `login_required`, so they redirect (302) instead of serving content (200).

**Why `init_db()` doesn't help:** `database.py` line 136 checks `not os.path.exists(':memory:')`. The string `:memory:` is not a valid filesystem path, so `os.path.exists` returns False and `init_db()` is called. But `init_db()` opens its own in-memory connection, seeds it, and closes it. Every subsequent `get_db()` call opens a new, empty `:memory:` connection.

## Summary

- **Total checks:** 18
- **PASS:** 6
- **FAIL:** 12

### Failing checks
1. `POST /auth/login` — 500 (`no such table: users`)
2. `session['user_id']` not set (cascades from login failure)
3. All 10 project-scoped routes return 302 instead of 200 (cascades from login failure)

### Passing checks
- All 3 public GET routes resolve correctly
- CSRF token is present in the login form
- CSP header includes `cdn.jsdelivr.net`
- App imports and starts without error

STATUS: FAIL -- 12 routes failed
