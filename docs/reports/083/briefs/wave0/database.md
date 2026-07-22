# Worker Brief — WAVE 0 — database agent (Run 083 swarmlimit)

You are a swarm worker rooted on a worktree that CONTAINS the converged spec at
`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md`. **READ THAT SPEC FIRST — it is
authoritative.** This brief points you at your files and sections; it does not restate the spec.

## Your assignment
You own EXACTLY TWO files: **`swarmlimit/database.py`** and **`swarmlimit/schema.sql`**.

Read the spec sections that govern your files:
- "Database Schema (swarmlimit/schema.sql — database agent owns this file)" — the EXACT DDL + seed.
- "Database Connection (swarmlimit/database.py — database agent owns this file)".
- §1a Infrastructure exports (`get_db`, `query`, `transaction`, `init_db` — exact signatures).
- §5 Transaction Contracts (autocommit semantics; the `transaction()` context manager contract).

## schema.sql must contain
The EXACT DDL from the spec (users, suppliers, categories, products, product_categories, orders,
order_items, shipments, returns, payments, audit_logs) — every column, type, CHECK, UNIQUE, and
`REFERENCES ... ON DELETE ...` edge EXACTLY as written. Plus the SEED rows (1 admin
`admin@swarm.test`/`swarmpass`, 2 customers; 2 suppliers; 3 categories; 4 products each with supplier +
≥1 category, stock ≥ 5, deleted_at NULL; 1 order for customer-1 with 2 order_items; NO
shipments/returns/payments). Every seeded row must satisfy all NOT NULL / CHECK / UNIQUE constraints.
Money is integer cents. Timestamps are ISO-8601 TEXT (UTC) via `datetime('now')`.

## database.py must contain (exact per spec)
- `get_db() -> sqlite3.Connection` — one connection per request via Flask `g`; opened with
  **`isolation_level=None`** (AUTOCOMMIT); `row_factory = sqlite3.Row`; sets the THREE per-connection
  pragmas `PRAGMA foreign_keys = ON;`, `PRAGMA journal_mode = WAL;`, `PRAGMA busy_timeout = 5000;`.
  Registered teardown closes it.
- `init_db() -> None` — executes `schema.sql`, inserts seed rows. Idempotent guard is handled by the
  scaffold (calls init_db only when the DB file is absent); your DDL is `CREATE TABLE` run once.
- `query(sql, params=(), one=False) -> list[dict] | dict | None` — returns plain dicts (never leak
  `sqlite3.Row` across a boundary). `one=True` → single dict or None; else list of dicts.
- `transaction()` context manager — wraps the single `get_db()` request connection with an explicit
  **`BEGIN IMMEDIATE`**; on clean exit `COMMIT`; on ANY exception `ROLLBACK` then re-raise
  (`try/except/ROLLBACK/raise`). Same connection every model function uses. **Nested `transaction()`
  is forbidden.** Because the connection is `isolation_level=None` AUTOCOMMIT, the explicit
  `BEGIN IMMEDIATE` is the ONLY transaction boundary.
- Class-A writers rely on autocommit: a single INSERT/UPDATE/DELETE on the request connection persists
  immediately — no `conn.commit()`, no `transaction()`. Only the two class-B units open `transaction()`.

```
## Known Pitfalls (from prior builds — MUST follow)
- FC1 (naming): Use EXACT names from the spec §1 Export Names Table / §1d Orchestration Entrypoints. Never invent a name crossing a file boundary.
- FC2 (wrong usage): Match the spec RETURN TYPE. int return → name var <x>_id; transaction() → always `with`; INTEGER → ints not strings.
- FC3 (dead wiring): Every export you create must have a consumer in §2 Cross-Boundary Wiring; don't leave a prescribed call unwired.
- FC4 (validation gap): Validate ALL inputs in YOUR handler for EVERY method per §3 — never assume another layer validates.
- FC5 (swarm consistency): Match cross-cutting patterns EXACTLY (error(...) envelope, response objects, audit record(...) signature) per §4.
- FC6 (non-transactional): Class-B units use the ONE transaction(); class-C in-tx helpers take caller conn and NEVER commit; class-A autocommit (no conn.commit(), no transaction()).
- FC7 (route paths): NO url_prefix on any blueprint; every @bp.route declares the FULL absolute path EXACTLY = the manifest (no trailing slash on collections).
- FC8 (bash): One command per Bash call. No &&/;/cd/loops/echo >/python3 -c. Use git -C and the Write tool.
- FC9 (mock/data): Read EXACT field/param names from the spec; never guess.
- FC10 (fail-closed): guards fail CLOSED on error; every route except returns an error status; never fall through without a return.

## Bash rules (MANDATORY)
One command per Bash call. (1) no `cd x && y` — use `git -C`; (2) no `source venv/activate` — full path; (3) no for-loops; (4) no `python3 -c` — Write a file; (5) no `echo` for content — Write tool; (6) no `&&`/`;` chaining.
```

## Per-role pitfalls (database)
- database: column types MUST match what model agents write; PRAGMA per-connection not per-db (FC40);
  NEVER `executescript()` inside a with-conn block, use `conn.execute` (FC14); idempotent DDL (FC16);
  `row['col']` not `str(row)`.

## Strict rules
1. Create ONLY your assigned file(s). No other files. (smoke-author also writes its two docs/reports/083 artifacts.)
2. Use EXACT names from the spec for all functions, routes, classes, variables.
3. Do not make design decisions — the spec at docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md decides everything. READ IT FIRST.
4. Do not import from other agents' files except as §2 Cross-Boundary Wiring defines.
5. Follow the spec's directory structure exactly (swarmlimit/ namespace).
6. If the spec is ambiguous, pick the simplest interpretation.
7. No TODOs, no placeholders — production-quality code.
8. Create any directories your files need.
9. When done, commit ALL your files with a descriptive message (one Bash call: git -C <worktree> add -A ; then a separate git -C <worktree> commit -m "...").
