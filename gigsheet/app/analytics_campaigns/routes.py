from flask import Blueprint, render_template, abort, g
from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import get_campaign, get_campaign_recipients

analytics_campaigns_bp = Blueprint('analytics_campaigns', __name__)


def _pct(part, total):
    """Return percentage as a float rounded to 1 decimal, or 0.0 if total is 0."""
    if not total:
        return 0.0
    return round(part / total * 100, 1)


@analytics_campaigns_bp.route('/<int:id>')
@login_required
@require_workspace
def detail(id):
    conn = get_db()

    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    # FC35: verify campaign belongs to current workspace
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    recipients = get_campaign_recipients(conn, id)

    # Pull template name if the campaign has a linked template
    template = None
    if campaign['template_id']:
        template = conn.execute(
            'SELECT * FROM templates WHERE id = ?',
            (campaign['template_id'],)
        ).fetchone()

    # Build metrics with percentages
    total = campaign['total_recipients']
    metrics = {
        'sent':      {'count': campaign['sent_count'],      'pct': _pct(campaign['sent_count'], total)},
        'delivered': {'count': campaign['delivered_count'],  'pct': _pct(campaign['delivered_count'], total)},
        'opened':    {'count': campaign['opened_count'],     'pct': _pct(campaign['opened_count'], total)},
        'clicked':   {'count': campaign['clicked_count'],    'pct': _pct(campaign['clicked_count'], total)},
        'bounced':   {'count': campaign['bounced_count'],    'pct': _pct(campaign['bounced_count'], total)},
        'failed':    {'count': campaign['failed_count'],     'pct': _pct(campaign['failed_count'], total)},
    }

    return render_template(
        'analytics_campaigns/detail.html',
        campaign=campaign,
        template=template,
        recipients=recipients,
        total_recipients=total,
        metrics=metrics,
    )
