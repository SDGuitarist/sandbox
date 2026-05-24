# SQLite WAL Mode + Connection Management in Flask

Research agent output for run 059 deepen phase.

## Summary

The plan's `get_db()` context manager pattern creates a new connection per call and closes it when the context exits. This works but diverges from Flask's recommended `g`-object pattern, which reuses one connection per request. For these sandbox apps the practical difference is small, but the `g`-object pattern is safer against accidental multiple-connection bugs and is what Flask's own documentation prescribes. WAL mode is correctly persistent and only needs to be set once (in `init_db`). The `timeout=10` parameter is fine. `PRAGMA foreign_keys=ON` per-connection is the only correct approach. The explicit `conn.commit()` after read-only queries is a harmless no-op. `executescript()` does issue an implicit COMMIT before running, but this does not interfere with the WAL pragma because PRAGMA journal_mode is not transactional. Thread safety is not a concern when each request gets its own connection.

---

## Findings

### 1. Connection-per-request vs. Flask `g` object

**Question:** Is creating a new connection per call (connect + close in context manager) the right pattern, or should we use Flask's `g` object for connection reuse?

**Answer:** Flask's official documentation recommends the `g`-object pattern:

```python
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(...)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
```

This creates at most one connection per request and automatically closes it when the request context tears down (via `app.teardown_appcontext(close_db)`).

The context-manager pattern in the plan creates a **new connection every time `get_db()` is called**, even within the same request. If a route handler calls two model functions, that is two separate connections, two separate transactions. This is not wrong, but it has two downsides:

- **No cross-call transaction guarantee.** If route code calls `create_thing()` then `update_related()`, each runs in its own connection/transaction. A crash between them leaves the DB in an inconsistent state.
- **Minor overhead.** Opening a SQLite connection involves re-parsing the schema. Benchmarks show this is roughly an order of magnitude slower than reusing an existing connection, though the absolute cost is still only milliseconds for small schemas.

**However**, the context-manager pattern has one advantage the plan exploits: `BEGIN IMMEDIATE` support for write operations. The `g`-object pattern does not easily support switching between deferred and immediate transactions mid-request.

**Practical recommendation:** For routes that need a single read or a single write, either pattern works fine. For routes that need multiple DB calls that should be atomic, the `g`-object pattern is better because it naturally shares one connection. The `BEGIN IMMEDIATE` feature can be layered on top by having the route explicitly call `g.db.execute('BEGIN IMMEDIATE')` when needed.

The existing project already uses the `g`-object pattern in `app/db.py` (the brewery app). The bookmark-manager and chat apps use the context-manager pattern. Both work; the `g`-object pattern is the Flask-canonical one.

### 2. WAL mode persistence

**Question:** Once set, is WAL mode truly persistent across connections? Any cases where it reverts?

**Answer:** **Yes, WAL mode is persistent.** It is stored as a property of the database file itself, not just the connection. Once you execute `PRAGMA journal_mode=WAL` on a database, every subsequent connection to that file automatically uses WAL mode. You do not need to re-set it per connection.

This is unique to WAL -- all other journal modes (DELETE, TRUNCATE, PERSIST, MEMORY, OFF) revert to DELETE when you reopen the database.

**Known cases where WAL does not work or reverts:**

1. **In-memory databases (`:memory:`)** -- WAL is not supported.
2. **Temporary databases** -- Cannot be set to WAL mode.
3. **VFS without shared-memory support** -- If the underlying Virtual File System does not support shared-memory methods (e.g., some network filesystems), opening a WAL-mode database will fail or fall back.
4. **Explicit revert** -- Only reverts if you explicitly run `PRAGMA journal_mode=DELETE` (or another mode).

**For this plan:** Setting WAL in `init_db` is correct and sufficient. The bookmark-manager's `get_db()` re-sets `PRAGMA journal_mode=WAL` on every connection, which is unnecessary but harmless (it returns "wal" and does nothing). The plan's version (WAL only in `init_db`) is the cleaner approach.

### 3. The `timeout=10` parameter

**Question:** Does this apply to lock acquisition? Is 10 seconds appropriate?

**Answer:** Yes. Python's `sqlite3.connect(db_path, timeout=10)` sets the busy timeout to 10 seconds (10,000 milliseconds). Under the hood, this calls SQLite's `sqlite3_busy_timeout()`, which is identical to `PRAGMA busy_timeout=10000`. They are the same mechanism -- pick one, not both.

When a connection cannot acquire a lock, SQLite will retry with exponential backoff for up to the timeout duration before raising `sqlite3.OperationalError: database is locked`.

**Is 10 seconds appropriate?** For a sandbox web app, yes. The Python default is 5 seconds. 10 seconds is conservative and appropriate. In production web apps with higher concurrency, you would want to tune this alongside WAL mode and connection management.

**Important caveat:** The busy timeout does NOT help with all lock scenarios. Specifically, if connection A holds a write lock and connection B tries to upgrade from a read transaction to a write transaction, B will fail immediately with "database is locked" regardless of the timeout. This is why `BEGIN IMMEDIATE` is important for write operations -- it acquires the write lock up front rather than trying to upgrade later.

### 4. `PRAGMA foreign_keys=ON` per-connection

**Question:** Must be set per-connection. Is there any way this could be missed?

**Answer:** `PRAGMA foreign_keys` is **not persistent** -- it must be set on every new connection. There is no database-level flag for it (unlike WAL mode). The only way to change the default is to recompile SQLite with `SQLITE_DEFAULT_FOREIGN_KEYS=1`, which is not practical for most deployments.

**Can it be missed in this plan?** With the context-manager pattern, no -- `get_db()` sets it every time a connection is created. This is correct.

With the `g`-object pattern, it is also set in `get_db()` on first call, so it cannot be missed during normal request handling.

**The one risk:** If any code creates a raw `sqlite3.connect()` call outside of `get_db()` (e.g., in a CLI command, migration script, or test fixture), foreign keys will be silently disabled. The `init_db()` function in the plan does NOT set `PRAGMA foreign_keys=ON` -- but this is fine because `init_db` only runs DDL (CREATE TABLE), and foreign key constraints are only enforced on DML (INSERT/UPDATE/DELETE), not on schema creation.

**Additional gotcha:** `PRAGMA foreign_keys=ON` is a no-op if executed inside an active transaction. It must be set before any transaction begins. Both patterns in the plan do this correctly (the pragma runs immediately after `connect()`, before any `BEGIN`).

### 5. Explicit `conn.commit()` on read operations

**Question:** When `immediate=False` (read operations), is the explicit `conn.commit()` a no-op, or could it cause issues?

**Answer:** It is a **harmless no-op**.

Under Python's legacy transaction control (the default), SQLite only implicitly opens a transaction when you execute DML statements (INSERT, UPDATE, DELETE). A SELECT query does not open a transaction, so there is no pending transaction to commit. Calling `conn.commit()` when no transaction is active does nothing.

The Python docs confirm: "If autocommit is True, or there is no open transaction, this method does nothing."

**Could it cause issues?** No. It is safe to always call `conn.commit()` in the `try` block. The alternative (checking whether a write occurred) would add complexity with no benefit.

### 6. `executescript()` and WAL pragma in `init_db`

**Question:** Does `executescript()` auto-commit? Could this interfere with WAL pragma?

**Answer:** Yes, `executescript()` issues an implicit COMMIT before running its SQL. The Python docs state: "If autocommit is LEGACY_TRANSACTION_CONTROL and there is a pending transaction, an implicit COMMIT statement is executed first."

**Does this interfere with the WAL pragma?** No, for two reasons:

1. `PRAGMA journal_mode=WAL` is executed via `conn.execute()` **before** `executescript()` is called. The pragma takes effect immediately -- it is not transactional and does not need to be committed. It modifies the database file header directly.

2. Even if there were an implicit COMMIT between the pragma and `executescript()`, the WAL mode is already persisted to the file at that point.

**The plan's `init_db` ordering is correct:**
```python
conn.execute("PRAGMA journal_mode=WAL")   # Takes effect immediately, persists
conn.executescript(schema)                 # Implicit COMMIT first (no-op), then runs DDL
```

**One subtlety:** `executescript()` also does NOT issue a final COMMIT after running. If the schema SQL does not end with a COMMIT, any final statements in a transaction will not be committed. However, DDL statements like CREATE TABLE in SQLite implicitly commit, so this is not a problem for schema scripts that only contain DDL.

### 7. Thread safety

**Question:** Flask's dev server is single-threaded, but with `check_same_thread=False` not set, is this safe?

**Answer:** Yes, the plan is safe.

**Why `check_same_thread` is not needed:**

- The `check_same_thread` parameter (default `True`) raises `ProgrammingError` if a connection created in one thread is used in another thread.
- The context-manager pattern creates a **new connection per call**, uses it, and closes it -- all within the same thread. The connection never crosses thread boundaries.
- The `g`-object pattern also creates one connection per request, and Flask ensures that each request is handled by a single thread. The `g` object is thread-local by design.

**Multi-threaded scenarios:**

- Flask's development server (`app.run()`) is single-threaded by default.
- With `app.run(threaded=True)` or a production WSGI server (gunicorn with threads), each request gets its own thread. As long as each thread creates its own connection (which both patterns do), there is no thread-safety issue.
- The only danger would be sharing a connection object across threads (e.g., a module-level global connection). Neither pattern does this.

**`check_same_thread=False` would only be needed** if you were creating a single connection and passing it to multiple threads -- which is an anti-pattern for web apps and not what this plan does.

---

## Recommended Plan Changes

- **Consider using the `g`-object pattern instead of the context-manager pattern** if routes need to call multiple model functions atomically. The existing `app/db.py` in the brewery app already uses this pattern and can serve as a template. If the plan's app only does one DB call per route, the context-manager pattern is fine as-is.

- **Remove `PRAGMA journal_mode=WAL` from `get_db()`** if any version of the code sets it per-connection (as the bookmark-manager currently does). WAL only needs to be set once in `init_db()`. Setting it per-connection is a wasted roundtrip. The plan as written already does this correctly (WAL only in `init_db`), so no change needed if the plan is followed as stated.

- **No other changes needed.** The remaining patterns (timeout=10, foreign_keys per-connection, explicit commit, executescript ordering, thread safety) are all correct as designed.
