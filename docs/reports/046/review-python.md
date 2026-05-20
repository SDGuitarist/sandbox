# Python Code Quality Review -- Invoice & CRM Flask Application

**Reviewer:** Kieran (Python Quality Agent)
**Date:** 2026-05-19
**Scope:** 12 Flask blueprints, ~2,500 lines of route/helper/db code across a 15-agent swarm build

---

## Executive Summary

The codebase is structurally sound for a swarm build. Blueprint isolation is clean, the database layer uses a context manager correctly, money is stored in cents consistently, and every mutating route checks `user_id` ownership. The problems are almost entirely in two areas: (1) a massive copy-paste duplication of line-item parsing across `create_invoice` and `edit_invoice`, and (2) missing type hints on every function in the project. There are also several lower-severity issues around money conversion safety, transaction boundaries, and query patterns. Nothing is broken today, but several items will bite as the codebase grows.

**Finding counts:** 6 P1, 9 P2, 8 P3

---

## P1 -- Must Fix

### P1-1: Line-item parsing logic is copy-pasted verbatim (invoices/routes.py)

**Lines:** 147-218 (create) and 375-429 (edit)

The 70-line block that extracts parallel form arrays, converts dollars to cents, and computes per-line tax totals is duplicated character-for-character between `create_invoice` and `edit_invoice`. This is the single largest quality risk in the codebase -- any fix applied to one copy will be missed in the other.

**Fix:** Extract a function:

```python
def _parse_line_items(
    form_data: dict,
) -> tuple[list[dict], int, int] | None:
    """Parse parallel form arrays into line items.
    Returns (parsed_items, subtotal_cents, tax_cents) or None on validation error.
    """
```

Call it from both routes. The redirect-on-error can be handled by the caller checking for `None`.

---

### P1-2: Invoice number generation is a race condition (invoices/routes.py, recurring/routes.py)

**Lines:** invoices/routes.py:168-173, invoices/routes.py:531-536, recurring/routes.py:22-32

Three separate locations compute `MAX(CAST(SUBSTR(...))) + 1` to generate the next invoice number. This pattern is not atomic -- two concurrent requests can read the same max, produce the same number, and one INSERT will fail on the UNIQUE constraint with an unhandled `sqlite3.IntegrityError`.

**Additionally**, the recurring generator at line 23 uses `inv['invoice_number'][:3]` as the prefix length, which hard-codes a 3-character prefix. If a user sets their prefix to something like `ACME`, it will extract the wrong substring and produce an incorrect or colliding number.

**Fix:** Wrap the generate-and-insert in a single SQL statement using `INSERT INTO ... SELECT`, or catch `IntegrityError` and retry. For the prefix bug, use the actual `user_row['invoice_prefix']` (which is already fetched on line 30) instead of slicing the existing invoice number.

---

### P1-3: Floating-point money conversion is unsafe (7 locations across 4 files)

Every dollars-to-cents conversion uses `int(round(float(value) * 100))`. Floating-point multiplication produces representational errors -- `float('19.99') * 100` is `1998.9999999999998`. The `round()` call masks this for most values, but it will silently produce off-by-one-cent results for certain inputs (e.g., values near half-cent boundaries when tax rates are involved).

**Affected files:**
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/invoices/routes.py` (lines 185, 396)
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/payments/routes.py` (line 27)
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/catalog/routes.py` (lines 25, 60)
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/pipeline/routes.py` (lines 55, 120)

**Fix:** Use `Decimal` for all money math. The payment form already uses `DecimalField`, so the data is already a `Decimal` -- just stop converting it to `float` first:

```python
from decimal import Decimal, ROUND_HALF_UP

def dollars_to_cents(value: str | Decimal) -> int:
    """Convert a dollar amount to cents without floating-point error."""
    d = Decimal(str(value))
    return int((d * 100).to_integral_value(rounding=ROUND_HALF_UP))
```

---

### P1-4: Payment deletion reverts status to hardcoded 'sent' (payments/routes.py)

**Lines:** 130-141

When a payment is deleted and the invoice is no longer fully paid, the code unconditionally sets the status back to `'sent'`. But the invoice may have been in `'viewed'` or `'overdue'` status before it was marked `'paid'`. The original pre-payment status is never stored, so there is no way to restore it correctly. This silently rewrites invoice history.

**Fix:** Either store the `previous_status` on the invoice when marking it `'paid'` (add a column), or revert to `'sent'` only if the invoice was `'sent'` before (check the activity log). At minimum, document this as a known limitation and add a flash message warning the user.

---

### P1-5: Dashboard triggers recurring generation + overdue update on every page load (dashboard/routes.py)

**Lines:** 14-25

The dashboard `index()` route calls `generate_due_invoices()` and runs an overdue-status UPDATE on every single GET request. For a single-user SQLite app this is tolerable, but:

1. It issues two separate `db.commit()` calls inside one `with get_db()` block (lines 17 and 25), which means if the overdue UPDATE fails, the recurring generation is already committed and cannot be rolled back.
2. Any user repeatedly refreshing the dashboard re-runs these mutations every time.

**Fix:** Move recurring generation and overdue checking into a scheduled job (cron endpoint or background task), or at minimum, guard with a time-based check (e.g., only run if last run was >1 hour ago). Combine both mutations into a single commit.

---

### P1-6: delete_invoice manually deletes line items despite ON DELETE CASCADE (invoices/routes.py)

**Lines:** 592-593

```python
db.execute("DELETE FROM invoice_line_items WHERE invoice_id = ?", (invoice_id,))
db.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
```

The schema defines `invoice_line_items.invoice_id ... REFERENCES invoices(id) ON DELETE CASCADE`, so the first DELETE is redundant. More importantly, deleting line items first and then the invoice means that if the second DELETE fails, the line items are already gone but the invoice remains -- an orphaned invoice with no line items. The CASCADE would handle this atomically.

**Fix:** Remove the manual line-item delete. Just delete the invoice and let CASCADE do its job.

---

## P2 -- Should Fix

### P2-1: Zero type hints anywhere in the codebase

Not a single function in any of the reviewed files has parameter or return type annotations. This is the most pervasive quality gap. For a Flask app with raw SQL, type hints on at least the helper functions and data-processing code would catch entire classes of bugs.

**Priority targets (highest value for effort):**
- `helpers.py`: `dollars(cents: int | None) -> str`, `log_activity(db: sqlite3.Connection, ...)`
- `db.py`: `get_db() -> Generator[sqlite3.Connection, None, None]`
- `clients/routes.py`: `_sync_tags(db: sqlite3.Connection, client_id: int, user_id: int, tag_names: list[str]) -> None`
- `recurring/routes.py`: `generate_due_invoices(db: sqlite3.Connection, user_id: int) -> int`

---

### P2-2: Unused imports (activities/routes.py, pipeline/routes.py)

Both files import `abort` from Flask but never call it.

- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/activities/routes.py` line 1
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/pipeline/routes.py` line 1

**Fix:** Remove `abort` from both import statements.

---

### P2-3: `format_date` imports `datetime` inside the function body (helpers.py)

**Line:** 17

```python
def format_date(date_str):
    if not date_str:
        return ''
    from datetime import datetime   # <-- lazy import inside hot path
```

This is called in every template that formats a date. While Python caches module imports, the `from ... import` lookup still runs every call. More importantly, it violates the standard import organization pattern and makes the dependency invisible at the top of the file.

**Fix:** Move `from datetime import datetime` to the top of `helpers.py`.

---

### P2-4: LIKE patterns are not escaped for wildcard characters (search/routes.py, clients/routes.py)

**Lines:** search/routes.py:17, clients/routes.py:104

User input is interpolated directly into LIKE patterns as `f'%{q}%'`. If a user searches for `%` or `_`, those are LIKE wildcards and will match unintended rows. This is not a SQL injection (parameterized queries prevent that), but it is a logic bug.

**Fix:** Escape LIKE wildcards before interpolation:

```python
def escape_like(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

like_pattern = f'%{escape_like(q)}%'
# then: "WHERE name LIKE ? ESCAPE '\\'"
```

---

### P2-5: `SELECT *` used in 47 places across 14 files

Nearly every query uses `SELECT *`. This has two problems:
1. It fetches columns that are never used, wasting memory on larger result sets.
2. It makes the code fragile to schema changes -- adding a column silently changes what every query returns.

**Highest-priority fixes** (these are the queries that fetch rows only to check one or two fields):
- `invoices/routes.py:476` -- fetches full invoice row just to read `status`
- `payments/routes.py:16` -- fetches full invoice row just to confirm existence
- `activities/routes.py:84` -- fetches full activity row just to confirm existence before deletion

**Fix:** Replace `SELECT *` with explicit column lists, at least for the queries where only a subset of columns is used.

---

### P2-6: `_sync_tags` uses f-string SQL with dynamic placeholders (clients/routes.py)

**Lines:** 28-33

```python
placeholders = ','.join('?' * len(tag_names))
db.execute(
    f"""DELETE FROM client_tag_map WHERE client_id = ? AND tag_id NOT IN (
        SELECT id FROM client_tags WHERE user_id = ? AND name IN ({placeholders})
    )""",
    (client_id, user_id, *tag_names)
)
```

While the values are parameterized (safe from injection), the f-string SQL pattern is harder to read and maintain. It also means the SQL string changes shape on every call, which defeats SQLite's prepared statement cache.

**Fix:** Consider a two-step approach: fetch current tag IDs, then delete by explicit ID list. Or accept this as a pragmatic tradeoff and add a comment explaining why the dynamic placeholder count is safe.

---

### P2-7: No error handling on the `set_recurring` POST route (recurring/routes.py)

**Lines:** 89-103

The `recurrence_interval` and `next_recurrence_date` values come directly from `request.form.get()` with no validation. There is no WTForms form for this route. A malformed date string (e.g., `"not-a-date"`) will be stored directly in the database and cause `generate_due_invoices` to produce unpredictable results when it later tries `date(next_recurrence_date, ?)` in SQL.

**Fix:** Create a `RecurringSettingsForm` with a `DateField` validator and a `SelectField` for the interval choices, consistent with how every other POST route in the app uses WTForms.

---

### P2-8: Reports `_aging_data` uses f-string SQL for bucket conditions (reports/routes.py)

**Lines:** 56-67

```python
for label, condition in buckets:
    row = db.execute(
        f"""... AND {condition}""",
        (user_id,),
    ).fetchone()
```

The `condition` values are hardcoded strings, not user input, so this is not a security issue. But it is fragile -- the pattern looks identical to SQL injection and would fail a security audit. Anyone extending the buckets could accidentally introduce user input.

**Fix:** Either use parameterized date boundaries, or add a clear comment: `# SAFETY: conditions are hardcoded constants, not user input`.

---

### P2-9: Double commit in dashboard route (dashboard/routes.py)

**Lines:** 17 and 25

```python
generated = generate_due_invoices(db, user_id)
if generated > 0:
    db.commit()           # commit 1
# ...
db.execute("UPDATE invoices SET status = 'overdue'...")
db.commit()               # commit 2
```

Two commits in one `with get_db()` block means these are not atomic. If the second commit fails, the first is already persisted. This is inconsistent with the rest of the codebase where a single `db.commit()` is the norm.

**Fix:** Combine into a single commit after both mutations.

---

## P3 -- Nice to Have

### P3-1: Invoice form uses parallel arrays instead of WTForms FieldList

The `create_invoice` and `edit_invoice` routes manually parse `descriptions[]`, `quantities[]`, etc. from `request.form.getlist()`. WTForms has `FieldList` and `FormField` specifically for this pattern. Using them would centralize validation and remove the manual length-checking code.

---

### P3-2: `InvoiceForm` is defined but not used in `create_invoice` or `edit_invoice`

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/invoices/forms.py`

`InvoiceForm` is imported at line 11 of `routes.py` but never instantiated in `create_invoice` or `edit_invoice`. Only `StatusForm` is actually used. This is dead code.

---

### P3-3: `dollars()` helper duplicated inline in payments/routes.py

**Line:** payments/routes.py:57

```python
amount_display = f"${amount_cents / 100:,.2f}"
```

The `dollars()` helper in `helpers.py` does exactly this. Use it instead.

---

### P3-4: `log_activity` silently does nothing when `client_id` is falsy (helpers.py)

**Line:** helpers.py:41

```python
def log_activity(db, client_id, user_id, activity_type, notes):
    if client_id:
        db.execute(...)
```

Callers in `invoices/routes.py` pass `invoice['client_id']` which can be `None` (the schema allows it via `ON DELETE SET NULL`). When the client has been deleted, activities are silently dropped. This may be intentional, but there is no docstring explaining the decision.

**Fix:** Add a docstring: `"Skips logging when client_id is None (e.g., orphaned invoices)."`

---

### P3-5: Lazy import of `date` type in pipeline/routes.py

**Line:** pipeline/routes.py:143

```python
from datetime import date as date_type
form.expected_close_date.data = date_type.fromisoformat(deal['expected_close_date'][:10])
```

This is imported inline inside an `if request.method == 'GET'` block. Move it to the top of the file.

---

### P3-6: `init_db()` creates its own connection instead of using `get_db()` (db.py)

**Lines:** db.py:30-33

`init_db()` opens a raw `sqlite3.connect()` call, bypassing the `get_db()` context manager. This means the WAL pragma and foreign keys pragma are set on different connections. The foreign keys pragma especially needs to be set on every connection, not just the `get_db()` one.

The `init_db` connection does not set `row_factory` or `PRAGMA foreign_keys = ON`. This is fine for DDL, but inconsistent.

---

### P3-7: `logout` should be POST-only (auth/routes.py)

**Line:** auth/routes.py:50-52

```python
@bp.route('/logout')
def logout():
    session.clear()
```

Logout is a state-changing operation exposed as a GET endpoint. A CSRF attack or prefetch could log users out. Best practice is `methods=['POST']` with a CSRF-protected form.

---

### P3-8: CSV export `report_type` is not validated against a whitelist (reports/routes.py)

**Lines:** reports/routes.py:136-168

The `export_csv` route uses an `if/elif/else` chain on `report_type`, which is fine for correctness, but the `else` branch returns a bare string `"Invalid report type", 404` instead of using `abort(404)` or returning a proper `Response`.

---

## Cross-Cutting Observations

### What the codebase does well

1. **Consistent ownership checks.** Every route that reads or mutates data includes `WHERE user_id = ?`. No multi-tenancy leaks.
2. **Transaction discipline.** Helpers explicitly document "does NOT commit" and callers commit. This contract is followed everywhere except the dashboard double-commit.
3. **Context manager for DB.** The `get_db()` context manager with rollback-on-exception is a solid pattern.
4. **Cents storage.** All money is stored as integer cents in the database. No floating-point columns for money.
5. **CSRF protection.** Flask-WTF CSRFProtect is initialized globally, and WTForms are used for most POST routes.
6. **Batch tag fetching.** `_get_tags_for_clients()` avoids an N+1 query on the client list page.

### What needs the most attention

1. **The line-item parsing duplication** (P1-1) is the single highest-risk item. It is a guaranteed source of divergence bugs.
2. **Money conversion** (P1-3) should be fixed globally with a single `dollars_to_cents()` utility before any more routes are added.
3. **Type hints** (P2-1) should be added incrementally, starting with `helpers.py` and `db.py`.

---

## Files Reviewed

| File | Lines | Verdict |
|---|---|---|
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/db.py` | 174 | Clean, minor P3-6 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/helpers.py` | 46 | P2-1, P2-3, P3-4 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/__init__.py` | 63 | Clean |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/invoices/routes.py` | 597 | P1-1, P1-2, P1-3, P1-6, P2-5, P3-2 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/clients/routes.py` | 325 | P2-4, P2-6 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/payments/routes.py` | 147 | P1-3, P1-4, P3-3 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/dashboard/routes.py` | 131 | P1-5, P2-9 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/reports/routes.py` | 175 | P2-8, P3-8 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/recurring/routes.py` | 143 | P1-2, P2-7 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/pipeline/routes.py` | 210 | P1-3, P2-2, P3-5 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/auth/routes.py` | 91 | P3-7 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/catalog/routes.py` | 107 | P1-3 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/activities/routes.py` | 96 | P2-2 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/search/routes.py` | 40 | P2-4 |
| `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/settings_bp/routes.py` | 75 | Clean |

---

## Recommended Fix Order

1. **P1-1** (line-item extraction) -- highest risk of divergence, pure refactor
2. **P1-3** (money conversion) -- add `dollars_to_cents()` to helpers, update all 7 callsites
3. **P1-2** (invoice number race) -- fix the prefix bug in recurring first, then add retry logic
4. **P1-4** (payment deletion status) -- decide on approach, add column or document limitation
5. **P1-5** (dashboard mutations) -- combine commits, add time guard
6. **P1-6** (redundant delete) -- one-line fix, remove the manual delete
7. **P2-1** (type hints) -- add to helpers.py and db.py first, then propagate
8. Everything else by priority tier
