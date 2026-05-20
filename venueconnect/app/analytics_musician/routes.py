from flask import Blueprint, render_template, g

from app.db import get_db
from app.decorators import login_required, role_required
from app.models import (
    get_musician_earnings_by_month,
    get_musician_venues_played,
    get_musician_booking_success_rate,
)

analytics_musician_bp = Blueprint('analytics_musician', __name__)


@analytics_musician_bp.route('/')
@login_required
@role_required('musician')
def index():
    conn = get_db()
    user_id = g.user['id']

    # Convert sqlite3.Row lists to list of dicts for tojson
    earnings_data = [dict(r) for r in get_musician_earnings_by_month(conn, user_id)]
    venues_data = [dict(r) for r in get_musician_venues_played(conn, user_id)]

    # success_data is already a dict (from get_musician_booking_success_rate)
    success_data = get_musician_booking_success_rate(conn, user_id)

    return render_template(
        'analytics/musician.html',
        earnings_data=earnings_data,
        venues_data=venues_data,
        success_data=success_data,
    )
