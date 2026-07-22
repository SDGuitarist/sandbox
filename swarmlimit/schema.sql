-- swarmlimit schema — DDL for the throwaway e-commerce-order back office.
-- Stdlib sqlite3. Money is integer cents (never float). Timestamps are ISO-8601
-- TEXT (UTC) via datetime('now'). Per-connection pragmas (foreign_keys=ON,
-- journal_mode=WAL, busy_timeout=5000) are set in get_db(), not here.

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
