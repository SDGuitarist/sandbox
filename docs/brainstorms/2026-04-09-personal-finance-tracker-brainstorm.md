---
title: "Personal Finance Tracker with Budgets and Spending Categories"
date: 2026-04-09
status: complete
origin: "autopilot"
swarm_candidate: true
---

# Personal Finance Tracker -- Brainstorm

## Problem

Track personal spending by category with monthly budgets. See at a glance
where money goes and whether spending stays within budget for each category.

## Context

- Greenfield project in `finance-tracker/` subdirectory of sandbox
- Python 3.12+ / Flask (sandbox standard for web apps)
- Storage: SQLite via sqlite3 stdlib module
- No ORM -- raw SQL (sandbox convention)
- Multi-file structure: routes, models, templates, static CSS
- Single user, personal app -- no auth needed
- Money stored as INTEGER cents to avoid floating-point issues

## What We're Building

A Flask web app with:

### Categories

- Create a category with name and color (e.g., "Groceries" #22c55e)
- List all categories
- Edit category name/color
- Delete category (what happens to transactions? reassign to "Uncategorized")

### Transactions

- Add a transaction: amount, description, date, category
- List transactions with category color indicator
- Edit a transaction
- Delete a transaction
- Default sort: newest first

### Budgets

- Set a monthly budget amount per category
- One budget row per category per month (year-month key)
- Edit budget amount
- If no budget set for a category, show "No budget" (not $0)

### Dashboard

- Current month summary: total spent, total budgeted
- Per-category row: category name (colored), spent this month, budget, remaining
- Over-budget categories highlighted in red
- Month selector to view past months

## Schema

```sql
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT '#6366f1',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Seed "Uncategorized" as id=1 on init, never deletable

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL DEFAULT 1 REFERENCES categories(id) ON DELETE SET DEFAULT,
    amount INTEGER NOT NULL CHECK(amount > 0),  -- cents, always positive (all spending)
    description TEXT NOT NULL DEFAULT '',
    transaction_date TEXT NOT NULL DEFAULT (date('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_category_id
    ON transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date
    ON transactions(transaction_date);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    year_month TEXT NOT NULL,  -- 'YYYY-MM' format
    amount INTEGER NOT NULL CHECK(amount > 0),  -- cents
    UNIQUE(category_id, year_month)
);

CREATE INDEX IF NOT EXISTS idx_budgets_year_month
    ON budgets(year_month);
```

**Database init requirements:**
- `PRAGMA journal_mode=WAL` -- prevents "database is locked" during concurrent reads
- `PRAGMA foreign_keys=ON` -- required or all FK constraints are silently ignored
- `PRAGMA busy_timeout=5000` -- wait up to 5s on lock instead of failing immediately
- Seed "Uncategorized" category (id=1) via INSERT OR IGNORE after schema creation

**Category deletion order of operations:**
1. The `ON DELETE SET DEFAULT` on `transactions.category_id` handles reassignment
   automatically -- SQLite sets category_id to DEFAULT (1) when the referenced
   category is deleted
2. The `ON DELETE CASCADE` on `budgets.category_id` deletes associated budgets
3. Application code just needs: `DELETE FROM categories WHERE id = ? AND id != 1`
   (guard against deleting Uncategorized)

## Key Decisions

### Money as Integer Cents

Store all amounts as integer cents (e.g., $45.99 = 4599). Display with
`amount / 100` formatting. This avoids floating-point rounding issues that
plague finance apps. Input fields accept decimal (e.g., "45.99") and convert
on submission: `int(round(float(value) * 100))`.

### No Income Tracking

This is a spending tracker, not a full accounting system. All transactions
are expenses. Income tracking, account balances, and transfers are out of
scope. Keeps the data model simple: one transaction type, always positive
amounts.

### Category Deletion -> Reassign to "Uncategorized"

When a category is deleted, its transactions move to a permanent
"Uncategorized" category (id=1, seeded on DB init). This preserves
transaction history. CASCADE delete would lose financial data -- unacceptable
for a finance app. Budgets for the deleted category DO cascade-delete since
they're meaningless without the category.

### Year-Month String for Budget Periods

Using 'YYYY-MM' TEXT instead of separate year/month INTEGER columns.
Simpler to query (`WHERE year_month = '2026-04'`), sort, and display.
The UNIQUE constraint on (category_id, year_month) prevents duplicate
budget entries.

### No Chart Libraries

Text-based progress bars for budget vs. actual (CSS width percentage).
Same pattern as task-tracker dashboard progress bars. Charts are Phase 3.

## Why This Approach

### SQLite over JSON

Three related tables (categories, transactions, budgets) with aggregate
queries (SUM by category and month). Relational store is the only sane choice.

### Raw SQL over ORM

Sandbox convention. The aggregate queries (SUM with GROUP BY, LEFT JOIN for
budget-vs-actual) are clearer in raw SQL than ORM abstractions.

### Flat Transaction Model (No Accounts)

A real finance app has accounts, transfers, double-entry bookkeeping. That's
massive scope for a sandbox app. Flat "I spent X on Y" model covers 90% of
personal tracking needs with 10% of the complexity.

## Swarm Suitability

Good swarm candidate -- 3 agents:
1. **Core agent:** app.py, models.py, database.py (schema + model functions)
2. **Routes agent:** routes.py (all Flask routes and form handling)
3. **Templates agent:** All Jinja2 templates + static CSS

Clear ownership boundaries. Models agent owns the DB schema and all query
functions. Routes agent imports from models. Templates agent imports nothing
(pure Jinja2).

## Out of Scope (Confirmed)

- Multi-user auth
- Income / account balances
- CSV import/export
- Charts (Phase 3)
- Recurring transactions
- Currency selection / i18n
- Transaction search/filter beyond month view

## Refinement Findings

| # | Gap | Severity | Source |
|---|-----|----------|--------|
| 1 | Schema had no ON DELETE action on transactions.category_id | High | brainstorm-refinement |
| 2 | Missing PRAGMA foreign_keys=ON, WAL, busy_timeout | High | task-tracker-categories, 4+ solution docs |
| 3 | No CHECK constraint on amounts (zero/negative possible) | Medium | brainstorm-refinement |
| 4 | Order of operations for category deletion unspecified | Medium | brainstorm-refinement |
| 5 | Zero budget ambiguity ($0 budget vs no budget) | Low | brainstorm-refinement |

**Resolution:** Issues 1-4 fixed in schema and notes above. Issue 5: $0 budget
is valid (means "no spending allowed for this category"). "No budget" means no
row exists in the budgets table for that category+month.

## Patterns from Solution Docs

| Pattern | Source Doc |
|---------|-----------|
| AUTOINCREMENT for PKs | cli-todo-app |
| ON DELETE CASCADE for budgets | task-tracker-categories |
| ON DELETE SET DEFAULT for reassignment | (new pattern for this app) |
| PRAGMA foreign_keys=ON + WAL + busy_timeout | task-tracker-categories, multiple |
| `with get_db() as conn:` context manager | task-tracker-categories |
| CSRF on all POST forms | autopilot-swarm-orchestration |
| SECRET_KEY from env | autopilot-swarm-orchestration |
| Color via inline styles | task-tracker-categories |
| Scalar return usage examples in spec | task-tracker-categories |
| Simplicity deepening before build | recipe-organizer |

## Feed-Forward

- **Hardest decision:** Whether to store money as cents (INTEGER) vs. REAL.
  Chose cents to avoid floating-point display issues, but this adds
  conversion logic in every input/output path. The conversion must be
  correct everywhere or amounts will be off by 100x.

- **Rejected alternatives:** (1) CASCADE delete on categories -- would lose
  transaction history. (2) Separate year + month columns for budgets --
  unnecessary complexity. (3) Income tracking -- out of scope, would double
  the data model. (4) REAL for money -- floating-point rounding.

- **Least confident:** The cents conversion layer. Every form input must
  multiply by 100, every display must divide by 100. If any path misses the
  conversion, users see "$4599" instead of "$45.99" or vice versa. This is
  the highest-risk area for bugs and should be the first thing verified.
