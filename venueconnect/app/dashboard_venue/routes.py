from flask import Blueprint, render_template, g
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import (get_venue_upcoming_bookings, get_venue_pending_count,
                         get_venues_by_manager)

dashboard_venue_bp = Blueprint('dashboard_venue', __name__)


@dashboard_venue_bp.route('/')
@login_required
@role_required('venue_manager')
def index():
    conn = get_db()
    venues = get_venues_by_manager(conn, g.user['id'])

    # Aggregate data across all venues owned by the manager
    upcoming_bookings = []
    pending_count = 0
    for venue in venues:
        upcoming_bookings.extend(get_venue_upcoming_bookings(conn, venue['id']))
        pending_count += get_venue_pending_count(conn, venue['id'])

    return render_template('dashboard/venue.html',
                           upcoming_bookings=upcoming_bookings,
                           pending_count=pending_count,
                           venues=venues)
