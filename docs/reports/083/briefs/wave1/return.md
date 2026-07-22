# Worker Brief — WAVE 1 — return model agent (Run 083 swarmlimit)

You are a swarm worker rooted on a worktree that CONTAINS the converged spec at
`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md`. **READ THAT SPEC FIRST — it is
authoritative.** This brief points you at your file and sections; it does not restate the spec.

## Your assignment
You own EXACTLY ONE file: **`swarmlimit/models/return_models.py`** (owns the `process_return`
transaction — the 4-table atomic unit, the DENSEST cross-agent write in the spec).

Read "### return_models.py" in §Model Functions, plus the `returns` schema table, the Ownership-Scoped
Getter Contract, §1a (`return_models._TX_FAULT`), §1d entrypoints, §2 wiring (imports FOUR peer models:
product `restock_product_in_tx`, shipment `set_shipment_status_in_tx`, payment `refunded_total` +
`add_refund_in_tx`, order `order_total`, plus refs `assert_ext_ref_unique`), §5(B) + the fault seam.

## Exact function signatures (copy verbatim)
- `list_returns(order_id=None) -> list[dict]` (unscoped; admin callers).
- `list_returns_for(actor) -> list[dict]` — Ownership-Scoped Getter Contract (transitive via order).
- `get_return(rid) -> dict | None`
- `get_return_for(rid, actor) -> dict | None` — Ownership-Scoped Getter Contract.
- `process_return(order_id, ext_ref, reason, refund_cents) -> int` — **OWNS one `transaction()`
  internally (class-B).** Inside `with transaction() as conn:` (BEGIN IMMEDIATE):
  (1) `refs.assert_ext_ref_unique(conn, ext_ref)` → ValueError (route → 409);
  (2) select the order's UNIQUE shipment on `conn` (`UNIQUE(order_id)` ⇒ at most one); require it EXISTS
  and `status == 'delivered'`, else `ValueError('shipment not delivered')` (route → 409);
  (3) **refund guard:** `refunded_total(conn, order_id) + refund_cents <= order_total(conn, order_id)`,
  else `ValueError('refund exceeds original')` → rollback;
  (4) insert the return row;
  (5) `shipment_models.set_shipment_status_in_tx(conn, shipment_id, 'returned')`;
  (6) for each order_item of the order: `product_models.restock_product_in_tx(conn, product_id, qty)`;
  (7) `payment_models.add_refund_in_tx(conn, order_id, refund_cents)`.
  **`_TX_FAULT` checkpoint: invoke `if _TX_FAULT: _TX_FAULT()` immediately AFTER step (7)
  `add_refund_in_tx`** (the last write), before the block exits. Does NOT audit (route audits
  post-commit). Touches {returns, shipments.status, products.stock, payments} atomically.
- Module attr `_TX_FAULT: Callable[[], None] | None = None` (default `None`; smoke sets/resets).

**HIGHLIGHT:** ONE `transaction()`; the 4-table write threaded on a single `conn`; refund guard =
`refunded_total+refund <= order_total`; the `_TX_FAULT` checkpoint is AFTER `add_refund_in_tx`.

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
  `transaction()` manager owns that; your class-B `process_return` just uses `with transaction() as conn`).
- FC35 model-layer ownership scoping via SQL WHERE predicate (get_<x>_for returns None/[] for
  non-owner, never post-fetch 403).
- FC63 return-shape pinned (single-row getter→dict|None, lister→list[dict], creator→int id,
  mutator→None; convert `sqlite3.Row`→plain dict).
- stock guard = `UPDATE ... WHERE ... AND stock>=:qty` then require rowcount==1 (you CALL the product
  `restock_product_in_tx` helper; do not reimplement).

## NAMING PIN (avoids FC1 at the return→payment seam)
The payment in-tx helper is `add_refund_in_tx(conn, oid, amount_cents)` — third param name
**amount_cents** is authoritative; `refunded_total(conn, order_id)` is called positionally. Use the
§Model Functions / §1d signatures EXACTLY.

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
