# Performance Review: Invoice & CRM Flask Application

**Run:** 046  
**Date:** 2026-05-19  
**Reviewer:** Performance Oracle (Claude Opus 4.6)  
**Scope:** 12 blueprints, ~6,000 lines, Flask + SQLite + Jinja2  

---

## 1. Performance Summary

The application is a single-tenant Flask/SQLite invoicing and CRM system built by a 15-agent swarm. For a single-user or small-team deployment, most operations will feel fast today. However, the codebase has several structural patterns that will degrade noticeably once data grows past a few hundred records per table. The most urgent issue is the dashboard route, which runs **12 separate queries plus write operations on every single GET request**, including recurring invoice generation and overdue status updates. This is a correctness risk in addition to a performance risk -- concurrent requests can produce duplicate invoices or race conditions on the status UPDATE.

The schema has good basic index coverage (user_id, client_id, status indexes are present). The biggest gap is that SQLite cannot use indexes on `strftime()` function calls, which means all payment-date revenue queries do full table scans.

**Overall risk level:** Moderate. The application will work fine up to ~500 invoices and ~100 clients. Past that, the dashboard will noticeably slow, the search will degrade, and the CSV export could spike memory.

---

## 2. Critical Issues (P1 -- Must Fix)

### P1-1: Dashboard runs write operations (recurring generation + overdue UPDATE) on every GET

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/dashboard/routes.py`, lines 14-25

**What happens:** Every time anyone loads the dashboard, two things happen before any read queries:
1. `generate_due_invoices()` is called, which runs a SELECT, then for each due invoice runs 4+ additional queries (max invoice number, user settings, INSERT invoice, SELECT + INSERT line items, UPDATE recurrence date).
2. A blanket `UPDATE invoices SET status = 'overdue'` fires for all sent invoices past due.

Both are followed by `db.commit()`.

**Why this is P1:**
- **Race condition:** If two browser tabs load the dashboard simultaneously, `generate_due_invoices` can create duplicate invoices. The invoice number generation reads MAX then inserts -- no locking between the read and write. SQLite serializes writes, but the read-then-write gap is not atomic.
- **Write amplification:** Every dashboard page view triggers disk writes. For a page that should be read-only, this is architecturally wrong.
- **Performance cost:** The recurring generation loop is O(R * L) where R = number of due recurring invoices and L = average line items per invoice. Each iteration runs 5+ queries. If 10 recurring invoices are due with 5 line items each, that is 50+ queries before the dashboard even starts loading data.

**Projected impact at scale:** With 50 recurring invoices due on a Monday morning, a single dashboard load fires 250+ queries and inserts 50 invoices with all their line items. Under concurrent load this becomes worse.

**Recommended fix:**
Move recurring generation and overdue updates to a background job (e.g., a cron job, APScheduler, or a CLI command run by cron). At minimum, use a lightweight check first:

```python
# Only run generation if there are actually due invoices
count = db.execute("""
    SELECT COUNT(*) FROM invoices
    WHERE user_id = ? AND is_recurring = 1
      AND next_recurrence_date IS NOT NULL
      AND next_recurrence_date <= date('now')
      AND status != 'draft'
""", (user_id,)).fetchone()[0]

if count > 0:
    generated = generate_due_invoices(db, user_id)
    db.commit()
```

Better solution: Extract to a Flask CLI command (`flask generate-recurring`) and run it via cron once per hour. Remove it from the dashboard GET entirely.

---

### P1-2: Dashboard fires 12 queries per page load

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/dashboard/routes.py`, lines 30-119

**What happens:** After the write operations, the dashboard runs 10 separate SELECT queries:
1. Revenue this month (payments table scan)
2. Revenue last month (payments table scan)
3. Revenue YTD (payments table scan)
4. Outstanding invoices total
5. Overdue invoices total
6. Recent 10 invoices (with JOIN)
7. All overdue invoices (with JOIN)
8. Pipeline stages (deals GROUP BY)
9. Upcoming recurring invoices (with JOIN)
10. Top 5 clients by revenue (3-table JOIN with GROUP BY)

**Why this is P1:** Queries 1-3 all scan the payments table using `strftime()` on `payment_date`, which prevents index usage (see P1-3). These three queries could be consolidated into a single query. Queries 4-5 both scan the invoices table and could be combined. Total could be reduced from 10 to 5-6 with simple query consolidation.

**Projected impact at scale:** With 10,000 payments and 5,000 invoices, the dashboard will take 1-2 seconds on SQLite. Each strftime-based scan is O(N) over all payments for that user.

**Recommended fix -- consolidate queries:**

```python
# Combine revenue queries into one pass over payments
revenue = db.execute("""
    SELECT
        COALESCE(SUM(CASE WHEN payment_date >= date('now', 'start of month')
                     THEN amount_cents END), 0) AS this_month,
        COALESCE(SUM(CASE WHEN payment_date >= date('now', 'start of month', '-1 month')
                          AND payment_date < date('now', 'start of month')
                     THEN amount_cents END), 0) AS last_month,
        COALESCE(SUM(CASE WHEN payment_date >= date('now', 'start of year')
                     THEN amount_cents END), 0) AS ytd
    FROM payments
    WHERE user_id = ?
""", (user_id,)).fetchone()

# Combine outstanding + overdue into one pass
totals = db.execute("""
    SELECT
        COALESCE(SUM(CASE WHEN status IN ('sent', 'viewed')
                     THEN total_cents END), 0) AS outstanding,
        COALESCE(SUM(CASE WHEN status = 'overdue'
                     THEN total_cents END), 0) AS overdue_total
    FROM invoices
    WHERE user_id = ?
""", (user_id,)).fetchone()
```

This alone reduces query count from 10 to 7. Using date range comparisons instead of strftime also allows index usage (see P1-3).

---

### P1-3: strftime() in WHERE clauses prevents index usage on payment queries

**Files:**
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/dashboard/routes.py`, lines 31-48
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/reports/routes.py`, lines 13-26

**What happens:** Revenue queries filter payments using `strftime('%Y-%m', payment_date) = strftime('%Y-%m', 'now')`. SQLite cannot use an index when a function wraps the indexed column. This forces a full table scan of every payment row for the user.

**Why this is P1:** The payments table will grow fastest (every invoice can have multiple payments). Once it reaches thousands of rows, every dashboard load and revenue report will scan every single row.

**Recommended fix:** Replace function-wrapped comparisons with range comparisons:

```sql
-- Instead of: strftime('%Y-%m', payment_date) = strftime('%Y-%m', 'now')
-- Use:
WHERE payment_date >= date('now', 'start of month')
  AND payment_date < date('now', 'start of month', '+1 month')
```

Then add a composite index:

```sql
CREATE INDEX IF NOT EXISTS idx_payments_user_date
    ON payments(user_id, payment_date);
```

This turns O(N) full scans into O(log N) index lookups.

---

### P1-4: Recurring invoice generation has N+1 query pattern with no atomicity

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/recurring/routes.py`, lines 7-73

**What happens:** For each due recurring invoice, the function runs:
1. `SELECT MAX(...)` to find the next invoice number
2. `SELECT ... FROM users` to get prefix and payment terms
3. `INSERT INTO invoices` to create the new invoice
4. `SELECT last_insert_rowid()`
5. `SELECT * FROM invoice_line_items` to get the source line items
6. For each line item: `INSERT INTO invoice_line_items`
7. `UPDATE invoices` to advance the recurrence date

That is 5 + L queries per recurring invoice (where L is the line item count). The user settings query (step 2) is identical every iteration and should be fetched once before the loop.

**Why this is P1:** The invoice number generation (step 1) reads MAX then inserts. If two recurring invoices generate in the same loop iteration, they correctly get sequential numbers because SQLite serializes. But the `inv['invoice_number'][:3]` used as the prefix in the MAX query is wrong -- it hard-codes a 3-character prefix assumption. If the user's prefix is "INVOICE", this will read `"INV"` and generate a wrong number or collision.

**Recommended fix:**

```python
# Fetch user settings ONCE before the loop
user_row = db.execute(
    "SELECT invoice_prefix, default_payment_terms FROM users WHERE id = ?",
    (user_id,)
).fetchone()
prefix = user_row['invoice_prefix']
payment_terms = user_row['default_payment_terms']

for inv in due:
    max_num = db.execute(
        "SELECT MAX(CAST(SUBSTR(invoice_number, LENGTH(?) + 2) AS INTEGER)) "
        "FROM invoices WHERE user_id = ?",
        (prefix, user_id)  # Use the actual prefix, not sliced invoice_number
    ).fetchone()[0] or 0
    # ... rest of generation
```

Also consider using `executemany()` for the line item inserts if the batch is large.

---

## 3. Should Fix (P2)

### P2-1: Invoice list view has no pagination

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/invoices/routes.py`, lines 28-77

**What happens:** `list_invoices()` calls `.fetchall()` with no LIMIT. Every invoice for the user is loaded into memory and passed to the template.

**Projected impact:** At 1,000 invoices, this loads 1,000 Row objects into memory and renders 1,000 table rows in HTML. At 10,000 invoices, the page will be several MB of HTML and take seconds to render.

**Affects also:**
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/payments/routes.py` line 100 (list_payments -- no LIMIT)
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/pipeline/routes.py` line 17 (list_deals -- no LIMIT)
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/activities/routes.py` line 21 (list_activities -- no LIMIT)
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/clients/routes.py` line 120 (list_clients -- no LIMIT)

**Recommended fix:** Add LIMIT/OFFSET pagination to all list views. A simple approach:

```python
page = request.args.get('page', 1, type=int)
per_page = 25
offset = (page - 1) * per_page

query += " LIMIT ? OFFSET ?"
params.extend([per_page, offset])

# Also run a COUNT query for pagination controls
count = db.execute("SELECT COUNT(*) FROM ...", ...).fetchone()[0]
```

---

### P2-2: LIKE search queries cannot use indexes

**Files:**
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/clients/routes.py`, lines 102-105
- `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/search/routes.py`, lines 17-37

**What happens:** Search uses `WHERE name LIKE '%query%'`. The leading wildcard prevents SQLite from using any index on the `name` column. This is a full table scan.

**Projected impact:** At 500 clients, negligible. At 5,000+ clients, search will take noticeable time. The global search page (`search/routes.py`) scans three tables (clients, invoices, deals) sequentially.

**Recommended fix (short-term):** For prefix matching, use `name LIKE 'query%'` (no leading wildcard), which can use an index. For full-text search, SQLite's FTS5 extension is the right tool:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS clients_fts USING fts5(name, email, company, content=clients, content_rowid=id);
```

This is a bigger change, so it is P2 rather than P1. The current LIKE approach is fine for the expected data volumes of a small-business CRM.

---

### P2-3: CSV export loads all data into memory via StringIO

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/reports/routes.py`, lines 136-174

**What happens:** The `export_csv()` function writes all rows to an `io.StringIO()` buffer, then returns `output.getvalue()` as the response body. This means the entire CSV is built in memory before any bytes are sent to the client.

**Projected impact:** With 100,000 payments, the revenue_by_month export itself is fine (aggregated), but if the application later adds a "full payment export" or "all invoices export," this pattern will use unbounded memory. The current exports are all aggregated, so the actual row count is bounded (months, clients, 4 aging buckets, months of deals). This is P2 because the risk is latent.

**Recommended fix:** Use Flask's streaming response pattern:

```python
from flask import stream_with_context

def generate_csv():
    yield 'Month,Total\n'
    with get_db() as db:
        for row in db.execute(...):
            yield f"{row['month']},{row['total_cents'] / 100:.2f}\n"

return Response(
    stream_with_context(generate_csv()),
    mimetype='text/csv',
    headers={'Content-Disposition': f'attachment; filename={report_type}.csv'},
)
```

This uses near-zero memory regardless of data size.

---

### P2-4: Aging report runs 4 separate queries instead of 1

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/reports/routes.py`, lines 47-73

**What happens:** The `_aging_data()` function loops through 4 bucket definitions and runs a separate query for each. Each query scans the invoices table.

**Recommended fix:** Combine into a single query using CASE expressions:

```sql
SELECT
    SUM(CASE WHEN due_date >= date('now', '-30 days') THEN 1 ELSE 0 END) AS current_count,
    COALESCE(SUM(CASE WHEN due_date >= date('now', '-30 days') THEN total_cents END), 0) AS current_total,
    SUM(CASE WHEN due_date BETWEEN date('now', '-60 days') AND date('now', '-31 days') THEN 1 ELSE 0 END) AS bucket_31_60_count,
    -- ... etc for each bucket
FROM invoices
WHERE user_id = ? AND status IN ('sent', 'viewed', 'overdue')
```

Reduces 4 queries to 1 and 4 table scans to 1.

---

### P2-5: Missing index on payments.payment_date

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/db.py`

**What is missing:** The payments table has indexes on `invoice_id` and `user_id`, but no index on `payment_date`. Every revenue query that filters by date range must scan all payment rows for the user, even after fixing the strftime issue (P1-3).

**Recommended fix:** Add a composite index:

```sql
CREATE INDEX IF NOT EXISTS idx_payments_user_date ON payments(user_id, payment_date);
```

This supports the dashboard revenue queries, the revenue_by_month report, and any future date-filtered payment queries.

---

### P2-6: Missing index on invoices.due_date

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/db.py`

**What is missing:** The overdue update (`WHERE status = 'sent' AND due_date < date('now')`) and aging report both filter on `due_date`, but there is no index for it. The `idx_invoices_status` index helps filter by status but the due_date predicate still requires scanning all matching rows.

**Recommended fix:**

```sql
CREATE INDEX IF NOT EXISTS idx_invoices_status_due ON invoices(user_id, status, due_date);
```

This composite index supports both the overdue update and the aging report efficiently.

---

### P2-7: Line item INSERT loop in invoice creation -- no batching

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/invoices/routes.py`, lines 232-240

**What happens:** Each line item is inserted with an individual `db.execute()` call inside a loop. For an invoice with 20 line items, that is 20 separate INSERT statements.

**Recommended fix:** Use `executemany()`:

```python
db.executemany("""
    INSERT INTO invoice_line_items
        (invoice_id, catalog_item_id, description, quantity,
         unit_price_cents, tax_rate, line_total_cents, sort_order)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", [
    (invoice_id, item['catalog_item_id'], item['description'],
     item['quantity'], item['unit_price_cents'], item['tax_rate'],
     item['line_total_cents'], item['sort_order'])
    for item in parsed_items
])
```

This is faster because SQLite can batch the inserts into a single transaction more efficiently.

---

## 4. Nice to Have (P3)

### P3-1: Foreign key PRAGMA runs on every connection

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/db.py`, line 15

**What happens:** `PRAGMA foreign_keys = ON` executes every time `get_db()` creates a connection. This is correct behavior (SQLite requires it per-connection), but the `get_db()` function stores the connection in Flask's `g` object and only creates it once per request. So this is fine for correctness. However, the connection is only created once per request because of the `if 'db' not in g` guard, meaning the PRAGMA also only runs once. No change needed here -- this is actually well-implemented.

---

### P3-2: WAL mode is set during init_db but not verified at connection time

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/db.py`, line 33

**What happens:** WAL mode is set in `init_db()` which runs at app startup. WAL mode is persistent (survives restarts), so this is fine. However, if the database file is copied or recreated without running init_db, WAL mode would be lost.

**Recommendation:** This is defensive, but you could add `PRAGMA journal_mode` to the connection setup. Low priority since init_db runs on every app start.

---

### P3-3: `_sync_tags` runs INSERT OR IGNORE + SELECT per tag

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/clients/routes.py`, lines 12-40

**What happens:** For each tag name, two queries run: INSERT OR IGNORE (to upsert) and then SELECT to get the ID. This is O(T) queries where T is the number of tags.

**Projected impact:** Tags per client are typically 1-5, so this is negligible. If a bulk import ever adds 100 tags, this would run 200 queries. Low risk given the domain.

**Recommendation:** Use `INSERT OR IGNORE ... RETURNING id` (SQLite 3.35+) to combine into one query per tag, or use a CTE. Low priority.

---

### P3-4: `delete_invoice` manually deletes line items despite ON DELETE CASCADE

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/invoices/routes.py`, line 592

**What happens:** The code runs `DELETE FROM invoice_line_items WHERE invoice_id = ?` before `DELETE FROM invoices WHERE id = ?`. The schema has `ON DELETE CASCADE` on invoice_line_items.invoice_id, so the first DELETE is redundant.

**Performance impact:** Negligible, but it is an extra query and could cause confusion about whether CASCADE is trusted.

---

### P3-5: Global search runs three sequential queries that could be parallelized

**File:** `/Users/alejandroguillen/Projects/sandbox/invoice-crm/app/search/routes.py`, lines 21-37

**What happens:** The search page queries clients, invoices, and deals sequentially. In a threaded or async framework these could run concurrently. In Flask with SQLite (single writer, shared-nothing connections), parallelization is not straightforward, but if the app ever moves to PostgreSQL, this would be a candidate for asyncio.gather.

---

## 5. Scalability Assessment

### Data Volume Projections

| Table | Expected after 1 year | After 3 years | Impact |
|-------|----------------------|---------------|--------|
| invoices | 500-1,000 | 2,000-5,000 | Dashboard queries slow without pagination |
| payments | 500-2,000 | 2,000-10,000 | strftime scans become noticeable at 5,000+ |
| clients | 50-200 | 100-500 | LIKE search acceptable at this scale |
| line_items | 2,000-5,000 | 10,000-25,000 | Well-indexed, no concern |
| deals | 100-500 | 500-2,000 | Pipeline view fine without pagination |
| activities | 500-2,000 | 2,000-10,000 | No pagination, will grow unbounded on detail pages |

### Concurrent User Analysis

SQLite with WAL mode supports concurrent reads well. The problem is the dashboard's write-on-read pattern (P1-1). With 5 concurrent users loading the dashboard:
- 5 simultaneous attempts to generate recurring invoices
- SQLite serializes writes, so one succeeds and the others either duplicate or wait
- 60+ queries per dashboard load x 5 users = 300+ queries in a burst

### Resource Utilization

- **Memory:** The main risk is unpaginated list views (P2-1). At 10,000 invoices, a list page load would use ~10-20 MB of RAM for sqlite3.Row objects and the rendered HTML.
- **Disk I/O:** WAL mode is correctly configured, which helps. The unnecessary dashboard writes (P1-1) add I/O on every page view.
- **CPU:** The strftime calls (P1-3) are CPU-bound string operations on every row. Replacing with date range comparisons removes this overhead.

---

## 6. Recommended Actions (Priority Order)

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| P1-1 | Move recurring generation + overdue update out of dashboard GET | Medium | Eliminates race condition, removes writes from reads |
| P1-3 | Replace strftime() filters with date range comparisons | Low | Enables index usage on all payment queries |
| P1-2 | Consolidate dashboard queries (10 -> 5-6) | Low | Halves query count on most-visited page |
| P1-4 | Fix recurring generation N+1 and prefix bug | Low | Prevents wrong invoice numbers, reduces queries |
| P2-5 | Add `idx_payments_user_date` composite index | Trivial | Speeds up all date-filtered payment queries |
| P2-6 | Add `idx_invoices_status_due` composite index | Trivial | Speeds up overdue detection and aging report |
| P2-1 | Add pagination to all list views | Medium | Bounds memory and render time |
| P2-4 | Consolidate aging report to single query | Low | 4 table scans -> 1 |
| P2-7 | Use executemany() for line item inserts | Trivial | Minor speedup on invoice creation |
| P2-2 | Consider FTS5 for full-text search | High | Better search at scale, but overkill for now |
| P2-3 | Stream CSV exports | Low | Future-proofs for larger exports |

---

## 7. What the Swarm Got Right

Credit where due -- the swarm build did several things well from a performance standpoint:

- **WAL mode enabled at init.** This is the single most important SQLite configuration for a web application, and it is set correctly.
- **Foreign key PRAGMA per connection.** Correctly placed inside the connection guard.
- **Index coverage on foreign keys.** All FK columns have indexes (client_id, user_id, invoice_id). Many swarm builds miss this.
- **Batch tag fetching.** `_get_tags_for_clients()` in clients/routes.py fetches tags for all listed clients in a single query instead of N+1. This is the right pattern.
- **Connection pooling via Flask g.** One connection per request, properly closed on teardown. Simple and correct for SQLite.
- **Bounded queries on detail pages.** Client detail limits invoices and activities to 10 with `LIMIT 10`. Dashboard limits recent invoices to 10.

---

## Feed-Forward

- **Hardest decision:** Classifying the dashboard writes-on-GET as P1 rather than P2. The race condition on invoice number generation in `generate_due_invoices` pushed it to P1 -- it is a correctness bug, not just a performance concern.
- **Rejected alternatives:** Considered recommending a move to PostgreSQL for better concurrency. Rejected because SQLite with WAL is appropriate for the app's scale, and the issues found are all fixable within SQLite.
- **Least confident:** The real-world impact of the strftime scan (P1-3). With typical small-business volumes (under 1,000 payments), the scans may be imperceptible. But it is architecturally wrong and trivial to fix, so it stays P1.
