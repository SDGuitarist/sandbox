PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(length(name) <= 50),
    color TEXT NOT NULL DEFAULT '#6366f1' CHECK(length(color) <= 7),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

INSERT OR IGNORE INTO categories (id, name, color) VALUES (1, 'Uncategorized', '#9ca3af');

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL DEFAULT 1 REFERENCES categories(id) ON DELETE SET DEFAULT,
    amount INTEGER NOT NULL CHECK(amount > 0),
    description TEXT NOT NULL DEFAULT '' CHECK(length(description) <= 200),
    transaction_date TEXT NOT NULL DEFAULT (date('now')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_cat_date
    ON transactions(category_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_date
    ON transactions(transaction_date);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    year_month TEXT NOT NULL CHECK(length(year_month) = 7),
    amount INTEGER NOT NULL CHECK(amount > 0),
    UNIQUE(category_id, year_month)
);

CREATE INDEX IF NOT EXISTS idx_budgets_year_month
    ON budgets(year_month);
