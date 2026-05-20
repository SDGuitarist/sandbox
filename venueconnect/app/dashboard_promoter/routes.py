from flask import Blueprint, render_template, g
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import get_promoter_upcoming_events, get_promoter_settlement_status

dashboard_promoter_bp = Blueprint('dashboard_promoter', __name__)


@dashboard_promoter_bp.route('/')
@login_required
@role_required('promoter')
def index():
    conn = get_db()
    upcoming_events = get_promoter_upcoming_events(conn, g.user['id'])
    settlement_status = get_promoter_settlement_status(conn, g.user['id'])
    return render_template(
        'dashboard/promoter.html',
        upcoming_events=upcoming_events,
        settlement_status=settlement_status,
    )
