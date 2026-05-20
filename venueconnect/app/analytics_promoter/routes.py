from flask import Blueprint, render_template, g
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import (get_promoter_revenue_by_month,
                         get_promoter_settlements_by_venue,
                         get_promoter_event_status_counts)

analytics_promoter_bp = Blueprint('analytics_promoter', __name__)


@analytics_promoter_bp.route('/')
@login_required
@role_required('promoter')
def index():
    conn = get_db()
    user_id = g.user['id']

    revenue_data = [dict(r) for r in get_promoter_revenue_by_month(conn, user_id)]
    settlements_data = [dict(r) for r in get_promoter_settlements_by_venue(conn, user_id)]
    status_data = [dict(r) for r in get_promoter_event_status_counts(conn, user_id)]

    return render_template('analytics/promoter.html',
                           revenue_data=revenue_data,
                           settlements_data=settlements_data,
                           status_data=status_data)
