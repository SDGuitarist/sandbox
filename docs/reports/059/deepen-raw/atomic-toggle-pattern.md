# Deepen Research: Flask/SQLite Atomic Toggle Pattern

## Summary

The plan's INSERT OR IGNORE + rowcount toggle pattern is functionally correct for the happy path (UNIQUE constraint on `(habit_id, completed_date)`), but has a critical gap: INSERT OR IGNORE treats foreign key violations as ABORT, not IGNORE, meaning a toggle call with a nonexistent `habit_id` will raise an unhandled `sqlite3.IntegrityError` instead of failing silently. Switching to `INSERT INTO ... ON CONFLICT(habit_id, completed_date) DO NOTHING` is a strict improvement -- it targets only the intended UNIQUE constraint, still surfaces FK errors as exceptions, and makes the developer intent explicit. BEGIN IMMEDIATE correctly serializes concurrent toggles in Flask, but only if `busy_timeout` is set on every connection.

## Findings

### 1. Is INSERT OR IGNORE + rowcount a reliable idempotent toggle? Edge cases?

**Verdict: Reliable for the happy path, but masks unrelated constraint errors.**

- When INSERT OR IGNORE hits a UNIQUE constraint violation, SQLite skips the row silently. The Python `cursor.rowcount` property returns 0 for the ignored insert, which the plan uses to branch into the DELETE path. This is correct and well-documented behavior.
- However, INSERT OR IGNORE applies the IGNORE algorithm to **all** applicable constraints (UNIQUE, NOT NULL, CHECK), not just the one you care about. If a future schema change adds a CHECK constraint or a NOT NULL column to the `completions` table, INSERT OR IGNORE would silently swallow those violations too -- the toggle would appear to "un-complete" a habit when it actually failed to insert for an unrelated reason.
- The modern alternative is `INSERT INTO completions (habit_id, completed_date) VALUES (?, ?) ON CONFLICT(habit_id, completed_date) DO NOTHING`. This targets **only** the UNIQUE constraint on those two columns and lets all other constraint violations (NOT NULL, CHECK, FK) propagate as errors. This is semantically what the plan intends.
- Source: [SQLite ON CONFLICT Clause docs](https://sqlite.org/lang_conflict.html), [hoelz.ro blog on INSERT OR IGNORE pitfalls](https://hoelz.ro/blog/with-sqlite-insert-or-ignore-is-often-not-what-you-want).

### 2. Does BEGIN IMMEDIATE serialize concurrent toggles in Flask?

**Verdict: Yes, but requires `busy_timeout` configuration.**

- SQLite allows only one writer at a time, even in WAL mode. BEGIN IMMEDIATE acquires the write lock at transaction start (not deferred until the first write), which prevents the "upgrade deadlock" that can occur with plain BEGIN.
- When two Flask request threads call BEGIN IMMEDIATE simultaneously, one acquires the lock and the other blocks until the first commits. This is exactly the serialization the toggle pattern needs -- two concurrent toggles on the same `(habit_id, date)` will execute sequentially, producing the correct final state.
- **Critical prerequisite:** the connection must have `busy_timeout` set (e.g., `conn.execute("PRAGMA busy_timeout = 5000")`). Without it, the second writer gets an immediate `SQLITE_BUSY` / "database is locked" error instead of waiting. Flask's default sqlite3 connections have no busy_timeout.
- WAL mode is strongly recommended for Flask apps (`PRAGMA journal_mode=WAL`). It allows concurrent reads while a write transaction is active. Without WAL (default rollback journal), readers are also blocked during writes.
- `PRAGMA foreign_keys = 1` and `PRAGMA busy_timeout` must be set **per connection** -- they do not persist across connections. If using raw sqlite3, set them in a connection factory function.
- Source: [Ten Thousand Meters: SQLite concurrent writes](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/), [SQLite WAL docs](https://sqlite.org/wal.html), [SQLite PRAGMA docs](https://sqlite.org/pragma.html).

### 3. Alternative atomic toggle patterns

**Three alternatives exist; the plan's two-statement approach is the best fit.**

**a) ON CONFLICT DO NOTHING (recommended refinement, not a structural change):**
```python
cursor = conn.execute(
    "INSERT INTO completions (habit_id, completed_date) VALUES (?, ?) "
    "ON CONFLICT(habit_id, completed_date) DO NOTHING",
    (habit_id, target_date)
)
if cursor.rowcount > 0:
    return True
conn.execute(
    "DELETE FROM completions WHERE habit_id = ? AND completed_date = ?",
    (habit_id, target_date)
)
return False
```
Same logic, but targets the specific UNIQUE constraint. Requires SQLite 3.24.0+ (released June 2018; Python 3.7+ ships with 3.21+, Python 3.8+ ships with 3.24+).

**b) Single-statement CTE approach (not recommended):**
SQLite supports CTEs prefixed to DELETE/INSERT statements, so in theory you could write a single statement that conditionally deletes or inserts. In practice, SQLite does not support conditional branching (IF/ELSE) inside a single statement, so you would need two CTEs chained together. This is fragile, hard to read, and provides no atomicity advantage over two statements inside BEGIN IMMEDIATE.

**c) DELETE first, then INSERT (not recommended):**
```python
deleted = conn.execute("DELETE FROM completions WHERE habit_id = ? AND completed_date = ?", (habit_id, target_date))
if deleted.rowcount == 0:
    conn.execute("INSERT INTO completions (habit_id, completed_date) VALUES (?, ?)", (habit_id, target_date))
    return True
return False
```
This works but is slightly worse: the DELETE always runs (even on the "create" path), and there is no way to distinguish "row didn't exist" from "DELETE failed for another reason."

**d) INSERT OR REPLACE with a soft-delete column (overkill for this use case):**
Add an `is_active` boolean and use `INSERT OR REPLACE` to toggle it. This adds schema complexity for no benefit in a simple toggle scenario.

**The plan's two-statement approach (INSERT then DELETE) is the right pattern.** The only change is swapping INSERT OR IGNORE for ON CONFLICT DO NOTHING.

### 4. What happens if `habit_id` FK doesn't exist?

**INSERT OR IGNORE does NOT swallow FK violations -- it raises an error.**

This is the most important finding. From the SQLite docs:

> "The IGNORE conflict resolution algorithm [...] works like ABORT for foreign key constraint errors."

Concretely: if `PRAGMA foreign_keys = ON` and the caller passes a `habit_id` that doesn't exist in the `habits` table, `INSERT OR IGNORE` will raise `sqlite3.IntegrityError: FOREIGN KEY constraint failed`. The IGNORE algorithm only suppresses UNIQUE, NOT NULL, and CHECK violations -- not FK violations.

This is actually **desirable behavior** -- you want to know if a client sends an invalid habit_id rather than silently ignoring it. But the plan should document this explicitly and ensure the Flask route has error handling for it (e.g., return 404).

Switching to `ON CONFLICT(habit_id, completed_date) DO NOTHING` preserves this behavior: FK violations still raise errors because they don't match the specified conflict target.

**Important:** `PRAGMA foreign_keys` must be enabled per connection. SQLite defaults to OFF. If the app doesn't set it, FK constraints are silently unenforced and the INSERT will succeed even with a nonexistent habit_id, creating orphan rows.

Source: [SQLite ON CONFLICT Clause](https://sqlite.org/lang_conflict.html), [SQLite mailing list discussion](https://sqlite-users.sqlite.narkive.com/0iPHB4mV/sqlite-insert-or-ignore-with-foreign-keys).

### 5. SQLite version-specific behavior

- **UPSERT / ON CONFLICT DO NOTHING** requires SQLite 3.24.0+ (2018-06-04). Python 3.8+ bundles SQLite 3.24+. Python 3.7 bundles 3.21 which does NOT support UPSERT. If the plan targets Python 3.8+, this is safe.
- **`cursor.rowcount` for INSERT OR IGNORE:** The underlying C API function `sqlite3_changes()` returns 0 when a row is ignored. This behavior is stable and documented across all modern SQLite versions.
- **WAL mode** has been stable since SQLite 3.7.0 (2010). No version concerns.
- **BEGIN IMMEDIATE** has been available since SQLite 3.0.0. No version concerns.
- **PRAGMA foreign_keys** requires SQLite 3.6.19+ (2009). No version concerns, but it must be compiled with `SQLITE_OMIT_FOREIGN_KEY` not defined (default in all standard builds including Python's bundled SQLite).

Source: [SQLite UPSERT docs](https://sqlite.org/lang_upsert.html), [SQLite release history](https://sqlite.org/changes.html).

## Recommended Plan Changes

- **Switch INSERT OR IGNORE to ON CONFLICT DO NOTHING.** Replace `INSERT OR IGNORE INTO completions (habit_id, completed_date) VALUES (?, ?)` with `INSERT INTO completions (habit_id, completed_date) VALUES (?, ?) ON CONFLICT(habit_id, completed_date) DO NOTHING`. This targets only the UNIQUE constraint and won't silently swallow future NOT NULL or CHECK violations.
- **Add PRAGMA configuration to connection setup.** The plan should prescribe setting three PRAGMAs on every new connection: `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`, and `PRAGMA busy_timeout = 5000` (or similar). These are per-connection and must be set in the connection factory, not just once at app startup.
- **Add FK error handling in the Flask route.** The toggle endpoint should catch `sqlite3.IntegrityError` for FK violations and return HTTP 404 (habit not found) rather than letting it bubble up as a 500.
- **Document the minimum Python/SQLite version.** ON CONFLICT DO NOTHING requires SQLite 3.24.0+. If the plan doesn't already specify Python >= 3.8, it should, since Python 3.7 ships with SQLite 3.21 which lacks UPSERT support.
- **No structural changes needed.** The two-statement toggle pattern (INSERT then conditional DELETE) inside BEGIN IMMEDIATE is correct and is the best approach for this use case. The changes above are refinements, not redesigns.
