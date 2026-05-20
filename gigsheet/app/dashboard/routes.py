from flask import Blueprint, render_template, g
from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import count_leads_by_workspace, get_campaigns_by_workspace, get_stage_counts

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
@require_workspace
def index():
    conn = get_db()
    total_leads = count_leads_by_workspace(conn, g.workspace['id'])
    active_campaigns = get_campaigns_by_workspace(conn, g.workspace['id'], status='sending')
    recent_campaigns = get_campaigns_by_workspace(conn, g.workspace['id'])[:5]
    stage_counts = get_stage_counts(conn, g.workspace['id'])
    return render_template('dashboard/index.html',
        total_leads=total_leads,
        active_campaigns=active_campaigns,
        recent_campaigns=recent_campaigns,
        stage_counts=stage_counts,
    )
