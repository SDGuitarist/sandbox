from flask import render_template
from ..db import get_db
from ..decorators import setup_required
from ..models import (
    get_revenue_snapshot,
    get_active_projects_summary,
    get_pipeline_summary,
    get_overdue_tasks,
    get_upcoming_deadlines,
    get_hours_this_week,
    get_cash_flow,
    get_recent_activity,
)
from . import bp


@bp.route('/')
@setup_required
def index():
    """Main dashboard — read-only aggregate view of all business metrics."""
    with get_db() as db:
        revenue = get_revenue_snapshot(db)
        projects = get_active_projects_summary(db)
        pipeline = get_pipeline_summary(db)
        overdue_tasks = get_overdue_tasks(db, limit=5)
        upcoming = get_upcoming_deadlines(db, days=7)
        hours = get_hours_this_week(db)
        cash_flow = get_cash_flow(db)
        activity = get_recent_activity(db, limit=10)

        # Get business profile for currency symbol
        profile = db.execute(
            "SELECT * FROM business_profile LIMIT 1"
        ).fetchone()

    return render_template(
        'dashboard/index.html',
        revenue=revenue,
        projects=projects,
        pipeline=pipeline,
        overdue_tasks=overdue_tasks,
        upcoming=upcoming,
        hours=hours,
        cash_flow=cash_flow,
        activity=activity,
        profile=profile,
    )
