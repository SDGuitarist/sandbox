CREATE TABLE IF NOT EXISTS registrants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK(role IN ('Writer', 'Director', 'Composer', 'Post-Production', 'Student', 'Other')),
    status TEXT NOT NULL DEFAULT 'pending_payment'
        CHECK(status IN ('pending_payment', 'paid', 'waitlisted', 'cancelled', 'payment_failed')),
    queue_position INTEGER,
    square_order_id TEXT,
    square_payment_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    paid_at TEXT,
    cancelled_at TEXT
);

CREATE TABLE IF NOT EXISTS email_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registrant_id INTEGER NOT NULL REFERENCES registrants(id),
    template_type TEXT NOT NULL CHECK(template_type IN ('confirmation', 'reminder_7d', 'reminder_1d', 'post_workshop', 'waitlist_confirmation', 'waitlist_promotion', 'payment_failed')),
    resend_message_id TEXT,
    status TEXT NOT NULL DEFAULT 'sent' CHECK(status IN ('sent', 'failed')),
    sent_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS webhook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    square_event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    processed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_registrants_status ON registrants(status);
CREATE INDEX IF NOT EXISTS idx_registrants_email ON registrants(email);
CREATE INDEX IF NOT EXISTS idx_email_log_registrant ON email_log(registrant_id);
