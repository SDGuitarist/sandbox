from flask import Blueprint, render_template, g
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import get_musician_upcoming_gigs, get_musician_pending_count
from app.notifications import get_notifications

dashboard_musician_bp = Blueprint('dashboard_musician', __name__)


@dashboard_musician_bp.route('/')
@login_required
@role_required('musician')
def index():
    conn = get_db()
    upcoming_gigs = get_musician_upcoming_gigs(conn, g.user['id'])
    pending_count = get_musician_pending_count(conn, g.user['id'])
    recent_notifications = get_notifications(conn, g.user['id'], limit=5)
    return render_template('dashboard/musician.html',
                           upcoming_gigs=upcoming_gigs,
                           pending_count=pending_count,
                           recent_notifications=recent_notifications)
