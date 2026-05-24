---
title: "feat: Habit Tracker (Web)"
type: feat
status: active
date: 2026-05-23
origin: docs/brainstorms/2026-05-23-habit-tracker-web-brainstorm.md
swarm: false
feed_forward:
  risk: "Whether the weekly calendar UI will feel intuitive for toggling completions on past dates. The interaction model (click a cell to toggle) needs to be visually clear about which date you're toggling and whether it's currently marked or not."
  verify_first: false
---

# feat: Habit Tracker (Web)

## Plan Quality Gate

1. **What exactly is changing?** New `habit-tracker-web/` directory in sandbox with a complete Flask + SQLite + Jinja2 web app for daily habit tracking with weekly calendar view.
2. **What must not change?** The existing `habit-tracker/` CLI app, all other sandbox apps, CLAUDE.md, agent-pitfalls.md, solution docs.
3. **How will we know it worked?** EARS acceptance tests below, plus: app starts without errors, habits can be created/edited/archived, toggle marks today complete, calendar shows current week with visual indicators, streaks compute correctly.
4. **What is the most likely way this plan is wrong?** The toggle route's INSERT/DELETE logic might have a TOCTOU race if a user double-clicks rapidly before the first response returns. Mitigated by BEGIN IMMEDIATE + UNIQUE constraint, but the UX of double-click is untested.

## Overview

A web-based daily habit tracker. Single user creates habits, marks them complete each day, and views a weekly streak calendar. Dashboard shows current streaks at a glance. Reuses proven streak algorithm from the CLI version.

Flask + SQLite + Jinja2. No external APIs. Solo autopilot build.

(see brainstorm: docs/brainstorms/2026-05-23-habit-tracker-web-brainstorm.md)

## Technical Approach

### Architecture

```
Browser <-> Flask (port 5000)
              |
              +-- habits_bp (/) -- dashboard, CRUD, toggle, calendar
              +-- /health (inline in app factory)
              |
              +-- SQLite (habits.db)
```

Single Flask app, one blueprint, server-rendered Jinja2 templates. No separate frontend.

### File Structure

```
habit-tracker-web/
  app/
    __init__.py              # App factory, health endpoint, error handler
    db.py                    # get_db context manager, init_db
    models.py                # Habit CRUD, completion toggle, streak computation
    blueprints/
      habits/
        __init__.py          # habits_bp declaration + route import
        routes.py            # All user-facing routes
    templates/
      base.html              # Shared layout (nav, CSS)
      dashboard.html         # Main view: habit list + today status + streaks
      calendar.html          # Weekly calendar view per habit
      habits/
        form.html            # Create/edit habit form
    static/
      css/
        style.css            # Custom CSS (grid calendar, streak indicators)
  schema.sql                 # CREATE TABLE statements
  requirements.txt           # Python dependencies
  run.py                     # Entry point
  .env.example               # Environment variable template
  .gitignore                 # Standard ignores
```

**Total files:** 14

### Database Schema (SQLite -- Source of Truth)

```sql
-- habit-tracker-web/schema.sql

CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (date('now')),
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    completed_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(habit_id, completed_date)
);

CREATE INDEX IF NOT EXISTS idx_completions_habit_id ON completions(habit_id);
CREATE INDEX IF NOT EXISTS idx_completions_date ON completions(completed_date);
```

**Design rationale:**
- Separate `completions` table (not JSON column) because SQLite can query date ranges efficiently and UNIQUE constraint provides built-in idempotency for toggle operations.
- `archived` flag instead of hard delete preserves historical streak data.
- Index on `completed_date` optimizes the calendar range query.
- `ON DELETE CASCADE` ensures orphan completions are removed when a habit is permanently deleted.

### Data Ownership

| Table | Owner Module | Read By |
|-------|-------------|---------|
| habits | habits/routes.py (create, edit, archive) | habits/routes.py |
| completions | habits/routes.py (toggle) | habits/routes.py |

Single blueprint owns everything (no cross-agent boundary concerns for solo build).

### Model Functions

All functions take `conn` as the first argument. Return types documented with usage examples.

```python
# app/models.py

def create_habit(conn, name: str) -> int:
    """Insert new habit. Returns the new habit ID (int).
    Usage: habit_id = create_habit(conn, name)
    """

def get_all_habits(conn) -> list[sqlite3.Row]:
    """Get all active (non-archived) habits. Returns list of Row objects.
    Sorted by created_at ASC (oldest first).
    Usage: habits = get_all_habits(conn)
    """

def get_habit_by_id(conn, habit_id: int) -> sqlite3.Row | None:
    """Get single habit. Returns Row or None.
    Usage: habit = get_habit_by_id(conn, habit_id)
           if habit is None: abort(404)
    """

def update_habit(conn, habit_id: int, name: str) -> bool:
    """Update habit name. Returns True if row existed and was updated.
    Usage: updated = update_habit(conn, habit_id, name)
    """

def archive_habit(conn, habit_id: int) -> bool:
    """Soft-delete (archive) a habit. Returns True if row existed.
    Usage: archived = archive_habit(conn, habit_id)
    """

def toggle_completion(conn, habit_id: int, target_date: str) -> bool:
    """Toggle completion for a habit on a specific date.
    Returns True if completion was ADDED, False if REMOVED.
    MUST be called inside get_db(immediate=True) context.
    Uses INSERT OR IGNORE + rowcount check for atomic idempotent toggle.
    Usage: was_added = toggle_completion(conn, habit_id, '2026-05-23')
    """

def get_completions_for_week(conn, habit_id: int, week_start: str, week_end: str) -> set[str]:
    """Get all completion dates for a habit within a date range.
    Returns set of date strings (ISO format).
    Usage: completed_dates = get_completions_for_week(conn, habit_id, '2026-05-19', '2026-05-25')
    """

def get_all_completions(conn, habit_id: int) -> list[str]:
    """Get all completion dates for a habit (for streak computation).
    Returns list of date strings (ISO format).
    Usage: all_dates = get_all_completions(conn, habit_id)
    """

def compute_current_streak(completions: list[str]) -> int:
    """Compute current streak from list of date strings.
    Uses set deduplication before date math (proven pattern from CLI version).
    Returns 0 if no streak.
    Usage: streak = compute_current_streak(all_dates)
    """

def compute_longest_streak(completions: list[str]) -> int:
    """Compute longest streak from list of date strings.
    Uses set deduplication before date math.
    Returns 0 if empty.
    Usage: longest = compute_longest_streak(all_dates)
    """
```

### Prescribed SQL for Atomic Toggle

```python
def toggle_completion(conn, habit_id: int, target_date: str) -> bool:
    """Atomic toggle: INSERT if not exists, DELETE if exists."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO completions (habit_id, completed_date) VALUES (?, ?)",
        (habit_id, target_date)
    )
    if cursor.rowcount > 0:
        return True  # Completion was ADDED
    # Row already existed -- remove it
    conn.execute(
        "DELETE FROM completions WHERE habit_id = ? AND completed_date = ?",
        (habit_id, target_date)
    )
    return False  # Completion was REMOVED
```

**Critical:** This is atomic because:
1. `BEGIN IMMEDIATE` (from `get_db(immediate=True)`) serializes writes
2. `INSERT OR IGNORE` + `rowcount` determines state without a separate SELECT (no TOCTOU)
3. The UNIQUE constraint prevents duplicate completions even under rapid clicks

### Prescribed Streak Functions

```python
from datetime import date, timedelta

def compute_current_streak(completions: list[str]) -> int:
    """Same algorithm as CLI version (proven, tested)."""
    if not completions:
        return 0
    dates = sorted({date.fromisoformat(d) for d in completions}, reverse=True)
    today = date.today()
    if dates[0] != today and dates[0] != today - timedelta(days=1):
        return 0
    streak = 1
    for i in range(1, len(dates)):
        if dates[i - 1] - dates[i] == timedelta(days=1):
            streak += 1
        else:
            break
    return streak


def compute_longest_streak(completions: list[str]) -> int:
    if not completions:
        return 0
    dates = sorted({date.fromisoformat(d) for d in completions})
    longest = 1
    current = 1
    for i in range(1, len(dates)):
        if dates[i] - dates[i - 1] == timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest
```

**Key:** Set comprehension `{...}` deduplicates before sorting (lesson from `2026-04-09-cli-habit-tracker-streaks.md`).

### Database Layer

```python
# app/db.py -- based on feedback-board pattern

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
    Sets WAL mode (persistent -- only needs to run once).
    Uses try/finally to prevent FD leaks on schema errors (P1 from feedback-board review)."""
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    db_path = app.config['DB_PATH']
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        with open(schema_path) as f:
            conn.executescript(f.read())
    finally:
        conn.close()
```

**Notes:**
- `PRAGMA foreign_keys=ON` in `get_db` -- without this, SQLite silently ignores FK constraints on `completions.habit_id`.
- `PRAGMA journal_mode=WAL` in `init_db` only -- WAL is persistent once set.
- `executescript()` is safe here because `schema.sql` only contains `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` -- no destructive DDL.
- `try/finally` on init_db prevents FD leak if schema execution fails (lesson from feedback-board P1 finding).

### App Factory

```python
# app/__init__.py

import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_wtf import CSRFProtect
from werkzeug.exceptions import HTTPException

csrf = CSRFProtect()

def create_app(db_path: str | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)

    # SECRET_KEY: fail-closed in production (no silent fallback)
    secret = os.environ.get('SECRET_KEY')
    if not secret:
        if app.debug:
            secret = 'dev-only-not-for-production'
        else:
            raise RuntimeError("SECRET_KEY environment variable must be set")
    app.config['SECRET_KEY'] = secret

    app.config['DB_PATH'] = db_path or os.environ.get('DB_PATH',
        str(Path(__file__).resolve().parent.parent / 'habits.db'))

    csrf.init_app(app)

    from app.db import init_db
    with app.app_context():
        init_db(app)

    from app.blueprints.habits import habits_bp
    app.register_blueprint(habits_bp)

    @app.route("/health")
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
        code = 200 if db_status == "connected" else 503
        return jsonify({"status": status_label, "db": db_status}), code

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

| Method | Path | Handler | Purpose | Response |
|--------|------|---------|---------|----------|
| GET | / | habits.dashboard | List habits + today status + streaks | render dashboard.html |
| GET | /habits/new | habits.new_habit | Show create form | render habits/form.html |
| POST | /habits | habits.create_habit | Create habit | redirect / |
| GET | /habits/\<int:habit_id\>/edit | habits.edit_habit | Show edit form | render habits/form.html |
| POST | /habits/\<int:habit_id\>/edit | habits.update_habit | Update habit name | redirect / |
| POST | /habits/\<int:habit_id\>/archive | habits.archive_habit | Soft-delete habit | redirect / |
| POST | /habits/\<int:habit_id\>/toggle | habits.toggle_today | Toggle today's completion | redirect / |
| POST | /habits/\<int:habit_id\>/toggle/\<target_date\> | habits.toggle_date | Toggle specific date (target_date is ISO string, validated in handler) | redirect to calendar |
| GET | /calendar | habits.calendar | Weekly calendar view | render calendar.html |
| GET | /health | health | Health check | JSON |

### Template Render Context

| Template | Route | Variables |
|----------|-------|-----------|
| dashboard.html | GET / | `habits` (list of dicts assembled in route: id, name, streak, done_today -- each built by querying habit + computing streak from completions) |
| calendar.html | GET /calendar | `habits` (list of Row), `week_dates` (list of date objects), `completions` (dict: habit_id -> set of date strings), `current_week_start` (date), `prev_week` (str), `next_week` (str) |
| habits/form.html | GET /habits/new, GET /habits/\<id\>/edit | `habit` (Row or None), `action_url` (str) |

### CSRF in Templates

Every POST form includes:
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

The toggle button is a mini-form (not a link):
```html
<form method="POST" action="{{ url_for('habits.toggle_today', habit_id=habit.id) }}" style="display:inline">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit" class="toggle-btn">Mark Done</button>
</form>
```

### Weekly Calendar UI Design

The calendar view (GET /calendar) shows a 7-column CSS Grid (Monday-Sunday):

```
       Mon   Tue   Wed   Thu   Fri   Sat   Sun
       19    20    21    22    23    24    25

Habit1  *     *     *     *     o     -     -
Habit2  *     o     *     o     o     -     -
```

Visual states per cell:
- **Filled circle (green):** Completed on that date. Clicking toggles to incomplete.
- **Empty circle (gray):** Not completed. Clicking toggles to complete.
- **Dash (light gray):** Future date -- not clickable.
- **Today's cell:** Highlighted border to show "you are here."

Each cell that is clickable is wrapped in a mini-form POST to `/habits/<id>/toggle/<date>`.

Navigation: `<< Prev Week` and `Next Week >>` links pass `?week=YYYY-MM-DD` query param. Default is the Monday of the current week.

**Backfill constraint:** Only allow toggling dates within the current week view (prevents arbitrary backdating). The route validates that `target_date` is within 7 days of the current week start shown.

### Input Validation

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| POST /habits | `name` (form) | Strip whitespace, 1-100 chars, required | Flash "Habit name is required" / "Habit name too long", redirect back |
| POST /habits/\<id\>/edit | `name` (form) | Strip whitespace, 1-100 chars, required | Flash error, redirect back |
| POST /habits/\<id\>/toggle/\<target_date\> | `target_date` (URL string) | Parse with `date.fromisoformat()`; must be valid ISO date, must not be in the future (`> date.today()`), must be within 7 days of today | abort(400) on parse error or constraint violation |
| POST /habits/\<id\>/archive | `habit_id` (URL) | Must exist in DB | abort(404) |
| POST /habits/\<id\>/toggle | `habit_id` (URL) | Must exist in DB, must not be archived | abort(404) |

### Date Handling

- All dates stored as ISO 8601 TEXT in SQLite (`YYYY-MM-DD`)
- Python `datetime.date` for all computation
- Week start = Monday (ISO standard). Compute with `date - timedelta(days=date.weekday())`
- System local timezone via `date.today()` (sufficient for single-user personal tool)
- Calendar query: `SELECT completed_date FROM completions WHERE habit_id = ? AND completed_date BETWEEN ? AND ?`

### CSS Approach

Single `style.css` file. Clean, minimal custom CSS. Key structures:

```css
/* Calendar grid -- 7 columns for days */
.calendar-grid {
    display: grid;
    grid-template-columns: 120px repeat(7, 1fr);
    gap: 4px;
}

/* Streak indicators */
.completed { background: #22c55e; border-radius: 50%; }
.not-completed { background: #e5e7eb; border-radius: 50%; }
.future { background: #f9fafb; opacity: 0.5; }
.today { border: 2px solid #3b82f6; }
```

No CSS framework needed at this scale.

### run.py (Prescribed)

```python
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

### Environment Variables

```env
# REQUIRED in production (app will crash without it)
SECRET_KEY=change-me-to-a-random-string
# Optional: override database location
DB_PATH=habits.db
```

### Requirements

```
flask>=3.0
flask-wtf>=1.2
python-dotenv
```

## Acceptance Tests (EARS Format)

### Happy Path
- WHEN a user visits the dashboard THE SYSTEM SHALL display all active habits with their current streak count and today's completion status
- WHEN a user submits a valid habit name THE SYSTEM SHALL create the habit and redirect to the dashboard showing the new habit
- WHEN a user clicks "Mark Done" on a habit THE SYSTEM SHALL toggle today's completion and update the streak display
- WHEN a user visits /calendar THE SYSTEM SHALL display a 7-day grid (Mon-Sun) for the current week with completion indicators for each habit

### Toggle Behavior
- WHEN a user toggles a habit that is not yet completed today THE SYSTEM SHALL mark it complete (insert completion record)
- WHEN a user toggles a habit that is already completed today THE SYSTEM SHALL mark it incomplete (delete completion record)
- WHEN a user toggles a past date within the current week view THE SYSTEM SHALL update that date's completion status
- WHEN a user attempts to toggle a future date THE SYSTEM SHALL return 400 and not modify any data

### Streaks
- WHEN a habit has been completed for 3 consecutive days including today THE SYSTEM SHALL display "3d streak" on the dashboard
- WHEN a habit was completed yesterday but not today THE SYSTEM SHALL still count yesterday as part of the streak (streak includes yesterday)
- WHEN a habit has no completions THE SYSTEM SHALL display "no streak"
- WHEN completions contain duplicate dates THE SYSTEM SHALL deduplicate before computing streaks (UNIQUE constraint prevents this at DB level, but streak function handles it defensively)

### CRUD
- WHEN a user edits a habit name THE SYSTEM SHALL update the name and redirect to dashboard
- WHEN a user archives a habit THE SYSTEM SHALL remove it from the dashboard but preserve completion data in the database
- WHEN a user submits an empty habit name THE SYSTEM SHALL flash an error and not create the habit
- WHEN a user submits a habit name longer than 100 characters THE SYSTEM SHALL flash an error

### Calendar Navigation
- WHEN a user clicks "Prev Week" THE SYSTEM SHALL show the previous week's completions
- WHEN a user clicks "Next Week" and next week is in the future THE SYSTEM SHALL show the next week with future dates grayed out and non-clickable

### Security
- WHEN a POST form lacks a valid CSRF token THE SYSTEM SHALL return 400
- WHEN SECRET_KEY is not set and debug mode is off THE SYSTEM SHALL crash at startup with RuntimeError

### Health
- WHEN GET /health is called THE SYSTEM SHALL return {"status": "ok", "db": "connected"} with status 200

### Verification Commands
```bash
# Start server
cd habit-tracker-web
SECRET_KEY=dev-key python run.py

# Health check
curl http://localhost:5000/health

# Create a habit (requires CSRF -- use browser or test client)
# Verify via dashboard at http://localhost:5000/

# Calendar view
curl http://localhost:5000/calendar
curl "http://localhost:5000/calendar?week=2026-05-12"
```

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Double-click sends two toggle requests | MEDIUM | Toggles cancel each other | BEGIN IMMEDIATE serializes; UX could add JS disable-on-click later |
| Calendar toggle on wrong date | LOW | User confusion | Visual highlight of today + date labels on every cell |
| Streak computation slow with years of data | VERY LOW | Slow dashboard | At personal scale (365 days x 20 habits = 7,300 comparisons) this is negligible |
| init_db FD leak on schema error | LOW | File descriptor exhaustion | try/finally pattern (learned from feedback-board P1) |

## Sources & References

### Origin
- **Brainstorm document:** [docs/brainstorms/2026-05-23-habit-tracker-web-brainstorm.md](../brainstorms/2026-05-23-habit-tracker-web-brainstorm.md) -- Key decisions: separate completions table, UNIQUE constraint for idempotency, weekly calendar view, reuse CLI streak algorithm

### Internal References
- CLI habit tracker streak algorithm: `habit-tracker/habit_tracker.py:51-79`
- Flask app factory: `feedback-board/app/__init__.py`
- Flask DB pattern (get_db + init_db): `feedback-board/app/db.py`
- Blueprint pattern: `feedback-board/app/blueprints/public/__init__.py`
- CSRF mini-form: `feedback-board/app/templates/index.html` (upvote form)

### Solution Docs Referenced
- `2026-04-09-cli-habit-tracker-streaks.md` -- Set deduplication before date math, guard empty lists, idempotent operations
- `2026-04-05-flask-url-shortener-api.md` -- WAL mode, init_db at startup only, atomic SQL patterns
- `2026-04-05-db-migration-runner.md` -- executescript() implicit COMMIT side effect (safe here: only CREATE IF NOT EXISTS)
- `2026-05-18-feedback-board-solo-build.md` -- init_db try/finally FD leak prevention, INSERT OR IGNORE + rowcount pattern

## Feed-Forward

- **Hardest decision:** Whether to allow toggling past dates or only today. Chose to allow toggling within the displayed week because users legitimately forget to mark habits and need to backfill. The constraint is "within current week view only" which prevents arbitrary backdating while keeping UX simple.
- **Rejected alternatives:** Month calendar view (brief says weekly), JavaScript SPA with API (unnecessary complexity for single-user), using Flask-Login for auth (no auth needed for single-user MVP), rate limiting (no multi-user abuse vector).
- **Least confident:** Whether the CSS Grid calendar with mini-form buttons in each cell will feel responsive and not "jumpy" when toggling. Each toggle is a full POST + redirect, meaning the page reloads. For the calendar view, this could feel slow if the user wants to backfill multiple days. A future enhancement could add JavaScript for optimistic UI updates, but for MVP the server-rendered approach is simpler and guaranteed correct.
