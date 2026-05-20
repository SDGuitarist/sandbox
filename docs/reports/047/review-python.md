# Python Code Quality Review -- Solopreneur Command Center

**Reviewer:** Kieran (Python quality agent)
**Date:** 2026-05-19
**Scope:** 14 route files, `db.py`, `models.py`, `filters.py`, `decorators.py`, `__init__.py`, `schema.sql`
**Estimated LOC reviewed:** ~3,200 (routes + core) + ~1,570 (models) + schema

---

## Verdict

The codebase is structurally sound for a 16-agent swarm build. The `db.py` context manager pattern is solid, the schema has proper indexes and FTS5 triggers, and the `|dollars` filter is consistent. However, there are several findings that range from a money-handling bug (P1) to pervasive code duplication that will make the next feature addition painful (P2).

---

## P1 -- Must Fix

### P1-1. Race condition in auth registration (check-then-act)

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/auth/routes.py`, lines 61-78

The registration flow checks email uniqueness in one `get_db()` call (read-only), then inserts in a separate `get_db(immediate=True)` call. Between those two calls, another request could register the same email. The UNIQUE constraint on `user.email` will raise an unhandled `sqlite3.IntegrityError`, resulting in a 500 error instead of a friendly flash message.

**Fix:** Move the uniqueness check inside the same `get_db(immediate=True)` block as the INSERT, or wrap the INSERT in a try/except for `IntegrityError`.

```python
# Option A: single transaction
with get_db(immediate=True) as db:
    existing = db.execute("SELECT id FROM user WHERE email = ?", (email,)).fetchone()
    if existing:
        flash('An account with that email already exists.', 'error')
        return render_template('auth/register.html')
    db.execute("INSERT INTO user ...")

# Option B: catch the constraint violation
with get_db(immediate=True) as db:
    try:
        db.execute("INSERT INTO user ...", ...)
    except sqlite3.IntegrityError:
        flash('An account with that email already exists.', 'error')
        return render_template('auth/register.html')
```

### P1-2. Unguarded `int(float(...))` in settings financial route

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/settings/routes.py`, lines 104-105 and 139-140 and 149

```python
rate_cents = int(float(rate_dollars) * 100)  # line 105
monthly_cents = int(float(monthly_dollars) * 100)  # line 139
quarterly_cents = int(float(quarterly_dollars) * 100)  # line 140
int(request.form.get('weekly_hours_target', 40))  # line 149
int(request.form.get('fiscal_year_start', 1))  # line 116
```

These are NOT wrapped in try/except. If a user submits a non-numeric string (or an empty string), this will raise `ValueError` and produce a 500 error. Every other route in the codebase wraps identical conversions in try/except. The settings routes are the exception.

**Fix:** Apply the same `try/except (ValueError, TypeError)` pattern used everywhere else (e.g., `pipeline/routes.py` lines 129-132).

### P1-3. `_get_or_create_profile` calls `conn.commit()` inside a non-immediate connection

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/settings/routes.py`, line 50

```python
def _get_or_create_profile(conn):
    ...
    if row is None:
        conn.execute("INSERT INTO business_profile ...")
        conn.commit()  # <-- explicit commit on a read-only connection
```

When called from a GET route (line 89: `with get_db() as conn`), this issues a manual `commit()` on a connection that was not opened with `immediate=True`. The `get_db()` context manager only commits/rollbacks when `immediate=True`. This creates an inconsistency: the helper does its own commit, but if the INSERT fails, the context manager does not rollback because it was not in immediate mode. This is fragile and will surprise the next developer.

**Fix:** Either always call `_get_or_create_profile` inside a `get_db(immediate=True)` block, or remove the explicit `conn.commit()` and have the caller manage the transaction.

### P1-4. `setup_required` decorator queries the database on every single request

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/decorators.py`, lines 17-25

Every protected route opens a database connection just to check `setup_complete`. With 13 blueprints all using this decorator, every page load incurs an extra SELECT before the route's own queries even begin.

**Why this is P1:** The decorator also opens a brand new `get_db()` connection that is fully separate from the connection the route will open moments later. This means every write route (create, edit, delete) opens at minimum two database connections per request: one in the decorator, one in the route.

**Fix:** Cache `setup_complete` in the session after the first check. The value only changes once (during `/auth/setup`), so after that it never needs to be re-queried.

```python
def setup_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if not session.get('setup_complete'):
            with get_db() as db:
                user = db.execute(
                    "SELECT setup_complete FROM user WHERE id = ?",
                    (session['user_id'],),
                ).fetchone()
                if not user or not user['setup_complete']:
                    return redirect(url_for('auth.setup'))
                session['setup_complete'] = True
        return f(*args, **kwargs)
    return decorated
```

---

## P2 -- Should Fix

### P2-1. `PIPELINE_STAGES` is duplicated across three files

**Locations:**
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/pipeline/routes.py`, lines 8-16
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/models.py`, lines 17-27

Both define the identical `PIPELINE_STAGES` list and `STAGE_MAP` dict. If a stage is added or a probability changes, both files must be updated in lockstep. This is a classic divergence bug waiting to happen.

**Fix:** Define `PIPELINE_STAGES` and `STAGE_MAP` in one place (e.g., `models.py` since it already has them) and import from there into `pipeline/routes.py`.

### P2-2. `EXPORT_MODULES` is duplicated between reports and settings

**Locations:**
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/reports/routes.py`, lines 14-25
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/settings/routes.py`, lines 12-23

Identical dict mapping module names to table names. If a new table is added, it must be added in two places.

**Fix:** Extract to a shared constant (e.g., in `models.py` or a new `constants.py`).

### P2-3. N+1 query pattern in pipeline board view

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/pipeline/routes.py`, lines 32-48

```python
for key, label, probability in BOARD_STAGES:
    deals = db.execute(
        "SELECT d.*, c.name as contact_name ..."
        "WHERE d.stage = ? ...",
        (key,)
    ).fetchall()
```

This executes 5 separate queries (one per active stage) inside a loop. For a Kanban board that will be loaded on nearly every session, this should be a single query that fetches all active deals, then groups them in Python.

**Fix:**
```python
all_deals = db.execute(
    "SELECT d.*, c.name as contact_name "
    "FROM deal d LEFT JOIN contact c ON d.contact_id = c.id "
    "WHERE d.stage NOT IN ('won', 'lost') "
    "ORDER BY d.updated_at DESC"
).fetchall()

from itertools import groupby
deals_by_stage = {k: list(g) for k, g in groupby(all_deals, key=lambda d: d['stage'])}
```

### P2-4. N+1 query pattern in pipeline stats view

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/pipeline/routes.py`, lines 336-350

Same pattern: one SELECT per stage inside a loop. Additionally duplicated in `models.py` `get_pipeline_stats()` (lines 1427-1443).

### P2-5. Activity log insertion is copy-pasted ~30 times across routes

Nearly every create/update/delete route contains:
```python
db.execute(
    "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
    ('created', 'contact', contact_id, f"Created contact {name}")
)
```

This is the same 3-line pattern with only the parameters changing. The `models.py` file already has `create_activity()`. The `settings/routes.py` file already has a `_log_activity()` helper. Neither is used by any other route file.

**Fix:** Use the existing `create_activity()` from `models.py` everywhere, or create a thin wrapper in a shared module. This reduces ~90 lines of duplicated SQL to single function calls.

### P2-6. Form-parsing boilerplate is heavily duplicated (tasks create vs. edit)

**Files:**
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/tasks/routes.py`, lines 100-142 vs. 172-218

The create and edit routes parse the exact same 11 form fields with the exact same validation and type conversion logic. This is ~40 lines of identical code.

Similarly duplicated in:
- `contacts/routes.py` create (lines 106-124) vs. edit (lines 158-177)
- `pipeline/routes.py` create (lines 121-141) vs. edit (lines 195-216)
- `revenue/routes.py` `add_income` vs. `edit_income`, `add_expense` vs. `edit_expense`

**Fix:** Extract a `_parse_task_form(request) -> dict` helper per entity, called by both create and edit. This is the correct level of DRY -- no shared abstraction across entities, just within each entity.

### P2-7. `SELECT *` used extensively in routes that only need a few columns

**Examples:**
- `contacts/routes.py` detail: `SELECT * FROM contact WHERE id = ?` then only reads `name`, `company_id`
- `pipeline/routes.py` board: `SELECT d.*, c.name as contact_name` fetches all deal columns including `notes`, `loss_reason`, etc. that the board template does not display
- `reports/routes.py` export: `SELECT * FROM {table}` fetches all data -- this is intentional for export

For the detail/list views, explicitly naming columns would be cleaner but is low-impact for a single-user SQLite app. Flagging as P2 only because it sets a bad habit for when this codebase grows.

### P2-8. `db.py` module-level mutable global `DATABASE`

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/db.py`, lines 5, 9

```python
DATABASE = None  # Set by init_app

def init_app(app):
    global DATABASE
    DATABASE = app.config['DATABASE']
```

A module-level mutable global is fragile. If `create_app()` is called twice (e.g., in tests), the global is silently overwritten. Flask's convention is to read from `current_app.config`.

**Fix:** Replace `DATABASE` references in `get_db()` and `get_raw_connection()` with `current_app.config['DATABASE']`. This also eliminates the global.

### P2-9. No multi-tenancy guard -- routes do not filter by `user_id`

Every query in every route operates on unscoped data. The `user` table exists and `session['user_id']` is set, but no route ever includes `WHERE user_id = ?` in its queries (except `settings/routes.py` for `business_profile`). This means if a second user registers, they see all of user 1's data.

This is acceptable for a single-user solopreneur tool, but the moment the app is shared (even accidentally), all data leaks. Worth noting as P2 because the `user` table and session infrastructure are already there.

### P2-10. `revenue/routes.py` `pl()` and `by_month()` are nearly identical

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/revenue/routes.py`

Lines 247-298 (`pl`) and lines 331-365 (`by_month`) execute the same two queries, build the same `income_by_month`/`expense_by_month` dicts, iterate the same way, and compute the same `profit`/`margin_pct`. The only difference is that `pl()` also computes YTD totals and renders `revenue/pl.html`, while `by_month()` renders `revenue/by_month.html`.

**Fix:** Extract the shared query + computation into a helper function.

### P2-11. Missing index on `time_entry(project_id, billable)`

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/schema.sql`

The `reports/routes.py` time report (line 137) and utilization report (line 272) both run:
```sql
SUM(CASE WHEN te.billable = 1 THEN te.minutes ELSE 0 END)
```

grouped by `project_id` or `date`. The existing `idx_time_entry_project` only covers `project_id`. A composite index on `(project_id, billable, minutes)` would allow SQLite to satisfy these queries from the index alone.

Similarly, `income(contact_id)` has an index but `income(project_id)` does not, even though several queries filter on it.

### P2-12. Reports CSV export has no row limit

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/reports/routes.py`, line 370

```python
rows = db.execute(f"SELECT * FROM {table}").fetchall()
```

No LIMIT clause. For a solopreneur app this is unlikely to be a problem, but if `activity_log` grows large (it gets a row on every single action), this could OOM the process.

The `settings/routes.py` export (line 259) has the same issue.

---

## P3 -- Nice to Have

### P3-1. No type hints anywhere

Not a single function signature in any route file has type hints. The `models.py` functions are also untyped. For a Flask app this is common, but it makes IDE support and static analysis impossible.

**Example of what good looks like:**
```python
def _parse_cents(value_str: str) -> int:
    """Convert a dollar string from the form to integer cents."""
    try:
        return int(float(value_str) * 100)
    except (ValueError, TypeError):
        return 0
```

### P3-2. `_parse_cents` helper exists in `projects/routes.py` but not shared

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/projects/routes.py`, lines 14-19

This is the exact logic used in `pipeline/routes.py` (lines 129-132), `revenue/routes.py` (lines 23-26, 73-76, 141-144, 183-186), `goals/routes.py` (lines 79-82), and `settings/routes.py` (lines 104-105). Only `projects/routes.py` extracted it into a named function. The other 5+ locations inline the same try/except block.

**Fix:** Move `_parse_cents` to a shared module and import it everywhere.

### P3-3. Status/priority/source constants are hardcoded as inline lists

Across routes, these lists appear repeatedly:
- `['lead', 'active_client', 'past_client', 'partner']` -- contacts (3 occurrences)
- `['referral', 'website', 'social', 'cold_outreach', 'other']` -- contacts/pipeline (5 occurrences)
- `['not_started', 'in_progress', 'on_hold', 'completed', 'cancelled']` -- projects (4 occurrences)
- `['low', 'medium', 'high', 'urgent']` -- tasks (4 occurrences)
- `['todo', 'in_progress', 'done']` -- tasks (4 occurrences)

If a new status is added, every occurrence must be found and updated.

**Fix:** Define these as module-level constants (e.g., `CONTACT_STATUSES`, `PROJECT_STATUSES`) in the respective blueprint or in a shared `constants.py`.

### P3-4. `models.py` is 1,574 lines and growing

This file contains CRUD functions for all 21 tables plus dashboard aggregation queries plus report helpers. It is well-organized with section headers, but at this size it becomes hard to navigate and is a merge conflict magnet in multi-agent builds.

**Fix:** Consider splitting into `models/contact.py`, `models/project.py`, `models/dashboard.py`, `models/reports.py`, etc. Each module handles one domain.

### P3-5. Routes do not use `models.py` functions

The `models.py` file provides `create_contact()`, `get_contact()`, `list_contacts()`, `update_contact()`, `delete_contact()`, and equivalent functions for every entity. None of the route files use them. Every route writes its own raw SQL.

This means there are two complete data access layers: one in `models.py` and one scattered across 14 route files. Changes to the schema must be reflected in both places.

**Assessment:** This is likely a swarm build artifact -- one agent generated `models.py`, another generated routes independently. For now, this is P3 because both layers work. Long-term, pick one and delete the other.

### P3-6. `search/routes.py` swallows FTS5 exceptions silently

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/search/routes.py`, lines 45-56 and 131-141

```python
try:
    notes = db.execute("... WHERE notes_fts MATCH ? ...", (query,)).fetchall()
except Exception:
    notes = db.execute("... WHERE title LIKE ? ...", (like_pattern,)).fetchall()
```

The bare `except Exception` catches everything including programming errors. The intent is to catch invalid FTS5 syntax, but the correct exception to catch is `sqlite3.OperationalError`.

### P3-7. `date` used as a variable name shadowing the `date` module

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/revenue/routes.py`, lines 29, 80

```python
date = request.form.get('date', '').strip()
```

This shadows `from datetime import date` if it were imported (it is not in this file, but the pattern is confusing). The `notes/routes.py` file handles this correctly by importing `from datetime import date as date_module`.

### P3-8. `get_raw_connection()` in `db.py` is never used

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/db.py`, lines 20-25

Dead code. No file in the codebase imports or calls `get_raw_connection()`.

### P3-9. FTS5 content tables may drift from source tables

The FTS5 virtual tables use `content='note'` and `content='journal_entry'` with triggers to keep them in sync. However, if data is modified outside the triggers (e.g., direct `executescript` during a migration), the FTS index becomes stale. This is a known SQLite FTS5 limitation, not a code bug, but worth documenting.

### P3-10. `filters.py` functions lack type hints

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/filters.py`

```python
def dollars(cents, symbol='$'):   # should be: def dollars(cents: int | None, symbol: str = '$') -> str:
def minutes_to_hours(minutes):    # should be: def minutes_to_hours(minutes: int | None) -> str:
```

---

## Positive Observations

1. **Money handling is consistent.** All monetary values are stored as integer cents in the schema. The `|dollars` Jinja filter correctly divides by 100. Form inputs are converted with `int(float(x) * 100)`. No floating-point dollar amounts are stored.

2. **Transaction boundaries are correct.** Write operations use `get_db(immediate=True)` which issues `BEGIN IMMEDIATE`, auto-commits on success, and rolls back on exception. Read-only operations use `get_db()` without immediate mode. Helpers like `_render_income_form` correctly use read-only connections.

3. **SQL injection is not possible.** All user inputs are parameterized. The `EXPORT_MODULES` whitelist prevents table name injection in CSV export. The `_safe_order` / `_safe_direction` helpers in `models.py` whitelist ORDER BY columns.

4. **Schema has good index coverage.** Foreign keys, status columns, date columns, and `created_at` on `activity_log` are all indexed. FTS5 virtual tables with proper sync triggers for full-text search.

5. **CSRF protection is enabled globally** via `flask_wtf.csrf.CSRFProtect`.

6. **`get_db()` context manager pattern is clean.** Resource management via `with` statement ensures connections are always closed, even on exception.

7. **CSV export in settings has formula injection protection** (`_sanitize_csv`), while the reports export does not (noted but not flagged as a finding since this is a single-user app).

---

## Summary Table

| ID | Severity | Category | File(s) | One-line summary |
|----|----------|----------|---------|-----------------|
| P1-1 | P1 | Transaction | auth/routes.py | Race condition in email uniqueness check |
| P1-2 | P1 | Error handling | settings/routes.py | Unguarded int/float conversions crash on bad input |
| P1-3 | P1 | Transaction | settings/routes.py | Helper calls commit() on non-immediate connection |
| P1-4 | P1 | Performance | decorators.py | setup_required opens a DB connection on every request |
| P2-1 | P2 | Duplication | pipeline/routes.py, models.py | PIPELINE_STAGES defined twice |
| P2-2 | P2 | Duplication | reports/routes.py, settings/routes.py | EXPORT_MODULES defined twice |
| P2-3 | P2 | Performance | pipeline/routes.py | N+1 queries in board view (5 SELECTs in a loop) |
| P2-4 | P2 | Performance | pipeline/routes.py, models.py | N+1 queries in stats view |
| P2-5 | P2 | Duplication | all routes | Activity log INSERT copy-pasted ~30 times |
| P2-6 | P2 | Duplication | tasks, contacts, pipeline, revenue | Form-parsing boilerplate duplicated in create vs. edit |
| P2-7 | P2 | Style | all routes | SELECT * when only a few columns are needed |
| P2-8 | P2 | Architecture | db.py | Module-level mutable global for DATABASE path |
| P2-9 | P2 | Security | all routes | No user_id scoping on any query |
| P2-10 | P2 | Duplication | revenue/routes.py | pl() and by_month() are near-identical |
| P2-11 | P2 | Performance | schema.sql | Missing composite index on time_entry(project_id, billable) |
| P2-12 | P2 | Safety | reports/routes.py, settings/routes.py | CSV export has no row limit |
| P3-1 | P3 | Style | all files | No type hints on any function |
| P3-2 | P3 | Duplication | projects/routes.py | _parse_cents exists but is not shared |
| P3-3 | P3 | Duplication | contacts, projects, tasks, pipeline | Status/priority constants hardcoded as inline lists |
| P3-4 | P3 | Architecture | models.py | 1,574-line monolith file |
| P3-5 | P3 | Architecture | models.py vs. routes | Two complete data access layers, neither uses the other |
| P3-6 | P3 | Error handling | search/routes.py | Bare except Exception swallows errors |
| P3-7 | P3 | Style | revenue/routes.py | Variable name shadows module name |
| P3-8 | P3 | Dead code | db.py | get_raw_connection() is never called |
| P3-9 | P3 | Documentation | schema.sql | FTS5 content tables can drift |
| P3-10 | P3 | Style | filters.py | Missing type hints on filter functions |
