STATUS: PASS

# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md
**Checked:** 2026-07-22
**Checker:** spec-consistency-checker agent (gates-consistency gate, pre-swarm)

---

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Schema vs Route | Schema field names (snake_case throughout) | Route params (`<int:oid>`, `<int:sid>`, `<int:pid>`, `<int:cid>`, `<int:rid>`) | PASS | All URL params use `<int:x>` converter; model function params use full names (`order_id`, `pid`, etc.); no naming mismatch between schema column names and route params |
| 2 | SQL Types vs App-Layer | SQL `INTEGER` for all ids, `TEXT` for email/role/status/timestamps, `INTEGER` cents | §Model Functions return types: `int` id, `str` email, `dict` rows, `list[dict]` listers | PASS | All SQL types match their app-layer representations. Money is integer cents in both schema and model layer. Timestamps are TEXT (ISO-8601). |
| 3 | Route Table vs §6 Auth Matrix | Route Table: 31 routes (auth×3, suppliers×5, categories×5, products×6, orders×3, shipments×3, returns×3, payments×2, audit×1) | §6 Auth Matrix: covers all 31 with matching auth modes | PASS | Every route in the Route Table appears in §6 with the same auth mode. No route missing from either section. |
| 4 | Route Table vs §3 Input Validation | Route Table mutating routes: POST/PATCH/DELETE/PUT entries (17 mutating + GET typed-params global) | §3 Input Validation rows | PASS | All mutating routes have §3 rows. PATCH /categories/<int:cid> added in Round-2 fix is present. GET routes excluded per §3 scope. No gaps. |
| 5 | Route Table vs Manifest (31-endpoint set) | Route Table endpoints (counted): 31 | Manifest `endpoints[]` array: 31 | PASS | Exact set equality verified: Auth(3)+Suppliers(5)+Categories(5)+Products(6)+Orders(3)+Shipments(3)+Returns(3)+Payments(2)+Audit(1)=31 in Route Table; manifest JSON lists 31 identical (method, path) pairs in `<int:...>` form. |
| 6 | 10 Path-B `--case`s vs EARS bijection | EARS Path-B entries: 10 (4 happy + 6 error) | 10-case table: state-machine-legal, state-machine-illegal, uniqueness-ok, uniqueness-collision, soft-delete, soft-delete-order, process-return, process-return-rollback, process-return-guard-refund, process-return-guard-shipment | PASS | Each EARS Path-B entry maps 1:1 to a `--case` name. No EARS entry without a case; no case without an EARS entry. |
| 7 | §5 Class-A list vs Model Functions | §5(A) names: create_user, create_supplier, update_supplier, delete_supplier, create_category, update_category, delete_category, create_product, update_product, soft_delete_product, set_product_categories, create_shipment, advance_shipment, record | Model Functions: each of these says "persists immediately via SQLite autocommit; does not call conn.commit()" | PASS | All 14 class-A writers listed in §5(A) match the "no conn.commit(), no transaction()" annotation in their Model-Functions definition. |
| 8 | §5 Class-B pair vs Model Functions | §5(B): exactly create_order, process_return | Model Functions: only these two say "OWNS one transaction() internally" | PASS | Exactly two class-B owners. No other model function opens transaction(). |
| 9 | §5 Class-C (7 in-tx helpers) vs §1d/§4/Model Functions | §5(C): 4 writers (decrement_stock_in_tx, restock_product_in_tx, set_shipment_status_in_tx, add_refund_in_tx) + 1 uniqueness guard (assert_ext_ref_unique) + 2 readers (order_total, refunded_total) | §1d orchestration entrypoints: 7 rows, all "caller conn, no commit" | PASS | All 7 in-tx helpers have consistent `conn` arg, no-commit, and class-C classification across §Model Functions, §1d, §4, and §5(C). |
| 10 | FK on-delete DDL vs FK-policy prose | DDL: RESTRICT on supplier_id, category_id (via product_categories), user_id (orders), product_id (order_items), order_id (returns), order_id (payments); CASCADE on product_id (product_categories.product_id), order_id (order_items), order_id (shipments); SET NULL on actor_id (audit_logs) | FK-policy prose (line 239-244): names each FK and its policy | PASS | All 10 FK edges match between DDL ON DELETE token and prose description. audit_logs.entity_id is explicitly FC46-exempt (polymorphic, no REFERENCES). |
| 11 | `*_id` INTEGER columns REFERENCES check (FC46) | All INTEGER `*_id` columns in schema: supplier_id, category_id (two tables), order_id (three tables), product_id (two tables), user_id, actor_id, entity_id | REFERENCES present or FC46-exempt | PASS | Every `*_id` column has a REFERENCES clause except `audit_logs.entity_id` which is explicitly labeled "INTENTIONALLY no REFERENCES (not an FK; FC46 exempt)" in the DDL comment. |
| 12 | Export Names vs Import References | §1b consumer column for `list_shipments, get_shipment` → "routes/shipments.py"; `list_orders, get_order` → "routes/orders.py"; `list_returns, get_return` → "routes/returns.py"; `list_payments, get_payment` → "routes/payments.py" | Route Table: no `GET /shipments` list route; `GET /orders` calls `list_orders_for`; `GET /orders/<int:oid>` calls `get_order_for`; similarly for returns and payments | WARN | The unscoped admin variants (`list_shipments`, `get_shipment`, `list_orders`, `get_order`, `list_returns`, `get_return`, `list_payments`, `get_payment`) are declared in Model Functions and listed in §1b as consumed by their respective route files, but no Route Table entry actually calls them (all routes use the `*_for(actor)` ownership-scoped variants). A route-agent worker reading §1b might believe it needs to wire in a `GET /shipments` or `GET /orders` (unscoped-admin) endpoint, conflicting with the Route Table and manifest. However, the Route Table is authoritative and these functions can exist as dead code. Risk: a worker inventing a route not in the manifest would trigger a manifest-equality C2 failure, not a silent break. |
| 13 | `add_refund_in_tx` parameter names — §Model Functions vs §1b vs §1d vs §5 call | Model Functions: `add_refund_in_tx(conn, order_id, amount_cents) -> int`; §1b: `add_refund_in_tx(conn, oid, amount)`; §1d: `add_refund_in_tx(conn, oid, amount_cents) -> int`; §5 call: `add_refund_in_tx(conn, oid, refund_cents)` | Four occurrences use three different names for param 2 (`order_id`/`oid`) and three different names for param 3 (`amount_cents`/`amount`/`refund_cents`) | WARN | Parameters are positional-only in Python; a worker calling with the wrong name keyword-style can't happen since no caller passes them as kwargs (in-tx helpers are always called positionally). Runtime-safe. However, a model-agent writing `payment_models.py` might name the parameter `amount` (from §1b) instead of `amount_cents` (from Model Functions and §1d). This is a documentation inconsistency, not a runtime contradiction, since both §1d and Model Functions agree on `amount_cents` for the definition. Not a cross-section contradiction that breaks execution, but a worker could be confused about which name is authoritative. |
| 14 | `refunded_total` parameter name — §Model Functions vs §1b/§1d | Model Functions: `refunded_total(conn, order_id) -> int`; §1b: `refunded_total(conn, oid)`; §1d: `refunded_total(conn, oid)` | Two occurrences say `oid`; one says `order_id` | WARN | Same category as #13. Positional-only; the "original payment" pin note at line 469 also uses `refunded_total(conn,order_id)` (consistent with Model Functions). §1b/§1d use `oid`. Documentation inconsistency, not a runtime contradiction. |
| 15 | Shipment state-machine reachability | `LEGAL_TRANSITIONS = {('pending','shipped'), ('shipped','delivered')}`; `→returned` absent; §3 allows `returned` as valid `to_status` input (syntactically) | `advance_shipment` checks against LEGAL_TRANSITIONS → any `(x,'returned')` not in set → 409; `set_shipment_status_in_tx` called ONLY by `process_return` | PASS | The `→returned` transition is unreachable via `advance_shipment` (no pair in LEGAL_TRANSITIONS ends in `returned`); reachable ONLY via `process_return`. §3 correctly accepts `returned` as syntactically valid input (so it reaches the 409 path, proving the guard fires). Consistent across §Model Functions, §3, §5, EARS case `state-machine-illegal`, and §5 state-machine invariant. |
| 16 | ext_ref cross-resource uniqueness — single owner + per-table backstops | `refs.assert_ext_ref_unique(conn, ext_ref)` is the SINGLE authority; called inside BOTH class-B transactions within BEGIN IMMEDIATE | Per-table: `orders.ext_ref UNIQUE` and `returns.ext_ref UNIQUE` are explicitly labeled "intra-table backstop" | PASS | The two-layer design (cross-resource guard inside serialized BEGIN IMMEDIATE + per-table intra-table backstop) is consistent and non-contradictory. BEGIN IMMEDIATE serializes concurrent inserters. No conflict between the guard and the backstops. |
| 17 | ON DELETE behavior vs delete function docstrings / route error handling | `delete_supplier`: products.supplier_id ON DELETE RESTRICT → raises IntegrityError → ValueError('supplier in use') → route 409 `conflict`. `delete_category`: product_categories.category_id ON DELETE RESTRICT → ValueError('category in use') → 409. `delete_product`: soft-delete only (no hard delete), so FK RESTRICT on order_items.product_id never fires at runtime (soft-delete sets deleted_at, doesn't DELETE the row). delete_order: no route. delete_user: no route. | §3 delete rows and Model-Functions docstrings for delete_supplier, delete_category, soft_delete_product | PASS | Every RESTRICT FK that could fire during a route-triggered delete is correctly mapped to a ValueError + 409 response. Soft-delete on products means the RESTRICT on order_items.product_id is a schema backstop only (never fires at runtime — confirmed by docstring "does NOT touch order_items"). No missing or incorrect IntegrityError catch. |
| 18 | `create_order` tx tables vs §5 + manifest | §5(B) create_order: "Touches {orders, order_items, products.stock}"; manifest `transactions[0].tables`: ["orders","order_items","products.stock"] | Model Functions create_order prose: "No order, no partial items, no stock change" | PASS | All three sources agree: create_order's atomic unit covers exactly {orders, order_items, products.stock}. No audit_logs in the tx (post-commit route-level audit is separate and consistent with §4). |
| 19 | `process_return` tx tables vs §5 + manifest | §5(B) process_return: "Touches {returns, shipments.status, products.stock, payments}"; manifest `transactions[1].tables`: ["returns","shipments.status","products.stock","payments"] | Model Functions process_return: "all four writes" | PASS | All three sources agree on the four-table atomic unit. |
| 20 | `_TX_FAULT` checkpoint placement vs EARS proof claims | §5 / §1a: `create_order` invokes `_TX_FAULT` AFTER the first order_item insert + stock decrement; `process_return` invokes it AFTER `add_refund_in_tx` (last write) | EARS: create_order rollback proves "after first item write but before commit"; process-return-rollback proves "after add_refund_in_tx but before commit" | PASS | Checkpoint placements match exactly between §5/§1a and the EARS descriptions. The rollback cases prove real mid-tx rollback (not pre-write guard failures). Consistent. |
| 21 | `POST /auth/register` privilege pin — create_user role param | §3: "route calls create_user(email=email, password=password, role='customer', name=name)" (F1 fix from 2nd-final Codex pass); Route Table note: "register ALWAYS creates a customer — supplied role ignored/overridden"; §6: "register ALWAYS creates a customer (supplied role ignored)"; auth_models.py create_user: "raises ValueError('email exists') on UNIQUE" with `role` parameter for trusted seed | PASS | Consistent across §3, Route Table note, §6, §Model Functions, and EARS `register-role-ignored` case. The hard-coded `role='customer'` in the register view and the trusted `role` param for seed/internal use are separated correctly. |
| 22 | CSRF/auth precedence — 401 before 400 | App Configuration: "Auth precedes CSRF (pinned)"; §4: "401 (anon) precedes 400 (authed bad-CSRF) precedes 403 (authed wrong-role)"; §6: "Anonymous → 401 auth — even a mutating one; authenticated authed bad-CSRF → 400; wrong role → 403"; EARS anon-401 + CSRF-400 cases | PASS | All five sections agree: anonymous mutating request → 401 (falls through CSRF before_request since no session['_csrf'] exists); authenticated + bad CSRF → 400; authenticated wrong-role → 403. No heuristic needed. |
| 23 | `--manifest` invocation vs plain run — `<R>` report dir and manifest-equality scope | Verification Commands: "--manifest invocation writes <R>/c2-smoke-report.md and runs manifest-equality; plain no-arg run does NOT discover <R>, write the report, or run manifest-equality" | §1a smoke.py `if __name__ == '__main__'` argparse contract; EARS Verification header; 10-case table note | PASS | All references to C2 report writing are gated on `--manifest <R>/planned-manifest.json`. The plain run executes the suite and prints/returns result only. No conflict. |
| 24 | `role_required` two-branch contract vs anonymous-401 guarantee | §auth.py: `role_required` returns 401 for None/anonymous actor, 403 only for authenticated wrong-role; §4 Auth-failure-codes: same; §6 404-not-403 note: same; Ownership-Scoped Getter Contract: "getter never sees a None actor" | PASS | The pinned two-branch contract is consistent across all four sections that reference it. The 401-before-403 outcome is guaranteed at the decorator layer without stacking order dependence. |

---

## ON DELETE FK Analysis (per Check #17)

Parent tables with delete routes:

**suppliers** → `delete_supplier` → hard DELETE:
- product_categories is NOT a child of suppliers
- products.supplier_id → ON DELETE RESTRICT → IntegrityError → ValueError('supplier in use') → 409
- Route catches: YES (409 `conflict` if in use) — CORRECT

**categories** → `delete_category` → hard DELETE:
- product_categories.category_id → ON DELETE RESTRICT → IntegrityError → ValueError('category in use') → 409
- Route catches: YES (409 `conflict` if referenced) — CORRECT

**products** → `soft_delete_product` → sets deleted_at, does NOT issue DELETE:
- No FK RESTRICT fires (row not deleted) — catch unnecessary and absent — CORRECT

**orders** → no delete route — N/A

**users** → no delete route — N/A

All FK behaviors correctly represented.

---

## Summary

- **Total checks:** 24
- **PASS:** 21
- **FAIL:** 0
- **WARN:** 3 (items #12, #13, #14)
- **N/A (section absent):** 0

### WARN Disposition

**WARN #12 — Unscoped model functions listed in §1b with route-file consumers but no corresponding route:**
`list_shipments`, `get_shipment`, `list_orders`, `get_order`, `list_returns`, `get_return`, `list_payments`, `get_payment` are each listed in §1b as consumed by their resource route file. The Route Table only exposes the `*_for(actor)` ownership-scoped variants. Risk is that a route-agent worker reads §1b and invents a list/detail endpoint for admin-only unscoped access, which would appear in the exercised set but not the manifest → C2 manifest-equality FAIL (surfaced, not silent). Mitigation: workers are instructed the Route Table is authoritative and the manifest is frozen. Not a silent break.

**WARN #13 — `add_refund_in_tx` parameter naming inconsistency across 4 spec locations:**
Three names for param 3: `amount_cents` (Model Functions definition + §1d), `amount` (§1b), `refund_cents` (§5 call site). Two names for param 2: `order_id` (Model Functions), `oid` (§1b, §1d, §5). Runtime-safe (positional calls only). Model-agent should use `amount_cents` (Model Functions + §1d are authoritative for the definition). Mitigation: Model Functions takes precedence as the definition source.

**WARN #14 — `refunded_total` parameter naming inconsistency:**
`order_id` in Model Functions definition vs `oid` in §1b and §1d. Runtime-safe (positional). Same category as #13. Model Functions definition (`order_id`) is authoritative.
