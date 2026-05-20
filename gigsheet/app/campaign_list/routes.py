from flask import Blueprint, render_template, request, g

from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import get_campaigns_by_workspace

campaign_list_bp = Blueprint('campaign_list', __name__)

VALID_STATUSES = {'draft', 'scheduled', 'sending', 'sent', 'paused', 'cancelled'}


@campaign_list_bp.route('/')
@login_required
@require_workspace
def index():
    conn = get_db()
    status_filter = request.args.get('status')

    # Validate status filter -- ignore invalid values
    if status_filter and status_filter not in VALID_STATUSES:
        status_filter = None

    campaigns = get_campaigns_by_workspace(
        conn, g.workspace['id'], status=status_filter
    )

    return render_template(
        'campaign_list/index.html',
        campaigns=campaigns,
        current_status=status_filter,
    )
