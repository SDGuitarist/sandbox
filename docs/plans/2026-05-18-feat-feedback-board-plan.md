---
title: "feat: Feedback Board"
type: feat
status: active
date: 2026-05-18
origin: docs/brainstorms/2026-05-18-feedback-board-brainstorm.md
swarm: false
feed_forward:
  risk: "Denormalized vote_count consistency under concurrent upvotes. BEGIN IMMEDIATE + SQLite write serialization should handle it, but untested."
  verify_first: false
---

# feat: Feedback Board

## Deepening Key Improvements

**Deepened on:** 2026-05-18
**Research agents used:** SQLite INSERT OR IGNORE verification, security-sentinel, kieran-python-reviewer

### Key Improvements
1. **INSERT OR IGNORE + rowcount confirmed:** `cursor.rowcount` returns 0 when row is ignored (empirically tested). Upvote dedup pattern is safe.
2. **SECRET_KEY fail-closed:** Hard crash at startup if missing or default (was: silent fallback enabling CSRF bypass)
3. **ADMIN_PASSWORD startup check:** Reject known weak values at boot
4. **PRAGMA foreign_keys=ON** added to `get_db` (was: missing, FK constraints silently ignored)
5. **WAL mode** moved to `init_db` (was: wastefully set on every connection)
6. **Exception handler** passes through `HTTPException` (was: swallowing 404/401 as 500)
7. **updated_at** explicitly set in `update_feedback_status` SQL
8. **Security headers** via `@app.after_request` (CSP, X-Frame-Options, nosniff)
9. **CSV sanitizer** handles leading whitespace, `\t`, `\r`, `\n`
10. **Health endpoint** exempt from rate limiting, returns "degraded" when DB is down
11. **Admin auth** via `before_request` hook (was: per-route function call)
12. **ON DELETE CASCADE** on votes FK
13. **Brute-force dict** capped at 10,000 entries to prevent memory leak
14. **run.py** content prescribed explicitly

### New Considerations Discovered
- `BEHIND_PROXY` must only be set behind a trusted proxy (X-Forwarded-For spoofing risk)
- Upvote rate limit lowered from 30/min to 10/min
- VALID_CATEGORIES and VALID_STATUSES defined as module-level constants in models.py

## Overview

A lightweight feedback/suggestion board. Anonymous users submit ideas (title, description, category) and upvote others' suggestions. A single admin manages the board through a basic-auth-protected dashboard with status tracking, filtering, and CSV export.

Flask + SQLite + Jinja2. No external APIs. Solo autopilot build (run 045).

(see brainstorm: docs/brainstorms/2026-05-18-feedback-board-brainstorm.md)

## Plan Quality Gate

1. **What exactly is changing?** New `feedback-board/` directory in sandbox with a complete Flask app.
2. **What must not change?** All existing sandbox apps, CLAUDE.md, agent-pitfalls.md, shared spec templates.
3. **How will we know it worked?** EARS acceptance tests below, plus: app starts, form submits, upvotes deduplicate, admin filters work, CSV downloads.
4. **What is the most likely way this plan is wrong?** The atomic upvote transaction (INSERT OR IGNORE + UPDATE vote_count) might not correctly handle the case where INSERT OR IGNORE silently succeeds but the row already existed -- `cursor.rowcount` might return 1 for IGNORE. Testing will verify.

## Technical Approach

### Architecture

```
Browser <-> Flask (port 5000)
              |
              +-- public_bp (/) -- index, submit, upvote
              +-- admin_bp (/admin) -- dashboard, status update, CSV export
              +-- /health (inline in app factory)
              |
              +-- SQLite (feedback.db)
```

Single Flask app, two blueprints, server-rendered Jinja2 templates. No separate frontend.

### File Structure

```
feedback-board/
  app/
    __init__.py              # App factory, health endpoint, error handler
    db.py                    # get_db context manager, init_db
    models.py                # All model functions
    blueprints/
      public/
        __init__.py          # public_bp declaration + route import
        routes.py            # Submit, list, upvote routes
      admin/
        __init__.py          # admin_bp declaration + route import
        routes.py            # Dashboard, status update, CSV export
    templates/
      base.html              # Shared layout (nav, CSS, flash messages)
      index.html             # Feedback list + submission form
      admin/
        dashboard.html       # Admin filterable table with status dropdowns
    static/
      css/
        style.css            # All styles
  schema.sql                 # CREATE TABLE statements
  requirements.txt           # Python dependencies
  run.py                     # Entry point
  .env.example               # Environment variable template
  .gitignore                 # Standard ignores
```

**Total files:** 16

### Database Schema (SQLite -- Source of Truth)

```sql
-- feedback-board/schema.sql

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL CHECK(category IN ('Feature', 'Bug', 'Improvement', 'Other')),
    status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new', 'planned', 'in_progress', 'done')),
    vote_count INTEGER NOT NULL DEFAULT 0,
    ip_address TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_id INTEGER NOT NULL REFERENCES feedback(id) ON DELETE CASCADE,
    ip_address TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(feedback_id, ip_address)
);

CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status);
CREATE INDEX IF NOT EXISTS idx_feedback_category ON feedback(category);
CREATE INDEX IF NOT EXISTS idx_votes_feedback_id ON votes(feedback_id);
```

### Data Ownership

| Table | Owner Module | Read By |
|-------|-------------|---------|
| feedback | public/routes.py (insert), admin/routes.py (status update) | Both blueprints |
| votes | public/routes.py (insert only) | public/routes.py |

### Model Functions

All functions take `conn` as the first argument. Return types documented with usage examples.

```python
# app/models.py

def create_feedback(conn, title: str, description: str, category: str, ip_address: str) -> int:
    """Insert new feedback. Returns the new feedback ID (int).
    Usage: feedback_id = create_feedback(conn, title, desc, category, ip)
    """

def get_all_feedback(conn, status: str | None = None, category: str | None = None) -> list[sqlite3.Row]:
    """Get feedback with optional filters. Returns list of Row objects.
    Public sort: vote_count DESC, created_at DESC.
    Usage: items = get_all_feedback(conn, status='new', category='Bug')
    """

def get_all_feedback_admin(conn, status: str | None = None, category: str | None = None) -> list[sqlite3.Row]:
    """Get feedback for admin view. Returns list of Row objects.
    Admin sort: created_at DESC.
    Usage: items = get_all_feedback_admin(conn, status='planned')
    """

def get_feedback_by_id(conn, feedback_id: int) -> sqlite3.Row | None:
    """Get single feedback item. Returns Row or None.
    Usage: item = get_feedback_by_id(conn, feedback_id)
    """

def upvote_feedback(conn, feedback_id: int, ip_address: str) -> bool:
    """Atomic upvote with dedup. Returns True if vote was new, False if duplicate.
    Uses INSERT OR IGNORE + conditional vote_count increment.
    MUST be called inside get_db(immediate=True) context.
    Usage: was_new = upvote_feedback(conn, feedback_id, ip)
    """

def update_feedback_status(conn, feedback_id: int, new_status: str) -> bool:
    """Update feedback status. Returns True if row existed and was updated.
    Usage: updated = update_feedback_status(conn, feedback_id, 'planned')
    """

def get_feedback_stats(conn) -> dict:
    """Get counts by status. Returns dict.
    Usage: stats = get_feedback_stats(conn)
    # stats = {'total': 12, 'new': 5, 'planned': 3, 'in_progress': 2, 'done': 2}
    """
```

### Prescribed SQL for Atomic Upvote

```python
def upvote_feedback(conn, feedback_id: int, ip_address: str) -> bool:
    cursor = conn.execute(
        "INSERT OR IGNORE INTO votes (feedback_id, ip_address) VALUES (?, ?)",
        (feedback_id, ip_address)
    )
    if cursor.rowcount == 0:
        return False  # Already voted
    conn.execute(
        "UPDATE feedback SET vote_count = vote_count + 1 WHERE id = ?",
        (feedback_id,)
    )
    return True
```

**Critical:** Use `vote_count = vote_count + 1` (SQL expression), never read-modify-write in Python (TOCTOU race). The `BEGIN IMMEDIATE` from `get_db(immediate=True)` serializes concurrent writes.

### Database Layer

```python
# app/db.py -- based on task-tracker-categories pattern

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from flask import current_app

@contextmanager
def get_db(immediate=False):
    """Context manager for DB connections. Auto-commits on success, rollbacks on error.
    Use immediate=True for write operations (BEGIN IMMEDIATE).
    """
    db_path = current_app.config['DB_PATH']
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if immediate:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(app):
    """Initialize database from schema.sql. Called once at startup.
    Sets WAL mode (persistent -- only needs to run once)."""
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    db_path = app.config['DB_PATH']
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()
```

**Notes:**
- `PRAGMA foreign_keys=ON` in `get_db` -- without this, SQLite silently ignores FK constraints on `votes.feedback_id`.
- `PRAGMA journal_mode=WAL` in `init_db` only -- WAL is persistent once set, no need to re-run per connection.
- `executescript()` is safe here because `schema.sql` only contains `CREATE TABLE IF NOT EXISTS` -- no destructive DDL (FC14).
- `pathlib.Path` instead of nested `os.path.dirname` for clarity.

### App Factory

```python
# app/__init__.py

import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

csrf = CSRFProtect()
limiter = Limiter(get_remote_address, default_limits=["60 per minute"])

def create_app(db_path: str | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)

    # SECRET_KEY: fail-closed in production (no silent fallback)
    secret = os.environ.get('SECRET_KEY')
    if not secret:
        if app.debug or os.environ.get('FLASK_ENV') == 'development':
            secret = 'dev-only-not-for-production'
        else:
            raise RuntimeError("SECRET_KEY environment variable must be set")
    app.config['SECRET_KEY'] = secret

    app.config['DB_PATH'] = db_path or os.environ.get('DB_PATH',
        str(Path(__file__).resolve().parent.parent / 'feedback.db'))

    # ADMIN_PASSWORD: reject weak defaults at startup
    admin_pw = os.environ.get('ADMIN_PASSWORD', '')
    if admin_pw and admin_pw in ('change-me', 'changeme', 'password', 'admin'):
        raise RuntimeError("ADMIN_PASSWORD is too weak -- set a strong password")

    if os.environ.get('BEHIND_PROXY'):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

    csrf.init_app(app)
    limiter.init_app(app)

    from app.db import init_db
    with app.app_context():
        init_db(app)

    from app.blueprints.public import public_bp
    app.register_blueprint(public_bp)

    from app.blueprints.admin import admin_bp
    app.register_blueprint(admin_bp)

    @app.route("/health")
    @limiter.exempt
    def health():
        from app.db import get_db
        db_status = "connected"
        status_label = "ok"
        try:
            with get_db() as conn:
                conn.execute("SELECT 1")
        except Exception:
            db_status = "disconnected"
            status_label = "degraded"
        return jsonify({"status": status_label, "db": db_status}), (200 if db_status == "connected" else 503)

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return e
        app.logger.error(f"Unhandled exception: {e}", exc_info=True)
        return "Internal server error", 500

    return app
```

### Route Table

| Method | Path | Handler | Blueprint | Auth | Rate Limit | Response |
|--------|------|---------|-----------|------|------------|----------|
| GET | / | index | public_bp | None | default | render index.html |
| POST | /submit | submit | public_bp | None | 10/min | redirect / |
| POST | /upvote/\<int:id\> | upvote | public_bp | None | 10/min | redirect / |
| GET | /admin | dashboard | admin_bp | Basic | default | render admin/dashboard.html |
| POST | /admin/status/\<int:id\> | update_status | admin_bp | Basic | default | redirect /admin (preserve filters) |
| GET | /admin/export | export_csv | admin_bp | Basic | default | text/csv download |
| GET | /health | health | (inline) | None | default | JSON |

### Template Render Context

| Template | Route | Variables |
|----------|-------|-----------|
| index.html | GET / | `feedback_items` (list of Row), `categories` (list of str) |
| admin/dashboard.html | GET /admin | `feedback_items` (list of Row), `stats` (dict), `categories` (list of str), `current_status` (str\|None), `current_category` (str\|None) |

### CSRF in Templates

Every POST form includes:
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

The upvote button is a mini-form (not a link):
```html
<form method="POST" action="{{ url_for('public.upvote', id=item.id) }}" style="display:inline">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit">Upvote ({{ item.vote_count }})</button>
</form>
```

### Admin Authentication

Port the brute-force auth from workshop-registration (`app/admin/routes.py:16-70`). Key adaptations:
- Returns HTTP 401 with `WWW-Authenticate: Basic realm="Feedback Admin"` header
- Uses `hmac.compare_digest` for timing-safe password comparison
- Reads `ADMIN_PASSWORD` from env var
- 429 on lockout with `Retry-After: 60`
- Cap `_failed_attempts` dict at 10,000 entries to prevent memory leak under distributed brute-force
- Use `@admin_bp.before_request` hook instead of per-route `require_admin()` calls:

```python
@admin_bp.before_request
def check_admin_auth():
    error_response = require_admin(request)
    if error_response:
        return error_response
```

### Prescribed Constants (models.py)

```python
VALID_CATEGORIES: tuple[str, ...] = ("Feature", "Bug", "Improvement", "Other")
VALID_STATUSES: tuple[str, ...] = ("new", "planned", "in_progress", "done")
```

Reference these in both validation routes and template select options.

### Prescribed SQL for update_feedback_status

```python
def update_feedback_status(conn, feedback_id: int, new_status: str) -> bool:
    cursor = conn.execute(
        "UPDATE feedback SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, feedback_id)
    )
    return cursor.rowcount > 0
```

**Critical:** Include `updated_at = datetime('now')` -- the acceptance tests require it.

### run.py (Prescribed)

```python
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

### Input Validation

| Field | Required | Constraints | Server-side Check |
|-------|----------|-------------|-------------------|
| title | yes | 1-200 chars after trim | `if not title or len(title) > 200` |
| description | no | max 2000 chars after trim | `if len(description) > 2000` |
| category | yes | Must be in VALID_CATEGORIES set | `if category not in VALID_CATEGORIES` |
| status (admin) | yes | Must be in VALID_STATUSES set | `if new_status not in VALID_STATUSES` |

On validation failure: `flash(error_message, 'error')` and redirect back (PRG pattern).

### CSV Export

```python
# In admin/routes.py
import csv
import io

@admin_bp.route("/export")
def export_csv():
    # ... auth check ...
    with get_db() as conn:
        rows = get_all_feedback_admin(conn)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "title", "description", "category", "status", "vote_count", "created_at", "updated_at"])
    for row in rows:
        writer.writerow([
            row["id"],
            _sanitize_csv(row["title"]),
            _sanitize_csv(row["description"]),
            row["category"],
            row["status"],
            row["vote_count"],
            row["created_at"],
            row["updated_at"],
        ])
    # ... return Response with text/csv ...

def _sanitize_csv(value):
    """Prevent formula injection in spreadsheets."""
    if not value:
        return value
    # Strip null bytes
    value = value.replace('\x00', '')
    # Check after stripping leading whitespace (prevents " =SUM()" bypass)
    stripped = value.strip()
    if stripped and stripped[0] in '=-+@|\t\r\n':
        return "'" + value
    return value
```

### Environment Variables

```env
# REQUIRED in production (app will crash without it)
SECRET_KEY=change-me-to-a-random-string
# REQUIRED: Set a strong password (min 12 chars, not 'change-me')
ADMIN_PASSWORD=change-me
DB_PATH=feedback.db
# Only set BEHIND_PROXY=1 when running behind a trusted reverse proxy.
# If set without a proxy, attackers can spoof IPs via X-Forwarded-For.
BEHIND_PROXY=
```

### Requirements

```
flask>=3.0
flask-wtf>=1.2
flask-limiter
python-dotenv
```

## Acceptance Tests (EARS Format)

### Happy Path
- WHEN a visitor submits a valid feedback form THE SYSTEM SHALL create a new feedback item with status "new" and redirect to the index page
- WHEN a visitor clicks upvote on a feedback item THE SYSTEM SHALL increment the vote count by 1 and redirect to the index page
- WHEN an admin visits /admin with correct credentials THE SYSTEM SHALL display all feedback items sorted by created_at descending
- WHEN an admin selects a new status for a feedback item THE SYSTEM SHALL update the status and updated_at timestamp

### Upvote Dedup
- WHEN the same IP upvotes the same feedback item twice THE SYSTEM SHALL count only one vote (INSERT OR IGNORE)
- WHEN two different IPs upvote the same feedback item THE SYSTEM SHALL count both votes

### Filtering
- WHEN an admin filters by status "new" THE SYSTEM SHALL show only feedback with status "new"
- WHEN an admin filters by category "Bug" THE SYSTEM SHALL show only feedback with category "Bug"
- WHEN an admin combines status and category filters THE SYSTEM SHALL apply both filters with AND logic

### Validation
- WHEN a visitor submits a form with an empty title THE SYSTEM SHALL show a flash error and not create feedback
- WHEN a visitor submits a title longer than 200 characters THE SYSTEM SHALL show a flash error
- WHEN a visitor submits an invalid category THE SYSTEM SHALL show a flash error

### Security
- WHEN an unauthenticated request hits /admin THE SYSTEM SHALL return 401 with WWW-Authenticate header
- WHEN 5 failed auth attempts occur from one IP in 60 seconds THE SYSTEM SHALL return 429 with Retry-After header
- WHEN a POST form lacks a valid CSRF token THE SYSTEM SHALL return 400

### Export
- WHEN an admin clicks CSV export THE SYSTEM SHALL download a file containing all feedback items without IP addresses
- WHEN a feedback title starts with "=" THE SYSTEM SHALL prefix with "'" in CSV export to prevent formula injection

### Health
- WHEN GET /health is called THE SYSTEM SHALL return {"status": "ok", "db": "connected"}

### Verification Commands
```bash
# Start server
cd feedback-board
python run.py

# Health check
curl http://localhost:5000/health | python3 -m json.tool

# Submit feedback
curl -X POST http://localhost:5000/submit \
  -d "title=Test+Feedback&description=A+test&category=Feature&csrf_token=<token>" \
  -L -o /dev/null -w "%{http_code}"

# Admin dashboard (basic auth)
curl -u admin:changeme http://localhost:5000/admin -o /dev/null -w "%{http_code}"

# CSV export
curl -u admin:changeme http://localhost:5000/admin/export -o feedback.csv
```

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| vote_count desync under concurrent upvotes | LOW | Data inconsistency | BEGIN IMMEDIATE + SQL atomic increment |
| CSRF token invalid for users without cookies | LOW | Can't submit/upvote | Flask-WTF handles session creation automatically |
| Brute-force lockout locks legitimate admin | LOW | Admin locked out 60s | Sliding window auto-recovers; restart clears dict |
| Formula injection in CSV | MEDIUM | Security risk | _sanitize_csv prefixes dangerous characters |

## Sources & References

### Origin
- **Brainstorm document:** [docs/brainstorms/2026-05-18-feedback-board-brainstorm.md](../brainstorms/2026-05-18-feedback-board-brainstorm.md) -- Key decisions: Jinja2 over Express, IP-based upvote dedup, PRG pattern, four-status state machine

### Internal References
- Flask app factory: `task-tracker-categories/app/__init__.py:1-33`
- Flask DB pattern: `task-tracker-categories/app/db.py:1-30`
- Blueprint pattern: `task-tracker-categories/app/blueprints/tasks/__init__.py:1-5`
- Admin auth + brute-force: `workshop-registration/app/admin/routes.py:16-70`
- CSV export: `workshop-registration/app/admin/routes.py:118-145`
- Rate limiting: `workshop-registration/app/__init__.py:6-12`
- Flask shared spec template: `docs/templates/shared-spec-flask.md`

### Solution Docs Referenced
- `2026-04-05-flask-url-shortener-api.md` -- WAL mode, atomic counters, init_db pattern
- `2026-04-05-db-migration-runner.md` -- Never executescript() for destructive DDL
- `2026-05-05-venue-scraper-search-discovery-csv-pipeline.md` -- CSV formula injection prevention
- `2026-04-30-ethics-toolkit-platform-build.md` -- Atomic increment problem, dead wiring

## Feed-Forward

- **Hardest decision:** Using `get_db(immediate=True)` wrapper from task-tracker vs manual `BEGIN IMMEDIATE` from workshop-registration. Chose the wrapper for auto-commit/rollback safety -- callers can't forget to commit or rollback.
- **Rejected alternatives:** Manual transaction management (error-prone), separate API endpoints for AJAX upvotes (adds complexity, breaks PRG pattern), redis for rate limiting (overkill at workshop scale).
- **Least confident:** ~~Whether `cursor.rowcount` correctly returns 0 for INSERT OR IGNORE~~ RESOLVED: empirically confirmed rowcount=0 on ignored rows (deepening research). New risk: whether the `before_request` admin auth hook correctly interacts with Flask-WTF CSRF on admin POST routes -- the CSRF check runs before the view function but `before_request` runs even earlier, so auth should fire first. Should work but is untested in this exact combination.
