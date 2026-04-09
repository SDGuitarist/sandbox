---
title: "feat: Personal Finance Tracker with Budgets"
type: feat
status: active
date: 2026-04-09
origin: docs/brainstorms/2026-04-09-personal-finance-tracker-brainstorm.md
swarm: true
agents: 3
feed_forward:
  risk: "Cents conversion layer -- every form input multiplies by 100, every display divides by 100. A missed conversion shows $4599 instead of $45.99 or vice versa. Must be verified on every input/output path."
  verify_first: true
deepened: 2026-04-09
---

# feat: Personal Finance Tracker with Budgets

## Enhancement Summary

**Deepened on:** 2026-04-09
**Review agents used:** 6 (architecture, security, performance, simplicity, pattern, specflow)

### Key Improvements from Deepening
1. Moved dashboard/budget routes from `__init__.py` to a `views` blueprint (architecture)
2. Extracted `dollars_to_cents` and `format_dollars` to `app/utils.py` (architecture)
3. Added `year_month` format validation (`^\d{4}-\d{2}$`) on all routes (security)
4. Fixed `dollars_to_cents` to reject NaN, Inf, and amounts rounding to 0 cents (security)
5. Replaced N+1 budget queries with `get_budgets_for_month` batch query (performance)
6. Added composite index `idx_transactions_cat_date` (performance)
7. Changed date filter from LIKE to range predicate for index use (performance)
8. Cut `get_monthly_total` -- derive from dashboard data with `sum()` (simplicity)
9. Added max amount cap (999999.99 = 99999999 cents) in validation (specflow)
10. Added delete confirmation pattern for categories (specflow)
11. Budget POST flashes error on invalid amounts instead of silent skip (security)

---

## Overview

Personal finance tracker with spending categories, transactions, and monthly
budgets per category. Dashboard shows budget-vs-actual for the current month
with a month selector for history. Flask + SQLite + Jinja2, following the
recipe-organizer/bookmark-manager swarm pattern.

(see brainstorm: docs/brainstorms/2026-04-09-personal-finance-tracker-brainstorm.md)

## Problem Statement

No centralized place to track personal spending by category and compare it
against monthly budgets. The core value: "Am I over budget this month, and
where?"

## Proposed Solution

Three-domain Flask app (categories, transactions, budgets) with a dashboard
view. Money stored as integer cents to avoid floating-point issues. Categories
are color-coded. Budgets are per-category per-month. Dashboard aggregates
spending with LEFT JOIN to show budget vs. actual. "Uncategorized" is a
permanent seed category (id=1) that absorbs orphaned transactions on category
deletion.

---

## Plan Quality Gate

1. **What exactly is changing?** New `finance-tracker/` directory with ~20 files: app factory, db layer, models, 2 blueprints (categories, transactions), dashboard route, templates, static CSS, schema, run.py.
2. **What must not change?** No files outside `finance-tracker/` are modified. No changes to other sandbox apps.
3. **How will we know it worked?** Smoke test: create category, add transaction with amount in dollars, verify cents stored correctly, set budget, dashboard shows correct budget vs. actual, delete category and verify transactions reassigned to Uncategorized.
4. **Most likely way this plan is wrong?** The cents conversion -- if any form input or display path misses the *100 or /100 conversion, amounts appear 100x too large or too small. The plan defines exact conversion points below.

---

## File Structure

```
finance-tracker/
    run.py
    requirements.txt
    app/
        __init__.py              # App factory + CSRF + error handlers
        db.py                    # DB connection context manager
        models.py                # All SQL queries as pure functions
        utils.py                 # dollars_to_cents, format_dollars (pure functions)
        schema.sql               # DDL for all tables + indexes + seed data
        static/
            style.css            # Complete CSS
        templates/
            layout.html          # Base template with nav
            dashboard.html       # Monthly overview with budget bars
            errors/
                404.html         # Not found page
                403.html         # CSRF forbidden page
            categories/
                list.html        # Category index
                form.html        # Create/edit category form
            transactions/
                list.html        # Transaction list with category colors
                form.html        # Create/edit transaction form
            budgets/
                manage.html      # Budget management per month
        blueprints/
            categories/
                __init__.py      # Blueprint registration
                routes.py        # Category CRUD routes
            transactions/
                __init__.py      # Blueprint registration
                routes.py        # Transaction CRUD routes
            views/
                __init__.py      # Blueprint registration
                routes.py        # Dashboard + budget routes
```

---

## Database Schema

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(length(name) <= 50),
    color TEXT NOT NULL DEFAULT '#6366f1' CHECK(length(color) <= 7),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

-- Seed permanent "Uncategorized" category
INSERT OR IGNORE INTO categories (id, name, color) VALUES (1, 'Uncategorized', '#9ca3af');

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL DEFAULT 1 REFERENCES categories(id) ON DELETE SET DEFAULT,
    amount INTEGER NOT NULL CHECK(amount > 0),
    description TEXT NOT NULL DEFAULT '' CHECK(length(description) <= 200),
    transaction_date TEXT NOT NULL DEFAULT (date('now')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

-- Composite index covers both category filter and date range queries.
-- Replaces separate single-column indexes.
CREATE INDEX IF NOT EXISTS idx_transactions_cat_date
    ON transactions(category_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_date
    ON transactions(transaction_date);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    year_month TEXT NOT NULL CHECK(length(year_month) = 7),
    amount INTEGER NOT NULL CHECK(amount > 0),
    UNIQUE(category_id, year_month)
);

CREATE INDEX IF NOT EXISTS idx_budgets_year_month
    ON budgets(year_month);
```

### Key Schema Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Money storage | `INTEGER` (cents) | Avoids floating-point rounding. $45.99 = 4599. (see brainstorm: Key Decisions) |
| Category deletion | `ON DELETE SET DEFAULT` | Reassigns transactions to Uncategorized (id=1). Preserves financial history. |
| Budget deletion | `ON DELETE CASCADE` | Budgets for deleted category are meaningless |
| Budget period | `year_month TEXT` ('YYYY-MM') | Simple to query, sort, display. UNIQUE(category_id, year_month) prevents duplicates |
| Budget amount=0 | Not allowed (`CHECK(amount > 0)`) | $0 budget has no meaning. "No budget" = no row in table |
| Category name | `UNIQUE COLLATE NOCASE` | Prevents "Food" vs "food" duplicates |
| Uncategorized | Seeded as id=1, guarded in app | Cannot be deleted or renamed. Always exists as fallback |

---

## Cents Conversion Layer (Feed-Forward Risk Area)

This is the highest-risk area. Every path that touches money must convert correctly.

### `app/utils.py` (pure functions, no Flask dependency)

```python
import math

MAX_AMOUNT_CENTS = 99_999_999  # $999,999.99

def dollars_to_cents(value_str):
    """Convert user input like '45.99' to integer cents 4599.
    Raises ValueError on invalid input."""
    value = float(value_str)
    if math.isnan(value) or math.isinf(value):
        raise ValueError("Invalid amount")
    if value <= 0:
        raise ValueError("Amount must be positive")
    cents = int(round(value * 100))
    if cents <= 0:
        raise ValueError("Amount too small (rounds to zero)")
    if cents > MAX_AMOUNT_CENTS:
        raise ValueError("Amount too large (max $999,999.99)")
    return cents

def format_dollars(cents):
    """Format integer cents as dollar string. 4599 -> '$45.99'"""
    if cents is None:
        return "—"
    return f"${cents / 100:.2f}"

def validate_year_month(value):
    """Validate 'YYYY-MM' format. Raises ValueError if invalid."""
    import re
    if not re.match(r'^\d{4}-\d{2}$', value):
        raise ValueError("Invalid month format")
    year, month = int(value[:4]), int(value[5:7])
    if month < 1 or month > 12:
        raise ValueError("Invalid month")
    return value
```

**Where used:**
- Transaction create/edit: `amount = dollars_to_cents(request.form["amount"])`
- Budget set: `amount = dollars_to_cents(field)`
- Dashboard/budget routes: `year_month = validate_year_month(request.args.get("month", ...))`

### Output (database -> display): divide by 100

```python
# Registered as Jinja2 filter |dollars in app factory:
# app.jinja_env.filters["dollars"] = format_dollars
```

**Where used:**
- Every template that shows an amount uses `{{ amount|dollars }}`
- Dashboard budget remaining calculation done in cents, formatted at display

### Template filter registration (in app factory)

```python
app.jinja_env.filters["dollars"] = format_dollars
```

### Anti-Patterns (DO NOT DO THIS)

```python
# WRONG: storing dollars as float
amount = float(request.form["amount"])  # 45.99 might become 45.98999...

# WRONG: displaying raw cents
{{ transaction.amount }}  # shows 4599 instead of $45.99

# WRONG: converting in template math
{{ transaction.amount / 100 }}  # no formatting, shows 45.99 not $45.99

# WRONG: forgetting conversion on form prefill
<input value="{{ transaction.amount }}">  # shows 4599 in edit form
# CORRECT:
<input value="{{ '%.2f'|format(transaction.amount / 100) }}">
```

---

## Models Layer (`app/models.py`)

All functions are pure, taking `conn: sqlite3.Connection` as the first argument.
Money values are always in cents at the model layer. No conversion in models.

### Constants

```python
ITEMS_PER_PAGE: Final[int] = 20
```

### Function Signatures + Return Types + Usage Examples

| Function | Parameters | Returns | Usage Example |
|----------|-----------|---------|---------------|
| `get_all_categories` | `conn` | `list[Row]` | `cats = get_all_categories(conn)` |
| `get_category` | `conn, category_id` | `Row \| None` | `cat = get_category(conn, 1); if cat is None: abort(404)` |
| `create_category` | `conn, name, color` | `int` | `cat_id = create_category(conn, "Food", "#22c55e"); redirect(...)` |
| `update_category` | `conn, category_id, name, color` | `None` | `update_category(conn, 2, "Groceries", "#16a34a")` |
| `delete_category` | `conn, category_id` | `bool` | `ok = delete_category(conn, 5)  # returns False if id=1` |
| `get_transactions` | `conn, year_month, category_id, limit, offset` | `list[Row]` | `txns = get_transactions(conn, "2026-04", None, 20, 0)  # Row includes category_name, category_color` |
| `get_transaction_count` | `conn, year_month, category_id` | `int` | `total = get_transaction_count(conn, "2026-04", None)` |
| `get_transaction` | `conn, transaction_id` | `Row \| None` | `txn = get_transaction(conn, 42); if txn is None: abort(404)` |
| `create_transaction` | `conn, category_id, amount, description, transaction_date` | `int` | `txn_id = create_transaction(conn, 2, 4599, "", "2026-04-09"); redirect(...)` |
| `update_transaction` | `conn, transaction_id, category_id, amount, description, transaction_date` | `None` | `update_transaction(conn, 42, 2, 4599, "Lunch", "2026-04-09")` |
| `delete_transaction` | `conn, transaction_id` | `None` | `delete_transaction(conn, 42)` |
| `get_budget` | `conn, category_id, year_month` | `Row \| None` | `b = get_budget(conn, 2, "2026-04")  # None means no budget set` |
| `set_budget` | `conn, category_id, year_month, amount` | `None` | `set_budget(conn, 2, "2026-04", 50000)  # $500 budget` |
| `delete_budget` | `conn, category_id, year_month` | `None` | `delete_budget(conn, 2, "2026-04")` |
| `get_dashboard_data` | `conn, year_month` | `list[Row]` | `data = get_dashboard_data(conn, "2026-04")  # Row: category_id, name, color, spent, budget_amount` |
| `get_budgets_for_month` | `conn, year_month` | `dict[int, Row]` | `bmap = get_budgets_for_month(conn, "2026-04"); bmap.get(2)  # Row or None` |

### `get_transactions` with JOIN

```python
def get_transactions(conn, year_month=None, category_id=None, limit=20, offset=0):
    """Returns transactions with category_name and category_color via JOIN.
    Filters by year_month (prefix match on transaction_date) and/or category_id."""
    query = """
        SELECT t.*, c.name AS category_name, c.color AS category_color
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
    """
    conditions = []
    params = []
    if year_month:
        # Range predicate is index-friendly (unlike LIKE)
        conditions.append("t.transaction_date >= ? AND t.transaction_date < ?")
        params.extend([f"{year_month}-01", f"{year_month}-32"])
    if category_id:
        conditions.append("t.category_id = ?")
        params.append(category_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY t.transaction_date DESC, t.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return conn.execute(query, params).fetchall()
```

### `get_dashboard_data` (Budget vs Actual)

```python
def get_dashboard_data(conn, year_month):
    """Returns one row per category with spent amount and budget for the month.
    Categories with no transactions or no budget still appear (LEFT JOINs)."""
    return conn.execute("""
        SELECT
            c.id AS category_id,
            c.name,
            c.color,
            COALESCE(SUM(t.amount), 0) AS spent,
            b.amount AS budget_amount
        FROM categories c
        LEFT JOIN transactions t ON t.category_id = c.id
            AND t.transaction_date >= ?
            AND t.transaction_date < ?
        LEFT JOIN budgets b ON b.category_id = c.id
            AND b.year_month = ?
        GROUP BY c.id
        ORDER BY c.name COLLATE NOCASE
    """, (f"{year_month}-01", f"{year_month}-32", year_month)).fetchall()
```

### `get_budgets_for_month` (Batch -- replaces N+1)

```python
def get_budgets_for_month(conn, year_month):
    """Returns dict mapping category_id -> budget Row for one month.
    Single query replaces N individual get_budget calls."""
    rows = conn.execute(
        "SELECT * FROM budgets WHERE year_month = ?", (year_month,)
    ).fetchall()
    return {r["category_id"]: r for r in rows}
```

### `delete_category` Guard

```python
def delete_category(conn, category_id):
    """Delete a category. Returns False if trying to delete Uncategorized (id=1)."""
    if category_id == 1:
        return False
    conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    return True
```

### `set_budget` (Upsert)

```python
def set_budget(conn, category_id, year_month, amount):
    """Insert or update a budget for a category+month."""
    conn.execute("""
        INSERT INTO budgets (category_id, year_month, amount)
        VALUES (?, ?, ?)
        ON CONFLICT(category_id, year_month)
        DO UPDATE SET amount = excluded.amount
    """, (category_id, year_month, amount))
```

---

## Endpoint Registry

| Blueprint | Function | Method | Path | `url_for` Name |
|-----------|----------|--------|------|----------------|
| views | `dashboard` | GET | `/` | `views.dashboard` |
| categories | `index` | GET | `/categories/` | `categories.index` |
| categories | `create` | GET, POST | `/categories/new` | `categories.create` |
| categories | `edit` | GET, POST | `/categories/<int:category_id>/edit` | `categories.edit` |
| categories | `delete` | POST | `/categories/<int:category_id>/delete` | `categories.delete` |
| transactions | `index` | GET | `/transactions/` | `transactions.index` |
| transactions | `create` | GET, POST | `/transactions/new` | `transactions.create` |
| transactions | `edit` | GET, POST | `/transactions/<int:transaction_id>/edit` | `transactions.edit` |
| transactions | `delete` | POST | `/transactions/<int:transaction_id>/delete` | `transactions.delete` |
| views | `budgets_manage` | GET, POST | `/budgets/` | `views.budgets_manage` |

The dashboard is the home page (`/`). No redirect needed.

**Budget management:** Single page at `/budgets/` shows all categories for a
given month (via `?month=2026-04` query param, defaults to current month).
Each category has an amount input. POST submits all budgets at once. This
avoids per-category CRUD routes for budgets.

---

## Template Render Context

| Template | Route Function | Variables | Types |
|----------|---------------|-----------|-------|
| `dashboard.html` | `dashboard` | `data`, `year_month`, `total_spent`, `total_budgeted`, `months` | `list[Row]`, `str`, `int`, `int`, `list[str]` |
| `categories/list.html` | `categories.index` | `categories` | `list[Row]` |
| `categories/form.html` | `categories.create`, `categories.edit` | `category` (None for create), `is_edit` | `Row\|None`, `bool` |
| `transactions/list.html` | `transactions.index` | `transactions`, `year_month`, `category_id`, `categories`, `page`, `total_pages` | `list[Row]`, `str\|None`, `int\|None`, `list[Row]`, `int`, `int` |
| `transactions/form.html` | `transactions.create`, `transactions.edit` | `transaction` (None for create), `categories`, `is_edit` | `Row\|None`, `list[Row]`, `bool` |
| `budgets/manage.html` | `budgets_manage` | `categories`, `budgets_map`, `year_month`, `months` | `list[Row]`, `dict[int,Row\|None]`, `str`, `list[str]` |
| `errors/404.html` | error handler | `message` | `str` |
| `errors/403.html` | error handler | `message` | `str` |

### `months` helper

The dashboard and budget page need a list of months that have transactions,
plus the current month. This is a helper in routes or models:

```python
def get_available_months(conn):
    """Returns list of 'YYYY-MM' strings with transactions, plus current month."""
    rows = conn.execute("""
        SELECT DISTINCT substr(transaction_date, 1, 7) AS ym
        FROM transactions
        ORDER BY ym DESC
    """).fetchall()
    months = [r["ym"] for r in rows]
    current = date.today().strftime("%Y-%m")
    if current not in months:
        months.insert(0, current)
    return months
```

### `budgets_map` format

```python
# Dict mapping category_id -> budget Row (or KeyError = no budget for that month)
# Uses batch query instead of N+1 individual calls
budgets_map = get_budgets_for_month(conn, year_month)
# Template access: budgets_map.get(cat.id) -- returns Row or None
```

### Empty States

- `transactions/list.html`: "No transactions yet. Add your first expense!"
- `categories/list.html`: "No custom categories yet. Create one to organize your spending!"
- `dashboard.html` (no transactions): "No spending recorded this month."

---

## Budget Management UX

The budget page shows a table of all categories with their current budget for
the selected month. Each row has a dollar amount input. Submit updates all at
once.

```html
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <input type="hidden" name="year_month" value="{{ year_month }}">
    <table>
        <thead>
            <tr><th>Category</th><th>Budget</th></tr>
        </thead>
        <tbody>
            {% for cat in categories %}
            <tr>
                <td>
                    <span class="color-dot" style="background:{{ cat.color }}"></span>
                    {{ cat.name }}
                </td>
                <td>
                    <input type="number" name="budget_{{ cat.id }}"
                           step="0.01" min="0"
                           value="{{ '%.2f'|format(budgets_map[cat.id].amount / 100) if budgets_map[cat.id] else '' }}"
                           placeholder="No budget">
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <button type="submit" class="btn">Save Budgets</button>
</form>
```

**POST handler logic:**
```python
errors = []
for cat in categories:
    field = request.form.get(f"budget_{cat['id']}", "").strip()
    if field:
        try:
            amount_cents = dollars_to_cents(field)
            set_budget(conn, cat["id"], year_month, amount_cents)
        except ValueError as e:
            errors.append(f"{cat['name']}: {e}")
    else:
        delete_budget(conn, cat["id"], year_month)
if errors:
    flash(f"Some budgets had errors: {'; '.join(errors)}", "error")
else:
    flash("Budgets saved.", "success")
```

Empty field = remove budget. Non-empty = set/update. Invalid = flash error (not silent skip).

---

## Input Validation

| Field | Required | Max Length | Constraints |
|-------|----------|-----------|-------------|
| Category name | Yes | 50 | Non-empty after strip, unique (case-insensitive) |
| Category color | Yes | 7 | Hex format (#xxxxxx) |
| Transaction amount | Yes | - | Positive number, converted to cents |
| Transaction description | No | 200 | - |
| Transaction date | Yes | 10 | 'YYYY-MM-DD' format |
| Transaction category_id | Yes | - | Must reference existing category |
| Budget amount | Optional | - | Positive if provided, converted to cents |

Validation in route handlers before calling model functions. Flash error and
re-render form on failure. DB CHECK constraints as last defense. Dollar-to-cents
conversion wrapped in try/except ValueError.

---

## App Factory (`app/__init__.py`)

```python
import os
import secrets
from flask import Flask, session, request, abort, render_template
from .utils import format_dollars

def create_app(db_path=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(24))

    if db_path is None:
        db_path = "finance.db"
    app.config["DB_PATH"] = db_path

    # Register Jinja2 filter for cents -> dollars display
    app.jinja_env.filters["dollars"] = format_dollars

    from .db import init_db
    with app.app_context():
        init_db(app)

    # CSRF protection
    @app.before_request
    def csrf_protect():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        if request.method == "POST":
            token = request.form.get("csrf_token")
            if not token or token != session.get("csrf_token"):
                abort(403)

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": session.get("csrf_token", "")}

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html",
                               message="Page not found."), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html",
                               message="Request forbidden. Your session may "
                                       "have expired. Please go back and try "
                                       "again."), 403

    # Register blueprints
    from .blueprints.categories import categories_bp
    from .blueprints.transactions import transactions_bp
    from .blueprints.views import views_bp
    app.register_blueprint(categories_bp, url_prefix="/categories")
    app.register_blueprint(transactions_bp, url_prefix="/transactions")
    app.register_blueprint(views_bp)  # no prefix -- dashboard at /, budgets at /budgets/

    return app
```

## DB Layer (`app/db.py`)

```python
import os
import sqlite3
from contextlib import contextmanager
from flask import current_app

@contextmanager
def get_db(immediate=False):
    db_path = current_app.config["DB_PATH"]
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

# Usage (READ):
#   with get_db() as conn:
#       txn = get_transaction(conn, 42)
#
# Usage (WRITE):
#   with get_db(immediate=True) as conn:
#       txn_id = create_transaction(conn, ...)

def init_db(app):
    """Initialize database schema. Uses raw connection, NOT get_db()."""
    db_path = app.config["DB_PATH"]
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()
```

---

## Swarm Agent Assignment

Three agents, following the proven 3-agent split. 23 files total. Every file
assigned to exactly one agent. No overlaps.

### Validation Summary

| Check | Result |
|-------|--------|
| Files in plan structure | 23 |
| Files assigned | 23 (core: 7, routes: 6, templates: 10) |
| Duplicate assignments | 0 |
| Unassigned files | 0 |

---

### Agent: core (7 files)

**Role:** App factory, DB layer, models, utils, schema, entrypoint, dependencies.

**Files:**
1. `finance-tracker/run.py`
2. `finance-tracker/requirements.txt`
3. `finance-tracker/app/__init__.py`
4. `finance-tracker/app/db.py`
5. `finance-tracker/app/models.py`
6. `finance-tracker/app/utils.py`
7. `finance-tracker/app/schema.sql`

**Shared Interface Spec (core must follow):**

- `get_db(immediate=False)` is a context manager. Always use `with get_db() as conn:`.
- `create_category(conn, name, color)` returns `int` (the new ID), not a Row. Usage: `cat_id = create_category(conn, "Food", "#22c55e"); redirect(url_for('categories.index'))`.
- `create_transaction(conn, category_id, amount, description, transaction_date)` returns `int`. Usage: `txn_id = create_transaction(conn, 2, 4599, "Lunch", "2026-04-09"); redirect(url_for('transactions.index'))`.
- `get_category(conn, category_id)` returns `Row | None`. Check for None and `abort(404)`.
- `get_transaction(conn, transaction_id)` returns `Row | None`. Check for None and `abort(404)`.
- `delete_category(conn, category_id)` returns `bool` -- False if id=1 (Uncategorized).
- `set_budget(conn, category_id, year_month, amount)` upserts. Returns None.
- `get_dashboard_data(conn, year_month)` returns `list[Row]` with columns: `category_id`, `name`, `color`, `spent`, `budget_amount`. Derive totals: `total_spent = sum(r["spent"] for r in data)`, `total_budgeted = sum(r["budget_amount"] or 0 for r in data)`.
- `get_transactions(conn, year_month, category_id, limit, offset)` returns `list[Row]` with `category_name` and `category_color` via JOIN. Uses date range predicate (not LIKE).
- `get_budgets_for_month(conn, year_month)` returns `dict[int, Row]` -- batch query replaces N+1 individual get_budget calls.
- `get_available_months(conn)` returns `list[str]` of 'YYYY-MM' strings.
- `init_db(app)` uses raw connection, NOT `get_db()`.
- `get_db()` always commits on success, rollbacks on exception.
- `foreign_keys=ON` set per connection inside `get_db()`.
- WAL + busy_timeout set only in `init_db()`.
- Models use `limit`/`offset` parameters, not `page`.
- Constants: `ITEMS_PER_PAGE = 20`.
- All money values in models are cents (int). No conversion in models.
- `format_dollars(cents)` in `app/utils.py`, registered as Jinja2 filter `|dollars`.
- `dollars_to_cents(value_str)` in `app/utils.py`, converts user input to cents, raises ValueError. Rejects NaN, Inf, zero-cents, and amounts > $999,999.99.
- `validate_year_month(value)` in `app/utils.py`, validates 'YYYY-MM' format.
- Blueprint variables: `categories_bp`, `transactions_bp`, `views_bp`.
- Dashboard and budget routes live in `blueprints/views/routes.py`.

---

### Agent: routes (6 files)

**Role:** All blueprint registration and route handlers for categories, transactions, dashboard, and budgets.

**Files:**
1. `finance-tracker/app/blueprints/categories/__init__.py`
2. `finance-tracker/app/blueprints/categories/routes.py`
3. `finance-tracker/app/blueprints/transactions/__init__.py`
4. `finance-tracker/app/blueprints/transactions/routes.py`
5. `finance-tracker/app/blueprints/views/__init__.py`
6. `finance-tracker/app/blueprints/views/routes.py`

**Shared Interface Spec (routes must follow):**

- `get_db(immediate=False)` is a context manager. Always use `with get_db() as conn:`.
- `create_category(conn, name, color)` returns `int` (the new ID), not a Row.
- `create_transaction(conn, category_id, amount, description, transaction_date)` returns `int`.
- `delete_category(conn, category_id)` returns `bool`. Flash error if returns False.
- Read paths: `with get_db() as conn:`. Write paths: `with get_db(immediate=True) as conn:`.
- Models use `limit`/`offset` parameters. Pagination math in routes: `offset = (page - 1) * ITEMS_PER_PAGE`.
- Blueprint variables: `categories_bp = Blueprint("categories", __name__)`, `transactions_bp = Blueprint("transactions", __name__)`, `views_bp = Blueprint("views", __name__)`.
- Endpoint registry names: `categories.index`, `categories.create`, `categories.edit`, `categories.delete`, `transactions.index`, `transactions.create`, `transactions.edit`, `transactions.delete`, `views.dashboard`, `views.budgets_manage`.
- Transaction amount input is in dollars (e.g., "45.99"). Convert with `dollars_to_cents()` imported from `app.utils`. Wrap in try/except ValueError, flash error on failure.
- All routes accepting `month` query param must validate with `validate_year_month()` from `app.utils`.
- Transaction edit form prefills amount as dollars: `'%.2f' % (txn['amount'] / 100)`.
- Category delete of id=1 is blocked by model (returns False). Route flashes "Cannot delete Uncategorized category."
- Transaction list supports optional `?month=YYYY-MM` and `?category=ID` query params.
- Template render context must match the Template Render Context table exactly.
- Views blueprint (`views_bp`) handles dashboard (`/`) and budget management (`/budgets/`).
- Dashboard derives `total_spent` and `total_budgeted` from `get_dashboard_data` results -- no separate query.
- Budget GET uses `get_budgets_for_month(conn, year_month)` -- single batch query, not N+1.
- Budget POST flashes errors for invalid amounts instead of silently skipping.
- Category delete shows confirmation: `onclick="return confirm('Delete this category? Transactions will be moved to Uncategorized.')"`.

---

### Agent: templates (10 files)

**Role:** All Jinja2 templates, error pages, and static CSS.

**Files:**
1. `finance-tracker/app/templates/layout.html`
2. `finance-tracker/app/templates/dashboard.html`
3. `finance-tracker/app/templates/errors/404.html`
4. `finance-tracker/app/templates/errors/403.html`
5. `finance-tracker/app/templates/categories/list.html`
6. `finance-tracker/app/templates/categories/form.html`
7. `finance-tracker/app/templates/transactions/list.html`
8. `finance-tracker/app/templates/transactions/form.html`
9. `finance-tracker/app/templates/budgets/manage.html`
10. `finance-tracker/app/static/style.css`

**Shared Interface Spec (templates must follow):**

- Template render context variables (exact names and types from plan):
  - `dashboard.html`: `data` (list[Row]), `year_month` (str), `total_spent` (int), `total_budgeted` (int), `months` (list[str])
  - `categories/list.html`: `categories` (list[Row])
  - `categories/form.html`: `category` (Row|None), `is_edit` (bool)
  - `transactions/list.html`: `transactions` (list[Row] with category_name, category_color), `year_month` (str|None), `category_id` (int|None), `categories` (list[Row]), `page` (int), `total_pages` (int)
  - `transactions/form.html`: `transaction` (Row|None), `categories` (list[Row]), `is_edit` (bool)
  - `budgets/manage.html`: `categories` (list[Row]), `budgets_map` (dict[int, Row|None]), `year_month` (str), `months` (list[str])
  - `errors/404.html`: `message` (str)
  - `errors/403.html`: `message` (str)
- `csrf_token` is injected globally. All forms: `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`
- Money display: always use `{{ amount|dollars }}` filter. Never display raw cents.
- Transaction form amount field: `<input type="number" step="0.01" min="0.01">`. Prefill with `{{ '%.2f'|format(transaction.amount / 100) }}` for edit.
- Budget form amount fields: `<input type="number" step="0.01" min="0">`. Prefill with `{{ '%.2f'|format(budgets_map[cat.id].amount / 100) if budgets_map[cat.id] else '' }}`.
- Dashboard progress bars: `<div class="budget-bar" style="width: {{ [spent/budget*100, 100]|min }}%">` with `.over-budget` class if spent > budget.
- Color dots: `<span class="color-dot" style="background: {{ cat.color }}"></span>`
- Month selector: dropdown of `months` list, links to `?month=YYYY-MM`.
- CSS classes: `.container`, `.nav-links`, `.flash-success`, `.flash-error`, `.category-list`, `.transaction-list`, `.budget-table`, `.budget-bar`, `.budget-bar-fill`, `.over-budget`, `.color-dot`, `.form-group`, `.form-actions`, `.btn`, `.btn-danger`, `.btn-secondary`, `.pagination`, `.page-link`, `.page-current`, `.empty-state`, `.dashboard-summary`, `.dashboard-row`, `.error-page`, `.month-selector`.
- Empty states with `.empty-state` div.
- Layout nav links: Dashboard `/`, Transactions `/transactions/`, Categories `/categories/`, Budgets `/budgets/`.

---

## Shared Interface Spec

### Anti-Patterns (DO NOT DO THIS)

```python
# WRONG: bare call, not context manager
db = get_db()
txn = get_transaction(db, 42)

# WRONG: treating int return as Row
cat = create_category(conn, "Food", "#22c55e")
redirect(url_for('categories.edit', category_id=cat.id))  # AttributeError

# WRONG: storing dollars instead of cents
amount = float(request.form["amount"])
create_transaction(conn, cat_id, amount, ...)  # stores 45.99 not 4599

# WRONG: displaying cents without filter
{{ transaction.amount }}  # shows 4599

# WRONG: executescript inside get_db context
with get_db() as conn:
    conn.executescript(schema)  # implicit COMMIT breaks transaction

# WRONG: conditional commit
if immediate:
    conn.commit()  # ALWAYS commit
```

### Blueprint Registration

- `categories/__init__.py`: `categories_bp = Blueprint("categories", __name__)`
- `transactions/__init__.py`: `transactions_bp = Blueprint("transactions", __name__)`
- `views/__init__.py`: `views_bp = Blueprint("views", __name__)`

---

## Acceptance Criteria

- [ ] Create a category with name and color
- [ ] Edit category name and color
- [ ] Delete a category (transactions reassigned to Uncategorized via ON DELETE SET DEFAULT)
- [ ] Cannot delete Uncategorized category (id=1)
- [ ] Add a transaction: enter dollar amount, stored as cents
- [ ] Edit a transaction: form prefills dollar amount from cents
- [ ] Delete a transaction
- [ ] Transaction list shows category name with color dot
- [ ] Transaction list filterable by month and category
- [ ] Pagination on transaction list
- [ ] Set monthly budgets for each category (dollar input, stored as cents)
- [ ] Empty budget field removes the budget
- [ ] Dashboard shows per-category: spent, budget, remaining for current month
- [ ] Dashboard highlights over-budget categories in red
- [ ] Dashboard month selector shows past months
- [ ] CSRF token on all forms, POST without token returns 403
- [ ] Custom 404 error page
- [ ] Empty states for no transactions, no categories, no spending
- [ ] Cents conversion correct on every input/output path (Feed-Forward risk)
- [ ] No dependencies beyond `flask>=3.0`

---

## Sources & References

### Origin

- **Brainstorm:** [docs/brainstorms/2026-04-09-personal-finance-tracker-brainstorm.md](docs/brainstorms/2026-04-09-personal-finance-tracker-brainstorm.md) -- key decisions: integer cents for money, ON DELETE SET DEFAULT for category deletion, year-month TEXT for budget periods, no income tracking

### Solution Docs Applied

- Task Tracker Categories Swarm -- scalar return values, color via inline styles, PRAGMA settings
- Recipe Organizer Swarm -- simplicity deepening, get_db gold standard, template render context
- Bookmark Manager Swarm -- 3-agent split pattern, CSRF, endpoint registry
- Flask Swarm Acid Test -- context manager examples, anti-patterns in spec
- Autopilot Swarm Orchestration -- SECRET_KEY from env, CSRF on all forms

---

## Feed-Forward

- **Hardest decision:** Whether budgets should be per-category CRUD (4 routes) or a single batch form (1 route). Chose batch form -- simpler UX, fewer routes, and budgets are always set in the context of a month. Trade-off: can't deep-link to a single budget.

- **Rejected alternatives:** (1) Per-budget CRUD routes -- 4 extra routes for minimal benefit. (2) REAL for money -- floating-point rounding. (3) Income tracking -- doubles data model for no MVP value. (4) Chart.js for dashboard -- CSS bars are sufficient. (5) Separate blueprint for budgets -- only 1 route, not worth a blueprint.

- **Least confident:** The ON DELETE SET DEFAULT behavior in SQLite. The brainstorm says it should reassign transactions to category_id=1 when a category is deleted, but this is an uncommon SQLite feature. The work phase should test this immediately: create a category, add a transaction, delete the category, verify the transaction's category_id is now 1.
