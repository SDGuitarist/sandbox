from flask import render_template

from app.db import get_db
from app.models import get_dashboard_stats
from app.blueprints.dashboard import dashboard_bp


@dashboard_bp.route('/')
def index():
    with get_db() as conn:
        stats = get_dashboard_stats(conn)
    return render_template('dashboard/index.html',
        stats=stats
    )
