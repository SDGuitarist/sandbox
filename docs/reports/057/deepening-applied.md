# Deepening Applied -- Run 057

## Agents Run
1. deepen-security (best-practices-researcher)
2. deepen-transactions (best-practices-researcher)
3. deepen-schema (best-practices-researcher)
4. deepen-derived-state (best-practices-researcher)

## Changes Applied

### P0 Fixes
1. **isolation_level=None** -- Added to `sqlite3.connect()` in `get_db()`.
   Without this, Python's implicit transaction management conflicts with
   explicit `BEGIN IMMEDIATE` calls, causing `OperationalError: cannot start
   a transaction within a transaction`. (Source: deepen-transactions)

2. **Circular FK removed** -- Removed `REFERENCES batches(id)` from
   `tanks.current_batch_id`. Circular FKs are unreliable in SQLite because
   CREATE TABLE order matters and executescript doesn't guarantee FK
   resolution. UNIQUE constraint kept. Relationship enforced in application
   code. (Source: deepen-schema)

3. **session.permanent = True** -- Added to session keys table. Without this
   flag set in the login route, `PERMANENT_SESSION_LIFETIME` is ignored and
   the session cookie expires when the browser closes. (Source: deepen-security)

### P1 Fixes
4. **Float clamping in create_sale** -- Changed `new_remaining = batch[...] -
   quantity_oz` to `max(0, batch[...] - quantity_oz)`. Prevents float
   precision leaving a tiny positive remainder that never triggers the
   empty-batch transition. (Source: deepen-derived-state)

5. **SESSION_COOKIE_SECURE** -- Added `app.config['SESSION_COOKIE_SECURE'] =
   not app.debug` to App Configuration. (Source: deepen-security)

### P2 Notes (not applied, deferred)
- CSRF error handler (`@csrf.error_handler`) -- low priority, bare 400 is
  acceptable for single-admin tool
- Brute-force `time.monotonic()` vs `time.time()` -- acceptable for
  single-admin, documented as intentionally in-memory
- `delete_batch` IntegrityError for sales RESTRICT -- route agents should
  catch IntegrityError on all delete operations per Coordinated Behaviors

## Derived State Verification
All cross-table writes are declared in Derived State section. The sale chain
(INSERT -> decrement -> check empty -> update status -> clear tap) is complete.
No undeclared cross-table writes found.

## No Conflicts
No deepening agents modified the same section. All changes are additive.
