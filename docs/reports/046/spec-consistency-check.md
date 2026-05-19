# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/invoice-crm-plan.md
**Checked:** 2026-05-19

---

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Blueprint Prefix vs Route Decorator | Endpoint Registry: payments prefix `/payments`, path `/invoice/<int:invoice_id>/new` -> full URL `/payments/invoice/<id>/new` | Transaction Boundary Policy example: `@bp.route('/invoices/<int:invoice_id>/payments/new')` | FAIL | The example route in the Transaction Boundary Policy section uses `/invoices/...` as the relative path, which (a) conflicts with the `invoices` blueprint prefix and (b) the correct relative path for the payments blueprint should be `/invoice/<int:invoice_id>/new` not `/invoices/<int:invoice_id>/payments/new`. Any agent reading the example will implement the wrong route. |
| 2 | Schema Field vs Code Block Usage | `users.default_payment_terms INTEGER DEFAULT 30` (configurable per user) | `generate_due_invoices` code block hardcodes `30` as the payment terms argument | FAIL | The `generate_due_invoices` function in the Cross-Boundary Wiring section (line 681) passes the literal `30` for due_date calculation instead of reading `user['default_payment_terms']`. The settings agent is told to let users edit `default_payment_terms`, and the schema stores it, but the recurring generation code never reads it. Generated recurring invoices will always use 30-day terms regardless of user settings. |
| 3 | Endpoint Registry vs Agent Notes (Activities List) | Endpoint Registry for activities blueprint: only `create_activity` and `delete_activity` -- no list route | Agent 4 notes: "list.html is a partial included in client detail page OR a standalone page at `/clients/<id>/activities`" | WARN | The standalone list page option implies a GET route at `/clients/<int:client_id>/activities`, but no such route appears in the Endpoint Registry. If Agent 4 implements the standalone variant, it will add an unregistered route. If it implements the partial-only variant, the `list.html` template exists but has no standalone URL. Agents need to know which variant to build. |
| 4 | Project Structure vs Agent File Assignments | Project structure tree (lines 40-141): no `tests/` directory listed | Agent 15 (tests) creates 8 files under `invoice-crm/tests/` | WARN | The canonical project structure does not include the `tests/` directory, but Agent 15's file list requires it. This is not a contradiction that will cause a runtime failure, but any agent that uses the project structure tree as the authoritative file map will see an inconsistency. |
| 5 | activity_date Mixed Formats | `log_activity` function: `activity_date` set to `datetime('now')` (includes time, e.g. `2026-05-19 14:23:01`) | Agent 4 notes: "activity_date (date input, default today)" -- date-only value from HTML input (e.g. `2026-05-19`) | WARN | Two code paths write to the same `activity_date` column in different formats: the `log_activity` helper writes a datetime string, the activities form submits a date-only string. The column is TEXT so SQLite accepts both, but queries that sort or filter by `activity_date` may produce inconsistent ordering when timestamps mix with date-only values. |
| 6 | Schema vs Route SQL -- activities INSERT column names | Schema: `activities(client_id, user_id, type, notes, activity_date, created_at)` | `log_activity` INSERT: `(client_id, user_id, type, notes, activity_date)` | PASS | All column names match. `created_at` has a DEFAULT so omitting it is valid. |
| 7 | Schema vs Route SQL -- invoices INSERT column names | Schema: `invoices(user_id, client_id, invoice_number, status, issue_date, due_date, subtotal_cents, tax_cents, total_cents, notes, parent_invoice_id, ...)` | `generate_due_invoices` INSERT: same column list | PASS | All column names in the recurring invoice INSERT match the schema exactly. |
| 8 | Schema vs Route SQL -- invoice_line_items INSERT column names | Schema: `invoice_line_items(invoice_id, catalog_item_id, description, quantity, unit_price_cents, tax_rate, line_total_cents, sort_order)` | `generate_due_invoices` line items INSERT: same column list | PASS | All column names match. |
| 9 | Schema vs Route SQL -- payments SELECT column names | Schema: `payments.amount_cents`, `invoices.total_cents` | Payment->Invoice Status Update code: `SUM(amount_cents)` and `SELECT total_cents FROM invoices` | PASS | Column names match schema exactly. |
| 10 | Export vs Import -- generate_due_invoices | Recurring agent: `def generate_due_invoices(db, user_id)` in `app/recurring/routes.py` | Dashboard agent: `from app.recurring.routes import generate_due_invoices` | PASS | Export name matches import name exactly. Module path matches agent file location. |
| 11 | Export vs Import -- url_for names in Navigation Links | Navigation Links section defines 9 url_for names | Endpoint Registry defines matching function names and url_for names for all 9 | PASS | `dashboard.index`, `clients.list_clients`, `pipeline.list_deals`, `invoices.list_invoices`, `catalog.list_items`, `reports.index`, `settings_bp.index`, `auth.logout`, `search.search` -- all match registry entries exactly. |
| 12 | Cross-Boundary Wiring url_for -- Deal Won flow | Pipeline agent notes: `url_for('invoices.create_invoice', from_deal=deal_id)` | Endpoint Registry: invoices.create_invoice listed with function `create_invoice` | PASS | url_for name matches registry. |
| 13 | Money Convention -- catalog agent | Agent 6 notes: prefill `'%.2f' % (item['unit_price_cents'] / 100)` | Schema: `catalog_items.unit_price_cents INTEGER` | PASS | Field name and cents convention consistent. |
| 14 | Money Convention -- display filter references | Money Convention section: "Use `{{ value | dollars }}` Jinja2 filter" | `dollars` filter registered in helpers.py as `app.jinja_env.filters['dollars'] = dollars` | PASS | Filter name consistent between convention rule and registration code. |
| 15 | Blueprint Prefix vs Route Decorator -- activities shares /clients prefix | activities blueprint registered with `url_prefix='/clients'`; endpoint registry paths start with `/<int:client_id>/activities/...` | Blueprint template note: "Route decorators are RELATIVE to the blueprint prefix" | PASS | The activities routes are relative to `/clients` prefix, yielding correct absolute paths `/clients/<id>/activities/new` and `/clients/<id>/activities/<id>/delete`. No conflict with clients blueprint routes which use `/<int:client_id>` (no `/activities/` segment). |
| 16 | Schema vs Route SQL -- deals SELECT column names | Cross-Boundary Wiring deal prefill: `deal['client_id']`, `deal['title']` | Schema: `deals.client_id INTEGER`, `deals.title TEXT` | PASS | Column names match schema. |
| 17 | Endpoint Registry Completeness -- recurring blueprint | Registry: `set_recurring`, `view_history`, `generate_recurring` | Agent 8 notes: describes all three routes | PASS | All registry routes are addressed in agent notes. |
| 18 | Endpoint Registry Completeness -- reports blueprint | Registry: `index`, `revenue_by_month`, `revenue_by_client`, `aging`, `forecast`, `export_csv` | Agent 11 notes and project structure: templates for all 5 report pages present | PASS | `export_csv` has no template (returns CSV response directly) which is correct. All others have templates. |

---

## Summary

- **Total checks:** 18
- **PASS:** 13
- **FAIL:** 2
- **WARN:** 3
- **N/A (section absent):** 0

---

## FAIL Detail

### FAIL 1 -- Route Path Mismatch: Transaction Boundary Policy Example vs Endpoint Registry

**Location in spec:** Lines 302-303 (Transaction Boundary Policy code block)

The Transaction Boundary Policy section uses `create_payment` as its example of the "CORRECT" pattern:

```python
@bp.route('/invoices/<int:invoice_id>/payments/new', methods=['POST'])
@login_required
def create_payment(invoice_id):
```

The Endpoint Registry (payments blueprint, prefix `/payments`) defines:

| Function Name | Method | Path | url_for Name |
|---|---|---|---|
| create_payment | GET, POST | /invoice/\<int:invoice_id\>/new | payments.create_payment |

There are two contradictions embedded in the example:

1. **Path string mismatch:** The example uses `/invoices/<int:invoice_id>/payments/new` but the correct relative path (relative to `/payments` prefix) is `/invoice/<int:invoice_id>/new`. The example path has `invoices` (plural, matching the invoices blueprint name) and a `payments/new` suffix -- neither matches the registry entry.

2. **Implied absolute URL conflict:** If an agent treats the example's path literally as relative to the `/payments` prefix, the resulting absolute URL would be `/payments/invoices/<id>/payments/new`. If an agent treats it as an absolute path, it conflicts with the invoices blueprint's `/invoices/` prefix.

**Risk:** The payments agent may implement the wrong route path, making `url_for('payments.create_payment', invoice_id=...)` generate a URL that does not match the actual route registration, causing 404s on the payment link from invoice detail pages.

**Recommended fix:** Change the example path to match the registry: `@bp.route('/invoice/<int:invoice_id>/new', methods=['GET', 'POST'])`.

---

### FAIL 2 -- Hardcoded Payment Terms Ignore User Setting

**Location in spec:** Line 681 (`generate_due_invoices` code block in Cross-Boundary Wiring)

```python
db.execute("""
    INSERT INTO invoices (..., due_date, ...)
    VALUES (?, ..., date('now', '+' || ? || ' days'), ..., ?)
""", (user_id, inv['client_id'], new_number,
      30,  # default payment terms   <-- hardcoded
      ...))
```

The `users` table has `default_payment_terms INTEGER DEFAULT 30`, and the settings agent is explicitly told to expose this field for editing. The `generate_due_invoices` function already queries the users table once (to get `invoice_prefix`) but does not retrieve `default_payment_terms`.

**Risk:** Any user who changes their payment terms in Settings will find that recurring invoices continue to use 30-day terms. This is a silent behavior mismatch between the settings UI and the generation code.

**Recommended fix:** In `generate_due_invoices`, read `default_payment_terms` from the same `SELECT invoice_prefix FROM users WHERE id = ?` query (add `default_payment_terms` to the SELECT), then use that value instead of `30`.

---

## WARN Detail

### WARN 1 -- Activities List Route Missing from Endpoint Registry

Agent 4 notes say `list.html` can be used as "a standalone page at `/clients/<id>/activities`", but no GET route for this URL appears in the activities Endpoint Registry. The registry only has `create_activity` (GET, POST) and `delete_activity` (POST). If this route is intended, it must be added to the registry so other agents (e.g., clients detail template) know the correct `url_for` name to use for linking to it.

**Recommended fix:** Either (a) add `list_activities | GET | /<int:client_id>/activities | activities.list_activities` to the registry, or (b) remove the "standalone page" option from Agent 4 notes and confirm `list.html` is partial-only.

### WARN 2 -- tests/ Directory Absent from Project Structure Tree

The project structure tree does not include `invoice-crm/tests/`. Agent 15 depends on this directory existing. This is a documentation gap rather than a runtime failure, but it creates inconsistency when agents cross-reference the structure tree.

**Recommended fix:** Add `tests/` with its files to the project structure tree.

### WARN 3 -- Mixed activity_date Formats Across Two Write Paths

The `log_activity` helper writes `datetime('now')` (datetime string with time component) to `activity_date`. The activities form (Agent 4) submits a date-only string from an HTML date input. Both write to `activities.activity_date TEXT NOT NULL`. Queries that sort, filter, or display this field will encounter mixed formats (e.g., `2026-05-19 14:23:01` vs `2026-05-19`), which may produce subtly wrong sort order.

**Recommended fix:** Standardize both write paths. Either change `log_activity` to use `date('now')`, or accept datetime strings from both paths and sort consistently.

---

STATUS: FAIL -- 2 contradictions found
