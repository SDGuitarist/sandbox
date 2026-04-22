PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS campaigns (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    target_date       TEXT,
    segment_filter    TEXT,
    template_vars_json TEXT CHECK(json_valid(template_vars_json) OR template_vars_json IS NULL),
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK(status IN ('draft', 'active', 'complete')),
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS campaign_leads (
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    assigned_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    PRIMARY KEY (campaign_id, lead_id)
);

CREATE TABLE IF NOT EXISTS outreach_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    opener_text     TEXT,
    template_text   TEXT,
    full_message    TEXT,
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK(status IN ('draft', 'approved', 'sent', 'skipped')),
    generated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    approved_at     TEXT,
    sent_at         TEXT,
    UNIQUE(lead_id, campaign_id)
);
