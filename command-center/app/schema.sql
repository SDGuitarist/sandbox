PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    setup_complete INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS business_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    business_name TEXT NOT NULL DEFAULT '',
    owner_name TEXT NOT NULL DEFAULT '',
    industry TEXT NOT NULL DEFAULT 'other',
    currency_symbol TEXT NOT NULL DEFAULT '$',
    fiscal_year_start INTEGER NOT NULL DEFAULT 1,
    logo_url TEXT NOT NULL DEFAULT '',
    tagline TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    tax_id TEXT NOT NULL DEFAULT '',
    default_hourly_rate INTEGER NOT NULL DEFAULT 0,
    weekly_hours_target INTEGER NOT NULL DEFAULT 40,
    monthly_revenue_target INTEGER NOT NULL DEFAULT 0,  -- cents
    quarterly_revenue_target INTEGER NOT NULL DEFAULT 0,  -- cents
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS company (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    website TEXT NOT NULL DEFAULT '',
    industry TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    company_id INTEGER,
    role_title TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'other',
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'lead',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (company_id) REFERENCES company(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS interaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'email',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES contact(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS deal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    contact_id INTEGER,
    company_id INTEGER,
    value INTEGER NOT NULL DEFAULT 0,
    stage TEXT NOT NULL DEFAULT 'lead',
    probability_pct INTEGER NOT NULL DEFAULT 10,
    expected_close_date TEXT,
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    loss_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES contact(id) ON DELETE SET NULL,
    FOREIGN KEY (company_id) REFERENCES company(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_id INTEGER,
    status TEXT NOT NULL DEFAULT 'not_started',
    type TEXT NOT NULL DEFAULT 'hourly',
    value INTEGER NOT NULL DEFAULT 0,
    hourly_rate INTEGER NOT NULL DEFAULT 0,
    start_date TEXT,
    target_end_date TEXT,
    actual_end_date TEXT,
    description TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    deal_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES contact(id) ON DELETE SET NULL,
    FOREIGN KEY (deal_id) REFERENCES deal(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS milestone (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    description TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    project_id INTEGER,
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'todo',
    due_date TEXT,
    estimated_hours REAL NOT NULL DEFAULT 0,
    tags TEXT NOT NULL DEFAULT '',
    is_recurring INTEGER NOT NULL DEFAULT 0,
    recurrence_interval TEXT,
    recurrence_days INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS time_entry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    project_id INTEGER NOT NULL,
    task_id INTEGER,
    minutes INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT '',
    billable INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES task(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount INTEGER NOT NULL DEFAULT 0,
    date TEXT NOT NULL,
    contact_id INTEGER,
    project_id INTEGER,
    category TEXT NOT NULL DEFAULT 'other',
    payment_method TEXT NOT NULL DEFAULT 'bank_transfer',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES contact(id) ON DELETE SET NULL,
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS expense (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount INTEGER NOT NULL DEFAULT 0,
    date TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    vendor TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    tax_deductible INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS income_category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS expense_category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS goal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL UNIQUE,
    revenue_target INTEGER NOT NULL DEFAULT 0,
    hours_target INTEGER NOT NULL DEFAULT 0,
    revenue_actual INTEGER NOT NULL DEFAULT 0,
    hours_actual INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS journal_entry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS note (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS template_milestone (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    offset_days INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (template_id) REFERENCES project_template(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS template_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'medium',
    estimated_hours REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (template_id) REFERENCES project_template(id) ON DELETE CASCADE
);

-- FTS5 virtual table for notes search
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title, content, tags,
    content='note',
    content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS journal_fts USING fts5(
    content,
    content='journal_entry',
    content_rowid='id'
);

-- Seed default categories
INSERT OR IGNORE INTO income_category (name, is_default) VALUES
    ('project_payment', 1), ('retainer', 1), ('consulting', 1), ('product_sale', 1), ('other', 1);

INSERT OR IGNORE INTO expense_category (name, is_default) VALUES
    ('software', 1), ('hardware', 1), ('office', 1), ('travel', 1),
    ('marketing', 1), ('education', 1), ('contractor', 1), ('other', 1);

-- FTS5 triggers for note sync
CREATE TRIGGER IF NOT EXISTS notes_fts_insert AFTER INSERT ON note BEGIN
    INSERT INTO notes_fts(rowid, title, content, tags) VALUES (new.id, new.title, new.content, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS notes_fts_update AFTER UPDATE ON note BEGIN
    UPDATE notes_fts SET title = new.title, content = new.content, tags = new.tags WHERE rowid = new.id;
END;
CREATE TRIGGER IF NOT EXISTS notes_fts_delete AFTER DELETE ON note BEGIN
    DELETE FROM notes_fts WHERE rowid = old.id;
END;

-- FTS5 triggers for journal sync
CREATE TRIGGER IF NOT EXISTS journal_fts_insert AFTER INSERT ON journal_entry BEGIN
    INSERT INTO journal_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS journal_fts_update AFTER UPDATE ON journal_entry BEGIN
    UPDATE journal_fts SET content = new.content WHERE rowid = new.id;
END;
CREATE TRIGGER IF NOT EXISTS journal_fts_delete AFTER DELETE ON journal_entry BEGIN
    DELETE FROM journal_fts WHERE rowid = old.id;
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contact_company ON contact(company_id);
CREATE INDEX IF NOT EXISTS idx_contact_status ON contact(status);
CREATE INDEX IF NOT EXISTS idx_deal_stage ON deal(stage);
CREATE INDEX IF NOT EXISTS idx_deal_contact ON deal(contact_id);
CREATE INDEX IF NOT EXISTS idx_project_contact ON project(contact_id);
CREATE INDEX IF NOT EXISTS idx_project_status ON project(status);
CREATE INDEX IF NOT EXISTS idx_task_project ON task(project_id);
CREATE INDEX IF NOT EXISTS idx_task_status ON task(status);
CREATE INDEX IF NOT EXISTS idx_task_due ON task(due_date);
CREATE INDEX IF NOT EXISTS idx_time_entry_project ON time_entry(project_id);
CREATE INDEX IF NOT EXISTS idx_time_entry_date ON time_entry(date);
CREATE INDEX IF NOT EXISTS idx_income_date ON income(date);
CREATE INDEX IF NOT EXISTS idx_income_contact ON income(contact_id);
CREATE INDEX IF NOT EXISTS idx_expense_date ON expense(date);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at);
CREATE INDEX IF NOT EXISTS idx_interaction_contact ON interaction(contact_id);
