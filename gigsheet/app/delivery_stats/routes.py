from flask import Blueprint, render_template, abort, g
from app.db import get_db
from app.models import get_campaign, get_campaign_recipients
from app.decorators import login_required, require_workspace

delivery_stats_bp = Blueprint('delivery_stats', __name__)


@delivery_stats_bp.route('/<int:id>')
@login_required
@require_workspace
def detail(id):
    conn = get_db()

    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    # FC35: ownership check -- campaign must belong to current workspace
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    recipients = get_campaign_recipients(conn, id)

    return render_template(
        'delivery_stats/detail.html',
        campaign=campaign,
        recipients=recipients,
    )
