-- app/schema.sql (models agent)

-- Users: single role per account (venue_manager, musician, promoter)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('venue_manager', 'musician', 'promoter')),
    display_name TEXT NOT NULL DEFAULT '',
    bio TEXT NOT NULL DEFAULT '',
    genre_tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Venues: owned by a venue_manager
CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    capacity INTEGER NOT NULL DEFAULT 0,
    genre_tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_venues_user_id ON venues(user_id);

-- Rooms/stages within a venue
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT '',
    has_pa INTEGER NOT NULL DEFAULT 0,
    has_lighting INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_rooms_venue_id ON rooms(venue_id);

-- Weekly recurring availability windows for rooms
CREATE TABLE IF NOT EXISTS availability_windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_availability_room_id ON availability_windows(room_id);

-- Bookings: a musician books a room for a specific date
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    musician_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    event_name TEXT NOT NULL DEFAULT '',
    event_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'requested' CHECK (state IN ('requested', 'confirmed', 'advanced', 'performed', 'settled', 'paid', 'rejected', 'cancelled')),
    deal_type TEXT NOT NULL DEFAULT 'door_split' CHECK (deal_type IN ('guarantee', 'door_split', 'hybrid')),
    guarantee_cents INTEGER NOT NULL DEFAULT 0,
    door_split_pct INTEGER NOT NULL DEFAULT 70,
    promoter_fee_pct INTEGER NOT NULL DEFAULT 0,
    tax_pct INTEGER NOT NULL DEFAULT 0,
    advance_cents INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_bookings_room_id ON bookings(room_id);
CREATE INDEX IF NOT EXISTS idx_bookings_musician_user_id ON bookings(musician_user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_event_id ON bookings(event_id);
CREATE INDEX IF NOT EXISTS idx_bookings_state ON bookings(state);
CREATE INDEX IF NOT EXISTS idx_bookings_event_date ON bookings(event_date);
CREATE INDEX IF NOT EXISTS idx_bookings_room_date ON bookings(room_id, event_date);

-- Booking state transition audit trail
CREATE TABLE IF NOT EXISTS booking_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    actor_user_id INTEGER NOT NULL REFERENCES users(id),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_booking_history_booking_id ON booking_history(booking_id);

-- Events: created by promoters, group bookings across venues
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promoter_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    event_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_promoter_user_id ON events(promoter_user_id);
CREATE INDEX IF NOT EXISTS idx_events_venue_id ON events(venue_id);

-- Ticket tiers per booking
CREATE TABLE IF NOT EXISTS ticket_tiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    price_cents INTEGER NOT NULL DEFAULT 0,
    quantity INTEGER NOT NULL DEFAULT 0,
    sold_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ticket_tiers_booking_id ON ticket_tiers(booking_id);

-- Settlement sheets per booking
CREATE TABLE IF NOT EXISTS settlements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE CASCADE,
    door_revenue_cents INTEGER NOT NULL DEFAULT 0,
    expenses_cents INTEGER NOT NULL DEFAULT 0,
    musician_payout_cents INTEGER NOT NULL DEFAULT 0,
    venue_share_cents INTEGER NOT NULL DEFAULT 0,
    promoter_fee_cents INTEGER NOT NULL DEFAULT 0,
    tax_amount_cents INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved')),
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    approved_by_user_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    approved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_settlements_booking_id ON settlements(booking_id);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    link TEXT NOT NULL DEFAULT '',
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(user_id, is_read);

-- FTS5 full-text search for venues
CREATE VIRTUAL TABLE IF NOT EXISTS venues_fts USING fts5(
    name, location, description, genre_tags,
    content='venues',
    content_rowid='id'
);

-- FTS5 sync triggers
CREATE TRIGGER IF NOT EXISTS venues_fts_insert AFTER INSERT ON venues BEGIN
    INSERT INTO venues_fts(rowid, name, location, description, genre_tags)
    VALUES (new.id, new.name, new.location, new.description, new.genre_tags);
END;

CREATE TRIGGER IF NOT EXISTS venues_fts_update AFTER UPDATE ON venues BEGIN
    DELETE FROM venues_fts WHERE rowid = old.id;
    INSERT INTO venues_fts(rowid, name, location, description, genre_tags)
    VALUES (new.id, new.name, new.location, new.description, new.genre_tags);
END;

CREATE TRIGGER IF NOT EXISTS venues_fts_delete AFTER DELETE ON venues BEGIN
    DELETE FROM venues_fts WHERE rowid = old.id;
END;
