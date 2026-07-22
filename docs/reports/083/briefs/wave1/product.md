# Worker Brief — WAVE 1 — product model agent (Run 083 swarmlimit)

You are a swarm worker rooted on a worktree that CONTAINS the converged spec at
`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md`. **READ THAT SPEC FIRST — it is
authoritative.** This brief points you at your file and sections; it does not restate the spec.

## Your assignment
You own EXACTLY ONE file: **`swarmlimit/models/product_models.py`**.

Read "### product_models.py (product model agent — soft-delete + stock guard + M2M + in-tx helpers)"
in §Model Functions, plus the `products` + `product_categories` schema tables, §1d Orchestration
Entrypoints (the two in-tx helpers), §2 wiring, §5(A)/(C).

## Exact function signatures (copy verbatim)
- `list_products(q=None, category_id=None, include_deleted=False) -> list[dict]` — **excludes
  `deleted_at IS NOT NULL` unless `include_deleted=True`.** `q` LIKE-matches name/sku; `category_id`
  joins `product_categories`.
- `get_product(pid, include_deleted=False) -> dict | None` — **returns `None` for a soft-deleted
  product unless `include_deleted=True`.** Includes `category_ids: list[int]`.
- `create_product(sku, name, supplier_id, price_cents, stock=0, category_ids=None) -> int` — validates
  supplier exists; raises `ValueError('sku exists')` on UNIQUE; attaches M2M rows. Class-A.
- `update_product(pid, **fields) -> None` — whitelist: name, price_cents, stock, supplier_id. Class-A.
- `soft_delete_product(pid) -> None` — sets `deleted_at = datetime('now')`; does NOT touch
  `order_items`; idempotent (already-deleted → no-op). Class-A.
- `set_product_categories(pid, category_ids) -> None` — replaces M2M rows. Class-A.
- `decrement_stock_in_tx(conn, pid, qty) -> None` — **in-tx helper, caller `conn`, NO commit.** Stock
  guard: `UPDATE products SET stock = stock - :qty WHERE id = :pid AND deleted_at IS NULL AND
  stock >= :qty`; require `cursor.rowcount == 1` else raise `ValueError('insufficient stock')` (also
  fires if soft-deleted → rowcount 0). Called ONLY by `order_models.create_order`.
- `restock_product_in_tx(conn, pid, qty) -> None` — **in-tx helper, caller `conn`, NO commit.**
  `UPDATE products SET stock = stock + :qty WHERE id = :pid` (restocks regardless of `deleted_at`).
  Called ONLY by `return_models.process_return`.

**HIGHLIGHT:** soft-delete filters (list/get exclude deleted unless `include_deleted=True`) + the stock
guard (rowcount==1 or raise) + the M2M attach/replace + the two class-C in-tx helpers (caller conn, NO
commit) are the load-bearing pieces of this file.

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

## Per-role pitfalls (model cluster)
- FC46 phantom-FK (every `*_id` has REFERENCES + ON DELETE per spec — read the schema table).
- FC29+FC6 (no `conn.commit()` in in-tx helpers; BEGIN IMMEDIATE needs try/except/ROLLBACK — but the
  `transaction()` manager owns that; a class-B fn just uses `with transaction() as conn`).
- FC35 model-layer ownership scoping via SQL WHERE predicate (get_<x>_for returns None/[] for
  non-owner, never post-fetch 403).
- FC63 return-shape pinned (single-row getter→dict|None, lister→list[dict], creator→int id,
  mutator→None; convert `sqlite3.Row`→plain dict).
- stock guard = `UPDATE ... WHERE ... AND stock>=:qty` then require rowcount==1 else raise
  `insufficient stock`.

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
