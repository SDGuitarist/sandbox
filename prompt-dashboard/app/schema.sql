CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL DEFAULT '',
    user_prompt TEXT NOT NULL DEFAULT '',
    variables TEXT NOT NULL DEFAULT '[]',
    version_count INTEGER NOT NULL DEFAULT 1,
    last_tested_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prompt_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    system_prompt TEXT NOT NULL DEFAULT '',
    user_prompt TEXT NOT NULL DEFAULT '',
    variables TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(prompt_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_prompt_versions_prompt_id ON prompt_versions(prompt_id);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS prompt_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    UNIQUE(prompt_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_prompt_tags_prompt_id ON prompt_tags(prompt_id);
CREATE INDEX IF NOT EXISTS idx_prompt_tags_tag_id ON prompt_tags(tag_id);

CREATE TABLE IF NOT EXISTS test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_version_id INTEGER NOT NULL REFERENCES prompt_versions(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    variables_used TEXT NOT NULL DEFAULT '{}',
    response_text TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    duration_ms INTEGER,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_test_runs_prompt_version_id ON test_runs(prompt_version_id);

-- FTS5 virtual table for search (external content)
CREATE VIRTUAL TABLE IF NOT EXISTS prompts_fts USING fts5(
    name, description, system_prompt, user_prompt,
    content=prompts, content_rowid=id
);

-- Triggers to keep FTS5 in sync with prompts table
-- CRITICAL: DELETE and UPDATE delete-half MUST be BEFORE triggers.
-- FTS5 external content fetches old values from the content table to remove
-- tokens. If the row is already deleted/updated, FTS5 reads wrong values
-- and corrupts the index. (Deepening: framework-docs-researcher)
CREATE TRIGGER IF NOT EXISTS prompts_ai AFTER INSERT ON prompts BEGIN
    INSERT INTO prompts_fts(rowid, name, description, system_prompt, user_prompt)
    VALUES (new.id, new.name, new.description, new.system_prompt, new.user_prompt);
END;

CREATE TRIGGER IF NOT EXISTS prompts_bd BEFORE DELETE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, name, description, system_prompt, user_prompt)
    VALUES ('delete', old.id, old.name, old.description, old.system_prompt, old.user_prompt);
END;

CREATE TRIGGER IF NOT EXISTS prompts_bu BEFORE UPDATE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, name, description, system_prompt, user_prompt)
    VALUES ('delete', old.id, old.name, old.description, old.system_prompt, old.user_prompt);
END;

CREATE TRIGGER IF NOT EXISTS prompts_au AFTER UPDATE ON prompts BEGIN
    INSERT INTO prompts_fts(rowid, name, description, system_prompt, user_prompt)
    VALUES (new.id, new.name, new.description, new.system_prompt, new.user_prompt);
END;
