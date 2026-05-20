"""
Model functions for VenueConnect.
All functions take a conn (sqlite3.Connection) as first argument.
Functions marked "does NOT commit" leave commit responsibility to the caller.
"""


# ---------------------------------------------------------------------------
# User Functions
# ---------------------------------------------------------------------------

# Returns: int (the new user's ID)
# Usage:
#   user_id = create_user(conn, 'jdoe', 'j@example.com', hashed_pw, 'musician', 'John Doe')
#   redirect(url_for('auth.login'))
def create_user(conn, username, email, password_hash, role, display_name):
    cur = conn.execute(
        'INSERT INTO users (username, email, password_hash, role, display_name) VALUES (?, ?, ?, ?, ?)',
        (username, email, password_hash, role, display_name)
    )
    conn.commit()
    return cur.lastrowid


# Returns: sqlite3.Row or None
# Usage:
#   user = get_user_by_id(conn, user_id)
#   if user is None: abort(404)
def get_user_by_id(conn, user_id):
    return conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()


# Returns: sqlite3.Row or None
# Usage:
#   user = get_user_by_username(conn, username)
#   if user is None: flash('Invalid credentials', 'error')
def get_user_by_username(conn, username):
    return conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()


# Returns: None -- does NOT commit
# Usage:
#   update_user_profile(conn, g.user['id'], display_name, bio, genre_tags)
#   conn.commit()
def update_user_profile(conn, user_id, display_name, bio, genre_tags):
    conn.execute(
        'UPDATE users SET display_name = ?, bio = ?, genre_tags = ? WHERE id = ?',
        (display_name, bio, genre_tags, user_id)
    )


# ---------------------------------------------------------------------------
# Venue Functions
# ---------------------------------------------------------------------------

# Returns: int (the new venue's ID) -- does NOT commit
# Usage:
#   venue_id = create_venue(conn, g.user['id'], name, location, description, capacity, genre_tags)
#   conn.commit()
#   redirect(url_for('venues.detail', venue_id=venue_id))
def create_venue(conn, user_id, name, location, description, capacity, genre_tags):
    cur = conn.execute(
        'INSERT INTO venues (user_id, name, location, description, capacity, genre_tags) VALUES (?, ?, ?, ?, ?, ?)',
        (user_id, name, location, description, capacity, genre_tags)
    )
    return cur.lastrowid


# Returns: sqlite3.Row or None
def get_venue(conn, venue_id):
    return conn.execute('SELECT * FROM venues WHERE id = ?', (venue_id,)).fetchone()


# Returns: list[sqlite3.Row]
def get_venues_by_manager(conn, user_id):
    return conn.execute('SELECT * FROM venues WHERE user_id = ? ORDER BY name', (user_id,)).fetchall()


# Returns: list[sqlite3.Row]
def get_all_venues(conn):
    return conn.execute('SELECT * FROM venues ORDER BY name').fetchall()


# Returns: None -- does NOT commit
def update_venue(conn, venue_id, name, location, description, capacity, genre_tags):
    conn.execute(
        'UPDATE venues SET name=?, location=?, description=?, capacity=?, genre_tags=?, updated_at=datetime("now") WHERE id=?',
        (name, location, description, capacity, genre_tags, venue_id)
    )


# Returns: None -- does NOT commit
def delete_venue(conn, venue_id):
    conn.execute('DELETE FROM venues WHERE id = ?', (venue_id,))


# ---------------------------------------------------------------------------
# Room Functions
# ---------------------------------------------------------------------------

# Returns: int (room_id)
def create_room(conn, venue_id, name, capacity, description, has_pa, has_lighting):
    cur = conn.execute(
        'INSERT INTO rooms (venue_id, name, capacity, description, has_pa, has_lighting) VALUES (?, ?, ?, ?, ?, ?)',
        (venue_id, name, capacity, description, int(has_pa), int(has_lighting))
    )
    return cur.lastrowid


# Returns: sqlite3.Row or None
def get_room(conn, room_id):
    return conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()


# Returns: list[sqlite3.Row]
def get_rooms_by_venue(conn, venue_id):
    return conn.execute('SELECT * FROM rooms WHERE venue_id = ? ORDER BY name', (venue_id,)).fetchall()


# Returns: None -- does NOT commit
def update_room(conn, room_id, name, capacity, description, has_pa, has_lighting):
    conn.execute(
        'UPDATE rooms SET name=?, capacity=?, description=?, has_pa=?, has_lighting=? WHERE id=?',
        (name, capacity, description, int(has_pa), int(has_lighting), room_id)
    )


# Returns: None -- does NOT commit
def delete_room(conn, room_id):
    conn.execute('DELETE FROM rooms WHERE id = ?', (room_id,))


# ---------------------------------------------------------------------------
# Availability Functions
# ---------------------------------------------------------------------------

# Returns: int (window_id)
def create_availability_window(conn, room_id, day_of_week, start_time, end_time):
    cur = conn.execute(
        'INSERT INTO availability_windows (room_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?)',
        (room_id, day_of_week, start_time, end_time)
    )
    return cur.lastrowid


# Returns: list[sqlite3.Row]
def get_availability_windows(conn, room_id):
    return conn.execute(
        'SELECT * FROM availability_windows WHERE room_id = ? ORDER BY day_of_week, start_time',
        (room_id,)
    ).fetchall()


# Returns: None -- does NOT commit
def delete_availability_window(conn, window_id):
    conn.execute('DELETE FROM availability_windows WHERE id = ?', (window_id,))


# Returns: bool (True if available, False if conflict exists)
# IMPORTANT: must be called inside BEGIN IMMEDIATE transaction
# Usage:
#   conn = get_db()
#   conn.execute('BEGIN IMMEDIATE')
#   if not check_room_available(conn, room_id, event_date, start_time, end_time):
#       conn.rollback()
#       flash('Time slot conflict.', 'error')
#       return redirect(...)
#   booking_id = create_booking(conn, ...)
#   conn.commit()
def check_room_available(conn, room_id, event_date, start_time, end_time):
    conflict = conn.execute(
        '''SELECT id FROM bookings
           WHERE room_id = ? AND event_date = ?
           AND start_time < ? AND end_time > ?
           AND state NOT IN ('settled', 'paid')''',
        (room_id, event_date, end_time, start_time)
    ).fetchone()
    return conflict is None


# ---------------------------------------------------------------------------
# Booking Functions
# ---------------------------------------------------------------------------

# Returns: int (booking_id)
# IMPORTANT: does NOT commit -- caller commits after conflict check
# Usage (inside BEGIN IMMEDIATE):
#   booking_id = create_booking(conn, room_id, g.user['id'], event_name, event_date,
#                                start_time, end_time, deal_type, guarantee_cents,
#                                door_split_pct, promoter_fee_pct, tax_pct, notes)
#   conn.commit()
def create_booking(conn, room_id, musician_user_id, event_name, event_date,
                   start_time, end_time, deal_type, guarantee_cents,
                   door_split_pct, promoter_fee_pct, tax_pct, notes):
    cur = conn.execute(
        '''INSERT INTO bookings (room_id, musician_user_id, event_name, event_date,
           start_time, end_time, state, deal_type, guarantee_cents, door_split_pct,
           promoter_fee_pct, tax_pct, notes)
           VALUES (?, ?, ?, ?, ?, ?, 'requested', ?, ?, ?, ?, ?, ?)''',
        (room_id, musician_user_id, event_name, event_date, start_time, end_time,
         deal_type, guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct, notes)
    )
    return cur.lastrowid


# Returns: sqlite3.Row or None (with joined venue/room/musician info)
def get_booking(conn, booking_id):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, r.venue_id, v.name AS venue_name,
           v.user_id AS venue_manager_id, u.display_name AS musician_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE b.id = ?''',
        (booking_id,)
    ).fetchone()


# Returns: list[sqlite3.Row]
def get_bookings_by_musician(conn, musician_user_id):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, v.name AS venue_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           WHERE b.musician_user_id = ?
           ORDER BY b.event_date DESC''',
        (musician_user_id,)
    ).fetchall()


# Returns: list[sqlite3.Row]
def get_bookings_by_venue(conn, venue_id):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, u.display_name AS musician_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE r.venue_id = ?
           ORDER BY b.event_date DESC''',
        (venue_id,)
    ).fetchall()


# Returns: list[sqlite3.Row]
def get_pending_bookings_for_venue(conn, venue_id):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, u.display_name AS musician_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE r.venue_id = ? AND b.state = 'requested'
           ORDER BY b.event_date ASC''',
        (venue_id,)
    ).fetchall()


# Returns: list[sqlite3.Row]
def get_bookings_by_event(conn, event_id):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, u.display_name AS musician_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE b.event_id = ?
           ORDER BY b.start_time ASC''',
        (event_id,)
    ).fetchall()


# Returns: list[sqlite3.Row] (booking history for audit trail)
def get_booking_history(conn, booking_id):
    return conn.execute(
        '''SELECT bh.*, u.display_name AS actor_name
           FROM booking_history bh
           JOIN users u ON bh.actor_user_id = u.id
           WHERE bh.booking_id = ?
           ORDER BY bh.created_at DESC''',
        (booking_id,)
    ).fetchall()


# ---------------------------------------------------------------------------
# Event Functions
# ---------------------------------------------------------------------------

# Returns: int (event_id)
def create_event(conn, promoter_user_id, venue_id, name, description, event_date):
    cur = conn.execute(
        'INSERT INTO events (promoter_user_id, venue_id, name, description, event_date) VALUES (?, ?, ?, ?, ?)',
        (promoter_user_id, venue_id, name, description, event_date)
    )
    return cur.lastrowid


# Returns: sqlite3.Row or None (with venue name)
def get_event(conn, event_id):
    return conn.execute(
        '''SELECT e.*, v.name AS venue_name, u.display_name AS promoter_name
           FROM events e
           JOIN venues v ON e.venue_id = v.id
           JOIN users u ON e.promoter_user_id = u.id
           WHERE e.id = ?''',
        (event_id,)
    ).fetchone()


# Returns: list[sqlite3.Row]
def get_events_by_promoter(conn, promoter_user_id):
    return conn.execute(
        '''SELECT e.*, v.name AS venue_name
           FROM events e JOIN venues v ON e.venue_id = v.id
           WHERE e.promoter_user_id = ?
           ORDER BY e.event_date DESC''',
        (promoter_user_id,)
    ).fetchall()


# Returns: None -- does NOT commit
def update_event(conn, event_id, name, description, event_date):
    conn.execute(
        'UPDATE events SET name=?, description=?, event_date=?, updated_at=datetime("now") WHERE id=?',
        (name, description, event_date, event_id)
    )


# Returns: None -- does NOT commit
def link_booking_to_event(conn, booking_id, event_id):
    conn.execute('UPDATE bookings SET event_id = ? WHERE id = ?', (event_id, booking_id))


# ---------------------------------------------------------------------------
# Ticket Tier Functions
# ---------------------------------------------------------------------------

# Returns: int (tier_id)
def create_ticket_tier(conn, booking_id, name, price_cents, quantity):
    cur = conn.execute(
        'INSERT INTO ticket_tiers (booking_id, name, price_cents, quantity) VALUES (?, ?, ?, ?)',
        (booking_id, name, price_cents, quantity)
    )
    return cur.lastrowid


# Returns: list[sqlite3.Row]
def get_ticket_tiers(conn, booking_id):
    return conn.execute(
        'SELECT * FROM ticket_tiers WHERE booking_id = ? ORDER BY name', (booking_id,)
    ).fetchall()


# Returns: None -- does NOT commit
def update_ticket_tier(conn, tier_id, name, price_cents, quantity, sold_count):
    conn.execute(
        'UPDATE ticket_tiers SET name=?, price_cents=?, quantity=?, sold_count=? WHERE id=?',
        (name, price_cents, quantity, sold_count, tier_id)
    )


# Returns: None -- does NOT commit
def delete_ticket_tier(conn, tier_id):
    conn.execute('DELETE FROM ticket_tiers WHERE id = ?', (tier_id,))


# Returns: int (total door revenue in cents)
# Usage:
#   total_cents = get_total_door_revenue_cents(conn, booking_id)
def get_total_door_revenue_cents(conn, booking_id):
    row = conn.execute(
        'SELECT COALESCE(SUM(price_cents * sold_count), 0) AS total FROM ticket_tiers WHERE booking_id = ?',
        (booking_id,)
    ).fetchone()
    return row['total']


# ---------------------------------------------------------------------------
# Settlement Functions
# ---------------------------------------------------------------------------

# Returns: int (settlement_id) -- does NOT commit
def create_settlement(conn, booking_id, door_revenue_cents, expenses_cents,
                      musician_payout_cents, venue_share_cents,
                      promoter_fee_cents, tax_amount_cents, created_by_user_id):
    cur = conn.execute(
        '''INSERT INTO settlements (booking_id, door_revenue_cents, expenses_cents,
           musician_payout_cents, venue_share_cents, promoter_fee_cents,
           tax_amount_cents, created_by_user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (booking_id, door_revenue_cents, expenses_cents, musician_payout_cents,
         venue_share_cents, promoter_fee_cents, tax_amount_cents, created_by_user_id)
    )
    return cur.lastrowid


# Returns: sqlite3.Row or None (with booking/venue/musician info)
def get_settlement(conn, settlement_id):
    return conn.execute(
        '''SELECT s.*, b.event_name, b.event_date, b.deal_type,
           b.guarantee_cents, b.door_split_pct, b.promoter_fee_pct, b.tax_pct,
           b.musician_user_id, r.name AS room_name, r.venue_id,
           v.name AS venue_name, v.user_id AS venue_manager_id,
           u.display_name AS musician_name
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE s.id = ?''',
        (settlement_id,)
    ).fetchone()


# Returns: sqlite3.Row or None
def get_settlement_by_booking(conn, booking_id):
    return conn.execute(
        'SELECT * FROM settlements WHERE booking_id = ?', (booking_id,)
    ).fetchone()


# Returns: list[sqlite3.Row]
def get_settlements_list(conn, user_id, role):
    if role == 'venue_manager':
        return conn.execute(
            '''SELECT s.*, b.event_name, b.event_date, u.display_name AS musician_name
               FROM settlements s
               JOIN bookings b ON s.booking_id = b.id
               JOIN rooms r ON b.room_id = r.id
               JOIN venues v ON r.venue_id = v.id
               JOIN users u ON b.musician_user_id = u.id
               WHERE v.user_id = ?
               ORDER BY s.created_at DESC''',
            (user_id,)
        ).fetchall()
    elif role == 'musician':
        return conn.execute(
            '''SELECT s.*, b.event_name, b.event_date, v.name AS venue_name
               FROM settlements s
               JOIN bookings b ON s.booking_id = b.id
               JOIN rooms r ON b.room_id = r.id
               JOIN venues v ON r.venue_id = v.id
               WHERE b.musician_user_id = ?
               ORDER BY s.created_at DESC''',
            (user_id,)
        ).fetchall()
    else:  # promoter
        return conn.execute(
            '''SELECT s.*, b.event_name, b.event_date, v.name AS venue_name
               FROM settlements s
               JOIN bookings b ON s.booking_id = b.id
               JOIN rooms r ON b.room_id = r.id
               JOIN venues v ON r.venue_id = v.id
               JOIN events e ON b.event_id = e.id
               WHERE e.promoter_user_id = ?
               ORDER BY s.created_at DESC''',
            (user_id,)
        ).fetchall()


# Returns: None -- does NOT commit
def approve_settlement(conn, settlement_id, approved_by_user_id):
    conn.execute(
        '''UPDATE settlements SET status='approved', approved_by_user_id=?,
           approved_at=datetime('now') WHERE id=?''',
        (approved_by_user_id, settlement_id)
    )


# ---------------------------------------------------------------------------
# Analytics Functions
# ---------------------------------------------------------------------------

# Returns: list[sqlite3.Row] with columns: month (TEXT 'YYYY-MM'), total_cents (INT)
def get_venue_revenue_by_month(conn, venue_id):
    return conn.execute(
        '''SELECT strftime('%Y-%m', b.event_date) AS month,
           SUM(s.door_revenue_cents) AS total_cents
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           JOIN rooms r ON b.room_id = r.id
           WHERE r.venue_id = ?
           GROUP BY month ORDER BY month''',
        (venue_id,)
    ).fetchall()


# Returns: list[sqlite3.Row] with columns: room_name (TEXT), booking_count (INT)
def get_venue_occupancy_by_room(conn, venue_id):
    return conn.execute(
        '''SELECT r.name AS room_name,
           COUNT(b.id) AS booking_count
           FROM rooms r
           LEFT JOIN bookings b ON r.id = b.room_id AND b.state NOT IN ('requested')
           WHERE r.venue_id = ?
           GROUP BY r.id ORDER BY r.name''',
        (venue_id,)
    ).fetchall()


# Returns: list[sqlite3.Row] with columns: genre (TEXT), count (INT)
def get_venue_genre_distribution(conn, venue_id):
    return conn.execute(
        '''SELECT u.genre_tags AS genre, COUNT(*) AS count
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE r.venue_id = ? AND u.genre_tags != ''
           GROUP BY u.genre_tags ORDER BY count DESC LIMIT 10''',
        (venue_id,)
    ).fetchall()


# Returns: list[sqlite3.Row] with columns: month, total_cents
def get_musician_earnings_by_month(conn, user_id):
    return conn.execute(
        '''SELECT strftime('%Y-%m', b.event_date) AS month,
           SUM(s.musician_payout_cents) AS total_cents
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           WHERE b.musician_user_id = ?
           GROUP BY month ORDER BY month''',
        (user_id,)
    ).fetchall()


# Returns: list[sqlite3.Row] with columns: venue_name (TEXT), gig_count (INT)
def get_musician_venues_played(conn, user_id):
    return conn.execute(
        '''SELECT v.name AS venue_name, COUNT(*) AS gig_count
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           WHERE b.musician_user_id = ? AND b.state IN ('performed', 'settled', 'paid')
           GROUP BY v.id ORDER BY gig_count DESC LIMIT 10''',
        (user_id,)
    ).fetchall()


# Returns: dict with keys: confirmed (int), rejected (int), total (int)
def get_musician_booking_success_rate(conn, user_id):
    rows = conn.execute(
        '''SELECT state, COUNT(*) AS cnt FROM bookings
           WHERE musician_user_id = ? GROUP BY state''',
        (user_id,)
    ).fetchall()
    confirmed = sum(r['cnt'] for r in rows if r['state'] not in ('requested',))
    total = sum(r['cnt'] for r in rows)
    rejected_count = 0  # bookings that went back to available are deleted from history
    return {'confirmed': confirmed, 'rejected': rejected_count, 'total': total}


# Returns: list[sqlite3.Row] with columns: month, total_cents
def get_promoter_revenue_by_month(conn, user_id):
    return conn.execute(
        '''SELECT strftime('%Y-%m', b.event_date) AS month,
           SUM(s.promoter_fee_cents) AS total_cents
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           JOIN events e ON b.event_id = e.id
           WHERE e.promoter_user_id = ?
           GROUP BY month ORDER BY month''',
        (user_id,)
    ).fetchall()


# Returns: list[sqlite3.Row] with columns: venue_name, total_cents
def get_promoter_settlements_by_venue(conn, user_id):
    return conn.execute(
        '''SELECT v.name AS venue_name, SUM(s.door_revenue_cents) AS total_cents
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           JOIN events e ON b.event_id = e.id
           WHERE e.promoter_user_id = ?
           GROUP BY v.id ORDER BY total_cents DESC''',
        (user_id,)
    ).fetchall()


# Returns: list[sqlite3.Row] with columns: status (TEXT), count (INT)
def get_promoter_event_status_counts(conn, user_id):
    return conn.execute(
        '''SELECT b.state AS status, COUNT(*) AS count
           FROM bookings b
           JOIN events e ON b.event_id = e.id
           WHERE e.promoter_user_id = ?
           GROUP BY b.state''',
        (user_id,)
    ).fetchall()


# ---------------------------------------------------------------------------
# Dashboard Summary Functions
# ---------------------------------------------------------------------------

# Returns: list[sqlite3.Row] -- upcoming confirmed bookings for a venue
def get_venue_upcoming_bookings(conn, venue_id, limit=5):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, u.display_name AS musician_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE r.venue_id = ? AND b.state IN ('confirmed', 'advanced')
           AND b.event_date >= date('now')
           ORDER BY b.event_date ASC LIMIT ?''',
        (venue_id, limit)
    ).fetchall()


# Returns: int -- count of pending booking requests for a venue
def get_venue_pending_count(conn, venue_id):
    row = conn.execute(
        '''SELECT COUNT(*) AS cnt FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           WHERE r.venue_id = ? AND b.state = 'requested' ''',
        (venue_id,)
    ).fetchone()
    return row['cnt']


# Returns: list[sqlite3.Row] -- upcoming gigs for a musician
def get_musician_upcoming_gigs(conn, user_id, limit=5):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, v.name AS venue_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           WHERE b.musician_user_id = ? AND b.state IN ('confirmed', 'advanced')
           AND b.event_date >= date('now')
           ORDER BY b.event_date ASC LIMIT ?''',
        (user_id, limit)
    ).fetchall()


# Returns: int -- count of musician's pending requests
def get_musician_pending_count(conn, user_id):
    row = conn.execute(
        'SELECT COUNT(*) AS cnt FROM bookings WHERE musician_user_id = ? AND state = ?',
        (user_id, 'requested')
    ).fetchone()
    return row['cnt']


# Returns: list[sqlite3.Row] -- upcoming events for a promoter
def get_promoter_upcoming_events(conn, user_id, limit=5):
    return conn.execute(
        '''SELECT e.*, v.name AS venue_name
           FROM events e
           JOIN venues v ON e.venue_id = v.id
           WHERE e.promoter_user_id = ? AND e.event_date >= date('now')
           ORDER BY e.event_date ASC LIMIT ?''',
        (user_id, limit)
    ).fetchall()


# Returns: dict with keys: total_settlements (int), pending_settlements (int)
def get_promoter_settlement_status(conn, user_id):
    row = conn.execute(
        '''SELECT COUNT(*) AS total,
           SUM(CASE WHEN s.status = 'draft' THEN 1 ELSE 0 END) AS pending
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           JOIN events e ON b.event_id = e.id
           WHERE e.promoter_user_id = ?''',
        (user_id,)
    ).fetchone()
    return {'total_settlements': row['total'] or 0, 'pending_settlements': row['pending'] or 0}


# ---------------------------------------------------------------------------
# FTS5 Search Function
# ---------------------------------------------------------------------------

# Returns: list[sqlite3.Row] with venue columns
# Usage:
#   results = search_venues(conn, query)
def search_venues(conn, query):
    import re
    if not query or not query.strip():
        return get_all_venues(conn)
    # Sanitize FTS5 query: strip operators to prevent injection
    cleaned = re.sub(r'[*"():^]', '', query)
    cleaned = ' '.join(cleaned.split())
    if not cleaned:
        return get_all_venues(conn)
    # Quote as phrase to prevent FTS5 operator injection
    safe_query = f'"{cleaned}"'
    return conn.execute(
        '''SELECT v.* FROM venues v
           JOIN venues_fts ON v.id = venues_fts.rowid
           WHERE venues_fts MATCH ?
           ORDER BY rank LIMIT 50''',
        (safe_query,)
    ).fetchall()
