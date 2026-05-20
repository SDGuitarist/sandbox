from flask import Blueprint, render_template, g

from app.db import get_db
from app.models import count_leads_by_workspace, get_campaigns_by_workspace, get_stage_counts
from app.decorators import login_required, require_workspace
from app import PIPELINE_STAGES

bp = analytics_overview_bp = Blueprint('analytics_overview', __name__)


@bp.route('/')
@login_required
@require_workspace
def index():
    """Analytics overview: totals, conversion funnel, recent campaigns."""
    conn = get_db()
    workspace_id = g.workspace['id']

    # Total leads
    total_leads = count_leads_by_workspace(conn, workspace_id)

    # All campaigns for this workspace
    campaigns = get_campaigns_by_workspace(conn, workspace_id)
    total_campaigns = len(campaigns)

    # Sum counters across all campaigns
    total_sent = sum(c['sent_count'] for c in campaigns)
    total_opened = sum(c['opened_count'] for c in campaigns)
    total_bounced = sum(c['bounced_count'] for c in campaigns)

    # Conversion funnel: lead counts by pipeline stage
    stage_counts = get_stage_counts(conn, workspace_id)
    conversion_funnel = [
        {'stage': stage, 'count': stage_counts.get(stage, 0)}
        for stage in PIPELINE_STAGES
    ]

    # Recent campaigns (most recent 5)
    recent_campaigns = campaigns[:5]

    return render_template(
        'analytics_overview/index.html',
        total_leads=total_leads,
        total_campaigns=total_campaigns,
        total_sent=total_sent,
        total_opened=total_opened,
        total_bounced=total_bounced,
        conversion_funnel=conversion_funnel,
        recent_campaigns=recent_campaigns,
    )
