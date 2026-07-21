---
title: "swarmlimit — Shared Interface Spec (Run 082 Path-B autopilot-swarm)"
type: feat
status: draft            # → active only after Codex-clean AND human zero-P0 (see Convergence Handoff)
date: 2026-07-21
last_revised: 2026-07-21
swarm: true
autonomy_class: autopilot-swarm
executor: autopilot-skill           # NOT the Workflow engine (UNLAUNCHABLE — see run-plan origin)
namespace: swarmlimit/
run_plan: docs/plans/2026-07-21-feat-082-max-value-unattended-autopilot-limit-test-plan.md
template_source: docs/plans/2026-07-09-feat-lesson-studio-scale-validation-plan.md   # ported §5/§6
feed_forward:
  risk: "The two cross-resource transactions (create_order, process_return) and the ext_ref cross-resource uniqueness are the load-bearing seams. A single return-shape or class (A/B/C) drift between §Model Functions and §5 Transaction Contracts fails the atomic unit AND every Path-B EARS that reads it. process_return is the hardest: it is a 4-table atomic write (returns + shipments.status + products.stock + payments-refund) owned by model-return but reaching into three OTHER agents' tables via in-tx helpers — the densest cross-agent write in the spec."
  verify_first: true
---

# swarmlimit — Shared Interface Spec (Path-B, Run 082)

A **throwaway** e-commerce-order back office. **Flask + stdlib `sqlite3`, JSON API (no
Jinja/templates).** Its purpose is NOT the app — it is the **vehicle** for the biggest
*high-value* unattended autopilot-swarm limit-test (governance stress + pitfall harvest). See the
run-plan for goal/sizing/wave structure; **this document is the shared-interface contract** the
swarm workers build against, authored + converged **before** spawn.

Resources are chosen for **DISTINCT contradiction TYPES**, never clones (run-plan Path B):
owner-FK + role+own auth (`users→orders`), a multi-FK **atomic transaction** (`create_order`), a
**transitive ownership chain** (`products→suppliers`), an **M2M** (`categories↔products`), a
cross-cutting **audit** write, a status **STATE-MACHINE** (`shipments`), a **cross-resource
uniqueness** constraint (`ext_ref` across `orders`+`returns`), a **soft-delete** (`products.deleted_at`),
and a **second, structurally different** atomic transaction (`process_return`).

> **JSON-API decision (vs lesson-studio's HTML):** swarmlimit is a pure JSON API. The Path-B
> stressors are all status-code + transaction shaped (409 illegal transition, 409 uniqueness
> collision, atomic rollback, 404-not-403 ownership), so HTML/Jinja/template surface is pure
> overhead and is CUT. This removes FC53/FC54/FC61/FC62 (all Jinja-class) from the risk surface
> and shrinks every route agent to one `.py` file. CSRF becomes a header token (below), not a form
> field. Faithful to the run-plan (which never requires HTML).

---

## Namespace & Build Convention (FC59/FC48 — MANDATORY)

ALL application code lives under the top-level **`swarmlimit/`** dir — never the shared `app/`.
Confirmed free of collision on `master` (2026-07-21: `swarmlimit/` absent). Layout:

```
swarmlimit/
  __init__.py              # app factory (create_app, MODULE-LEVEL), blueprint registration, error/response schema, CSRF, /audit view (scaffold)
  database.py              # get_db, init_db, seed, query, transaction() (database agent)
  schema.sql              # DDL + seed constants (database agent)
  auth.py                 # login_required / role_required / ownership helpers (auth-core)
  refs.py                 # assert_ext_ref_unique — cross-resource ext_ref owner (shared-services)
  models/
    auth_models.py        # (auth-core)
    audit_models.py       # record + list_audit (shared-services — write-only lib + admin read)
    <resource>_models.py  # one file per model agent
  routes/
    auth.py               # (auth-core)
    <resource>.py         # one blueprint per route agent
  smoke.py                # smoke harness (smoke-author) — INSIDE the package at swarmlimit/smoke.py; run via `python -m swarmlimit.smoke`
```

**Canonical smoke harness location + invocation (pinned — the ONE authority; every reference below
uses it):** the harness is `swarmlimit/smoke.py` (inside the package, NOT a loose top-level script)
and is ALWAYS invoked as **`python -m swarmlimit.smoke`** (full run), **`python -m swarmlimit.smoke
--case <name>`** (single Path-B case), or **`python -m swarmlimit.smoke --manifest
<R>/planned-manifest.json`** (manifest-equality run). Being in-package means `python -m compileall
swarmlimit` byte-compiles it too, and `import swarmlimit.smoke` resolves. No other path/command form
(`python smoke.py`, `python swarmlimit/smoke.py`, `python swarmlimit smoke`) is valid. For `python -m`
to work, `swarmlimit/smoke.py` MUST have an `if __name__ == '__main__':` block with an `argparse`
parser accepting `--case <name>` and `--manifest <path>` (absent → the full default suite runs).

`create_app()` is defined at **module level** in `swarmlimit/__init__.py` (FC50 orchestration
entrypoint); `swarmlimit/smoke.py` does `from swarmlimit import create_app`. A module-level
`app = create_app()` is NOT created at import time (avoids side-effecting the DB on import); smoke
builds its own app against a throwaway temp DB. **Temp-DB pin (P0 — init_db must actually run):** smoke
creates a `tempfile.TemporaryDirectory()` and configures the DB to a **child path that does NOT yet
exist** (e.g. `<tempdir>/swarmlimit.sqlite`), then calls `create_app()`. Because the file is absent,
`create_app()`'s "init_db only if the DB file is absent" check fires and `init_db()` runs **exactly
once**, creating the schema. Smoke MUST NOT hand `create_app()` a pre-created empty file (a bare
`tempfile.NamedTemporaryFile`/`mkstemp` path already EXISTS → the absence check is false → `init_db()`
is skipped → the first query fails with no schema). FC49 still holds: a **real on-disk SQLite file**
inside the temp dir, never `:memory:`.

---

## App Configuration (swarmlimit/__init__.py — scaffold agent owns this file)

- `create_app(config=None)` application factory (module-level). Reads `SECRET_KEY` from env;
  **fail-closed**: if `SECRET_KEY` unset AND `FLASK_ENV != development`, raise at startup. In
  development, fall back to a fixed dev key with a logged warning.
- Session cookie: `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`,
  `SESSION_COOKIE_SECURE = (FLASK_ENV != development)`.
- **CSRF (header token, JSON API):** `create_app` registers a `before_request` that, on every
  `POST/PUT/PATCH/DELETE` **carrying an authenticated session**, requires request header
  `X-CSRF-Token` to equal `session['_csrf']` (minted at login) → **400** (`{"error":"csrf"}`) on
  absence/mismatch. **Auth precedes CSRF (pinned):** an anonymous request has no session (no
  `session['_csrf']`), so the CSRF `before_request` does NOT reject it — it falls through to the view's
  `login_required`, which returns **401 `auth`**. So an anonymous mutating request returns **401**, never
  400 (CSRF applies ONLY to authenticated mutating requests). `GET` is exempt. Login/register are exempt
  (no session yet). Smoke reads the token from the login response body.
- **CSP:** `create_app` sets a static `Content-Security-Policy: default-src 'none'` response header
  on all responses (JSON API serves no HTML/JS, so the strictest policy is correct and free). This
  is the "CSP if any" the run-plan names; it is a fixed constant, not per-route.
- **Error/response schema (pinned — every agent emits this exact shape):**
  - Success: the handler returns `(json_body, status)`; `json_body` is a JSON object (never a bare
    list — top-level is always an object, e.g. `{"orders":[...]}`) so no `[object Object]`/`{'`
    leakage and stable keys (FC63).
  - Error: a shared `error(code:str, status:int, **extra)` helper (defined in `__init__.py`,
    imported by every route) returns `({"error": code, **extra}, status)`. Canonical codes:
    `"validation"` (400), `"csrf"` (400), `"auth"` (401), `"forbidden"` (403), `"not_found"` (404),
    `"conflict"` (409). Every route uses `error(...)`; no route hand-rolls an error body.
- **Registration:** registers all blueprints (see Roster/Route Table) in a fixed order. Calls
  `init_db()` once if the DB file is absent (so callers — incl. smoke — MUST point the config at a DB
  path that does not yet exist for the schema to be created; see the Temp-DB pin above). Hosts the
  admin **`GET /audit`** view directly
  (reads `audit_models.list_audit`) — the one read the scaffold owns, mirroring lesson-studio's
  scaffold-hosts-/rooms pattern (keeps audit from needing its own route agent).

Deferred by design (throwaway vehicle — NOT production): password complexity beyond min length,
rate limiting, HTTPS/HSTS enforcement, email verification, pagination.

---

## Database Schema (swarmlimit/schema.sql — database agent owns this file)

Stdlib `sqlite3`. **Per-connection pragmas (pinned — set in `get_db`, every connection):**
`PRAGMA foreign_keys = ON;` · `PRAGMA journal_mode = WAL;` · `PRAGMA busy_timeout = 5000;`.
The connection is opened with **`isolation_level=None`** — Python `sqlite3` **AUTOCOMMIT** mode: the
driver opens NO implicit transaction, so each bare statement commits **immediately**, and a
multi-statement atomic unit must be opened EXPLICITLY by the app with `BEGIN IMMEDIATE` … `COMMIT`/
`ROLLBACK` (class-B only). All timestamps are ISO-8601 TEXT (UTC). Money is integer **cents** (never float).

```sql
-- ---------- identity ----------
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin','customer')),
    name          TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- catalog parents ----------
CREATE TABLE suppliers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    contact_email TEXT,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- products (soft-delete + stock guard + transitive parent + M2M) ----------
CREATE TABLE products (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sku          TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    supplier_id  INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,  -- transitive ownership parent
    price_cents  INTEGER NOT NULL CHECK (price_cents >= 0),
    stock        INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),                  -- CHECK backstops the stock guard
    deleted_at   TEXT,                                                           -- NULL = live; non-NULL = soft-deleted
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- M2M categories↔products
CREATE TABLE product_categories (
    product_id  INTEGER NOT NULL REFERENCES products(id)   ON DELETE CASCADE,   -- join row is a "part" of the product
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,  -- can't drop a category still in use
    PRIMARY KEY (product_id, category_id)
);

-- ---------- orders (owner FK + ext_ref cross-resource uniqueness + create_order tx) ----------
CREATE TABLE orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,        -- owner; financial record
    ext_ref    TEXT NOT NULL UNIQUE,                                            -- intra-table backstop; cross-table via refs.assert_ext_ref_unique
    status     TEXT NOT NULL DEFAULT 'placed' CHECK (status IN ('placed','fulfilled','cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE order_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES orders(id)   ON DELETE CASCADE,   -- child "part" of the order
    product_id    INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,  -- referenced parent; history preserved
    qty           INTEGER NOT NULL CHECK (qty > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0)             -- snapshot of product price at order time
);

-- ---------- fulfillment (STATE MACHINE) ----------
CREATE TABLE shipments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE, -- child of the order; UNIQUE ⇒ exactly one shipment per order (backstops the single-return story)
    status     TEXT NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending','shipped','delivered','returned')),
    carrier    TEXT,
    tracking   TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- returns (ext_ref cross-resource uniqueness + process_return tx) ----------
CREATE TABLE returns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,      -- financial/fulfillment record
    ext_ref     TEXT NOT NULL UNIQUE,                                           -- intra-table backstop; cross-table via refs
    reason      TEXT,
    refund_cents INTEGER NOT NULL CHECK (refund_cents > 0),   -- strictly positive; matches payments.amount_cents CHECK (a return always refunds >0)
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- payments (refund ledger; refund ≤ original guard) ----------
CREATE TABLE payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,      -- financial record
    kind        TEXT NOT NULL CHECK (kind IN ('refund')),                       -- only refunds are ledgered (see Transaction Contracts)
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- cross-cutting audit ----------
CREATE TABLE audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,             -- 'create'|'update'|'delete'|'advance'|'return'
    entity_type TEXT NOT NULL,             -- 'order'|'product'|'shipment'|'return'|...
    entity_id   INTEGER,                    -- polymorphic pointer (varies by entity_type) — INTENTIONALLY no REFERENCES (not an FK; FC46 exempt)
    detail      TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**FK on-delete policy (per edge — the run-plan pin):** CASCADE for "parts" (`order_items.order_id`,
`shipments.order_id`, `product_categories.product_id`); RESTRICT for financial/fulfillment records
and referenced parents (`payments.order_id`, `returns.order_id`, `orders.user_id`,
`order_items.product_id`, `products.supplier_id`, `product_categories.category_id`); SET NULL for
`audit_logs.actor_id`. Products are **never hard-deleted** (soft-delete only), so the RESTRICT on
`order_items.product_id` is a backstop, not a hot path.

**SEED DATA (database agent inserts in `init_db`):** 1 admin (`admin@swarm.test`/`swarmpass`),
2 customers; 2 suppliers; 3 categories; 4 products (each with a supplier + ≥1 category via
`product_categories`; stock ≥ 5; all `deleted_at=NULL`); 1 order for customer-1 (2 order_items) so
the smoke suite exercises real relationships; NO shipments/returns/payments seeded (created by
smoke's Path-B cases). Every seeded row satisfies all NOT NULL / CHECK / UNIQUE constraints.

---

## Database Connection (swarmlimit/database.py — database agent owns this file)

- `get_db() -> sqlite3.Connection` — one connection per request via Flask `g`; opened with
  `isolation_level=None`; sets `row_factory = sqlite3.Row` and the three pragmas (`foreign_keys=ON`,
  `journal_mode=WAL`, `busy_timeout=5000`). Registered teardown closes it.
- `init_db() -> None` — executes `schema.sql`, inserts seed rows. Idempotent guard: the app factory
  calls it only when the DB file does not already exist (FC16 — DDL is `CREATE TABLE`, run once).
  **Corollary (smoke):** because the guard keys on file absence, smoke must configure a DB path that
  does NOT yet exist (a child of a `TemporaryDirectory`, never a pre-created `NamedTemporaryFile`);
  otherwise `init_db()` is skipped and the schema is never created. See the Temp-DB pin in the
  Namespace section. `init_db` itself is NOT redesigned by this contract.
- `query(sql, params=(), one=False) -> list[dict] | dict | None` — thin helper returning plain
  dicts (never leak `sqlite3.Row` across a boundary — FC63/FC2).
- **Autocommit & class-A writes (`isolation_level=None`):** because no implicit transaction is open,
  a class-A writer's single `INSERT/UPDATE/DELETE` executed on the request connection commits
  **immediately** — it does NOT call `conn.commit()` (nothing is pending) and does NOT open
  `transaction()`. Only the two class-B units (`create_order`, `process_return`) open an explicit
  transaction.
- **`transaction()` context manager** — wraps the **single `get_db()` request connection** with an
  explicit **`BEGIN IMMEDIATE`** (takes the write lock up front → two concurrent class-B writers on
  separate requests serialize; the second blocks up to `busy_timeout`, then re-reads current state).
  On clean exit: `COMMIT`. On ANY exception: `ROLLBACK`, then re-raise (`try/except/ROLLBACK/raise`).
  Because it is the SAME connection every model function uses, reads done DURING the transaction see
  its own uncommitted writes (so in-tx guards are consistent). **Nested `transaction()` is
  forbidden** (a class-B writer never opens another class-B writer). Because the connection is in
  `isolation_level=None` **AUTOCOMMIT** mode, the explicit `BEGIN IMMEDIATE` issued here is the ONLY
  transaction boundary — there is no driver-managed implicit BEGIN to race it, and the matching
  `COMMIT`/`ROLLBACK` is likewise explicit.

All model functions convert `sqlite3.Row` → plain `dict` before returning.

---

## Model Functions (full signatures — Export Names contract derives from these)

Convention: single-row getters return `dict | None`; listers return `list[dict]`; creators return
the new `int` id; mutators return `None`. **Every class-A writer persists immediately via SQLite
autocommit (`isolation_level=None`) — it does NOT call `conn.commit()` and does NOT open a
transaction.** The ONLY functions that issue explicit transaction boundaries are the two class-B units
(`create_order`, `process_return`); the in-tx helpers (`decrement_stock_in_tx`, `restock_product_in_tx`,
`set_shipment_status_in_tx`, `add_refund_in_tx`) take a caller `conn` and neither commit nor open a
transaction — see §5.

### auth_models.py  (auth-core)
- `create_user(email, password, role, name) -> int` — hashes password (`werkzeug`); raises
  `ValueError('email exists')` on UNIQUE violation. persists immediately via SQLite autocommit; does not call `conn.commit()`.
  **Privilege pin:** the public `POST /auth/register` route ALWAYS calls this with `role='customer'`
  (client-supplied role ignored); the `role` parameter is variable ONLY for trusted seed/internal
  callers (e.g. `init_db` seeding `admin@swarm.test`).
- `get_user(user_id) -> dict | None`
- `get_user_by_email(email) -> dict | None`
- `verify_credentials(email, password) -> dict | None` — user dict if password matches, else None.

### swarmlimit/auth.py  (auth-core — decorators & session helpers, NOT a model)
- `login_user(user: dict) -> None` / `logout_user() -> None` — set/clear session (mints `_csrf`).
- `current_user() -> dict | None` — logged-in user row (cached on `g`).
- `login_required(view)` — **401** (`error('auth',401)`) when anonymous (JSON API — no redirect).
- `role_required(*roles)` — decorator; **403** (`error('forbidden',403)`) when `current_user()` role
  not in roles.

**Ownership-Scoped Getter Contract (UNIFORM across all owning agents — order, shipment, return,
payment; run-080 IDOR lesson, ported from lesson-studio).** Every ownership-scoped getter obeys the
SAME actor-based SQL-predicate rule (the check is a **SQL WHERE predicate in the query**, never a
fetch-then-compare in Python):

- Signature: `get_<x>_for(<id>, actor) -> dict | None` and `list_<x>_for(actor, **filters) -> list[dict]`.
  `actor` is the `current_user()` dict (`{id, role, ...}`), always the trailing arg on getters.
- `actor['role'] == 'admin'` → **no ownership restriction** (admin sees all).
- `actor['role'] == 'customer'` → restrict to rows the customer owns. For `orders` (the ownership
  root) the predicate is `orders.user_id = :actor_id`. For **derived** resources (shipments, returns,
  payments) ownership is transitive through the order: `EXISTS (SELECT 1 FROM orders o WHERE
  o.id = <x>.order_id AND o.user_id = :actor_id)`.
- A non-owner therefore gets **0 rows → `None`/`[]`**; the route does `row = get_<x>_for(...) or
  error('not_found',404)`. **No 403, no existence leak** on reads.

### refs.py  (shared-services — cross-resource ext_ref uniqueness owner)
- `assert_ext_ref_unique(conn, ext_ref) -> None` — on the **caller-supplied** `conn` (in-tx, no
  commit). Raises `ValueError('ext_ref exists')` if `ext_ref` appears in **either** `orders` OR
  `returns`. This is the SINGLE authority for cross-resource uniqueness (no single table owns it;
  the per-table `UNIQUE` on `orders.ext_ref` / `returns.ext_ref` is only an intra-table backstop).
  Called inside `create_order` and `process_return` BEFORE the respective insert.

### supplier_models.py  (supplier model agent)
- `list_suppliers(active_only=False) -> list[dict]`
- `get_supplier(sid) -> dict | None`
- `create_supplier(name, contact_email=None) -> int`
- `update_supplier(sid, **fields) -> None` — whitelist: name, contact_email, active.
- `delete_supplier(sid) -> None` — hard delete; relies on FK RESTRICT → raises
  `ValueError('supplier in use')` (caught from IntegrityError) if any product references it.

### category_models.py  (category model agent)
- `list_categories() -> list[dict]`
- `get_category(cid) -> dict | None`
- `create_category(name) -> int` — raises `ValueError('name exists')` on UNIQUE.
- `update_category(cid, **fields) -> None` — whitelist: name.
- `delete_category(cid) -> None` — FK RESTRICT via `product_categories.category_id` →
  `ValueError('category in use')` if referenced.

### product_models.py  (product model agent — soft-delete + stock guard + M2M + in-tx helpers)
- `list_products(q=None, category_id=None, include_deleted=False) -> list[dict]` — **excludes
  `deleted_at IS NOT NULL` unless `include_deleted=True`** (admin history only). `q` LIKE-matches
  name/sku; `category_id` joins `product_categories`.
- `get_product(pid, include_deleted=False) -> dict | None` — **returns `None` for a soft-deleted
  product unless `include_deleted=True`.** Includes `category_ids: list[int]`.
- `create_product(sku, name, supplier_id, price_cents, stock=0, category_ids=None) -> int` —
  validates supplier exists; raises `ValueError('sku exists')` on UNIQUE; attaches M2M rows. persists immediately via SQLite autocommit; does not call `conn.commit()`.
- `update_product(pid, **fields) -> None` — whitelist: name, price_cents, stock, supplier_id. persists immediately via SQLite autocommit; does not call `conn.commit()`.
- `soft_delete_product(pid) -> None` — sets `deleted_at = datetime('now')`; **does NOT touch
  `order_items`** (history preserved). Idempotent (already-deleted → no-op). persists immediately via SQLite autocommit; does not call `conn.commit()`.
- `set_product_categories(pid, category_ids) -> None` — replaces M2M rows. persists immediately via SQLite autocommit; does not call `conn.commit()`.
- `decrement_stock_in_tx(conn, pid, qty) -> None` — **in-tx helper, caller `conn`, NO commit.** The
  stock guard: `UPDATE products SET stock = stock - :qty WHERE id = :pid AND deleted_at IS NULL AND
  stock >= :qty`; require `conn.total_changes` delta / `cursor.rowcount == 1` else raise
  `ValueError('insufficient stock')` (also fires if the product is soft-deleted → rowcount 0).
  Called ONLY by `order_models.create_order`.
- `restock_product_in_tx(conn, pid, qty) -> None` — **in-tx helper, caller `conn`, NO commit.**
  `UPDATE products SET stock = stock + :qty WHERE id = :pid` (restocks regardless of `deleted_at` —
  a returned unit re-enters inventory even if the SKU was since retired). Called ONLY by
  `return_models.process_return`.

### order_models.py  (order model agent — owns orders + order_items + create_order transaction)
- `list_orders(user_id=None, status=None) -> list[dict]` — each row includes computed
  `total_cents = SUM(qty*unit_price_cents)` (unscoped; admin callers).
- `list_orders_for(actor, status=None) -> list[dict]` — **Ownership-Scoped Getter Contract**
  (admin→all; customer→`user_id = actor.id`). This is the `GET /orders` source.
- `get_order(oid) -> dict | None` — includes `items: list[dict]` + `total_cents` (unscoped).
- `get_order_for(oid, actor) -> dict | None` — **Ownership-Scoped Getter Contract**; includes
  `items` + `total_cents`. `GET /orders/<int:oid>` → `... or error('not_found',404)`.
- `order_total(conn, oid) -> int` — `SUM(qty*unit_price_cents)` on a caller `conn` (used in-tx by
  `process_return`'s refund-guard; also the read-time total). Read-only; no commit.
- `create_order(user_id, ext_ref, items) -> int` — **OWNS one `transaction()` internally.** `items`
  is `list[{product_id, qty}]` (non-empty; validated by the route). Inside `with transaction() as
  conn:` (BEGIN IMMEDIATE): (1) `refs.assert_ext_ref_unique(conn, ext_ref)` → `ValueError` on
  collision (route → 409); (2) insert the order row (`status='placed'`); (3) for each item: re-read
  the product on `conn` (must exist AND `deleted_at IS NULL`, else `ValueError('product unavailable')`);
  snapshot `unit_price_cents = product.price_cents`; `product_models.decrement_stock_in_tx(conn,
  product_id, qty)` (stock guard → `ValueError('insufficient stock')`); insert the order_item. Any
  failure rolls back the WHOLE unit (no order, no partial items, no stock change). **Does NOT audit**
  (route audits post-commit). Commits exactly once via the context manager. Touches
  **{orders, order_items, products.stock}** atomically.

### shipment_models.py  (shipment model agent — STATE MACHINE)
- `LEGAL_TRANSITIONS` (module constant): `{('pending','shipped'), ('shipped','delivered')}`. The
  `→'returned'` transition is DELIBERATELY ABSENT here — it is reachable ONLY via
  `set_shipment_status_in_tx` called inside `process_return` (a customer/staff cannot "advance" a
  shipment to returned; a return event does it atomically).
- `list_shipments(order_id=None, status=None) -> list[dict]`
- `get_shipment(sid) -> dict | None`
- `get_shipment_for(sid, actor) -> dict | None` — **Ownership-Scoped Getter Contract** (transitive
  via order). `GET /shipments/<int:sid>` → 404 for non-owner.
- `create_shipment(order_id, carrier=None, tracking=None) -> int` — validates the order exists;
  inserts `status='pending'`. **Exactly one shipment per order:** raises `ValueError('shipment exists')`
  if the order already has a shipment (the `UNIQUE(order_id)` constraint fires an `IntegrityError`,
  caught and re-raised as this named `ValueError`) → route maps to **409 `conflict`**. persists
  immediately via SQLite autocommit; does not call `conn.commit()`. (Admin creates the single shipment
  for a placed order.)
- `advance_shipment(sid, to_status) -> None` — the ROUTE has already checked `to_status` is one of
  the four stored statuses (else 400); this reads current status and, if `(current, to_status) NOT IN
  LEGAL_TRANSITIONS` → raise `ValueError('illegal transition')` and **leave status unchanged**
  (route → 409). On legal: `UPDATE shipments SET status=:to, updated_at=datetime('now')`. persists immediately via SQLite autocommit; does not call `conn.commit()`.
  **Never** succeeds for `'returned'` — `(x,'returned') ∉ LEGAL_TRANSITIONS` for every `x`, so a
  client `advance` to `returned` always 409s; only `process_return` sets `'returned'`.
- `set_shipment_status_in_tx(conn, sid, status) -> None` — **in-tx helper, caller `conn`, NO
  commit.** Unconditional `UPDATE ... SET status=:status`. Called ONLY by `process_return` (to set
  `'returned'`); the caller has already validated the shipment is `'delivered'`.

### return_models.py  (return model agent — owns process_return transaction, the 4-table atomic unit)
- `list_returns(order_id=None) -> list[dict]` (unscoped; admin callers).
- `list_returns_for(actor) -> list[dict]` — **Ownership-Scoped Getter Contract** (transitive via
  order). `GET /returns` source.
- `get_return(rid) -> dict | None`
- `get_return_for(rid, actor) -> dict | None` — **Ownership-Scoped Getter Contract**.
  `GET /returns/<int:rid>` → 404 for non-owner.
- `process_return(order_id, ext_ref, reason, refund_cents) -> int` — **OWNS one `transaction()`
  internally.** Inside `with transaction() as conn:` (BEGIN IMMEDIATE): (1)
  `refs.assert_ext_ref_unique(conn, ext_ref)` → `ValueError` (route → 409); (2) select the order's
  shipment on `conn` (the `UNIQUE(order_id)` constraint guarantees **at most one** — no ambiguity about
  which `shipment_id` to update); require it EXISTS and `status == 'delivered'`, else
  `ValueError('shipment not delivered')` (route → 409 — illegal state); (3) **refund guard:**
  `refund_cents + (existing refunds for the order) ≤ order_models.order_total(conn, order_id)`, else
  `ValueError('refund exceeds original')` → rollback; (4) insert the return row; (5)
  `shipment_models.set_shipment_status_in_tx(conn, shipment_id, 'returned')`; (6) for each order_item
  of the order: `product_models.restock_product_in_tx(conn, product_id, qty)`; (7)
  `payment_models.add_refund_in_tx(conn, order_id, refund_cents)`. Any failure rolls back **all four
  writes** (return, shipment status, restock, payment refund). **Does NOT audit** (route audits
  post-commit). Touches **{returns, shipments.status, products.stock, payments}** atomically.

### payment_models.py  (payment model agent — refund ledger)
- `list_payments(order_id=None) -> list[dict]` (unscoped; admin callers).
- `list_payments_for(actor) -> list[dict]` — **Ownership-Scoped Getter Contract** (transitive via
  order). `GET /payments` source.
- `get_payment(pid) -> dict | None`
- `get_payment_for(pid, actor) -> dict | None` — **Ownership-Scoped Getter Contract**.
- `refunded_total(conn, order_id) -> int` — `SUM(amount_cents) WHERE kind='refund'` for the order,
  on a caller `conn` (used in-tx by `process_return`'s refund guard). Read-only; no commit.
- `add_refund_in_tx(conn, order_id, amount_cents) -> int` — **in-tx helper, caller `conn`, NO
  commit.** Inserts a `kind='refund'` payment row with `amount_cents = refund_cents` (always `> 0` —
  the route + `returns.refund_cents` CHECK both enforce `> 0`, so the `payments.amount_cents > 0`
  CHECK can never fire at runtime; it is a backstop). Called ONLY by `process_return`.

> **"Original payment" definition (pin — the refund-guard reference):** swarmlimit does NOT ledger a
> `charge` row (create_order touches no payments — faithful to the run-plan EARS enumeration of
> {orders, order_items, stock}). The order's **original amount is `order_total` = SUM(order_items)**,
> the single source of truth. The refund guard is therefore
> `refunded_total(conn,order_id) + refund_cents ≤ order_total(conn,order_id)`. `payments` is a
> **refund-only** ledger (schema CHECK `kind IN ('refund')`).

### audit_models.py  (shared-services — WRITE-ONLY lib, imported by ALL mutating routes)
- `record(actor_id, action, entity_type, entity_id=None, detail=None) -> None` — inserts one
  audit_logs row; persists immediately via SQLite autocommit; does not call `conn.commit()`. Called **post-commit, route-level only** (one of the sanctioned
  cross-agent write calls). **NEVER called inside a `transaction()`** and never by a model writer.
- `list_audit(entity_type=None, limit=200) -> list[dict]` — admin audit view (`GET /audit`, hosted
  by scaffold).

---

## Route Table (blueprint · url_prefix · path · method · auth mode)

Auth modes: **public** · **auth** (any logged-in) · **role+own** (admin OR resource owner; 404 for
non-owner) · **admin**. JSON API — success/error bodies per the pinned schema. Full rules in §6.

### auth  (auth-core — no url_prefix; full paths)
| Method | Path | View | Auth |
|--------|------|------|------|
| POST | /auth/register | register (**always creates a `customer`** — supplied `role` ignored/overridden) | public |
| POST | /auth/login | login (response body includes `csrf_token`) | public |
| POST | /auth/logout | logout | auth |

> **`POST /auth/register` privilege pin (P0 — public route can NEVER mint an admin):** the register
> view calls `create_user(email=email, password=password, role='customer', name=name)` — it hard-codes `role='customer'`
> and ignores any `role` in the request body, so an anonymous caller submitting `role=admin` still
> receives a `customer` account. The seeded `admin@swarm.test` (inserted by `init_db`) is the sole
> bootstrap admin; the stale "first user forced admin" rule is removed. `create_user` keeps its
> `role` parameter for trusted seed/internal use (seeding, tests) — ONLY the public route is pinned
> to `customer`.

### suppliers  (supplier route agent — no url_prefix; full paths)
| GET | /suppliers | list_suppliers | auth |
| POST | /suppliers | create_supplier | admin |
| GET | /suppliers/<int:sid> | get_supplier → `... or error('not_found',404)` | auth |
| PATCH | /suppliers/<int:sid> | update_supplier | admin |
| DELETE | /suppliers/<int:sid> | delete_supplier (409 `conflict` if in use) | admin |

### categories  (category route agent — no url_prefix; full paths)
| GET | /categories | list_categories | auth |
| POST | /categories | create_category | admin |
| GET | /categories/<int:cid> | get_category | auth |
| PATCH | /categories/<int:cid> | update_category | admin |
| DELETE | /categories/<int:cid> | delete_category (409 `conflict` if in use) | admin |

### products  (product route agent — no url_prefix; full paths)
| GET | /products | list_products (excludes soft-deleted) | auth |
| POST | /products | create_product | admin |
| GET | /products/<int:pid> | get_product → 404 if soft-deleted/absent | auth |
| PATCH | /products/<int:pid> | update_product | admin |
| DELETE | /products/<int:pid> | soft_delete_product (200; sets deleted_at) | admin |
| PUT | /products/<int:pid>/categories | set_product_categories | admin |

### orders  (order route agent — no url_prefix; full paths)
| GET | /orders | `list_orders_for(current_user())` | role+own |
| POST | /orders | create_order → 409 on ext_ref/stock. **`user_id` resolution:** omitted → the **current actor's id** (both roles); customer → ALWAYS forced to own id (any supplied `user_id` ignored); admin → may override with an explicit `user_id` | auth |
| GET | /orders/<int:oid> | `get_order_for(oid, current_user()) or error('not_found',404)` | role+own |

### shipments  (shipment route agent — no url_prefix; full paths; two roots)
| POST | /orders/<int:oid>/shipments | create_shipment (**409 `conflict`** if the order already has a shipment) | admin |
| GET | /shipments/<int:sid> | `get_shipment_for(sid, current_user()) or 404` | role+own |
| POST | /shipments/<int:sid>/advance | advance_shipment (body `{to_status}`) → **409** illegal | admin |

### returns  (return route agent — no url_prefix; full paths)
| GET | /returns | `list_returns_for(current_user())` | role+own |
| POST | /returns | process_return (body `{order_id, ext_ref, reason?, refund_cents}`) → 409 ext_ref/state/refund | role+own |
| GET | /returns/<int:rid> | `get_return_for(rid, current_user()) or 404` | role+own |

### payments  (payment route agent — no url_prefix; full paths)
| GET | /payments | `list_payments_for(current_user())` | role+own |
| GET | /payments/<int:pid> | `get_payment_for(pid, current_user()) or 404` | role+own |

### audit  (/audit — hosted by scaffold in __init__.py)
| GET | /audit | list_audit | admin |

> **`POST /returns` auth (role+own on a body-supplied `order_id`):** the route resolves the order
> via `get_order_for(order_id, current_user())`; a non-owner customer gets `None` → **404** (no
> existence leak) BEFORE `process_return` runs. Admin bypasses by role. This is the one place a
> mutating route enforces ownership on a body field, not a path param — pinned so the agent doesn't
> skip the pre-check.

---

## 1. Export Names Table (every symbol crossing an agent boundary)

Model↔route is an **agent boundary** (separate agents own `models/X_models.py` vs `routes/X.py`),
so every model function a route calls is a cross-boundary export.

### 1a. Infrastructure exports
| Name | Type | Defined By | Used By | Full Signature |
|------|------|-----------|---------|----------------|
| `get_db` | function | swarmlimit/database.py | ALL agents | `get_db() -> sqlite3.Connection` |
| `query` | function | swarmlimit/database.py | ALL model agents | `query(sql, params=(), one=False) -> list[dict] | dict | None` |
| `transaction` | context mgr | swarmlimit/database.py | order_models, return_models (the two class-B openers) | `transaction() -> ContextManager[sqlite3.Connection]` |
| `init_db` | function | swarmlimit/database.py | scaffold (__init__) | `init_db() -> None` |
| `error` | function | swarmlimit/__init__.py | ALL route agents | `error(code: str, status: int, **extra) -> tuple[dict, int]` |
| `login_required` | decorator | swarmlimit/auth.py | ALL route agents | `login_required(view) -> view` |
| `role_required` | decorator | swarmlimit/auth.py | ALL route agents | `role_required(*roles) -> Callable[[view], view]` |
| `current_user` | function | swarmlimit/auth.py | ALL route agents | `current_user() -> dict | None` |
| `login_user` / `logout_user` | function | swarmlimit/auth.py | auth routes | `login_user(user: dict) -> None` / `logout_user() -> None` |
| `assert_ext_ref_unique` | function | swarmlimit/refs.py | order_models, return_models (in-tx) | `assert_ext_ref_unique(conn, ext_ref) -> None  # no commit; raises ValueError` |
| `record` | function | swarmlimit/models/audit_models.py | ALL mutating route agents | `record(actor_id, action, entity_type, entity_id=None, detail=None) -> None` |
| `order_models._TX_FAULT` | module attr (smoke-only test seam) | order_models.py | swarmlimit/smoke.py (sets/resets) | `_TX_FAULT: Callable[[], None] | None = None` — default `None` (no-op); invoked as `if _TX_FAULT: _TX_FAULT()` at the checkpoint AFTER the first `order_item` insert inside `create_order`'s `transaction()`. Smoke sets it to a raising callable, drives the unit, then resets to `None`. See §5 seam. |
| `return_models._TX_FAULT` | module attr (smoke-only test seam) | return_models.py | swarmlimit/smoke.py (sets/resets) | `_TX_FAULT: Callable[[], None] | None = None` — default `None` (no-op); invoked as `if _TX_FAULT: _TX_FAULT()` at the checkpoint AFTER `add_refund_in_tx` inside `process_return`'s `transaction()`. Smoke sets a raising callable, drives the unit, then resets to `None`. See §5 seam. |

### 1b. Model-function exports (complete inventory — reconciled with §2)
| Function | Defined By | Used By (consumers = §2) |
|----------|-----------|--------------------------|
| create_user, get_user, get_user_by_email, verify_credentials | auth_models.py | routes/auth.py, swarmlimit/auth.py (INTRA-agent auth-core) |
| list_suppliers, get_supplier, create_supplier, update_supplier, delete_supplier | supplier_models.py | routes/suppliers.py; product_models.py (create_product validates supplier exists) |
| list_categories, get_category, create_category, update_category, delete_category | category_models.py | routes/categories.py |
| list_products, get_product, create_product, update_product, soft_delete_product, set_product_categories, `decrement_stock_in_tx(conn,…)`, `restock_product_in_tx(conn,…)` | product_models.py | routes/products.py; **order_models.py** (decrement_stock_in_tx, in-tx); **return_models.py** (restock_product_in_tx, in-tx) |
| list_orders, `list_orders_for(actor,…)`, get_order, `get_order_for(oid, actor)`, `order_total(conn, oid)`, `create_order(user_id, ext_ref, items)` | order_models.py | routes/orders.py; routes/returns.py (`get_order_for` ownership pre-check); **return_models.py** (`order_total` in-tx) |
| list_shipments, get_shipment, `get_shipment_for(sid, actor)`, create_shipment, advance_shipment, `set_shipment_status_in_tx(conn, sid, status)` | shipment_models.py | routes/shipments.py; **return_models.py** (set_shipment_status_in_tx, in-tx) |
| list_returns, `list_returns_for(actor)`, get_return, `get_return_for(rid, actor)`, `process_return(order_id, ext_ref, reason, refund_cents)` | return_models.py | routes/returns.py |
| list_payments, `list_payments_for(actor)`, get_payment, `get_payment_for(pid, actor)`, `refunded_total(conn, oid)`, `add_refund_in_tx(conn, oid, amount)` | payment_models.py | routes/payments.py; **return_models.py** (refunded_total + add_refund_in_tx, in-tx) |
| record, list_audit | audit_models.py | ALL mutating routes (record); scaffold __init__ (list_audit for /audit) |
| assert_ext_ref_unique | refs.py | order_models.create_order, return_models.process_return |

### 1c. Blueprints & route paths
Blueprint names = the resource name (`auth`, `suppliers`, `categories`, `products`, `orders`,
`shipments`, `returns`, `payments`), each `Blueprint('<name>', __name__)` with **no `url_prefix`**;
every route declares its FULL absolute path (= the manifest path, no trailing slash) — see §4. `/audit`
is served by the scaffold in `__init__.py` (no blueprint). Registered in `swarmlimit/__init__.py` in
the fixed order: `auth, suppliers, categories, products, orders, shipments, returns, payments`.

### 1d. Orchestration entrypoints (FC50 — every cross-boundary non-getter call, Full Signature required)
| Name | Type | Defined By | Used By | Full Signature |
|------|------|-----------|---------|----------------|
| `refs.assert_ext_ref_unique` | orchestration entrypoint | refs.py | order_models.create_order, return_models.process_return | `assert_ext_ref_unique(conn, ext_ref) -> None  # no commit` |
| `product_models.decrement_stock_in_tx` | orchestration entrypoint | product_models.py | order_models.create_order (SAME conn) | `decrement_stock_in_tx(conn, pid, qty) -> None  # no commit` |
| `product_models.restock_product_in_tx` | orchestration entrypoint | product_models.py | return_models.process_return (SAME conn) | `restock_product_in_tx(conn, pid, qty) -> None  # no commit` |
| `shipment_models.set_shipment_status_in_tx` | orchestration entrypoint | shipment_models.py | return_models.process_return (SAME conn) | `set_shipment_status_in_tx(conn, sid, status) -> None  # no commit` |
| `payment_models.add_refund_in_tx` | orchestration entrypoint | payment_models.py | return_models.process_return (SAME conn) | `add_refund_in_tx(conn, oid, amount_cents) -> int  # no commit` |
| `order_models.order_total` | orchestration entrypoint | order_models.py | return_models.process_return (refund guard, in-tx) | `order_total(conn, oid) -> int  # read-only` |
| `payment_models.refunded_total` | orchestration entrypoint | payment_models.py | return_models.process_return (refund guard, in-tx) | `refunded_total(conn, oid) -> int  # read-only` |
| `order_models.get_order_for` | orchestration entrypoint | order_models.py | routes/returns.py (POST /returns ownership pre-check) | `get_order_for(oid, actor) -> dict | None` |
| `audit_models.record` | orchestration entrypoint | audit_models.py | every mutating view | `record(actor_id, action, entity_type, entity_id=None, detail=None) -> None` |

---

## 2. Cross-Boundary Wiring Table (producer file → consumer file → import)

| Producer | Consumer | Import |
|----------|----------|--------|
| swarmlimit/database.py (`get_db`, `query`) | every model + swarmlimit/auth.py | `from swarmlimit.database import get_db, query` |
| swarmlimit/database.py (`transaction`) | **order_models.py, return_models.py ONLY** (the two class-B openers — matches §1a + §5) | `from swarmlimit.database import transaction` |
| swarmlimit/database.py (`init_db`) | swarmlimit/__init__.py (scaffold — called once if the DB file is absent) | `from swarmlimit.database import init_db` |
| swarmlimit/__init__.py (`error`) | every route | `from swarmlimit import error` |
| swarmlimit/auth.py | every route | `from swarmlimit.auth import login_required, role_required, current_user` |
| swarmlimit/refs.py | order_models.py, return_models.py | `from swarmlimit.refs import assert_ext_ref_unique` |
| swarmlimit/models/audit_models.py | every mutating route; scaffold __init__ (list_audit) | `from swarmlimit.models.audit_models import record  # or list_audit` |
| swarmlimit/models/supplier_models.py | routes/suppliers.py, product_models.py (validate supplier) | `from swarmlimit.models.supplier_models import ...` |
| swarmlimit/models/category_models.py | routes/categories.py | `from swarmlimit.models.category_models import ...` |
| swarmlimit/models/product_models.py | routes/products.py, **order_models.py** (decrement_stock_in_tx), **return_models.py** (restock_product_in_tx) | `from swarmlimit.models.product_models import ...` |
| swarmlimit/models/order_models.py | routes/orders.py, routes/returns.py (get_order_for), **return_models.py** (order_total) | `from swarmlimit.models.order_models import ...` |
| swarmlimit/models/shipment_models.py | routes/shipments.py, **return_models.py** (set_shipment_status_in_tx) | `from swarmlimit.models.shipment_models import ...` |
| swarmlimit/models/return_models.py | routes/returns.py | `from swarmlimit.models.return_models import ...` |
| swarmlimit/models/payment_models.py | routes/payments.py, **return_models.py** (refunded_total + add_refund_in_tx) | `from swarmlimit.models.payment_models import ...` |
| swarmlimit/models/order_models.py (`_TX_FAULT`) + swarmlimit/models/return_models.py (`_TX_FAULT`) | swarmlimit/smoke.py (fault-injection seam — sets a raising callable at the owner's checkpoint, resets to `None` after) | `import swarmlimit.models.order_models as om; om._TX_FAULT = <raiser>` (and likewise `return_models`); default `None` in production. See §5 seam. |

**Densest coupling (Feed-Forward risk):** `return_models.py` imports FOUR peer models
(product `restock_product_in_tx`, shipment `set_shipment_status_in_tx`, payment `refunded_total`+
`add_refund_in_tx`, order `order_total`) — the `process_return` 4-table atomic unit. `order_models.py`
imports product (`decrement_stock_in_tx`) + refs. These two in-tx call chains are where a
return-shape / class-(C) / conn-threading drift bites hardest.

---

## 3. Input Validation Prescriptions (every mutating route + typed URL param)

| Route | Input | Validation | Error Response |
|-------|-------|-----------|----------------|
| POST /auth/register | email, password, name (role IGNORED) | email non-empty + `@`; password ≥ 8. **Public registration ALWAYS creates a `customer`:** the route ignores/overrides any client-supplied `role` and calls `create_user(..., role='customer', ...)` — a client can NEVER self-register as `admin`. The seeded `admin@swarm.test` (init_db) is the ONLY bootstrap-admin mechanism; there is no "first user forced admin" runtime path. | 400 `validation` |
| POST /auth/login | email, password | both non-empty | 401 `auth` (no field leak) |
| POST /auth/logout | (header only) | `X-CSRF-Token` matches session | 400 `csrf`; else 200 |
| POST /suppliers | name | name non-empty | 400 `validation` |
| PATCH /suppliers/<int:sid> | name?, contact_email?, active? | at least one whitelisted field; active ∈ {0,1} | 400 / 404 if absent |
| DELETE /suppliers/<int:sid> | (path) | supplier exists | 404 if absent; **409 `conflict`** if products reference it (FK RESTRICT → ValueError) |
| POST /categories | name | name non-empty | 400; **409 `conflict`** on duplicate name |
| PATCH /categories/<int:cid> | name | `name` supplied AND non-empty | 400 `validation` on invalid/empty; 404 if category absent; **409 `conflict`** on duplicate name (UNIQUE) |
| DELETE /categories/<int:cid> | (path) | category exists | 404; **409 `conflict`** if referenced |
| POST /products | sku, name, supplier_id, price_cents, stock?, category_ids? | sku+name non-empty; supplier exists; price_cents ≥ 0 int; stock ≥ 0 int; category_ids all exist | 400; 409 on dup sku |
| PATCH /products/<int:pid> | whitelist name/price_cents/stock/supplier_id | types as above | 400 / 404 |
| DELETE /products/<int:pid> | (path) | product id exists (live OR already soft-deleted) | **404 only if the product id never existed**; an already-soft-deleted product → **200** (idempotent no-op, per `soft_delete_product`'s declared contract); a live product → **200** (sets `deleted_at`) |
| PUT /products/<int:pid>/categories | category_ids | list of existing category ids | 400 / 404 |
| POST /orders | ext_ref, items (`[{product_id,qty}]`), user_id? | ext_ref non-empty; items non-empty; each qty > 0 int; each product_id int. **`user_id` resolution:** if omitted → the current actor's id (both roles); a customer is ALWAYS forced to their own id (any supplied `user_id` ignored); only an admin may pass an explicit `user_id` to place on another user's behalf | 400 `validation`; **409 `conflict`** on ext_ref collision OR insufficient stock OR unavailable product (in-tx guards raise) |
| POST /orders/<int:oid>/shipments | carrier?, tracking? | order exists; order has no shipment yet | 404 if order absent; **409 `conflict`** if the order already has a shipment (`UNIQUE(order_id)` → `ValueError('shipment exists')`); 201 on create |
| POST /shipments/<int:sid>/advance | to_status | `to_status ∈ {pending,shipped,delivered,returned}` (any STORED status is syntactically valid input; an unknown string → 400). Transition **legality** is decided by `advance_shipment` against `LEGAL_TRANSITIONS`, NOT here. | 400 `validation` on an unknown status; **409 `conflict`** if `(current,to_status) ∉ LEGAL_TRANSITIONS` (incl. every `→returned`, `delivered→pending`, and `pending→delivered` skip), status unchanged |
| POST /returns | order_id, ext_ref, reason?, refund_cents | order_id resolves via `get_order_for` (else 404); ext_ref non-empty; **refund_cents > 0 int** (a return always refunds a positive amount; `≤ 0` → 400) | 400 `validation`; 404 if non-owner/absent order; **409 `conflict`** on ext_ref collision / shipment-not-delivered / refund-exceeds-original |
| GET/DELETE typed params `<int:...>` | — | Flask 404 on non-int | 404 |

**Global:** every **authenticated** `POST/PUT/PATCH/DELETE` validates `X-CSRF-Token` against the session
→ **400 `csrf`** on mismatch (before_request); an **anonymous** mutating request returns **401 `auth`**
first (auth precedes CSRF — see App Configuration). Unknown row id on any GET detail → 404. Every request body is
parsed as JSON; a non-JSON/absent body on a mutating route → 400 `validation`.

---

## 4. Coordinated Behaviors (must be consistent across all agents)

- **Blueprint registration & path convention (pinned — the ONE rule; makes every
  `request.url_rule.rule` equal its manifest path EXACTLY):** all blueprints registered in
  `swarmlimit/__init__.py` in the fixed order `auth, suppliers, categories, products, orders,
  shipments, returns, payments`. **NO blueprint uses `url_prefix`** — each is
  `bp = Blueprint('<name>', __name__)` and EVERY `@bp.route(...)` declares the **FULL absolute path
  exactly as written in the Route Table = the manifest** (auth → `@bp.route('/auth/register', ...)`;
  suppliers → `'/suppliers'` and `'/suppliers/<int:sid>'`). This eliminates BOTH failure modes: no
  double-prefix (`/auth/auth/register` cannot arise — there is no prefix) and **no collection
  trailing-slash** (a collection is declared `'/suppliers'`, NEVER `'/suppliers/'`, so its rule has no
  trailing slash). Leave `strict_slashes` at Flask's default; since no declared path carries a trailing
  slash, no `/suppliers/` rule is ever registered. `/audit` is served directly by the scaffold (full
  absolute path, no blueprint). The `shipments` blueprint is **no longer special** — like every other
  it has no prefix; it simply declares routes under two roots (`/orders/<int:oid>/shipments` and
  `/shipments/...`).
- **Response envelope:** success bodies are always a JSON **object** (never a bare list); list
  endpoints wrap under a named key (`{"orders":[...]}`, `{"products":[...]}`, etc.). Error bodies are
  `{"error": <code>, ...}` via the shared `error(...)` helper. HTTP status codes per §1a/§3.
- **CSRF:** header `X-CSRF-Token` on every **authenticated** mutating request, minted at login, returned
  in the login response body as `csrf_token`. CSRF is enforced ONLY for authenticated mutating requests;
  an anonymous mutating request returns **401 `auth`** (auth precedes CSRF), not 400 `csrf`. One
  convention repo-wide.
- **Auth failure codes (precedence pinned):** anonymous on a protected route → **401** `auth` — **even a
  mutating one** (401 `auth` takes precedence over 400 `csrf`, so a worker never has to choose
  heuristically); wrong role → **403** `forbidden`; non-owner on a `role+own` READ → **404** `not_found`
  (existence hidden). One convention repo-wide (see §6).
- **Money:** integer cents everywhere; never float. Totals computed at read time
  (`SUM(order_items)`), never stored.
- **Datetime:** ISO-8601 TEXT (UTC) via `datetime('now')`.
- **Audit:** every create/update/delete/advance/return **view** (route) calls
  `audit_models.record(...)` exactly once, **AFTER** the model call returns and has committed —
  **never inside a `transaction()`, never from a model writer** (FC5/FC6). This guarantees the audit
  insert cannot commit-nested inside the `create_order`/`process_return` atomic units.
- **In-tx helper discipline (FC29/FC6):** the seven in-tx helpers — **four write** helpers
  (`decrement_stock_in_tx`, `restock_product_in_tx`, `set_shipment_status_in_tx`, `add_refund_in_tx`),
  **one read-only uniqueness guard** (`assert_ext_ref_unique` — a SELECT that raises on collision,
  writes nothing), and **two read-only total** helpers (`order_total`, `refunded_total`) — ALL take a
  caller `conn`, do NOT commit, and are called ONLY from within a class-B `transaction()`. No model
  writer opens a bare `conn.commit()` inside these.

---

## 5. Transaction Contracts (every DB writer annotated — ported from lesson-studio §5)

Three writer classes — every DB-writing function is in exactly one:

**(A) Persist immediately via SQLite autocommit (self-contained single logical write; no `conn.commit()`, no `transaction()`):** `create_user`, `create_supplier`,
`update_supplier`, `delete_supplier`, `create_category`, `update_category`, `delete_category`,
`create_product`, `update_product`, `soft_delete_product`, `set_product_categories`,
`create_shipment`, `advance_shipment`, `record`. Each executes its single `INSERT/UPDATE/DELETE`
directly on the request connection; under `isolation_level=None` **AUTOCOMMIT** that statement
persists **immediately** — NO explicit `BEGIN`/`COMMIT`/`ROLLBACK` is issued or needed, and a class-A
writer NEVER opens `transaction()` (that is class-B only). Where a class-A creator writes more than
one row (`create_product` + its M2M links, `set_product_categories`) each statement autocommits
independently — these are **NOT** atomicity-critical (only the two class-B units are); the route
validates referenced ids up front (§3) so a mid-write FK failure is avoided.

**(B) Own ONE explicit `transaction()` internally (BEGIN IMMEDIATE; commit as one atomic unit):**
exactly TWO — each opens `with transaction() as conn:` itself and threads that SAME `conn` into its
in-tx helpers; the ROUTE just calls them and never manages a transaction:
- `order_models.create_order(user_id, ext_ref, items)` — `assert_ext_ref_unique(conn,…)` → insert
  order → per item: re-read product (live?) + `decrement_stock_in_tx(conn,…)` + insert order_item.
  Touches {orders, order_items, products.stock}. Rolls back the whole unit on any raise.
- `return_models.process_return(order_id, ext_ref, reason, refund_cents)` —
  `assert_ext_ref_unique(conn,…)` → select the order's UNIQUE shipment (`UNIQUE(order_id)` ⇒ at most one) → require it exists and is `delivered` → refund guard
  (`refunded_total(conn,…) + refund_cents ≤ order_total(conn,…)`) → insert return →
  `set_shipment_status_in_tx(conn, sid, 'returned')` → per item `restock_product_in_tx(conn,…)` →
  `add_refund_in_tx(conn, oid, refund_cents)`. Touches {returns, shipments.status, products.stock,
  payments}. Rolls back all four on any raise.

**Fault-injection seam (smoke-only — enables the TRUE mid-transaction rollback proofs):** each class-B
owner module defines a module-level hook `_TX_FAULT = None` and, at a designated checkpoint INSIDE its
`with transaction() as conn:` block, runs `if _TX_FAULT: _TX_FAULT()`. Checkpoints: `create_order`
invokes it immediately AFTER the FIRST `order_item` insert (+ that item's stock decrement);
`process_return` invokes it immediately AFTER `add_refund_in_tx` (the last of the four writes), before
the block exits. In production `_TX_FAULT is None` → a no-op. Smoke sets `<owner>._TX_FAULT` to a
raising callable, drives the unit, asserts the exception propagated OUT of the `with` block (→ the
context manager's `ROLLBACK`), then resets it to `None`. This is the ONLY way to prove rollback of a
PARTIALLY-written unit; the pre-write guards (refund>original, shipment-not-delivered, ext_ref
collision) fail BEFORE any write and so prove the guard, not the rollback.

**(C) In-tx helpers — take a caller `conn`, do NOT commit, NEVER called outside a class-(B)
transaction (SEVEN total):** **four write** helpers — `product_models.decrement_stock_in_tx`,
`product_models.restock_product_in_tx`, `shipment_models.set_shipment_status_in_tx`,
`payment_models.add_refund_in_tx`; **one read-only uniqueness guard** — `refs.assert_ext_ref_unique`
(a SELECT that raises on collision, writes nothing); and **two read-only total** helpers —
`order_models.order_total`, `payment_models.refunded_total`. All seven take a caller `conn` and never
commit.

**Audit is NOT a writer class here:** `audit_models.record` (class A) is called only by the ROUTE,
post-commit — never nested inside a class-(B) transaction.

**Invariant (order total):** always `SUM(order_items.qty*unit_price_cents)` computed at read — never
a stored column — so a partial item write can never desync a persisted total.

**Invariant (refund bounds — lower AND upper):** every refund is strictly positive and cumulative
refunds never exceed the original, i.e. `0 < refund_cents` (per-refund) AND
`SUM(payments.amount_cents WHERE kind='refund' for order) ≤ order_total(order)` at all times. The
lower bound is enforced by the route + the `returns.refund_cents > 0` / `payments.amount_cents > 0`
CHECKs (agreeing rules); the upper bound by `process_return`'s in-tx guard. `payments` is refund-only
(schema CHECK `kind IN ('refund')`).

**Accepted simplification (human P0 pass, 2026-07-21) — restock is full but refund may be partial:**
`process_return` always restocks the ENTIRE order (every `order_item`) while `refund_cents` may be any
amount `≤ order_total`, so the "goods returned" and "money refunded" figures are permitted to differ.
This is intentional for a throwaway stress-test vehicle (no real money/inventory) and is bounded to at
most ONCE per order — once a return sets the shipment to `returned`, the state machine forbids a second
return of the same order (no double-restock). Flagged for the human pass; would be tidied (link restock
to the refunded fraction) only if this app ever became real.

**Invariant (ext_ref cross-resource uniqueness):** no `ext_ref` value appears in `orders` ∪
`returns`. Enforced by `refs.assert_ext_ref_unique` inside both class-B transactions (BEGIN IMMEDIATE
serializes concurrent inserters); the per-table `UNIQUE` constraints are intra-table backstops.
**Retry-safety (idempotency-on-retry) corollary:** because the transaction is all-or-nothing (a crash
before `COMMIT` leaves nothing persisted) AND `ext_ref` must be globally unique, a client that
re-submits the SAME `create_order`/`process_return` after an uncertain outcome is safe either way: if
the first attempt committed, the retry hits the uniqueness guard → **409** (no duplicate); if it did
not commit, the retry succeeds cleanly. No duplicate row and no lost write can result from a retry.

**Invariant (one shipment per order):** `shipments.order_id` is `UNIQUE`, so an order has **at most
one** shipment for its entire lifetime. `create_shipment` raises `ValueError('shipment exists')` → 409
on a second attempt (including after the shipment has been advanced to `returned`), so no one can mint a
fresh shipment to bypass the once-per-order return bound. This is what lets `process_return` speak of
"the order's shipment" unambiguously and backstops the restock-once guarantee below.

**Invariant (shipment state machine):** `shipments.status` only ever follows
`pending→shipped→delivered` (via `advance_shipment`) or `delivered→returned` (via `process_return`
only). No other transition is reachable; illegal `advance_shipment` calls raise and leave status
unchanged.

---

## 6. Authorization Matrix (every protected route)

| Route | Mode | Rule |
|-------|------|------|
| POST /auth/register, /auth/login | public | anonymous allowed. **register ALWAYS creates a `customer`** (supplied `role` ignored → `create_user(role='customer')`); a client can never self-promote to admin — the seeded `admin@swarm.test` is the only bootstrap admin |
| POST /auth/logout | auth | any logged-in |
| GET /suppliers, /suppliers/<int:sid>, /categories(+<cid>), /products(+<pid>) | auth | any logged-in may browse catalog |
| POST/PATCH/DELETE /suppliers, /categories, /products (+ PUT categories) | admin | admin only |
| GET /orders (list) | role+own | `list_orders_for(actor)` — customer→own, admin→all |
| POST /orders | auth | `user_id` omitted → current actor's id (both roles); customer ALWAYS forced to self (supplied `user_id` ignored); admin may override with an explicit `user_id` |
| GET /orders/<int:oid> | role+own | `get_order_for(oid, actor)` → None → **404** for non-owner |
| POST /orders/<int:oid>/shipments | admin | staff create shipments |
| GET /shipments/<int:sid> | role+own | `get_shipment_for(sid, actor)` (transitive via order) → **404** for non-owner |
| POST /shipments/<int:sid>/advance | admin | staff advance fulfillment (state machine) |
| GET /returns (list) | role+own | `list_returns_for(actor)` — customer→own, admin→all |
| POST /returns | role+own | order resolved via `get_order_for(order_id, actor)`; non-owner → **404** BEFORE `process_return` |
| GET /returns/<int:rid> | role+own | `get_return_for(rid, actor)` → None → **404** |
| GET /payments (list), /payments/<int:pid> | role+own | `list_payments_for` / `get_payment_for` (transitive via order) → **404** |
| GET /audit | admin | admin-only (scaffold-hosted) |

**404-not-403 rule (run-080 IDOR lesson):** every `role+own` **read** returns 404 for a non-owner,
enforced by the ownership-scoped `*_for(actor,…)` getters returning `None`/`[]` (0 rows) →
`error('not_found',404)` — NOT a post-fetch conditional. The one `role+own` **write** on a body
field (`POST /returns`) guards via `get_order_for(order_id, actor)` → 404 before mutating. Admin
bypasses ownership by role. Anonymous → **401** (even on a mutating route — 401 `auth` precedes 400
`csrf`); wrong role on an admin route → **403**. CSRF (400) is checked only AFTER a request is
authenticated.

---

## Acceptance Tests (EARS) — verified by `swarmlimit/smoke.py`, run as `python -m swarmlimit.smoke` (imports `from swarmlimit import create_app`, temp DB at a not-yet-existing child path of a `TemporaryDirectory` so `init_db()` runs once)

### Happy Path
- WHEN a new user registers with a valid email + password (≥8) THE SYSTEM SHALL create the user and return **201**.
- WHEN valid credentials are submitted THE SYSTEM SHALL establish a session and return **200** with a `csrf_token` in the body.
- WHEN an admin creates a supplier→product THE SYSTEM SHALL persist it and list it at `GET /products` (excluding any soft-deleted).
- WHEN `create_order` succeeds THE SYSTEM SHALL commit orders+order_items+products.stock **atomically** (audit recorded post-commit); the response asserts integer ids and NO `{'`/`[object Object]` in the JSON. — smoke value assertions.
- WHEN two `create_order` calls race the last unit of stock THE SYSTEM SHALL let exactly one succeed, the other → **409** `conflict` (`insufficient stock`), final stock non-negative and correct. — smoke concurrency case.
- WHEN a forced failure fires (via `order_models._TX_FAULT`) AFTER the first item write but BEFORE commit THE SYSTEM SHALL roll back the whole unit — `COUNT(orders)`/`COUNT(order_items)` unchanged AND every affected product `stock` VALUE unchanged (UPDATE rollback = value compare). — smoke `create_order` mid-tx rollback case.
- **(Path B — state-machine)** WHEN a shipment is advanced `pending→shipped` then `shipped→delivered` THE SYSTEM SHALL update status and record audit. — `python -m swarmlimit.smoke --case state-machine-legal; echo $?` → 0.
- **(Path B — uniqueness)** WHEN an `ext_ref` is unique across orders+returns THE SYSTEM SHALL accept and persist it. — `python -m swarmlimit.smoke --case uniqueness-ok; echo $?` → 0.
- **(Path B — soft-delete)** WHEN a product is soft-deleted THE SYSTEM SHALL set `deleted_at`, exclude it from `GET /products`, and preserve historical `order_items` referencing it. — `python -m swarmlimit.smoke --case soft-delete; echo $?` → 0.
- **(Path B — 2nd transaction)** WHEN `process_return` succeeds THE SYSTEM SHALL atomically insert the return, set the delivered shipment `status='returned'`, restock every order_item's product, and insert a `payments` refund — all four visible together. — `python -m swarmlimit.smoke --case process-return; echo $?` → 0.

### Error Cases
- **(Path B — state-machine)** WHEN an illegal transition is attempted THE SYSTEM SHALL return **409** and leave `status` unchanged — proven for ALL of: (a) `delivered→pending` (status stays `delivered`); (b) `pending→delivered` skipping `shipped` (status stays `pending`); (c) `advance`→`returned` from EVERY source status `∈{pending,shipped,delivered}` (status stays the source). — `python -m swarmlimit.smoke --case state-machine-illegal; echo $?` → 0.
- **(Path B — uniqueness)** WHEN a return reuses an existing order's `ext_ref` THE SYSTEM SHALL return **409** and create no return row. — `python -m swarmlimit.smoke --case uniqueness-collision; echo $?` → 0 (asserts 409 + `COUNT(returns)` unchanged).
- **(Path B — soft-delete)** WHEN `create_order` references a soft-deleted product THE SYSTEM SHALL reject (**409** `conflict`, product unavailable) and create no order/items/stock change. — `python -m swarmlimit.smoke --case soft-delete-order; echo $?` → 0.
- **(Path B — 2nd transaction ROLLBACK, real mid-tx)** WHEN a forced exception fires INSIDE `process_return` AFTER `add_refund_in_tx` but before the transaction commits THE SYSTEM SHALL roll back all four writes — `COUNT(returns)`/`COUNT(payments)` unchanged AND the shipment `status` VALUE still `'delivered'` AND every product `stock` VALUE unchanged. — `python -m swarmlimit.smoke --case process-return-rollback; echo $?` → 0.
- **(Path B — refund guard, pre-write)** WHEN `process_return` is called with `refund_cents` exceeding the order's remaining original amount THE SYSTEM SHALL return **409** `conflict` and write nothing (guard fires before any write). — `python -m swarmlimit.smoke --case process-return-guard-refund; echo $?` → 0.
- **(Path B — state guard, pre-write)** WHEN `process_return` is called for an order whose shipment is NOT `delivered` THE SYSTEM SHALL return **409** `conflict` and write nothing. — `python -m swarmlimit.smoke --case process-return-guard-shipment; echo $?` → 0.
- WHEN a customer requests another customer's `GET /orders/<int:oid>` THE SYSTEM SHALL return **404** (not 403).
- WHEN a customer POSTs to an admin route (e.g. `POST /products`) THE SYSTEM SHALL return **403**.
- WHEN a public `POST /auth/register` body supplies `role: admin` THE SYSTEM SHALL create a **customer** and return **201** (registration does NOT establish a session); AND WHEN that user then `POST /auth/login`s with those credentials and, with the login-issued `csrf_token`, `POST`s an admin-only route (e.g. `POST /products`) THE SYSTEM SHALL return **403** — a client can never self-promote. — default-smoke security assertion (a core smoke case, NOT one of the ten Path-B `--case`s).
- WHEN an anonymous request hits a protected route — **including a mutating one (POST/PUT/PATCH/DELETE)** — THE SYSTEM SHALL return **401** `auth` (auth precedes CSRF; an anonymous mutation is never a 400 `csrf`).
- WHEN an **authenticated** mutating request omits/mismatches `X-CSRF-Token` THE SYSTEM SHALL return **400** `csrf`.
- WHEN `SECRET_KEY` is unset and `FLASK_ENV != development` THE SYSTEM SHALL refuse to start. — smoke asserts `create_app()` raises.
- WHEN `DELETE /suppliers/<int:sid>` targets a supplier with products THE SYSTEM SHALL return **409** `conflict` (FK RESTRICT) and delete nothing.
- WHEN a second `POST /orders/<int:oid>/shipments` is issued for an order that already has a shipment THE SYSTEM SHALL return **409** `conflict` (`UNIQUE(order_id)`) and create no shipment row — including after the first shipment has been advanced to `returned` (no fresh shipment can be minted to permit a second return). — default-smoke integrity assertion (a core smoke case, NOT one of the ten Path-B `--case`s).

### Verification Commands
- `python -m swarmlimit.smoke` — full happy-path + all 10 Path-B `--case`s + IDOR-404 + atomicity + concurrency + CSRF + SECRET_KEY suite. Writes `<R>/c2-smoke-report.md`. (Assembly C2 step also runs `python -m swarmlimit.smoke --manifest <R>/planned-manifest.json`.)
- `python -m compileall swarmlimit` — byte-compile every module INCLUDING `swarmlimit/smoke.py` (parse check; NOT `python3 -c`, per repo Bash rules). This is the **Wave-0 gate** (parse-only, since a full import of `swarmlimit` can't succeed until routes exist post-assembly).
- Contract check (Step 9w.6) + ownership gate + assembly are enforced by the swarm pipeline.

---

## The 10 Path-B `--case` harness (`swarmlimit/smoke.py` owns; C2 + Path-B EARS both depend on it)

`swarmlimit/smoke.py` exposes `--case <name>` (run as `python -m swarmlimit.smoke --case <name>`)
returning exit 0 on pass, non-0 on fail. The ten cases (each an independent Path-B EARS proof):

| `--case` | Proves | Asserts |
|----------|--------|---------|
| `state-machine-legal` | legal advance | pending→shipped→delivered each 200; audit rows written |
| `state-machine-illegal` | illegal advance guarded (ONE case, three sub-checks — each asserts 409 AND status preserved) | (a) `delivered→pending` → 409 AND status still `delivered`; (b) `pending→delivered` (skip `shipped`) → 409 AND status still `pending`; (c) for EVERY source status `s ∈ {pending,shipped,delivered}`, `advance`→`returned` → 409 AND status still `s`. All via `POST /shipments/<int:sid>/advance`. |
| `uniqueness-ok` | ext_ref accepted | distinct ext_ref on order then return → both persist |
| `uniqueness-collision` | cross-resource uniqueness | return reusing an order's ext_ref → 409; `COUNT(returns)` unchanged |
| `soft-delete` | soft-delete semantics | delete → `deleted_at` set; absent from `GET /products`; prior order_items still present |
| `soft-delete-order` | create_order rejects deleted | order referencing a deleted product → 409; no order/items/stock delta |
| `process-return` | 4-table atomic commit | return row + shipment `returned` + stock restocked + refund row all present together |
| `process-return-rollback` | 4-table atomic ROLLBACK (real mid-tx) | set `return_models._TX_FAULT` to raise AFTER `add_refund_in_tx`; drive a VALID `process_return`; the raise propagates → `ROLLBACK`. Asserts `COUNT(returns)` + `COUNT(payments)` unchanged (INSERT rollback) AND the shipment `status` VALUE still `'delivered'` AND every restocked product `stock` VALUE unchanged (UPDATE rollback — value compare, not count). Resets `_TX_FAULT=None` after. |
| `process-return-guard-refund` | pre-write refund guard (409, zero writes) | `refund_cents` exceeding the order's remaining original → 409 `conflict` (`refund exceeds original`); `COUNT(returns)`/`COUNT(payments)` unchanged, shipment `status` + product `stock` VALUES unchanged (guard fires BEFORE any write) |
| `process-return-guard-shipment` | pre-write state guard (409, zero writes) | `process_return` on an order whose shipment is NOT `delivered` → 409 `conflict` (`shipment not delivered`); same zero-write assertions |

Plus the non-Path-B core cases (default `python -m swarmlimit.smoke` run): manifest-equality (planned == exercised),
create_order value assertions, create_order concurrency stock-race, create_order mid-tx rollback (via
`order_models._TX_FAULT` after the first item write — value-compares stock), IDOR-404, admin-403,
anon-401, CSRF-400, SECRET_KEY fail-closed, **register-role-ignored** (public `POST /auth/register`
with `role=admin` → a `customer` account, **201, no session**; smoke then `POST /auth/login`s with those
credentials, reads `csrf_token` from the login body, and `POST`s an admin route with it → **403**),
**shipment-unique** (a 2nd
`POST /orders/<oid>/shipments` for an order that already has a shipment → 409 `conflict`, no row
created, including after the first shipment is `returned`). These two are default-smoke security/
integrity assertions, NOT additions to the ten Path-B `--case`s.

---

## Immutable Planned Manifest (frozen pre-spawn → `<R>/planned-manifest.json`)

`<R>` = `docs/reports/<run-id>/` (skill-computed id — **currently would be 083**; `docs/reports/082/`
already exists from the identity spike, so the launch guard MUST assert `<R>` is ABSENT before
freezing). The canonical manifest content is below; at launch, Wave-0's smoke-author writes it to
`<R>/planned-manifest.json` and computes `content_hash` = SHA-256 over the canonicalized JSON with the
`content_hash` field removed. `smoke.py`'s manifest-equality check compares the **exercised**
(method,path) set against `endpoints` and fails on any `planned_minus_exercised` or
`exercised_minus_planned` delta.

> **Exercised-set capture pin (closes a manifest false-green):** the exercised set MUST be built from
> what smoke ACTUALLY drove, per request — NOT inferred. After each request the suite issues, record
> the exact pair `(request.method, request.url_rule.rule)` for the rule Flask matched (register a
> Flask `after_request` that appends this pair to a module-level set; skip requests where
> `request.url_rule is None` — e.g. a 404 that matched no rule). `request.url_rule.rule` is the
> rule-template form (`/suppliers/<int:sid>`) and the manifest `endpoints[].path` uses that same
> converter syntax, so the comparison is rule-form vs rule-form (well-defined; a concrete URL like
> `/suppliers/5` is never compared). **Do NOT** infer the exercised set by intersecting a global set
> of driven HTTP methods with every `app.url_map` rule — that would credit routes the suite never
> actually hit (a false-green). Each of the 31 manifest endpoints must appear in the per-request set,
> or C2 fails on the delta.

```json
{
  "run": "swarmlimit",
  "resources": ["users","suppliers","categories","products","product_categories",
                "orders","order_items","shipments","returns","payments","audit_logs"],
  "endpoints": [
    {"method":"POST","path":"/auth/register"},
    {"method":"POST","path":"/auth/login"},
    {"method":"POST","path":"/auth/logout"},
    {"method":"GET","path":"/suppliers"},
    {"method":"POST","path":"/suppliers"},
    {"method":"GET","path":"/suppliers/<int:sid>"},
    {"method":"PATCH","path":"/suppliers/<int:sid>"},
    {"method":"DELETE","path":"/suppliers/<int:sid>"},
    {"method":"GET","path":"/categories"},
    {"method":"POST","path":"/categories"},
    {"method":"GET","path":"/categories/<int:cid>"},
    {"method":"PATCH","path":"/categories/<int:cid>"},
    {"method":"DELETE","path":"/categories/<int:cid>"},
    {"method":"GET","path":"/products"},
    {"method":"POST","path":"/products"},
    {"method":"GET","path":"/products/<int:pid>"},
    {"method":"PATCH","path":"/products/<int:pid>"},
    {"method":"DELETE","path":"/products/<int:pid>"},
    {"method":"PUT","path":"/products/<int:pid>/categories"},
    {"method":"GET","path":"/orders"},
    {"method":"POST","path":"/orders"},
    {"method":"GET","path":"/orders/<int:oid>"},
    {"method":"POST","path":"/orders/<int:oid>/shipments"},
    {"method":"GET","path":"/shipments/<int:sid>"},
    {"method":"POST","path":"/shipments/<int:sid>/advance"},
    {"method":"GET","path":"/returns"},
    {"method":"POST","path":"/returns"},
    {"method":"GET","path":"/returns/<int:rid>"},
    {"method":"GET","path":"/payments"},
    {"method":"GET","path":"/payments/<int:pid>"},
    {"method":"GET","path":"/audit"}
  ],
  "transactions": [
    {"name":"create_order","owner":"order_models","tables":["orders","order_items","products.stock"],
     "in_tx_calls":["refs.assert_ext_ref_unique","product_models.decrement_stock_in_tx"],
     "guards":["ext_ref_unique_across_orders_returns","product_live_not_soft_deleted","stock>=qty"]},
    {"name":"process_return","owner":"return_models","tables":["returns","shipments.status","products.stock","payments"],
     "in_tx_calls":["refs.assert_ext_ref_unique","order_models.order_total","payment_models.refunded_total",
                    "shipment_models.set_shipment_status_in_tx","product_models.restock_product_in_tx",
                    "payment_models.add_refund_in_tx"],
     "guards":["ext_ref_unique_across_orders_returns","shipment_status==delivered","refunded_total+refund<=order_total"]}
  ],
  "content_hash": "SHA256-COMPUTED-AT-FREEZE"
}
```

---

## Projected Roster (Path B, honest — count is a byproduct, NOT a target; run-plan I1 is NON-gating)

**Wave 0 — shared surface (5, single-owner; R1 split so no agent is overloaded):**
scaffold · database · auth-core · **shared-services** (`refs.py` ext_ref owner + `audit_models.py`) ·
**smoke-author** (`swarmlimit/smoke.py` + freezes `<R>/pitfalls-baseline.txt`).

**Wave 1 — MODEL layer (7, parallel):**
supplier · category · product · order(+order_items) · shipment · return · payment.

**Wave 2 — ROUTES layer (7, parallel):**
suppliers · categories · products · orders · shipments · returns · payments. (`/audit` read is
scaffold-hosted — no route agent.)

**Tail (~3):** disconfirmer (Opus) · self-audit (Sonnet) · verify-harvest.

**Projected build agents ≈ 19; with tail ≈ 22.** This is BELOW the 31 record. Per the run-plan's own
rules this is acceptable: **I1 (>31) is instrumentation-only and MUST NOT be padded to clear.** The
Path-B value case rests on **contradiction-type richness** (state-machine + cross-resource uniqueness
+ soft-delete + a second 4-table transaction = a denser harvest surface per agent) and the 3-barrier
wave stress, NOT raw count. ⚠️ **Open sizing note (surface to Alex):** if genuinely clearing 31 is
wanted, it must be EARNED with additional *distinct* contradiction types (e.g. a coupon/discount
pricing interaction, a purchased-only review constraint), not clones — a decision for the launch
session, out of scope for spec convergence. See the run-plan §Sizing.

---

## Convergence Handoff (this phase — Plan Review)

This spec is a **complete draft, convergence-ready** — all six mandatory contract sections, Model
Functions, Route Table, EARS, the 10 Path-B `--case`s, and the planned manifest are present. It is
**NOT yet launch-ready.**

**Convergence loop (pre-spawn blocker):** Claude Code (structure) → **Codex (contradictions, FRESH
context — paste the FULL spec contents; the file is untracked so a path won't work)** → NotebookLM
(only if external data is referenced — swarmlimit has NONE, so NotebookLM is N/A this run) → fix →
Codex clean → **human structural P0 pass (Alex — non-optional cross-section field-matching)** → flip
`status: draft`→`active` → then 9w.5/9w.6/contract/smoke at launch. **Convergence criterion: Codex
clean AND human finds zero P0s.**

**Codex review prompt (paste to Codex, fresh context, WITH the full spec pasted above it):**
> Review this ~JSON-API Flask/SQLite swarm spec for the biggest high-value unattended
> autopilot-swarm run (manual /autopilot; Path B). Hunt specifically for **cross-section
> contradictions (P0s)** — each section is internally plausible; the risk is incompatibility ACROSS
> sections:
> 1. Any model-function signature in §Model Functions that disagrees with its row in §1 Export Names
>    or its use in §2 Cross-Boundary Wiring (esp. the in-tx helpers' `conn` arg + no-commit).
> 2. Any writer whose §5 class (A commit-internally / B owns-one-transaction / C in-tx-no-commit)
>    contradicts its Model-Functions signature — esp. the class-B pair (`create_order`,
>    `process_return`) and their class-C helpers (`assert_ext_ref_unique`, `decrement_stock_in_tx`,
>    `restock_product_in_tx`, `set_shipment_status_in_tx`, `add_refund_in_tx`) + the two read-only
>    in-tx helpers (`order_total`, `refunded_total`).
> 3. Any route in §Route Table missing from §6 Authorization Matrix or §3 Input Validation (or
>    vice-versa); any auth-mode mismatch (esp. the `POST /returns` body-field ownership pre-check and
>    the customer-forced-`user_id` on `POST /orders`).
> 4. Any FK edge in §Database Schema whose on-delete policy contradicts §5/the FK-policy prose; any
>    `*_id` integer column missing `REFERENCES` (FC46).
> 5. The ext_ref cross-resource uniqueness: is a single owner (`refs.assert_ext_ref_unique`, called
>    in BOTH class-B tx) genuinely sufficient, or can a concurrent order+return with the same ext_ref
>    slip past (BEGIN IMMEDIATE serialization)? Do the per-table UNIQUE backstops conflict with it?
> 6. process_return's refund guard: is "original payment = order_total (SUM items)" consistent
>    everywhere (create_order writes NO payments row)? Can cumulative refunds exceed the order total?
> 7. The shipment state machine: is `→returned` truly unreachable via `advance_shipment` and
>    reachable ONLY via `process_return` (from `delivered`)? Any transition the LEGAL_TRANSITIONS set
>    + the process_return path together make illegal-but-reachable or legal-but-unreachable?
> 8. The 10 `--case`s vs the EARS vs the manifest: is every Path-B EARS backed by exactly one
>    executable `--case`, and does the manifest's endpoint set match §Route Table exactly (so
>    manifest-equality can't false-green)?
> Return P0/P1/P2. P0 = a cross-section contradiction that would make a worker invent a heuristic, a
> bypassed gate, or a Path-B proof that can't actually run.

---

## Feed-Forward

- **Hardest decision:** defining "original payment" for the refund guard WITHOUT adding a `charge`
  payments row to `create_order` (which would have contradicted the run-plan's create_order EARS
  enumeration of {orders, order_items, stock}). Resolved: original = `order_total` (SUM items, the
  single source of truth); `payments` is a refund-only ledger. This keeps create_order faithful to
  the run-plan while still giving `process_return` a real, guarded financial invariant.
- **Rejected alternatives:** (a) HTML/Jinja app like lesson-studio — cut (pure overhead for
  status-code-shaped stressors; removes 4 Jinja-class FCs); (b) a `charge` payment row in
  create_order — cut (contradicts run-plan EARS; order_total suffices as the refund reference);
  (c) padding resources (coupons/reviews) to force count >31 — rejected (run-plan: never pad, I1
  non-gating).
- **Least confident:** (1) whether `process_return`'s 4-table atomic unit stays internally
  consistent across §Model Functions ↔ §1d ↔ §2 ↔ §5 through the swarm (a return-shape or
  conn-threading drift in ANY of the four in-tx helpers fails the unit AND its EARS) — the
  convergence loop must scrutinize this seam first (verify_first). (2) whether the honest ~22-agent
  count materially weakens the Path-B-over-A rationale (surfaced as the Open sizing note; Alex's call
  at launch).

---

## Cross-Section Self-Review Log (Claude authoring pass — pre-Codex)

Recorded here so Codex/human can see what was already reconciled (mirrors lesson-studio's Round-N log):
- **RESOLVED — audit atomicity contradiction (run-plan internal P0):** the run-plan EARS said
  "commit orders+order_items+stock+**audit** atomically" while its injection matrix + Wave-0 spec say
  audit is **post-commit only**. Reconciled in favor of the proven post-commit rule (2 sources vs 1;
  FC5/FC6): `create_order` commits {orders, order_items, stock}; the route records audit
  post-commit. The run-plan EARS wording is corrected in the R1–R3 update.
- **RESOLVED — "original payment" undefined:** pinned to `order_total` (SUM items); `payments`
  refund-only; refund guard is `refunded_total + refund ≤ order_total`.
- **RESOLVED — ext_ref ownership:** no single resource owns it → a Wave-0 `refs.py`
  (`assert_ext_ref_unique`) called in BOTH class-B transactions; per-table UNIQUE = intra-table
  backstops only.
- **RESOLVED — shipment blueprint prefix:** the shipments blueprint needs both
  `/orders/<int:oid>/shipments` and `/shipments/...`, so it registers with NO url_prefix and declares
  full paths (a documented exception to the one-prefix-per-blueprint convention).
- **RESOLVED — soft-delete + restock interaction:** `restock_product_in_tx` restocks regardless of
  `deleted_at` (a returned unit re-enters inventory even if the SKU was retired); `decrement_stock_in_tx`
  refuses a soft-deleted product (rowcount 0 → insufficient stock). Both pinned.
- **OPEN for Codex/human:** the four-way in-tx call chain in `process_return` (return + shipment +
  product + payment owners) — the densest cross-agent write; verify no class/return-shape drift.

**Fresh-context adversarial pass (proxy-Codex, 2026-07-21) — 9 cross-section categories checked:**
**ZERO P0s.** All load-bearing seams (both class-B transactions, the 7 in-tx helpers, ext_ref
single-owner ↔ per-table UNIQUE backstops, refund guard, shipment reachability, manifest 31==Route-Table
31, blueprint no-prefix) verified cross-section consistent. Two P1s found + FIXED here: (a) §4 said
"six in-tx helpers" but listed seven → corrected (final framing: "four write + one read-only uniqueness
guard + two read-only totals"); (b) manifest-equality path capture was unpinned → pinned to
**per-request `(request.method, request.url_rule.rule)` captured via `after_request`** (NOT inferred
from `app.url_map`, and never concrete URLs). P2s: `audit_logs.entity_id` marked FC46-exempt (polymorphic, no FK);
`order_total`/`refunded_total` `oid`-vs-`order_id` call-site variance left as harmless. **This is a
Claude-side proxy pass — it does NOT substitute for the real Codex fresh-context review + human P0 pass
(both still required before `status: active`).**

**REAL Codex fresh-context pass (2026-07-21) — 6 P0 + 1 P1 + 1 P2, ALL RESOLVED here:**
- **P0-1 (shipment illegal-transition ↔ §3 enum):** §3 rejected `pending`/`returned` as 400 bad-enum, so the `state-machine-illegal` case's `delivered→pending` and `→returned` could never reach `advance_shipment`/409. FIX: `to_status ∈ {pending,shipped,delivered,returned}` (any STORED status is valid input; unknown → 400); `LEGAL_TRANSITIONS` decides legality → 409, status unchanged. Reconciled §3 + `advance_shipment` note + the illegal EARS/case.
- **P0-2 (rollback proof was fake):** the refund-exceeds/ shipment-not-delivered failures fire BEFORE any write, so they can't prove rollback. FIX: added a smoke-only **`_TX_FAULT` fault-injection seam** (§5) that raises AFTER `add_refund_in_tx` (and, for create_order, after the first item write); `process-return-rollback` now injects it and asserts INSERT-count + UPDATE-**value** (shipment status still `delivered`, product stock unchanged) equality; the two pre-write guards split into `process-return-guard-refund` / `process-return-guard-shipment` (guard tests, not rollback proofs). Path-B cases 8→**10**.
- **P0-3 (manifest false-green):** replaced "intersect global driven-methods × url_map rules" with **per-request capture of `(request.method, request.url_rule.rule)`** via `after_request` (skip `url_rule is None`); each of the 31 must appear in the actually-driven set.
- **P0-4 (omitted `user_id`):** pinned — omitted → current actor's id (both roles); customer ALWAYS forced to self; admin may override. Reconciled Route Table + §3 + §6.
- **P0-5 (missing §3 row):** added `PATCH /categories/<int:cid>` — non-empty `name` → else 400; 404 if absent; 409 on duplicate.
- **P0-6 (SQLite semantics):** corrected `isolation_level=None` to **AUTOCOMMIT** (not "autocommit off"); class-A single statements persist immediately with NO bare `COMMIT`; only the two class-B owners issue explicit `BEGIN IMMEDIATE`…`COMMIT`/`ROLLBACK`. Reconciled schema intro, Database Connection, §5(A). Exactly two class-B owners preserved.
- **P1-7 (§2 wiring):** split the infra row — `get_db`/`query` to all consumers; **`transaction` to `order_models.py` + `return_models.py` ONLY** (matches §1a + §5).
- **P2-8 (helper count):** re-described the seven in-tx helpers as **four write + one read-only uniqueness guard (`assert_ext_ref_unique`) + two read-only totals**; caller-`conn`/no-commit preserved for all seven (§4 + §5C).
- **Manifest unchanged:** the 2 new guard cases exercise existing endpoints (POST /returns, POST /shipments/advance), so the endpoint set stays **31 = 31** vs the Route Table.
- **STILL REQUIRED before `status: active`:** the human zero-P0 structural pass (Codex + human is the convergence criterion).

**CONFIRMING Round-2 Codex pass (2026-07-21) — 3 P0 + 3 P1 + 1 P2, ALL RESOLVED here:**
- **P0-1 (state-machine-illegal too weak):** the `--case` now proves, in ONE case, three sub-checks each with status preserved: `delivered→pending`→409 (stays `delivered`); `pending→delivered` skip→409 (stays `pending`); `advance`→`returned` from EVERY source `∈{pending,shipped,delivered}`→409 (stays source). EARS tightened to match.
- **P0-2 (`_TX_FAULT` not in the export/wiring contract):** added `order_models._TX_FAULT` + `return_models._TX_FAULT` to §1a (default `None`, raising-callable, per-owner checkpoint, smoke sets+resets) and a §2 producer→consumer row (owners → `swarmlimit/smoke.py`).
- **P0-3 (blueprint path ambiguity):** pinned ONE convention — **no `url_prefix` on any blueprint; every route declares the FULL absolute path = the manifest**. Kills `/auth/auth/register` (no prefix) and collection trailing-slash `/suppliers/` (declared `'/suppliers'`, never `'/suppliers/'`). §4 + §1c + all Route-Table sub-tables converted to full paths so `request.url_rule.rule` == manifest exactly.
- **P1-4 (class-A "commits" wording):** replaced "commits internally"/"commits" with "persists immediately via SQLite autocommit; does not call `conn.commit()`" (umbrella, all 8 class-A functions, §5(A) header). Only `create_order`/`process_return` issue explicit boundaries.
- **P1-5 (stale self-review "app.url_map"):** corrected the historical note to the current per-request `request.url_rule.rule` via `after_request` mechanism.
- **P1-6 (missing §2 row):** added `database.init_db → scaffold __init__.py`.
- **P2-7 (stale helper count in self-review):** corrected "five write + two read-only" → "four write + one read-only uniqueness guard + two read-only totals".
- **Invariants preserved:** exactly two class-B owners; Path-B cases = 10; manifest = 31 = Route Table (no endpoints added/removed — path notation changed from relative to full, values identical).
- **STILL REQUIRED before `status: active`:** the human zero-P0 structural pass.

**HUMAN P0 pass (Alex, guided, 2026-07-21) — ZERO cross-section P0s found.** Walked five plain-English
rounds: (1) the 404-not-403 ownership rule — consistent across orders/shipments/returns/payments; (2)
money/refund rules — `>0` lower bound + `≤ order_total` upper bound agree across schema CHECKs, §3, and
the §5 invariant; recompute-total-from-frozen-items accepted; (3) the two class-B transactions
(`create_order`, `process_return`) — all-or-nothing story matches the EARS success + rollback + guard
cases; (4) shipment state machine — one-way path + `returned`-only-via-`process_return` agree between
§Model Functions, §3, §5, and the illegal `--case`. Two clarifications the human pass surfaced were
PINNED: (a) **retry-safety corollary** (ext_ref + all-or-nothing ⇒ safe re-submit — no duplicate/no
lost write; added to the §5 ext_ref invariant); (b) **restock-full/refund-partial accepted
simplification** (noted in §5, bounded to once-per-order by the state machine). Human judgment calls:
Call-1 (route-path notation) → **unified to `<int:...>` everywhere** (§3/§6/EARS/prose now match the
Route Table + manifest exactly); Call-2 (`_TX_FAULT` test-only seam) and Call-3 (non-atomic
`create_product`, guarded by up-front id validation) → **left as-is** (accepted for a throwaway
vehicle). **Convergence note:** human = zero P0. A confirming Codex round on THIS post-fix spec (the
Round-2 fixes + these human-pass edits) has NOT yet run — recommended before flipping `status:
draft→active`, to satisfy the full criterion (Codex-clean AND human-zero-P0).

**FINAL confirming Codex pass (2026-07-21) — NOT CLEAN: 4 P0 cross-section contradictions, ALL RESOLVED
here.** This fresh-context Codex round confirmed the previously-good invariants (Route Table = manifest =
31 exact method/path equality; Path-B `--case` table = 10; exactly two class-B owners `create_order`/
`process_return`; seven caller-`conn`/no-commit helpers = four writers + one uniqueness guard + two
readers; manual `/autopilot` the only launch engine, Workflow UNLAUNCHABLE; honest roster ~22, I1>31
non-gating and never padded) and found four NEW P0s:
- **P0-1 (public registration can create an admin):** the Route Table made `POST /auth/register` public
  while §3 accepted `role ∈ {admin,customer}` with a stale "first user forced admin" rule — but `init_db`
  already seeds `admin@swarm.test`, so the bootstrap branch is never the runtime path and an anonymous
  caller could POST `role=admin` and pass every admin route (hollowing the customer-403 proof). FIX:
  public registration ALWAYS creates a `customer` (the route ignores/overrides any supplied role →
  `create_user(..., role='customer', ...)`); removed the "first user forced admin" rule; seeded admin is
  the sole bootstrap-admin; `create_user`'s `role` param retained for trusted seed/internal use only.
  Added a **default-smoke** security assertion (`register-role-ignored`, NOT a new Path-B `--case`) that a
  `role:admin` registration still yields a customer + 403 on an admin route. Reconciled Route Table + note,
  §3, §6, `create_user` prose, EARS, and the smoke core-cases list.
- **P0-2 (multiple shipments break the single-return story):** `shipments.order_id` was not unique and
  `create_shipment` could be called repeatedly, so `process_return`'s "the order's shipment" was
  ambiguous and an admin could mint a second shipment to permit a second return (double-restock). FIX:
  `UNIQUE(order_id)` on `shipments` (DB backstop); `create_shipment` raises `ValueError('shipment exists')`
  → **409 `conflict`**; `process_return` selects the order's UNIQUE shipment (at most one) and requires it
  exists + is `delivered`. Added a **default-smoke** integrity assertion (`shipment-unique`, NOT a new
  Path-B `--case`) that a second `POST /orders/<oid>/shipments` → 409 with no row, incl. after the first is
  `returned`. Reconciled schema, `create_shipment` model + Route Table + §3, `process_return` steps + §5,
  a new §5 one-shipment-per-order invariant, EARS, and the smoke core-cases list. No second class-B owner;
  state machine + exactly-once return preserved.
- **P0-3 (active run-plan contradicted the authoritative spec):** the run-plan's §Decomposition + §6-Section
  Spec + EARS still carried the pre-spec-phase decomposition (Wave-0 ~2 agents, `@require_owner`, obsolete
  `audit_logs.record` signature, `add_item_in_tx`, `invoices.order_id`/`payments.invoice_id`,
  `<resource>/model.py`+`/routes.py`, a Wave-3 integration owner, Tail ~6, `refund ≤ original payment`,
  `soft-delete-order` "400/409", a two-subproof `state-machine-illegal`, and a `create_order` rollback that
  wrongly included `audit_logs`). FIX (in the linked run-plan): Wave 0 = five single-owner agents
  {scaffold, database, auth-core, shared-services, smoke-author}; Wave 1 = seven model agents owning
  `swarmlimit/models/<resource>_models.py`; Wave 2 = seven route agents owning
  `swarmlimit/routes/<resource>.py`; Wave 3 removed (smoke.py is Wave-0-owned, executed at assembly C2);
  Tail ~3 (disconfirmer/self-audit/verify-harvest; verify-self-audit + terminal disk-verify are native
  gates); three merge barriers + push/provenance re-verify preserved. Shared contracts corrected to the
  actor-based `*_for(actor)` getters, the full `record(actor_id, action, entity_type, entity_id=None,
  detail=None)` signature, direct order-item inserts (no `add_item_in_tx`), the real swarmlimit FK edges,
  and the exact refund rule `refunded_total + refund_cents ≤ order_total` (payments refund-only; create_order
  writes no charge). Run-plan EARS: `state-machine-illegal` now carries all three subproofs;
  `soft-delete-order` requires exactly 409; `process-return-rollback` uses the `_TX_FAULT` seam; the two
  pre-write guard cases (`process-return-guard-refund`, `process-return-guard-shipment`) were added so the
  run-plan EARS ↔ spec ten-case table is a **bijection of exactly ten**; `create_order` rollback drops
  `audit_logs` from the tx tables (audit is post-commit). Post-edit grep confirms no live occurrence of any
  stale token.
- **P0-4 (smoke could skip schema init with a pre-created tempfile):** `create_app()` runs `init_db()` only
  if the DB file is absent, but a bare `NamedTemporaryFile`/`mkstemp` path already EXISTS, so a smoke run
  handing that path to `create_app()` skips `init_db()` and the first query hits no schema. FIX: pinned
  smoke to a `tempfile.TemporaryDirectory()` **child path that does NOT yet exist** (e.g.
  `<tempdir>/swarmlimit.sqlite`), so the absence check fires and `init_db()` runs exactly once; FC49 (real
  on-disk SQLite, never `:memory:`) preserved; `init_db` not redesigned. Pinned in the Namespace Temp-DB
  note, App Configuration, Database Connection, and the Acceptance-Tests header.
- **Cross-section re-verification (post-fix):** Route Table set == manifest set == 31 (exact method/path
  equality, `<int:...>` form) — verified by set diff; Path-B EARS ↔ ten-case table ↔ run-plan EARS =
  bijection of ten (verified by name-set diff); exactly two class-B owners; `process_return` signature
  unchanged and consistent; unique-shipment rule consistent across schema/model/route/§5/state-machine/
  smoke; public registration can never mint an admin while the seeded admin still exercises admin routes;
  Wave owners single-owner and matching the namespace layout with smoke.py single-owned; `run_id` remains
  skill-computed and `docs/reports/<run-id>/` must be absent before freeze. `git diff --check` clean.
- **CONVERGENCE NOT YET MET:** this pass was **NOT clean** (four P0s found), so per the criterion (Codex-clean
  AND human-zero-P0) `status` stays **`draft`**. One more **fresh-context Codex confirmation** on THIS
  post-fix spec (comparing the linked run-plan at the reconciled sections) is required before flipping
  `draft→active`.

**SECOND FINAL confirming Codex pass (2026-07-21) — NOT CLEAN: 5 consistency findings, ALL RESOLVED here.**
This fresh-context round validated the four prior P0 fixes and surfaced five smaller cross-section
consistency defects introduced/left by them:
- **F1 (invalid `create_user` call):** the register-privilege note wrote
  `create_user(email, password, role='customer', name)` — invalid Python (positional arg after a keyword).
  FIX: `create_user(email=email, password=password, role='customer', name=name)` (matches the
  `create_user(email, password, role, name)` signature).
- **F2 (register-role-ignored overreached):** the EARS + smoke core-case claimed registration itself
  "logs the user in." Registration does NOT establish a session. FIX: registration creates the customer and
  returns **201**; smoke then explicitly `POST /auth/login`s with those credentials, reads `csrf_token`
  from the login body, and `POST`s an admin route with that token → **403**. EARS + default-smoke prose
  updated together; the "logs in" claim removed.
- **F3 (auth-vs-CSRF precedence unpinned):** a worker could 400-`csrf` an anonymous mutation instead of
  401-`auth`. FIX (pinned across App Configuration, §4 CSRF + Auth-failure-codes, §Global, §6, and both
  EARS): the CSRF `before_request` fires ONLY for a request carrying an authenticated session; an anonymous
  request has no `session['_csrf']`, so it falls through to `login_required` → **401 `auth`**. CSRF (400)
  is checked only AFTER a request is authenticated — **401 (anon) precedes 400 (authed, bad CSRF)**; no
  heuristic choice.
- **F4 (run-plan launch language):** replaced the "import-check/import-checked" wording with the actual
  parse-only `python -m compileall swarmlimit` gate (P1 risk row + Feed-Forward); removed the "small
  integration layer" (Enhancement Summary #2); renamed the `integration/smoke` injection row to the real
  **`smoke-author` (Wave 0)** owner; replaced the Codex-handoff `model→routes→smoke` phrasing with
  **Wave 0 smoke authoring/parse-check → Wave 1 models → Wave 2 routes → assembly C2 smoke execution**. No
  Wave 3 and single ownership of `swarmlimit/smoke.py` preserved.
- **F5 (repeated product deletion):** §3 said an already-soft-deleted product → 404 while
  `soft_delete_product` declares idempotent (already-deleted → no-op). FIX (kept the idempotent model
  contract): §3 now returns **404 only if the product id never existed**; an already-soft-deleted product
  → **200** (idempotent no-op); a live product → **200**. Route Table already said 200 — now consistent.
- **Cross-section re-verification (post-fix):** manifest == Route Table == **31** (set-diff clean);
  spec Path-B cases == run-plan EARS cases == **10** (bijection, name-set diff clean); exactly **two**
  class-B owners; **seven** in-tx helpers (four write + one uniqueness guard + two readers); registration
  role/session/CSRF, anonymous auth-vs-CSRF precedence, and the Wave-0-parse-vs-C2-execution split all
  consistent; shipment uniqueness + once-per-order return unchanged. `git diff --check` clean.
- **CONVERGENCE STILL NOT MET:** this pass was again NOT clean (5 findings), so `status` stays **`draft`**.
  A further fresh-context Codex confirmation on THIS post-fix spec (+ run-plan compare) is still required
  before `draft→active`.
