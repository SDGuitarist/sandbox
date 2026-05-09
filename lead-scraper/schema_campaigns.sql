PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS campaigns (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    target_date       TEXT,
    segment_filter    TEXT,
    template_vars_json TEXT CHECK(json_valid(template_vars_json) OR template_vars_json IS NULL),
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS campaign_leads (
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    assigned_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    PRIMARY KEY (campaign_id, lead_id)
);

CREATE TABLE IF NOT EXISTS sender_accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    platform        TEXT NOT NULL DEFAULT 'both'
                    CHECK(platform IN ('facebook', 'instagram', 'both')),
    profile_dir     TEXT NOT NULL,
    daily_cap       INTEGER NOT NULL DEFAULT 30,
    sends_today     INTEGER NOT NULL DEFAULT 0,
    last_send_at    TEXT,
    last_reset_date TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active', 'restricted', 'cooldown', 'disabled')),
    restricted_at   TEXT,
    cooldown_until  TEXT,
    risk_acknowledged INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS outreach_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    opener_text     TEXT,
    template_text   TEXT,
    full_message    TEXT,
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK(status IN ('draft', 'approved', 'sent', 'skipped', 'needs_review',
                                     'replied', 'booked', 'declined', 'no_response')),
    generated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    approved_at     TEXT,
    sent_at         TEXT,
    skip_reason     TEXT,
    gate_checked_at TEXT,
    sender_account_id INTEGER REFERENCES sender_accounts(id) ON DELETE SET NULL,
    UNIQUE(lead_id, campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_outreach_queue_campaign_status
    ON outreach_queue(campaign_id, status);
