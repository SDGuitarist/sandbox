from flask import Blueprint, render_template
from app.db import get_db
from app.auth import login_required
from app.models.submissions import count_by_status

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    conn = get_db()
    stats = count_by_status(conn)
    total = sum(stats.values())
    return render_template('dashboard/index.html', stats=stats, total=total)
