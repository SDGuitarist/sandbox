# Run 083 Review Summary

**Date:** 2026-07-22
**Branch:** feat/082-swarmlimit-spec
**Feed-Forward Risk Scrutinized:** process_return 4-table atomic write + create_order + ext_ref cross-resource uniqueness

## Review Agents

- security-sentinel (spawned, background)
- flow-trace-reviewer (spawned, background)
- learnings-researcher (spawned, background)
- Manual code review (tail-runner direct analysis)

## P1 Findings

None identified. The feed-forward risk areas (process_return, create_order, ext_ref uniqueness) are correctly implemented:

- `process_return` owns exactly ONE `transaction()` context; all four in-tx helpers receive the same `conn` and NEVER commit independently.
- `assert_ext_ref_unique` runs under the caller's BEGIN IMMEDIATE lock, serializing concurrent writers — no TOCTOU window.
- `create_order` snapshots `unit_price_cents` at insert time, not at validation time — correct.
- Auth decorators implement the correct two-branch contract (None→401, wrong-role→403), preventing null-actor crashes.
- All ownership-scoped getters use SQL WHERE predicates, not post-fetch Python comparison — no IDOR.
- CSRF exemption on login/register is correct (no session established yet); authenticated mutations require X-CSRF-Token.
- SECRET_KEY is fail-closed for non-development environments.
- `close_db` is correctly registered via `teardown_appcontext` (H3 assembly fix applied).
- `init_db` wrapped in app context (H6 assembly fix applied).

## P2 Findings

### P2-01: `restock_product_in_tx` does not validate product existence

**File:** `swarmlimit/models/product_models.py:204-215`
**Issue:** If `pid` doesn't exist, the UPDATE silently affects 0 rows with no error raised. In `process_return`, items come from `order_items WHERE order_id = ?` so they should be valid — but the gap means a corrupt DB or a mis-built item record could silently skip restocking without failing the transaction.
**Risk:** LOW — protected by the `get_order_for` pre-check and `order_items` FK constraint. However the silent 0-rowcount could mask a data inconsistency.
**Recommendation:** Add `if cur.rowcount == 0: raise ValueError("product not found for restock")` or at minimum log a warning.
**Decision:** DEFERRED — throwaway vehicle; FK constraint makes the scenario impossible in normal operation.

### P2-02: `advance_shipment` TOCTOU on class-A read-then-update

**File:** `swarmlimit/models/shipment_models.py:117-148`
**Issue:** `advance_shipment` reads the current status, checks `LEGAL_TRANSITIONS`, then issues a separate UPDATE — not inside a `transaction()`. Two concurrent callers both reading `status='shipped'` could both attempt `-> delivered`, and both would succeed (the second just re-updating to delivered). This is mostly harmless but means the state machine isn't strictly enforced under concurrent load.
**Risk:** LOW — SQLite WAL + busy_timeout=5000ms serializes writes; practical concurrent mutation is unlikely on this throwaway service.
**Decision:** DEFERRED — acceptable for SQLite throwaway; would need a transaction guard in a real production service.

### P2-03: H8 DELETE-success envelope divergence is benign for C2 but a real client contract gap

**Source:** harvest-findings H8
**File:** `swarmlimit/routes/suppliers.py`, `routes/categories.py`, `routes/products.py`
**Issue:** DELETE bodies diverge: categories→`{"ok":true}`, suppliers→`{"deleted":sid}`, products→`{"product":{"id":pid}}`. C2 passes because smoke asserts status only, not body. A real client consuming all three would need to handle 3 different shapes.
**Decision:** DEFERRED — documented in harvest. Pin every response branch in future specs.

## No Findings (checked and cleared)

- Transaction commit discipline: all in-tx helpers verified NOT calling `conn.commit()`
- ext_ref uniqueness: correct cross-table SELECT under BEGIN IMMEDIATE (serializes concurrent inserts)
- Role escalation via register: ALWAYS forces `role='customer'` — confirmed in route
- IDOR in GET /orders/<oid>: uses `get_order_for` with SQL predicate — correct
- IDOR in GET /shipments/<sid>: uses `get_shipment_for` with SQL predicate — correct
- IDOR in GET /returns/<rid>: uses `get_return_for` with SQL predicate — correct
- IDOR in GET /payments/<pid>: uses `get_payment_for` with SQL predicate — correct
- Audit recorded POST-commit (never inside transaction): verified in all three mutating routes checked
- `_TX_FAULT` injection seam: correctly `None` in production (no-op), set only by smoke
- Session cookie hardening: HTTPONLY=True, SAMESITE=Lax, SECURE=not is_development — correct
- CSP header: `default-src 'none'` on every response — correct for pure JSON API
- Password hashing: werkzeug `generate_password_hash` / `check_password_hash` — correct

## Feed-Forward Risk Resolution

The feed-forward risk ("process_return is a 4-table atomic write reaching into 3 other agents' tables via in-tx helpers") was CORRECTLY IMPLEMENTED. The 4-table chain:
1. `refs.assert_ext_ref_unique(conn, ext_ref)` — read-only under caller's tx ✓
2. Shipment lookup + status check — read under caller's tx ✓
3. `order_models.order_total(conn, order_id)` — read-only under caller's tx ✓
4. `payment_models.refunded_total(conn, order_id)` — read-only under caller's tx ✓
5. INSERT returns row — under caller's tx ✓
6. `shipment_models.set_shipment_status_in_tx(conn, sid, 'returned')` — no commit ✓
7. `product_models.restock_product_in_tx(conn, pid, qty)` — no commit ✓
8. `payment_models.add_refund_in_tx(conn, order_id, refund_cents)` — no commit ✓
9. `_TX_FAULT` checkpoint — post-commit seam ✓
All writes committed exactly ONCE via the `transaction()` context manager. PASS.

## Summary

| Severity | Count | Notes |
|----------|-------|-------|
| P1 | 0 | No critical findings |
| P2 | 3 | All deferred (throwaway vehicle) |
| P3 | 0 | — |

**Fix commits:** None required (0 P1 findings).
**Overall verdict:** The swarmlimit codebase is correct relative to the spec. The feed-forward risk seam held. The harvest findings (H1-H9) were pre-identified by the orchestrator; review confirms they are real and correctly categorized.
