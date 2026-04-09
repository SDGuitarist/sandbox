# Spec Contract Check: Personal Finance Tracker

**Date:** 2026-04-09
**Plan:** `docs/plans/2026-04-09-feat-personal-finance-tracker-plan.md`
**Checker:** spec-contract-checker agent

---

## Results

| # | Check | Status | Details |
|---|-------|--------|---------|
| 1 | Model functions (17 expected) | **PASS** | All 17 functions present with correct signatures (see details below) |
| 2 | Blueprint registration (3 `__init__.py` files) | **PASS** | `categories_bp`, `transactions_bp`, `views_bp` all exported correctly |
| 3 | Route endpoints (10 expected) | **FAIL** | All 10 endpoint functions exist, but route paths are DOUBLED (see details below) |
| 4 | Template/static files (10 expected) | **PASS** | All 10 files exist |
| 5 | Utils functions | **PASS** | `dollars_to_cents`, `format_dollars`, `validate_year_month` all present with correct signatures |
| 6 | App factory blueprint imports | **PASS** | All 3 blueprints imported and registered correctly |

---

## Overall STATUS: FAIL

One critical issue found in route endpoints (Check 3).

---

## Detailed Findings

### Check 1: Model Functions (PASS)

All 17 functions from the plan exist in `finance-tracker/app/models.py` with correct parameter names and return types:

| Function | Params Match | Returns Match |
|----------|-------------|---------------|
| `get_all_categories(conn)` | YES | `list[Row]` via `.fetchall()` |
| `get_category(conn, category_id)` | YES | `Row \| None` via `.fetchone()` |
| `create_category(conn, name, color)` | YES | `int` via `cur.lastrowid` |
| `update_category(conn, category_id, name, color)` | YES | `None` (implicit) |
| `delete_category(conn, category_id)` | YES | `bool` (False if id=1) |
| `get_transactions(conn, year_month, category_id, limit, offset)` | YES | `list[Row]` with JOIN |
| `get_transaction_count(conn, year_month, category_id)` | YES | `int` via `fetchone()[0]` |
| `get_transaction(conn, transaction_id)` | YES | `Row \| None` via `.fetchone()` |
| `create_transaction(conn, category_id, amount, description, transaction_date)` | YES | `int` via `cur.lastrowid` |
| `update_transaction(conn, transaction_id, category_id, amount, description, transaction_date)` | YES | `None` (implicit) |
| `delete_transaction(conn, transaction_id)` | YES | `None` (implicit) |
| `get_budget(conn, category_id, year_month)` | YES | `Row \| None` via `.fetchone()` |
| `set_budget(conn, category_id, year_month, amount)` | YES | `None` (upsert) |
| `delete_budget(conn, category_id, year_month)` | YES | `None` (implicit) |
| `get_dashboard_data(conn, year_month)` | YES | `list[Row]` with correct columns |
| `get_budgets_for_month(conn, year_month)` | YES | `dict[int, Row]` |
| `get_available_months(conn)` | YES | `list[str]` |

Constant `ITEMS_PER_PAGE = 20` also present.

### Check 2: Blueprint Registration (PASS)

| File | Variable Name | Blueprint Name | Match |
|------|--------------|----------------|-------|
| `blueprints/categories/__init__.py` | `categories_bp` | `"categories"` | YES |
| `blueprints/transactions/__init__.py` | `transactions_bp` | `"transactions"` | YES |
| `blueprints/views/__init__.py` | `views_bp` | `"views"` | YES |

### Check 3: Route Endpoints (FAIL -- Doubled Prefixes)

All 10 endpoint functions exist with the correct function names and HTTP methods. However, the route paths in the decorators conflict with the blueprint `url_prefix` registration in the app factory.

**The problem:** The app factory registers blueprints with prefixes:
- `app.register_blueprint(categories_bp, url_prefix="/categories")`
- `app.register_blueprint(transactions_bp, url_prefix="/transactions")`

But the route decorators ALSO include the full path:
- `@categories_bp.route("/categories/")` -- actual URL becomes `/categories/categories/`
- `@transactions_bp.route("/transactions/new")` -- actual URL becomes `/transactions/transactions/new`

**Expected (per plan):** Routes should use relative paths since the prefix is set at registration:
- `@categories_bp.route("/")` instead of `@categories_bp.route("/categories/")`
- `@transactions_bp.route("/new")` instead of `@transactions_bp.route("/transactions/new")`
- etc.

| Endpoint | Plan Path | Decorator Path | Actual Resolved Path | Match |
|----------|-----------|---------------|---------------------|-------|
| `views.dashboard` | `/` | `/` | `/` | YES |
| `categories.index` | `/categories/` | `/categories/` | `/categories/categories/` | **NO** |
| `categories.create` | `/categories/new` | `/categories/new` | `/categories/categories/new` | **NO** |
| `categories.edit` | `/categories/<int:category_id>/edit` | `/categories/<int:category_id>/edit` | `/categories/categories/<int:category_id>/edit` | **NO** |
| `categories.delete` | `/categories/<int:category_id>/delete` | `/categories/<int:category_id>/delete` | `/categories/categories/<int:category_id>/delete` | **NO** |
| `transactions.index` | `/transactions/` | `/transactions/` | `/transactions/transactions/` | **NO** |
| `transactions.create` | `/transactions/new` | `/transactions/new` | `/transactions/transactions/new` | **NO** |
| `transactions.edit` | `/transactions/<int:transaction_id>/edit` | `/transactions/<int:transaction_id>/edit` | `/transactions/transactions/<int:transaction_id>/edit` | **NO** |
| `transactions.delete` | `/transactions/<int:transaction_id>/delete` | `/transactions/<int:transaction_id>/delete` | `/transactions/transactions/<int:transaction_id>/delete` | **NO** |
| `views.budgets_manage` | `/budgets/` | `/budgets/` | `/budgets/` | YES |

**Fix:** Either remove `url_prefix` from blueprint registration in the app factory, OR change route decorators to use relative paths (e.g., `"/"`, `"/new"`, `"/<int:category_id>/edit"`). The plan shows both -- the app factory code uses `url_prefix` and the endpoint registry shows the full paths. The route decorators should use relative paths to work with the prefix.

### Check 4: Template/Static Files (PASS)

All 10 files exist:

| File | Exists |
|------|--------|
| `templates/layout.html` | YES |
| `templates/dashboard.html` | YES |
| `templates/errors/404.html` | YES |
| `templates/errors/403.html` | YES |
| `templates/categories/list.html` | YES |
| `templates/categories/form.html` | YES |
| `templates/transactions/list.html` | YES |
| `templates/transactions/form.html` | YES |
| `templates/budgets/manage.html` | YES |
| `static/style.css` | YES |

### Check 5: Utils Functions (PASS)

All 3 functions present in `finance-tracker/app/utils.py`:

| Function | Signature Match | Behavior Match |
|----------|----------------|----------------|
| `dollars_to_cents(value_str)` | YES | Rejects NaN, Inf, zero-cents, max cap at 99999999 |
| `format_dollars(cents)` | YES | Returns em-dash for None, `$XX.XX` format |
| `validate_year_month(value)` | YES | Regex `^\d{4}-\d{2}$`, month range check |

Constant `MAX_AMOUNT_CENTS = 99_999_999` also present.

### Check 6: App Factory Blueprint Imports (PASS)

In `finance-tracker/app/__init__.py`:
- `from .blueprints.categories import categories_bp` -- YES
- `from .blueprints.transactions import transactions_bp` -- YES
- `from .blueprints.views import views_bp` -- YES
- `app.register_blueprint(categories_bp, url_prefix="/categories")` -- YES
- `app.register_blueprint(transactions_bp, url_prefix="/transactions")` -- YES
- `app.register_blueprint(views_bp)` -- YES (no prefix, correct per plan)
- `app.jinja_env.filters["dollars"] = format_dollars` -- YES
