---
title: "Habit Tracker (Web)"
type: brainstorm
date: 2026-05-23
status: complete
---

# Habit Tracker (Web) -- Brainstorm

## What We're Building

A web-based daily habit tracker where a single user creates habits, marks them
complete each day, and views a weekly streak calendar. A simple dashboard shows
current streaks at a glance.

**Target user:** Single user (no auth needed for MVP -- single-tenant local app).

**Scale:** Personal use. Dozens of habits, months of data. No performance
concerns at this scale.

**Prior art:** The CLI habit tracker (`habit-tracker/habit_tracker.py`) already
exists in this repo. This web version reuses the same streak logic but wraps it
in a Flask web UI with persistent SQLite storage instead of a JSON file.

## Why This Approach

**Flask + SQLite + Jinja2** is the sandbox standard stack. Reasons:

- Server-rendered Jinja2 means no separate frontend (simple, one process)
- SQLite handles dates and queries better than flat JSON for calendar views
- Flask-WTF provides CSRF protection on all POST forms (mandatory per lessons)
- No external API keys or services needed -- fully autonomous build

**Web instead of extending the CLI** because:

- A weekly calendar view is inherently visual -- terminal rendering is awkward
- Click-to-toggle completion is faster than typing `python habit_tracker.py log 3`
- The dashboard with multiple habits at a glance is better served by HTML/CSS
- The CLI version still exists for power users who prefer terminal

**No auth** because:

- Single user app (brief says "single user")
- Runs locally or on a personal server
- Adding auth is Phase 2 if ever needed

## Key Decisions

### 1. Database Schema

Two tables:

```sql
CREATE TABLE habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (date('now')),
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    completed_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(habit_id, completed_date)
);
```

**Why separate tables instead of JSON array in a column:**
- SQLite can query completions by date range efficiently (needed for calendar)
- UNIQUE constraint prevents duplicate completions (idempotent toggle)
- Easy to count streaks with date math in Python after a range query

**Why `archived` instead of hard delete:**
- Preserves historical streak data
- User can soft-remove habits without losing their record
- Hard delete available via a separate "permanently delete" action

### 2. Streak Computation

Same algorithm as the CLI version (proven, tested, documented in solution doc
`2026-04-09-cli-habit-tracker-streaks.md`):

- Compute from completions list, never store
- Use set deduplication before date math (lesson from CLI version)
- Current streak: count consecutive days backward from today/yesterday
- Longest streak: scan all completions for longest consecutive run

**Performance at personal scale:** Even with 365 days of data per habit and
20 habits, we're looking at ~7,300 date comparisons. Negligible.

### 3. Weekly Calendar View

A 7-column grid showing the current week (Mon-Sun or Sun-Sat based on locale).
Each cell shows:
- The date number
- A visual indicator (filled circle = completed, empty circle = not)
- For today: the cell is highlighted and clickable to toggle

**Navigation:** Left/right arrows to view previous/next weeks. Default view is
the current week.

**Why week view (not month):**
- Brief explicitly says "weekly streak calendar"
- A week fits cleanly without scroll on any screen
- Month view is Phase 2

### 4. Daily Completion Toggle

Clicking a habit's "today" cell toggles completion:
- If not completed: INSERT into completions (UNIQUE constraint prevents dupes)
- If already completed: DELETE from completions for that habit+date

This is a POST request (state change) with CSRF protection. Uses
INSERT OR IGNORE + DELETE pattern, or a single conditional route.

**Idempotent by design:** The UNIQUE(habit_id, completed_date) constraint
means duplicate inserts are impossible even under concurrent requests.

### 5. Dashboard

The main page (`/`) shows:
- All active (non-archived) habits in a list
- For each: name, current streak count, today's completion status
- A "Mark Done" button for habits not yet completed today
- Quick visual: green checkmark (done) or gray circle (not done)

Below or beside the list: the weekly calendar view for all habits combined.

### 6. Architecture

```
habit-tracker-web/
  app/
    __init__.py          # App factory (Flask, CSRF, SECRET_KEY)
    db.py                # get_db context manager, init_db
    models.py            # habit CRUD, completion toggle, streak computation
    blueprints/
      habits.py          # All routes (dashboard, CRUD, toggle, calendar)
    templates/
      base.html          # Shared layout
      dashboard.html     # Main view with habits + streaks
      calendar.html      # Weekly calendar partial/page
      habits/
        form.html        # Create/edit habit form
    static/
      css/style.css      # Minimal custom CSS
  schema.sql
  requirements.txt
  run.py
```

Single blueprint is sufficient (no admin vs public split needed for single-user).

### 7. Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | / | Dashboard (list habits + today status + streaks) |
| GET | /habits/new | Show create form |
| POST | /habits | Create habit |
| GET | /habits/<id>/edit | Show edit form |
| POST | /habits/<id>/edit | Update habit name |
| POST | /habits/<id>/delete | Soft-delete (archive) habit |
| POST | /habits/<id>/toggle | Toggle today's completion |
| POST | /habits/<id>/toggle/<date> | Toggle specific date's completion |
| GET | /calendar | Weekly calendar view (query param: ?week=2026-05-19) |
| GET | /health | Health check endpoint |

### 8. CSRF Protection

Flask-WTF CSRFProtect on all POST forms. The toggle button is a mini-form with
hidden CSRF token (same pattern as feedback-board upvote). No bare links for
state changes.

### 9. SECRET_KEY Handling

From environment variable. Fail-closed in production, fallback to dev-only
value in debug mode (same pattern as feedback-board).

### 10. CSS Approach

Single `style.css` file. Clean, minimal custom CSS. The calendar grid uses
CSS Grid (7 columns). Streak indicators use simple colored circles.
No CSS framework needed at this scale.

### 11. Date Handling

- All dates stored as ISO 8601 TEXT in SQLite (`YYYY-MM-DD`)
- Python `datetime.date` for all computation
- Week boundaries computed in Python, not SQL
- System local timezone via `date.today()` (same as CLI version -- sufficient
  for single-user personal tool)

## Scope Boundaries

**In scope (Phase 1 / this build):**
- Habit CRUD (create, edit, delete/archive)
- Daily completion toggle (today + past dates via calendar)
- Weekly calendar view with streak visualization
- Dashboard showing all habits with current streaks
- CSRF protection on all POST forms
- SECRET_KEY from environment
- Health endpoint
- Input validation (habit name: 1-100 chars, trimmed)

**Out of scope (Phase 2+):**
- Multi-user / auth
- Mobile app or responsive mobile-first design
- Notifications / reminders
- Monthly/yearly calendar views
- Habit categories and tags
- Analytics beyond streak count
- Export to CSV

## Lessons Applied

| Lesson | Source | How Applied |
|--------|--------|-------------|
| CSRF on all POST forms | autopilot-swarm-orchestration, FC4 | Flask-WTF CSRFProtect |
| SECRET_KEY from env | autopilot-swarm-orchestration | `os.environ.get()` with fail-closed |
| Deduplicate before date math | cli-habit-tracker solution doc | Set comprehension in streak functions |
| Guard empty lists before max() | cli-habit-tracker solution doc | Check `if not completions` first |
| Idempotent operations | cli-habit-tracker solution doc | UNIQUE constraint + INSERT OR IGNORE |
| BEGIN IMMEDIATE for writes | feedback-board pattern | get_db(immediate=True) for toggles |
| Health endpoint | sandbox standard | GET /health with DB connectivity check |
| No file locking | cli-habit-tracker brainstorm | SQLite handles concurrency; single user anyway |

## Open Questions

1. **Should the calendar allow toggling past dates?** Leaning yes -- sometimes you
   forget to mark a habit and want to backfill yesterday. The toggle/<date> route
   handles this. Limit to current week only (no backfilling months ago).

2. **Week start day (Monday vs Sunday)?** Default to Monday (ISO standard). Could
   be a config option later but not for MVP.

3. **Should archived habits show in calendar history?** Leaning no for MVP -- once
   archived, they disappear from all views. Historical data preserved in DB for
   future analytics phase.

## Refinement Findings

**Gaps found:** 4

1. **Flask URL Shortener API** -- `init_db()` must run at startup only (not per-request), and WAL mode should be enabled for SQLite to prevent "database is locked" errors during overlapping browser requests.
   - Source: `docs/solutions/2026-04-05-flask-url-shortener-api.md`
   - Relevance: The brainstorm defines `db.py` with `get_db` and `init_db` but does not specify that `init_db` runs once at startup or that WAL mode is needed. Even a single-user app can trigger concurrent requests (e.g., rapid toggle clicks before the first response returns).

2. **Feedback Board Solo Build** -- `init_db` needs try/finally to prevent file descriptor leaks if schema execution fails.
   - Source: `docs/solutions/2026-05-18-feedback-board-solo-build.md`
   - Relevance: The brainstorm mentions `init_db` but not FD leak prevention. This was a P1 finding in the feedback-board review. Same risk applies here since both apps use the identical `init_db` pattern.

3. **DB Migration Runner** -- Never use `executescript()` for schema initialization because it has an implicit COMMIT side effect that can break open transactions.
   - Source: `docs/solutions/2026-04-05-db-migration-runner.md`
   - Relevance: The brainstorm's `schema.sql` will need to be executed during `init_db`. Using `executescript()` seems natural but is unsafe. Should use individual `conn.execute()` calls or read/split-by-statement instead.

4. **Flask URL Shortener API** -- Atomic SQL increment pattern (`SET col = col + 1`) prevents TOCTOU races on counters.
   - Source: `docs/solutions/2026-04-05-flask-url-shortener-api.md`
   - Relevance: While the habit-tracker doesn't store explicit counters, the toggle route's INSERT/DELETE pattern should be atomic. The brainstorm correctly uses UNIQUE constraint + INSERT OR IGNORE, but the plan should verify that the toggle logic doesn't read-then-decide-then-write (TOCTOU) under rapid clicks.

STATUS: PASS

## Feed-Forward

- **Hardest decision:** Whether to store completions in a separate table vs a JSON
  array column. Chose separate table because SQLite can query date ranges efficiently,
  and the UNIQUE constraint provides built-in idempotency. The tradeoff is slightly
  more complex queries (JOINs), but the benefit is cleaner data integrity.
- **Rejected alternatives:** Extending the CLI tool with curses-based TUI (too
  limited for calendar visualization), storing streaks as computed columns (stale
  data risk, same lesson as CLI version), using a JS frontend with Flask API
  (unnecessary complexity for single-user app).
- **Least confident:** Whether the weekly calendar UI will feel intuitive for
  toggling completions on past dates. The interaction model (click a cell to
  toggle) needs to be visually clear about which date you're toggling and whether
  it's currently marked or not. Plan phase should sketch the visual states.
