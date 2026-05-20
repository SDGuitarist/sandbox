from flask import Blueprint, render_template, g
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import get_venues_by_manager

dashboard_venue_bp = Blueprint('dashboard_venue', __name__)


@dashboard_venue_bp.route('/')
@login_required
@role_required('venue_manager')
def index():
    conn = get_db()
    user_id = g.user['id']
    venues = get_venues_by_manager(conn, user_id)

    # Two aggregate queries instead of N+1 loop per venue
    upcoming_bookings = conn.execute(
        '''SELECT b.*, r.name AS room_name, u.display_name AS musician_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE v.user_id = ? AND b.state IN ('confirmed', 'advanced')
           AND b.event_date >= date('now')
           ORDER BY b.event_date ASC LIMIT 10''',
        (user_id,)
    ).fetchall()

    row = conn.execute(
        '''SELECT COUNT(*) AS cnt FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           WHERE v.user_id = ? AND b.state = 'requested' ''',
        (user_id,)
    ).fetchone()
    pending_count = row['cnt']

    return render_template('dashboard/venue.html',
                           upcoming_bookings=upcoming_bookings,
                           pending_count=pending_count,
                           venues=venues)
