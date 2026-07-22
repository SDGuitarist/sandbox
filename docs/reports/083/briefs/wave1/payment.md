# Worker Brief — WAVE 1 — payment model agent (Run 083 swarmlimit)

You are a swarm worker rooted on a worktree that CONTAINS the converged spec at
`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md`. **READ THAT SPEC FIRST — it is
authoritative.** This brief points you at your file and sections; it does not restate the spec.

## Your assignment
You own EXACTLY ONE file: **`swarmlimit/models/payment_models.py`** (refund ledger).

Read "### payment_models.py (payment model agent — refund ledger)" in §Model Functions plus the
"Original payment" definition pin, the `payments` schema table, the Ownership-Scoped Getter Contract,
§1d entrypoints, §2 wiring (consumed by `return_models.process_return`), §5(A)/(C), and the §5 refund
invariants.

## Exact function signatures (copy verbatim)
- `list_payments(order_id=None) -> list[dict]` (unscoped; admin callers).
- `list_payments_for(actor) -> list[dict]` — Ownership-Scoped Getter Contract (transitive via order).
- `get_payment(pid) -> dict | None`
- `get_payment_for(pid, actor) -> dict | None` — Ownership-Scoped Getter Contract.
- `refunded_total(conn, order_id) -> int` — `SUM(amount_cents) WHERE kind='refund'` for the order, on a
  caller `conn` (class-C read-only; used in-tx by `process_return`'s refund guard). NO commit.
- `add_refund_in_tx(conn, order_id, amount_cents) -> int` — **in-tx helper, caller `conn`, NO commit.**
  Inserts a `kind='refund'` payment row with `amount_cents = amount_cents` (always `> 0`; the
  `payments.amount_cents > 0` CHECK is a backstop). Returns the new payment id (int). Called ONLY by
  `process_return`.

**HIGHLIGHT:** `refunded_total(conn, order_id)` + `add_refund_in_tx(conn, order_id, amount_cents)` are
class-C in-tx helpers (caller conn, NO commit). Payments is a REFUND-ONLY ledger (schema CHECK
`kind IN ('refund')`); create_order writes NO payments row; the order's "original amount" is
`order_total` (SUM of order_items), NOT a payments row.

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
- stock guard = `UPDATE ... WHERE ... AND stock>=:qty` then require rowcount==1 (cluster rule; applies
  to product).

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
