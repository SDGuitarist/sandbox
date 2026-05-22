from datetime import date

from flask import Blueprint, render_template

from app.auth import login_required
from app.db import get_db
from app.models import (
    count_active_members,
    count_new_members_this_month,
    get_revenue_this_month,
    get_schedules_by_date,
    get_recent_checkins,
    get_equipment_needing_maintenance,
)

bp = Blueprint('dashboard', __name__)


@bp.route('/')
@login_required
def index():
    conn = get_db()
    today = date.today().isoformat()
    return render_template(
        'dashboard/index.html',
        active_members=count_active_members(conn),
        new_this_month=count_new_members_this_month(conn),
        revenue_this_month=get_revenue_this_month(conn),
        todays_schedule=get_schedules_by_date(conn, today),
        recent_checkins=get_recent_checkins(conn, 10),
        needs_maintenance=get_equipment_needing_maintenance(conn),
    )
