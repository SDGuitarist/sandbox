-- app/schema.sql (models agent 3)

-- Users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Workspaces (multi-tenant)
CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_tier TEXT NOT NULL DEFAULT 'solo' CHECK (plan_tier IN ('solo', 'pro', 'agency')),
    monthly_email_quota INTEGER NOT NULL DEFAULT 500,
    emails_sent_this_month INTEGER NOT NULL DEFAULT 0,
    quota_reset_date TEXT NOT NULL DEFAULT (date('now', 'start of month', '+1 month')),
    from_email TEXT NOT NULL DEFAULT '',
    from_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_workspaces_owner ON workspaces(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_workspaces_slug ON workspaces(slug);

-- Workspace members (user-workspace join with roles)
CREATE TABLE IF NOT EXISTS workspace_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    invited_at TEXT NOT NULL DEFAULT (datetime('now')),
    joined_at TEXT,
    UNIQUE(workspace_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_wm_workspace ON workspace_members(workspace_id);
CREATE INDEX IF NOT EXISTS idx_wm_user ON workspace_members(user_id);

-- Leads (venue/promoter contacts)
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    email TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    venue_name TEXT NOT NULL DEFAULT '',
    capacity INTEGER NOT NULL DEFAULT 0,
    location TEXT NOT NULL DEFAULT '',
    genre_tags TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'csv', 'api')),
    pipeline_stage TEXT NOT NULL DEFAULT 'new' CHECK (pipeline_stage IN ('new', 'contacted', 'responded', 'interested', 'booking_requested', 'booked', 'declined')),
    notes TEXT NOT NULL DEFAULT '',
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_leads_workspace ON leads(workspace_id);
CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(workspace_id, pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(workspace_id, email);

-- Tags
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#6366f1',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(workspace_id, name)
);
CREATE INDEX IF NOT EXISTS idx_tags_workspace ON tags(workspace_id);

-- Lead-tag assignments (many-to-many)
CREATE TABLE IF NOT EXISTS lead_tags (
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (lead_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_lead_tags_tag ON lead_tags(tag_id);

-- Email templates
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    subject_line TEXT NOT NULL DEFAULT '',
    html_body TEXT NOT NULL DEFAULT '',
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_templates_workspace ON templates(workspace_id);

-- Campaigns
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'sending', 'sent', 'paused', 'cancelled')),
    total_recipients INTEGER NOT NULL DEFAULT 0,
    sent_count INTEGER NOT NULL DEFAULT 0,
    delivered_count INTEGER NOT NULL DEFAULT 0,
    opened_count INTEGER NOT NULL DEFAULT 0,
    clicked_count INTEGER NOT NULL DEFAULT 0,
    bounced_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    scheduled_at TEXT,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    started_at TEXT,
    completed_at TEXT,
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_campaigns_workspace ON campaigns(workspace_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(workspace_id, status);

-- Campaign recipients (which leads are in a campaign)
CREATE TABLE IF NOT EXISTS campaign_recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'delivered', 'opened', 'clicked', 'bounced', 'failed')),
    sent_at TEXT,
    message_id TEXT NOT NULL DEFAULT '',
    UNIQUE(campaign_id, lead_id)
);
CREATE INDEX IF NOT EXISTS idx_cr_campaign ON campaign_recipients(campaign_id);
CREATE INDEX IF NOT EXISTS idx_cr_lead ON campaign_recipients(lead_id);
CREATE INDEX IF NOT EXISTS idx_cr_message_id ON campaign_recipients(message_id);

-- Job queue (SQLite-backed async email sends)
CREATE TABLE IF NOT EXISTS job_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    recipient_id INTEGER NOT NULL REFERENCES campaign_recipients(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    worker_id TEXT NOT NULL DEFAULT '',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    scheduled_at TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at TEXT,
    completed_at TEXT,
    error_message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_jq_status ON job_queue(status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_jq_campaign ON job_queue(campaign_id);

-- Campaign progress (single row per campaign for SSE polling)
CREATE TABLE IF NOT EXISTS campaign_progress (
    campaign_id INTEGER PRIMARY KEY REFERENCES campaigns(id) ON DELETE CASCADE,
    total INTEGER NOT NULL DEFAULT 0,
    sent INTEGER NOT NULL DEFAULT 0,
    delivered INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'sending' CHECK (status IN ('sending', 'paused', 'completed')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Email events (delivery tracking from SendGrid webhooks)
CREATE TABLE IF NOT EXISTS email_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    recipient_id INTEGER REFERENCES campaign_recipients(id) ON DELETE SET NULL,
    message_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL CHECK (event_type IN ('delivered', 'opened', 'clicked', 'bounced', 'dropped', 'unsubscribed')),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    received_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ee_campaign ON email_events(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ee_message_id ON email_events(message_id);

-- Pipeline notes (notes on leads in pipeline context)
CREATE TABLE IF NOT EXISTS pipeline_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pn_lead ON pipeline_notes(lead_id);

-- Files (uploaded press kits, logos, EPKs)
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    filename_original TEXT NOT NULL,
    filename_stored TEXT NOT NULL,
    file_ext TEXT NOT NULL DEFAULT '',
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    uploaded_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_files_workspace ON files(workspace_id);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    link TEXT NOT NULL DEFAULT '',
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read);

-- Activity log (audit trail)
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT '',
    entity_id INTEGER,
    details TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_activity_workspace ON activity_log(workspace_id, created_at);

-- FTS5 for lead search
CREATE VIRTUAL TABLE IF NOT EXISTS leads_fts USING fts5(
    venue_name, contact_name, email, location, genre_tags,
    content='leads',
    content_rowid='id'
);

-- FTS5 sync triggers
CREATE TRIGGER IF NOT EXISTS leads_fts_insert AFTER INSERT ON leads BEGIN
    INSERT INTO leads_fts(rowid, venue_name, contact_name, email, location, genre_tags)
    VALUES (new.id, new.venue_name, new.contact_name, new.email, new.location, new.genre_tags);
END;

CREATE TRIGGER IF NOT EXISTS leads_fts_update AFTER UPDATE ON leads BEGIN
    DELETE FROM leads_fts WHERE rowid = old.id;
    INSERT INTO leads_fts(rowid, venue_name, contact_name, email, location, genre_tags)
    VALUES (new.id, new.venue_name, new.contact_name, new.email, new.location, new.genre_tags);
END;

CREATE TRIGGER IF NOT EXISTS leads_fts_delete AFTER DELETE ON leads BEGIN
    DELETE FROM leads_fts WHERE rowid = old.id;
END;
