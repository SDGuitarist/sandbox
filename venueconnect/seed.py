"""Seed script -- run with: .venv/bin/python seed.py"""
import os
import sys
os.environ.setdefault('SECRET_KEY', 'seed-dev-key')
sys.path.insert(0, os.path.dirname(__file__))

from werkzeug.security import generate_password_hash
from app import create_app
from app.db import get_db, init_db

app = create_app()

with app.app_context():
    init_db()
    conn = get_db()

    # Demo users (password: 'password123' for all)
    pw = generate_password_hash('password123')
    conn.execute("INSERT OR IGNORE INTO users (username, email, password_hash, role, display_name, bio, genre_tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('bluenote_mgr', 'mgr@bluenote.com', pw, 'venue_manager', 'Blue Note Manager', 'Managing the best jazz venue in town', 'jazz'))
    conn.execute("INSERT OR IGNORE INTO users (username, email, password_hash, role, display_name, bio, genre_tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('jazz_trio', 'trio@music.com', pw, 'musician', 'The Jazz Trio', 'Three-piece jazz ensemble', 'jazz,fusion'))
    conn.execute("INSERT OR IGNORE INTO users (username, email, password_hash, role, display_name, bio, genre_tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('rock_band', 'rock@music.com', pw, 'musician', 'The Amplifiers', 'High-energy rock band', 'rock,alternative'))
    conn.execute("INSERT OR IGNORE INTO users (username, email, password_hash, role, display_name, bio, genre_tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('city_nights', 'promo@citynights.com', pw, 'promoter', 'City Nights Promotions', 'Premier live music promoter', ''))
    conn.commit()

    # Get user IDs
    mgr = conn.execute("SELECT id FROM users WHERE username='bluenote_mgr'").fetchone()
    trio = conn.execute("SELECT id FROM users WHERE username='jazz_trio'").fetchone()
    rock = conn.execute("SELECT id FROM users WHERE username='rock_band'").fetchone()
    promo = conn.execute("SELECT id FROM users WHERE username='city_nights'").fetchone()

    # Venue + rooms
    conn.execute("INSERT OR IGNORE INTO venues (id, user_id, name, location, description, capacity, genre_tags) VALUES (1, ?, 'The Blue Note', '123 Jazz St, New York', 'Premier jazz venue since 1981', 300, 'jazz,blues,fusion')", (mgr['id'],))
    conn.execute("INSERT OR IGNORE INTO rooms (id, venue_id, name, capacity, description, has_pa, has_lighting) VALUES (1, 1, 'Main Stage', 200, 'Full concert stage with grand piano', 1, 1)")
    conn.execute("INSERT OR IGNORE INTO rooms (id, venue_id, name, capacity, description, has_pa, has_lighting) VALUES (2, 1, 'Lounge', 50, 'Intimate lounge setting', 1, 0)")

    # Availability windows (Fri-Sat 7pm-2am for Main Stage)
    conn.execute("INSERT OR IGNORE INTO availability_windows (id, room_id, day_of_week, start_time, end_time) VALUES (1, 1, 4, '19:00', '02:00')")
    conn.execute("INSERT OR IGNORE INTO availability_windows (id, room_id, day_of_week, start_time, end_time) VALUES (2, 1, 5, '19:00', '02:00')")
    conn.execute("INSERT OR IGNORE INTO availability_windows (id, room_id, day_of_week, start_time, end_time) VALUES (3, 2, 3, '20:00', '00:00')")

    # Bookings in various states
    conn.execute("""INSERT OR IGNORE INTO bookings (id, room_id, musician_user_id, event_name, event_date,
        start_time, end_time, state, deal_type, guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct, notes)
        VALUES (1, 1, ?, 'Jazz Night', '2026-06-06', '20:00', '23:00', 'confirmed', 'door_split', 0, 70, 0, 8, 'Looking forward to it')""",
        (trio['id'],))
    conn.execute("""INSERT OR IGNORE INTO bookings (id, room_id, musician_user_id, event_name, event_date,
        start_time, end_time, state, deal_type, guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct, notes)
        VALUES (2, 1, ?, 'Rock the House', '2026-05-30', '21:00', '01:00', 'performed', 'hybrid', 50000, 70, 10, 8, '')""",
        (rock['id'],))
    conn.execute("""INSERT OR IGNORE INTO bookings (id, room_id, musician_user_id, event_name, event_date,
        start_time, end_time, state, deal_type, guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct, notes)
        VALUES (3, 2, ?, 'Lounge Sessions', '2026-06-12', '20:00', '23:00', 'requested', 'guarantee', 30000, 0, 0, 8, 'Acoustic set')""",
        (trio['id'],))

    # Booking history
    conn.execute("INSERT OR IGNORE INTO booking_history (booking_id, from_state, to_state, actor_user_id, notes, created_at) VALUES (1, 'requested', 'confirmed', ?, '', datetime('now'))", (mgr['id'],))

    # Ticket tiers for the performed booking
    conn.execute("INSERT OR IGNORE INTO ticket_tiers (id, booking_id, name, price_cents, quantity, sold_count) VALUES (1, 2, 'General Admission', 2500, 150, 120)")
    conn.execute("INSERT OR IGNORE INTO ticket_tiers (id, booking_id, name, price_cents, quantity, sold_count) VALUES (2, 2, 'VIP', 5000, 30, 25)")

    # Settlement for the performed booking
    conn.execute("""INSERT OR IGNORE INTO settlements (id, booking_id, door_revenue_cents, expenses_cents,
        musician_payout_cents, venue_share_cents, promoter_fee_cents, tax_amount_cents,
        status, created_by_user_id)
        VALUES (1, 2, 425000, 15000, 287000, 83000, 42500, 34000, 'draft', ?)""",
        (mgr['id'],))

    # Event for promoter
    conn.execute("INSERT OR IGNORE INTO events (id, promoter_user_id, venue_id, name, description, event_date) VALUES (1, ?, 1, 'Summer Jazz Festival', 'Annual jazz celebration', '2026-07-15')", (promo['id'],))

    # Notifications
    conn.execute("INSERT OR IGNORE INTO notifications (user_id, message, link, is_read) VALUES (?, 'New booking request for Jazz Night', '/manage/bookings/1', 0)", (mgr['id'],))
    conn.execute("INSERT OR IGNORE INTO notifications (user_id, message, link, is_read) VALUES (?, 'Your booking \"Jazz Night\" has been confirmed!', '/bookings/1', 0)", (trio['id'],))
    conn.execute("INSERT OR IGNORE INTO notifications (user_id, message, link, is_read) VALUES (?, 'Settlement sheet ready for \"Rock the House\"', '/settlements/1', 0)", (rock['id'],))

    conn.commit()
    print("Seed data created successfully.")
    print("Demo accounts: bluenote_mgr / jazz_trio / rock_band / city_nights (password: password123)")
