---
date: 2026-05-22
run: 057
project: brewops
reviewer: flow-trace-agent
---

# Flow Trace Review -- BrewOps Craft Brewery Manager

Traced every critical data flow end-to-end across file boundaries.
Each value was followed from creation through storage through consumption.

## Files Read

- `/Users/alejandroguillen/Projects/sandbox/app/models/sale_models.py`
- `/Users/alejandroguillen/Projects/sandbox/app/models/batch_models.py`
- `/Users/alejandroguillen/Projects/sandbox/app/models/tank_models.py`
- `/Users/alejandroguillen/Projects/sandbox/app/models/tap_models.py`
- `/Users/alejandroguillen/Projects/sandbox/app/models/ingredient_models.py`
- `/Users/alejandroguillen/Projects/sandbox/app/models/recipe_models.py`
- `/Users/alejandroguillen/Projects/sandbox/app/models/recipe_ingredient_models.py`
- `/Users/alejandroguillen/Projects/sandbox/app/routes/sale_routes.py`
- `/Users/alejandroguillen/Projects/sandbox/app/routes/batch_routes.py`
- `/Users/alejandroguillen/Projects/sandbox/app/routes/tank_routes.py`
- `/Users/alejandroguillen/Projects/sandbox/app/routes/tap_routes.py`
- `/Users/alejandroguillen/Projects/sandbox/app/routes/ingredient_routes.py`
- `/Users/alejandroguillen/Projects/sandbox/app/routes/dashboard_routes.py`
- `/Users/alejandroguillen/Projects/sandbox/app/routes/recipe_routes.py`
- `/Users/alejandroguillen/Projects/sandbox/app/db.py`
- `/Users/alejandroguillen/Projects/sandbox/schema.sql`
- `/Users/alejandroguillen/Projects/sandbox/app/__init__.py`

---

## Flow 1: Sale Derived State Chain (sale_models.py -> batches -> taps)

### Flow: create_sale (sale_routes.py -> sale_models.py -> batches table -> taps table)

**Data traced:** `quantity_oz` submitted via POST /sales/, consumed by `create_sale`, which decrements `batches.remaining_volume_oz` and conditionally clears `taps.batch_id`.

**Storage step:** `sales` INSERT, then `batches.remaining_volume_oz` UPDATE, then conditionally `batches.status='empty'` UPDATE and `taps.batch_id=NULL` UPDATE.

**Code paths checked:**
- Happy path: tap found, batch found, sufficient volume, sale inserted, volume decremented, COMMIT
- Volume-exactly-zero path: `max(0, ...)` clamp applied, `new_remaining <= 0` triggers both status and tap updates
- Tap-not-found path: ROLLBACK, return None
- Batch-not-found path: ROLLBACK, return None
- Insufficient volume path: ROLLBACK, return None
- Exception path: ROLLBACK, re-raise

**Result:** PASS

**Notes:**

- `max(0, batch['remaining_volume_oz'] - quantity_oz)` is present at `sale_models.py:86`. Float clamping is confirmed.
- All 4 derived state steps (INSERT sale, decrement volume, set status='empty', clear tap.batch_id) are present and correctly ordered inside a single BEGIN IMMEDIATE transaction.
- `sale_routes.py` does NOT call `conn.commit()` after `create_sale` (line 70-73). Correct -- NEEDS-BEGIN-IMMEDIATE functions manage their own transaction.
- The isolation_level=None connection (autocommit mode) is set in `db.py:10`. The explicit `conn.execute('BEGIN IMMEDIATE')` in `create_sale` works correctly because autocommit mode does not issue implicit BEGIN statements that would conflict.

---

## Flow 2: Batch Lifecycle -- planned -> brewing (batch_routes.py -> batch_models.py -> tanks -> ingredients)

### Flow: start_brewing (batch_routes.py:start_brewing_route -> batch_models.py:start_brewing -> tanks.current_batch_id + batches.status + ingredients.stock_qty)

**Data traced:** `tank_id` from form POST /batches/<id>/start-brewing, passed to `start_brewing`. Triggers: tank assignment, ingredient decrement, batch status update. Three tables written atomically.

**Storage step:** `tanks.current_batch_id = batch_id`, `batches.status='brewing'`, `batches.tank_id=tank_id`, `batches.brew_date=date('now')`, `ingredients.stock_qty -= quantity` for each recipe ingredient.

**Code paths checked:**
- Happy path: all three writes committed atomically
- Batch not found: ROLLBACK, return error string
- Batch not in 'planned' status: ROLLBACK, return error string
- Tank not found: ROLLBACK, return error string
- Tank already occupied: ROLLBACK, return error string
- Tank capacity too small: ROLLBACK, return error string
- Ingredient stock insufficient (any single ingredient): ROLLBACK, return error string (only the first failing ingredient is reported; preceding stock decrements from the loop are rolled back correctly since ROLLBACK undoes all)
- Exception: ROLLBACK, re-raise

**Result:** PASS

**Notes:**

- Stock decrement loop at `batch_models.py:112-118` reads ALL ingredients first (`fetchall()`) inside the BEGIN IMMEDIATE lock, then decrements one by one. Since BEGIN IMMEDIATE holds an exclusive writer lock, no other transaction can modify stock between the reads and the writes. TOCTOU-safe.
- Route handler at `batch_routes.py:160` does NOT call `conn.commit()` after `start_brewing`. Correct.
- Route-level pre-check (`batch['status'] != 'planned'` at `batch_routes.py:155`) uses the pre-read batch. The model re-checks inside BEGIN IMMEDIATE. Defense-in-depth correctly applied.

---

## Flow 3: Batch Lifecycle -- conditioning -> ready, tank release (batch_routes.py -> batch_models.py -> tanks)

### Flow: advance_batch_status to 'ready' (batch_routes.py:advance -> batch_models.py:advance_batch_status -> tanks.current_batch_id + batches.tank_id)

**Data traced:** `new_status='ready'` from form POST /batches/<id>/advance. On 'ready' transition, both `tanks.current_batch_id` and `batches.tank_id` must be cleared atomically.

**Storage step:** `batches.status='ready'`, then if `batch['tank_id'] is not None`: `tanks.current_batch_id=NULL`, `batches.tank_id=NULL`.

**Code paths checked:**
- Happy path (conditioning -> ready with tank assigned): all three writes committed
- Happy path (batch with no tank assigned, tank_id IS NULL): status updated, tank release skipped correctly
- Invalid transition: ROLLBACK, error string returned
- Batch not found: ROLLBACK, error string returned
- Exception: ROLLBACK, re-raise

**Result:** PASS

**Notes:**

- `advance_batch_status` at `batch_models.py:164` reads `batch['tank_id']` from the pre-transaction snapshot. This is safe because the value is correct at the time of the BEGIN IMMEDIATE lock acquisition.
- Both `tanks.current_batch_id` and `batches.tank_id` are cleared in the same transaction (lines 165-170). No partial state possible.

---

## Flow 4: Batch Lifecycle -- ready -> tapped, tap assignment (batch_routes.py -> batch_models.py -> taps)

### Flow: assign_to_tap (batch_routes.py:assign_tap -> batch_models.py:assign_to_tap -> taps.batch_id + batches.status)

**Data traced:** `tap_id` from form POST /batches/<id>/assign-tap. Writes `taps.batch_id=batch_id` and `batches.status='tapped'` atomically.

**Storage step:** `taps.batch_id = batch_id`, `batches.status = 'tapped'`.

**Code paths checked:**
- Happy path: both writes committed atomically
- Batch not found: ROLLBACK, error string
- Batch not in 'ready' status: ROLLBACK, error string
- Tap not found: ROLLBACK, error string
- Tap already occupied: ROLLBACK, error string
- Exception: ROLLBACK, re-raise

**Result:** PASS

**Notes:**

- Both `taps.batch_id` and `batches.status` are written inside the same BEGIN IMMEDIATE (lines 206-211 in batch_models.py). No partial state possible.

---

## Flow 5: CRITICAL -- Manual tapped->empty Transition Leaves Tap Permanently Locked (batch_routes.py -> batch_models.py -> taps NOT UPDATED)

### Flow: advance tapped->empty (batch_routes.py:advance -> batch_models.py:advance_batch_status) -- tap NOT cleared

**Data traced:** `new_status='empty'` submitted via POST /batches/<id>/advance when batch is in 'tapped' status. `VALID_TRANSITIONS['tapped'] = ['empty']` allows this path. After the transition, `batches.status='empty'` but `taps.batch_id` still holds the batch ID.

**Storage step:** `batches.status='empty'` written. `taps.batch_id` is NOT updated.

**Code paths checked:**
- `advance_batch_status` at `batch_models.py:163-170`: only clears the TANK when `new_status == 'ready'`. There is no branch for `new_status == 'empty'` to clear `taps.batch_id`.
- `create_sale` is the only code path that clears `taps.batch_id` (at `sale_models.py:96-98`).
- The advance route at `batch_routes.py:169-192` passes `new_status` from form input through to `advance_batch_status` without any tap-clearing logic.

**Result:** FAIL

**Bug:** When an admin manually advances a tapped batch to 'empty' via POST /batches/<id>/advance (valid transition per VALID_TRANSITIONS), `advance_batch_status` sets `batches.status='empty'` but does NOT clear `taps.batch_id`. The tap remains permanently in 'occupied' state. The tap shows as assigned but the batch is empty.

**File:** `/Users/alejandroguillen/Projects/sandbox/app/models/batch_models.py` -- `advance_batch_status`, lines 159-170. The 'ready' case clears the tank at lines 164-170 but there is no parallel 'empty' case to clear the tap.

**Secondary file:** `/Users/alejandroguillen/Projects/sandbox/app/models/batch_models.py:4-12` -- `VALID_TRANSITIONS` map includes `'tapped': ['empty']`, making this reachable.

**Impact at runtime:** After the manual tapped->empty transition:
1. `taps.batch_id` still references the now-empty batch.
2. `get_available_taps()` (used by `assign_to_tap`) queries `WHERE batch_id IS NULL` -- this tap is excluded. No new batch can ever be assigned to this tap through the normal workflow.
3. `get_all_taps()` (used by dashboard, sales form) will join the tap with the empty batch and show it as occupied with 0 remaining volume.
4. The only escape path is deleting the empty batch, but `sales.batch_id` has `ON DELETE RESTRICT` -- if any sales were made against this batch, the delete fails with IntegrityError. The tap is permanently locked.
5. No "unassign tap" or "clear tap" operation exists in the spec or implementation.

**Fix:** Add a parallel branch in `advance_batch_status` alongside the 'ready' tank-clear branch:
```python
# Clear tap when batch reaches 'empty' status
if new_status == 'empty':
    conn.execute(
        "UPDATE taps SET batch_id = NULL, updated_at = datetime('now') WHERE batch_id = ?",
        (batch_id,))
```
This must be inside the same BEGIN IMMEDIATE transaction. Alternatively, remove 'empty' from `VALID_TRANSITIONS['tapped']` and require that 'empty' is only reached via `create_sale` (the only code path that correctly handles the tap clearing). The plan notes that `batches.status -> 'empty'` is owned by `sale_models` via `create_sale()`.

---

## Flow 6: Tank Assignment -- create/update/delete (tank_routes.py -> tank_models.py)

### Flow: Tank CRUD (tank_routes.py -> tank_models.py -> tanks table)

**Data traced:** `tank_id` return value from `create_tank`, used in redirect to `tanks.detail`.

**Storage step:** `tanks` INSERT; caller commits.

**Code paths checked:**
- `create_tank` returns `cur.lastrowid` (tank_models.py:32).
- `tank_routes.py:60`: `tank_id = create_tank(conn, ...)`, `conn.commit()` on line 61. Return value captured. CORRECT.
- `update_tank` and `delete_tank` are SERIAL-SAFE; callers commit. CORRECT.

**Result:** PASS

---

## Flow 7: Tap Assignment -- create/update/delete (tap_routes.py -> tap_models.py)

### Flow: Tap CRUD (tap_routes.py -> tap_models.py -> taps table)

**Data traced:** `tap_id` return from `create_tap`, used in redirect.

**Storage step:** `taps` INSERT; caller commits.

**Code paths checked:**
- `tap_routes.py:45-46`: `tap_id = create_tap(conn, ...)`, `conn.commit()`. Return value captured. CORRECT.
- Delete tap: wraps in try/except IntegrityError for sales RESTRICT. CORRECT.

**Result:** PASS

---

## Flow 8: Ingredient Stock -- recipe ingredients consume stock via start_brewing (batch_models.py -> ingredients table -> dashboard_routes.py:get_low_stock_ingredients)

### Flow: Ingredient stock decrement (batch_models.py:start_brewing -> ingredients.stock_qty -> ingredient_models.py:get_low_stock_ingredients -> dashboard_routes.py)

**Data traced:** Each recipe ingredient's `stock_qty` is decremented in `start_brewing`. The updated value is the authoritative source for low-stock alerts shown on the dashboard.

**Storage step:** `ingredients.stock_qty = stock_qty - ?` for each recipe ingredient (batch_models.py:116-118). Committed atomically with tank assignment and status update.

**Code paths checked:**
- After COMMIT in `start_brewing`, subsequent reads via `get_low_stock_ingredients` see the decremented values.
- `get_low_stock_ingredients` queries `WHERE stock_qty <= low_stock_threshold` -- uses `<=` (inclusive). Correct for "at or below threshold" alert.
- Dashboard calls `get_low_stock_ingredients` on every page load (dashboard_routes.py:25). No caching. Always reads current DB state post-COMMIT.

**Result:** PASS

---

## Flow 9: Recipe Ingredient Stock-Check Data (recipe_ingredient_models.py -> batch_models.py)

### Flow: Recipe ingredient quantities read during start_brewing (batch_models.py raw SQL -> ingredients.stock_qty)

**Data traced:** `start_brewing` does NOT import `get_recipe_ingredients` from `recipe_ingredient_models.py`. It issues its own JOIN query (batch_models.py:107-110) inside the BEGIN IMMEDIATE transaction. The query matches the spec contract.

**Storage step:** Read-only -- no storage issue here.

**Code paths checked:**
- `batch_models.py:107-110` JOIN query: `recipe_ingredients ri JOIN ingredients i ON ri.ingredient_id = i.id WHERE ri.recipe_id = ?`
- This is equivalent to `get_recipe_ingredients` plus the `stock_qty` from `ingredients`, all inside the transaction lock.
- The columns accessed (`ri.quantity`, `ri.ingredient_id`, `ri['ingredient_name']`, `i.stock_qty`) are all present in the query's SELECT *.

**Result:** PASS

**Note:** The plan spec explicitly documents this as intentional: "Uses raw SQL to query recipe_ingredients (does NOT import from recipe_ingredient_models)". No cross-file data mismatch.

---

## Flow 10: Transaction Commit Protocol -- SERIAL-SAFE callers (all routes -> model functions)

### Flow: SERIAL-SAFE write functions called without internal commit, routes call conn.commit()

**Data traced:** All SERIAL-SAFE model functions return without committing. Route handlers must call `conn.commit()` to persist the write.

**Code paths checked (exhaustive):**

| Route | Model call | conn.commit() present? |
|-------|-----------|----------------------|
| batch_routes.py:create (line 62-63) | create_batch | YES |
| batch_routes.py:update (line 114-115) | update_batch | YES |
| batch_routes.py:delete (line 130-131) | delete_batch | YES |
| recipe_routes.py:create (line 61-62) | create_recipe | YES |
| recipe_routes.py:update (line 129-130) | update_recipe | YES |
| recipe_routes.py:delete (line 149-150) | delete_recipe | YES |
| recipe_routes.py:add_ingredient (line 193-194) | add_recipe_ingredient | YES |
| recipe_routes.py:remove_ingredient (line 209-210) | remove_recipe_ingredient | YES |
| ingredient_routes.py:create (line 70-71) | create_ingredient | YES |
| ingredient_routes.py:update (line 139-140) | update_ingredient | YES |
| ingredient_routes.py:delete (line 158-159) | delete_ingredient | YES |
| tank_routes.py:create (line 60-61) | create_tank | YES |
| tank_routes.py:update (line 119-120) | update_tank | YES |
| tank_routes.py:delete (line 137-138) | delete_tank | YES |
| tap_routes.py:create (line 45-46) | create_tap | YES |
| tap_routes.py:update (line 97-98) | update_tap | YES |
| tap_routes.py:delete (line 116-117) | delete_tap | YES |

**NEEDS-BEGIN-IMMEDIATE callers -- verifying NO conn.commit() is called by route:**

| Route | Model call | conn.commit() absent? |
|-------|-----------|----------------------|
| batch_routes.py:start_brewing_route (line 160) | start_brewing | CORRECT -- no commit called |
| batch_routes.py:advance (line 186) | advance_batch_status | CORRECT -- no commit called |
| batch_routes.py:assign_tap (line 215) | assign_to_tap | CORRECT -- no commit called |
| sale_routes.py:create (line 70) | create_sale | CORRECT -- no commit called |

**Result:** PASS

---

## Flow 11: Dashboard Derived State Reads (dashboard_routes.py -> multiple models)

### Flow: Dashboard index reads derived state from multiple tables

**Data traced:** Dashboard at GET / reads: active batches (brewing/fermenting/conditioning), ready batches, tapped batches, low stock ingredients, all taps with batch info, today's sales total.

**Code paths checked:**
- `dashboard_routes.py:18-27` calls six model functions, all read-only.
- `get_all_taps` returns taps LEFT JOINed with batches and recipes (tap_models.py:11-18). After a `create_sale` empties a batch and clears `taps.batch_id`, the dashboard correctly shows that tap as unassigned on the next page load.
- EXCEPTION: After a manual `advance` to 'empty' (Flow 5 bug), the dashboard will show the tap as still assigned to the empty batch, misleading the operator.

**Result:** PASS (this read is correct; the inconsistency originates in the Flow 5 write bug)

---

## Summary of Issues

### P1 -- Manual tapped->empty transition leaves tap permanently locked

**Files:** `app/models/batch_models.py` (advance_batch_status, lines 159-170) and `app/models/batch_models.py` (VALID_TRANSITIONS, lines 4-12)

`VALID_TRANSITIONS['tapped'] = ['empty']` enables a transition that `advance_batch_status` does not fully handle. The function clears the tank on 'ready' (lines 164-170) but has no corresponding tap-clear on 'empty'. The only tap-clearing code lives in `create_sale` (sale_models.py:96-98), which is unreachable once the batch is already marked empty.

The three-file chain that reveals this: `VALID_TRANSITIONS` in `batch_models.py` makes the transition valid -> `advance_batch_status` in `batch_models.py` writes the status but has no tap-clear branch -> `taps.batch_id` in `schema.sql` is UNIQUE and never cleared -> tap is permanently locked from any new assignment.

**Severity:** P1 -- permanent data corruption with no operational recovery path (delete is blocked by RESTRICT on sales).

**Fix options:**
1. Add a tap-clear branch inside `advance_batch_status` for `new_status == 'empty'`: `UPDATE taps SET batch_id = NULL WHERE batch_id = ?`. Must be inside the same BEGIN IMMEDIATE.
2. Or remove 'empty' from `VALID_TRANSITIONS['tapped']` and document that 'empty' is only reachable via `create_sale`. This aligns with the Derived State table in the spec, which lists `batches.status -> 'empty'` as owned by `sale_models / create_sale()` only.

---

```
STATUS: FAIL -- 11 flows traced, 1 issue found

P1 (1): Manual tapped->empty advance leaves taps.batch_id non-null permanently
         (app/models/batch_models.py:advance_batch_status, VALID_TRANSITIONS)
```
