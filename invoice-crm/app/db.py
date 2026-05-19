import sqlite3
from contextlib import contextmanager
from flask import g, current_app


@contextmanager
def get_db():
    """Yield a database connection. Caller must commit. Rolls back on exception."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            timeout=10
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    try:
        yield g.db
    except Exception:
        g.db.rollback()
        raise


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Create all tables. WAL mode is set here (persistent)."""
    db = sqlite3.connect(current_app.config['DATABASE'], timeout=10)
    try:
        db.execute("PRAGMA journal_mode=WAL")

        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                company_name TEXT DEFAULT '',
                logo_url TEXT DEFAULT '',
                address TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                business_email TEXT DEFAULT '',
                tax_id TEXT DEFAULT '',
                invoice_prefix TEXT DEFAULT 'INV',
                default_payment_terms INTEGER DEFAULT 30,
                default_tax_rate REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'USD',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                company TEXT DEFAULT '',
                address TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive', 'lead')),
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_clients_user_id ON clients(user_id);
            CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);

            CREATE TABLE IF NOT EXISTS client_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                UNIQUE(user_id, name)
            );

            CREATE TABLE IF NOT EXISTS client_tag_map (
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES client_tags(id) ON DELETE CASCADE,
                PRIMARY KEY (client_id, tag_id)
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                type TEXT NOT NULL CHECK(type IN ('call', 'email', 'meeting', 'note')),
                notes TEXT DEFAULT '',
                activity_date TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_activities_client_id ON activities(client_id);

            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                value_cents INTEGER DEFAULT 0,
                stage TEXT DEFAULT 'lead' CHECK(stage IN ('lead', 'qualified', 'proposal', 'negotiation', 'won', 'lost')),
                expected_close_date TEXT,
                probability INTEGER DEFAULT 50,
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_deals_user_id ON deals(user_id);
            CREATE INDEX IF NOT EXISTS idx_deals_client_id ON deals(client_id);
            CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals(stage);

            CREATE TABLE IF NOT EXISTS catalog_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                unit_price_cents INTEGER DEFAULT 0,
                unit TEXT DEFAULT 'hour' CHECK(unit IN ('hour', 'item', 'project', 'month')),
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_catalog_items_user_id ON catalog_items(user_id);

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                invoice_number TEXT NOT NULL,
                status TEXT DEFAULT 'draft' CHECK(status IN ('draft', 'sent', 'viewed', 'paid', 'overdue')),
                issue_date TEXT DEFAULT (date('now')),
                due_date TEXT,
                subtotal_cents INTEGER DEFAULT 0,
                tax_cents INTEGER DEFAULT 0,
                total_cents INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                is_recurring INTEGER DEFAULT 0,
                recurrence_interval TEXT CHECK(recurrence_interval IN ('weekly', 'monthly', 'quarterly', 'annually') OR recurrence_interval IS NULL),
                next_recurrence_date TEXT,
                parent_invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, invoice_number)
            );
            CREATE INDEX IF NOT EXISTS idx_invoices_user_id ON invoices(user_id);
            CREATE INDEX IF NOT EXISTS idx_invoices_client_id ON invoices(client_id);
            CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
            CREATE INDEX IF NOT EXISTS idx_invoices_parent ON invoices(parent_invoice_id);

            CREATE TABLE IF NOT EXISTS invoice_line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                catalog_item_id INTEGER REFERENCES catalog_items(id) ON DELETE SET NULL,
                description TEXT NOT NULL,
                quantity REAL DEFAULT 1.0,
                unit_price_cents INTEGER DEFAULT 0,
                tax_rate REAL DEFAULT 0.0,
                line_total_cents INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_line_items_invoice_id ON invoice_line_items(invoice_id);

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                amount_cents INTEGER NOT NULL,
                payment_date TEXT NOT NULL,
                method TEXT DEFAULT 'other' CHECK(method IN ('cash', 'check', 'bank_transfer', 'card', 'other')),
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id);
            CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
        """)
    finally:
        db.close()
