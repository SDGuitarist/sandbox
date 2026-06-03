CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS industries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS component_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    cluster TEXT NOT NULL CHECK(cluster IN ('Your Reality', 'Your Assignment', 'Your Voice', 'Your Contract')),
    position INTEGER NOT NULL UNIQUE CHECK(position BETWEEN 1 AND 12),
    description TEXT NOT NULL DEFAULT '',
    placeholder_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS industry_guidance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    industry_id INTEGER NOT NULL REFERENCES industries(id) ON DELETE CASCADE,
    component_id INTEGER NOT NULL REFERENCES component_definitions(id) ON DELETE CASCADE,
    guidance_text TEXT NOT NULL DEFAULT '',
    UNIQUE(industry_id, component_id)
);
CREATE INDEX IF NOT EXISTS idx_industry_guidance_industry ON industry_guidance(industry_id);

CREATE TABLE IF NOT EXISTS prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    industry_id INTEGER NOT NULL REFERENCES industries(id) ON DELETE RESTRICT,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_industry ON prompt_templates(industry_id);

CREATE TABLE IF NOT EXISTS template_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    component_id INTEGER NOT NULL REFERENCES component_definitions(id) ON DELETE CASCADE,
    content TEXT NOT NULL DEFAULT '',
    UNIQUE(template_id, component_id)
);
CREATE INDEX IF NOT EXISTS idx_template_components_template ON template_components(template_id);

CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    industry_id INTEGER NOT NULL REFERENCES industries(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    completeness REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_prompts_user ON prompts(user_id);
CREATE INDEX IF NOT EXISTS idx_prompts_industry ON prompts(industry_id);

CREATE TABLE IF NOT EXISTS prompt_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    component_id INTEGER NOT NULL REFERENCES component_definitions(id) ON DELETE CASCADE,
    content TEXT NOT NULL DEFAULT '',
    UNIQUE(prompt_id, component_id)
);
CREATE INDEX IF NOT EXISTS idx_prompt_components_prompt ON prompt_components(prompt_id);

CREATE TABLE IF NOT EXISTS prompt_grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL UNIQUE REFERENCES prompts(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
    worked_well TEXT NOT NULL DEFAULT '',
    needs_improvement TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS share_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_share_tokens_template ON share_tokens(template_id);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_events_user ON audit_events(user_id);

CREATE TABLE IF NOT EXISTS saved_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    export_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_saved_exports_user ON saved_exports(user_id);

-- FTS5 for prompt search (indexes title only -- content is encrypted)
CREATE VIRTUAL TABLE IF NOT EXISTS prompts_fts USING fts5(
    title,
    content='prompts',
    content_rowid='id'
);

-- FTS5 triggers:
-- INSERT: AFTER (NEW.id not yet assigned at BEFORE time for AUTOINCREMENT)
-- DELETE: BEFORE (row still exists to read OLD values)
-- UPDATE: split into BEFORE (delete old) + AFTER (insert new)
CREATE TRIGGER IF NOT EXISTS prompts_ai AFTER INSERT ON prompts BEGIN
    INSERT INTO prompts_fts(rowid, title) VALUES (NEW.id, NEW.title);
END;

CREATE TRIGGER IF NOT EXISTS prompts_ad BEFORE DELETE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, title) VALUES('delete', OLD.id, OLD.title);
END;

CREATE TRIGGER IF NOT EXISTS prompts_au_del BEFORE UPDATE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, title) VALUES('delete', OLD.id, OLD.title);
END;

CREATE TRIGGER IF NOT EXISTS prompts_au_ins AFTER UPDATE ON prompts BEGIN
    INSERT INTO prompts_fts(rowid, title) VALUES (NEW.id, NEW.title);
END;
