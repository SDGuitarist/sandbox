# Performance Review: Solopreneur Command Center

**Run:** 047
**Date:** 2026-05-19
**Reviewer:** Performance Oracle (Claude Opus 4.6)
**Scope:** Flask + SQLite + Jinja2 app, 13 blueprints, ~12,800 lines, 21 tables

---

## Performance Summary

The application is a single-user solopreneur tool. At typical solopreneur data volumes (dozens of projects, hundreds of tasks, a few thousand time entries), performance will be fine. However, several structural issues will cause noticeable degradation as data grows past ~1,000 rows per table, and a few patterns are outright bugs that will cause problems at any scale.

The most impactful issues are: (1) the dashboard fires 12+ separate queries per page load, (2) the pipeline board fires one query per stage in a loop, (3) there are zero indexes on several heavily-filtered columns, (4) CSV export loads entire tables into memory with no limit, and (5) every single route opens a new SQLite connection (WAL mode is set only at init, not per-connection).

---

## Critical Issues

### P1-01: `setup_required` decorator opens a DB connection on EVERY request

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/decorators.py` (line 18-22)

Every protected route calls `setup_required`, which opens its own `get_db()` connection, runs `SELECT setup_complete FROM user WHERE id = ?`, and closes it. Then the route handler opens a *second* connection. This means every single page load opens at minimum 2 SQLite connections.

**Current impact:** Doubles connection overhead on every request. With SQLite, each `connect()` call opens the file, negotiates the WAL, and runs `PRAGMA foreign_keys=ON`.

**Projected impact at 10x concurrent requests:** SQLite's write lock contention increases linearly with connection count. The decorator connection is pure waste.

**Fix:** Cache the `setup_complete` flag in the Flask session after first check. Only re-query on login or setup completion.

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

### P1-02: WAL mode set only at init_db, not on per-request connections

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/db.py` (line 63 vs lines 41-42)

`init_db()` correctly sets `PRAGMA journal_mode=WAL`, but this is a database-level setting that persists in the file -- so it works. However, the `get_db()` context manager creates a brand-new `sqlite3.connect()` on every call and never reuses connections. This is technically correct for SQLite (WAL persists), but it means:

1. No connection pooling -- every request opens/closes a file handle.
2. `PRAGMA foreign_keys=ON` runs on every connection (correct, since it does not persist).
3. No `PRAGMA busy_timeout` is set on per-request connections. The `timeout=10` in `sqlite3.connect()` is Python-level retry, not SQLite-level `busy_timeout`. They behave differently under contention.

**Fix:** Add `PRAGMA busy_timeout=5000` to `get_db()` for proper SQLite-level timeout handling. Consider using Flask's `g` object to reuse the connection within a single request instead of opening multiple connections.

---

### P1-03: Dashboard fires 12+ queries per page load

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/dashboard/routes.py` (lines 21-34)
**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/models.py` (lines 1112-1283)

A single dashboard load executes these queries:

| # | Function | Queries Inside |
|---|----------|----------------|
| 1 | `get_revenue_snapshot()` | 3 SELECTs on `income` + 1 on `business_profile` |
| 2 | `get_active_projects_summary()` | 1 SELECT on `project` |
| 3 | `get_pipeline_summary()` | 2 SELECTs on `deal` |
| 4 | `get_overdue_tasks()` | 1 SELECT on `task` JOIN `project` |
| 5 | `get_upcoming_deadlines()` | 2 SELECTs (tasks + milestones) |
| 6 | `get_hours_this_week()` | 1 SELECT on `time_entry` + 1 on `business_profile` |
| 7 | `get_cash_flow()` | 2 SELECTs (income + expense) |
| 8 | `get_recent_activity()` | 1 SELECT on `activity_log` |
| 9 | `business_profile` query | 1 SELECT on `business_profile` |

**Total: ~16 queries per dashboard load.** Plus 1 from the `setup_required` decorator = **17 queries**.

`get_business_profile()` is called 3 separate times (revenue snapshot, hours this week, and the direct query in the route). Each call is a separate query.

**Current impact:** Measurable but tolerable at low data volumes. Each query is O(n) or O(n log n) with indexes.

**Projected impact at 1,000+ income/expense rows:** The 3 income-table scans in `get_revenue_snapshot()` all do date range filtering. They will each scan the `idx_income_date` index, which is fine, but the sheer count of round-trips adds up.

**Fix (two-phase):**

Phase 1 -- Deduplicate `business_profile` reads. Read it once in the route and pass it to helper functions.

Phase 2 -- Consolidate the revenue/expense queries. The 3 income queries in `get_revenue_snapshot` (this_month, last_month, YTD) can be a single query:

```sql
SELECT
    COALESCE(SUM(CASE WHEN date >= :this_month_start THEN amount ELSE 0 END), 0) AS this_month,
    COALESCE(SUM(CASE WHEN date >= :last_month_start AND date < :this_month_start THEN amount ELSE 0 END), 0) AS last_month,
    COALESCE(SUM(CASE WHEN date >= :year_start THEN amount ELSE 0 END), 0) AS ytd
FROM income
WHERE date >= :year_start
```

This reduces 3 queries to 1. Apply the same pattern to `get_cash_flow` (2 queries to 1 with a UNION or combined CASE).

---

### P1-04: Pipeline board fires one query per stage (loop pattern)

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/pipeline/routes.py` (lines 30-48)

```python
for key, label, probability in BOARD_STAGES:
    deals = db.execute(
        "SELECT d.*, c.name as contact_name "
        "FROM deal d LEFT JOIN contact c ON d.contact_id = c.id "
        "WHERE d.stage = ? ORDER BY d.updated_at DESC",
        (key,)
    ).fetchall()
```

This fires 5 separate queries (one per active stage). The same pattern repeats in `pipeline/stats` (lines 336-349) and in `models.py` `get_pipeline_stats()` (lines 1428-1443) -- another 5 queries per stage.

**Current impact:** 5 queries + 1 for contacts dropdown + 1 decorator = 7 queries for the board.

**Fix:** Single query, group in Python:

```python
all_deals = db.execute(
    "SELECT d.*, c.name as contact_name "
    "FROM deal d LEFT JOIN contact c ON d.contact_id = c.id "
    "WHERE d.stage NOT IN ('won', 'lost') "
    "ORDER BY d.updated_at DESC"
).fetchall()

deals_by_stage = {}
for deal in all_deals:
    deals_by_stage.setdefault(deal['stage'], []).append(deal)
```

This collapses 5 queries into 1. Complexity remains O(n) -- just one pass instead of five.

---

### P1-05: CSV export loads entire table into memory with no limit or streaming

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/reports/routes.py` (lines 361-390)

```python
rows = db.execute(f"SELECT * FROM {table}").fetchall()
output = io.StringIO()
writer = csv.writer(output)
for row in rows:
    writer.writerow(list(row))
return Response(output.getvalue(), ...)
```

Three problems:

1. **No LIMIT** -- fetches every row in the table. For `activity_log` (which grows unboundedly), this is a memory bomb.
2. **`fetchall()` loads everything into Python memory** before writing to the StringIO buffer. At 100K rows, this is hundreds of MB.
3. **`output.getvalue()` creates a second copy** of the entire CSV string in memory.

**Projected impact at 10K activity_log entries:** ~50MB memory spike per export request. At 100K: ~500MB, likely crashes the process.

**Fix:** Use a streaming generator response:

```python
def generate_csv(table):
    with get_db() as db:
        cursor = db.execute(f"SELECT * FROM {table}")
        header = [desc[0] for desc in cursor.description]
        yield ','.join(header) + '\n'
        while True:
            rows = cursor.fetchmany(500)
            if not rows:
                break
            buf = io.StringIO()
            writer = csv.writer(buf)
            for row in rows:
                writer.writerow(list(row))
            yield buf.getvalue()

return Response(
    generate_csv(table),
    mimetype='text/csv',
    headers={'Content-Disposition': f'attachment; filename="{module}.csv"'},
)
```

This keeps memory usage constant regardless of table size.

---

## Should-Fix Issues

### P2-01: No index on `income.contact_id` + `income.date` (composite)

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/schema.sql` (lines 292-307)

The schema has `idx_income_date` and `idx_income_contact` as separate indexes. But the revenue report (`reports/routes.py` line 66-73) filters on BOTH `date` and `contact_id` simultaneously. SQLite can only use one index per table per query, so this query does a partial index scan + row filtering.

The client report (`reports/routes.py` lines 99-113) does a 3-way LEFT JOIN (`contact`, `income`, `project`, `interaction`) grouped by `contact.id`. Without a composite index, this will degrade as tables grow.

**Fix:** Add composite indexes for the most common multi-column filters:

```sql
CREATE INDEX IF NOT EXISTS idx_income_date_contact ON income(date, contact_id);
CREATE INDEX IF NOT EXISTS idx_time_entry_date_project ON time_entry(date, project_id);
CREATE INDEX IF NOT EXISTS idx_task_status_due ON task(status, due_date);
CREATE INDEX IF NOT EXISTS idx_deal_stage_expected_close ON deal(stage, expected_close_date);
```

---

### P2-02: No index on `expense.category` or `expense.tax_deductible`

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/schema.sql`

The expense report groups by `category` and filters by `tax_deductible`. Neither column is indexed. The `idx_expense_date` index only covers date-range filters.

**Fix:**

```sql
CREATE INDEX IF NOT EXISTS idx_expense_category ON expense(category);
```

---

### P2-03: Task list view has no pagination

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/tasks/routes.py` (lines 38, 51-54)

The task query has no `LIMIT` clause at all. While the `LIMIT 1000` pattern is used elsewhere, the task index route skips it entirely. With hundreds of tasks, the page sends all of them to the browser.

After fetching, the route also computes totals in Python by iterating all entries (lines 43-44 in time_tracking):

```python
total_hours = sum(e['minutes'] for e in entries)
billable_hours = sum(e['minutes'] for e in entries if e['billable'])
```

This is O(n) in Python instead of using SQL aggregation.

**Fix:** Add `LIMIT 100` with offset-based pagination. Move aggregation to SQL:

```sql
SELECT COALESCE(SUM(minutes), 0) as total,
       COALESCE(SUM(CASE WHEN billable = 1 THEN minutes ELSE 0 END), 0) as billable
FROM time_entry te WHERE ...
```

---

### P2-04: `get_utilization_by_week` fires 12 queries in a loop

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/models.py` (lines 1461-1497)

```python
for i in range(weeks):
    week_start = monday - timedelta(weeks=i)
    week_end = week_start + timedelta(days=6)
    row = db.execute(
        """SELECT ... FROM time_entry WHERE date >= ? AND date <= ?""",
        (ws, we),
    ).fetchone()
```

This fires 12 queries (default `weeks=12`) to get utilization data -- one per week.

**Fix:** Single query using `strftime` grouping:

```sql
SELECT strftime('%Y-W%W', date) AS week,
       COALESCE(SUM(CASE WHEN billable = 1 THEN minutes ELSE 0 END), 0) AS billable,
       COALESCE(SUM(minutes), 0) AS total
FROM time_entry
WHERE date >= :twelve_weeks_ago AND date <= :today
GROUP BY strftime('%Y-W%W', date)
ORDER BY week DESC
```

One query instead of twelve. Complexity: O(n) single pass vs O(12n) twelve passes.

---

### P2-05: Client report has a 3-way LEFT JOIN with no covering index

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/reports/routes.py` (lines 99-113)

```sql
SELECT c.id, c.name, ..., MAX(intr.date) AS last_interaction
FROM contact c
LEFT JOIN income i ON i.contact_id = c.id
LEFT JOIN project p ON p.contact_id = c.id
LEFT JOIN interaction intr ON intr.contact_id = c.id
GROUP BY c.id
```

This query joins 4 tables. The LEFT JOINs cause a Cartesian product between income, project, and interaction rows for the same contact before the GROUP BY collapses them. With 50 contacts, 200 income rows, 30 projects, and 500 interactions, the intermediate result set could be `200 * 30 * 500 = 3,000,000` rows before grouping.

**Fix:** Use subqueries instead of JOINs:

```sql
SELECT c.id, c.name AS contact_name,
       (SELECT COALESCE(SUM(amount), 0) FROM income WHERE contact_id = c.id) AS revenue,
       (SELECT COUNT(*) FROM project WHERE contact_id = c.id) AS projects,
       (SELECT COALESCE(SUM(amount), 0) / MAX(COUNT(*), 1) FROM income WHERE contact_id = c.id) AS avg_value,
       (SELECT MAX(date) FROM interaction WHERE contact_id = c.id) AS last_interaction
FROM contact c
ORDER BY revenue DESC
```

This is O(contacts * log(n)) per subquery with indexes, vs O(contacts * income * projects * interactions) for the JOIN approach.

---

### P2-06: Revenue P&L and by-month views duplicate identical queries

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/revenue/routes.py`

The `pl()` route (line 247) and the `by_month()` route (line 331) execute *exactly the same two queries* -- income grouped by month and expenses grouped by month. The Python processing is also nearly identical.

**Fix:** Extract a shared helper function. This is a code quality issue but also a performance issue: if someone visits both pages in quick succession, the same data is computed twice.

---

### P2-07: `activity_log` table grows unboundedly with no cleanup

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/schema.sql` (lines 213-220)

Every CRUD operation inserts into `activity_log`. There is no TTL, no archival, and no cleanup. The CSV export for `activity_log` (via the generic export) has no LIMIT.

**Projected impact:** After 1 year of daily use (5-10 actions/day), ~2,000-3,600 rows. After 3 years, ~10,000 rows. The `idx_activity_created` index helps for ordered reads, but the CSV export and any full-table scans will grow linearly.

**Fix:** Add a periodic cleanup or a LIMIT to the export. Optionally, add a `WHERE created_at >= date('now', '-1 year')` to the CSV export for activity_log.

---

## Nice-to-Have Optimizations

### P3-01: Contact search uses LIKE with leading wildcard

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/models.py` (lines 1073-1080)

```python
"WHERE name LIKE ? OR email LIKE ?", (f'%{query}%', f'%{query}%')
```

Leading `%` wildcards prevent index usage. SQLite must do a full table scan.

**Fix:** For a solopreneur app with <1,000 contacts, this is fine. If it ever becomes a problem, add an FTS5 virtual table for contacts (like the one already used for notes).

---

### P3-02: Multiple connections opened within single route on validation failure

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/revenue/routes.py` (lines 82-90)

In `edit_income`, when validation fails, a new `get_db()` connection is opened to re-fetch the income record. This happens inside the same request that already opened a connection for the POST. Minor issue since it only fires on validation errors.

---

### P3-03: `CASE WHEN priority` ordering is computed per-row

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/tasks/routes.py` (line 51)

```sql
ORDER BY CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 ...
```

This is a computed sort on every row. SQLite cannot use an index for this. At <1,000 tasks, the impact is negligible.

**Fix (only if needed):** Store priority as an integer column (1-4) and index it. Not worth the migration effort at current scale.

---

### P3-04: No HTTP caching headers on any response

No `Cache-Control`, `ETag`, or `Last-Modified` headers are set. Every navigation triggers a full server-side render. For a local single-user app this is tolerable, but adding `Cache-Control: private, max-age=0, must-revalidate` with ETags would allow conditional requests.

---

### P3-05: `get_upcoming_deadlines` merges two lists in Python then sorts

**File:** `/Users/alejandroguillen/Projects/sandbox/command-center/app/models.py` (lines 1206-1231)

Two queries (tasks and milestones) are fetched, concatenated in Python, sorted, then sliced. This could be a single `UNION ALL` query with `ORDER BY ... LIMIT 20` in SQL.

---

## Scalability Assessment

### Data Volume Projections

| Table | Year 1 | Year 3 | Bottleneck? |
|-------|--------|--------|-------------|
| contact | 50-200 | 200-1,000 | No |
| deal | 30-100 | 100-500 | No |
| project | 20-50 | 50-200 | No |
| task | 100-500 | 500-3,000 | P2-03 (no pagination) |
| time_entry | 500-2,000 | 2,000-10,000 | P2-04 (12-query loop) |
| income | 50-200 | 200-1,000 | No |
| expense | 100-500 | 500-3,000 | No |
| activity_log | 1,000-4,000 | 5,000-15,000 | P1-05 (CSV export) |

### Concurrent User Analysis

This is a single-user app, so concurrent writes are unlikely. However, multiple browser tabs or aggressive link-clicking could create concurrent reads. SQLite's WAL mode handles concurrent reads well. The main risk is write contention from `BEGIN IMMEDIATE` transactions overlapping.

### Resource Utilization Estimates

- **Memory per dashboard load:** ~2-5 MB (17 queries, all small result sets). Acceptable.
- **Memory per CSV export (activity_log, 10K rows):** ~50-100 MB. Unacceptable. (P1-05)
- **Disk I/O per page load:** 2 connection opens (decorator + route), 5-17 queries. WAL mode makes reads non-blocking.

---

## Recommended Actions (Priority Order)

| Priority | ID | Action | Impact | Effort |
|----------|------|--------|--------|--------|
| P1 | 01 | Cache `setup_complete` in session | -1 DB connection per request | 10 min |
| P1 | 03 | Consolidate dashboard queries (dedupe profile, merge income queries) | 17 queries -> ~10 | 30 min |
| P1 | 04 | Single query for pipeline board | 5 queries -> 1 | 15 min |
| P1 | 05 | Stream CSV exports with fetchmany | Constant memory vs linear | 20 min |
| P2 | 01 | Add composite indexes | Faster multi-column filters | 10 min |
| P2 | 04 | Single query for utilization by week | 12 queries -> 1 | 15 min |
| P2 | 05 | Rewrite client report with subqueries | Prevent Cartesian product | 15 min |
| P2 | 03 | Add pagination to task list | Bounded page size | 30 min |
| P2 | 07 | Add activity_log TTL or export limit | Bounded growth | 10 min |
| P1 | 02 | Add `PRAGMA busy_timeout` to get_db | Better contention handling | 5 min |

### Total estimated effort: ~2.5 hours for all P1 + P2 fixes.

---

## Key Files Reviewed

- `/Users/alejandroguillen/Projects/sandbox/command-center/app/db.py` -- connection management, WAL init
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/decorators.py` -- setup_required per-request query
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/models.py` -- dashboard queries, utilization loop
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/schema.sql` -- table definitions, indexes
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/dashboard/routes.py` -- 17-query dashboard
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/revenue/routes.py` -- duplicated P&L queries
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/reports/routes.py` -- CSV export, client report Cartesian join
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/time_tracking/routes.py` -- Python-side aggregation
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/tasks/routes.py` -- missing pagination
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/pipeline/routes.py` -- per-stage query loop
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/contacts/routes.py` -- detail page queries
- `/Users/alejandroguillen/Projects/sandbox/command-center/app/projects/routes.py` -- detail page, template copy loops
