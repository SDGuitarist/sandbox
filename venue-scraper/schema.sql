-- Venue-scraper schema.
-- Applied via: python scrape.py migrate
-- NEVER auto-run on startup.

CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    email TEXT,
    phone TEXT,
    address TEXT,
    website TEXT,
    description TEXT,
    venue_type TEXT,
    social_links TEXT,        -- JSON array
    capacity TEXT,
    pricing TEXT,
    star_rating REAL,
    review_count INTEGER,
    scraped_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS outreach_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('new','contacted','replied','partnered','declined')),
    notes TEXT,
    changed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(venue_id)
);
