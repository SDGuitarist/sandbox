from flask import Blueprint, render_template, abort, g
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import (get_venue_revenue_by_month, get_venue_occupancy_by_room,
                         get_venue_genre_distribution, get_venues_by_manager)

analytics_venue_bp = Blueprint('analytics_venue', __name__)


@analytics_venue_bp.route('/')
@login_required
@role_required('venue_manager')
def index():
    conn = get_db()
    venues = get_venues_by_manager(conn, g.user['id'])
    if not venues:
        abort(404)
    venue = venues[0]
    venue_id = venue['id']

    revenue_data = [dict(r) for r in get_venue_revenue_by_month(conn, venue_id)]
    occupancy_data = [dict(r) for r in get_venue_occupancy_by_room(conn, venue_id)]
    genre_data = [dict(r) for r in get_venue_genre_distribution(conn, venue_id)]

    return render_template('analytics/venue.html',
                           revenue_data=revenue_data,
                           occupancy_data=occupancy_data,
                           genre_data=genre_data,
                           venue=venue)
