import csv
import io

from flask import Blueprint, render_template, g, Response

from app.db import get_db
from app.models import get_campaigns_by_workspace
from app.decorators import login_required, require_workspace

delivery_dashboard_bp = Blueprint('delivery_dashboard', __name__)

FORMULA_CHARS = set('=-+@|')


def sanitize_csv_cell(value: str) -> str:
    """Prevent formula injection in CSV values."""
    if value and value[0] in FORMULA_CHARS:
        return "'" + value
    return value


@delivery_dashboard_bp.route('/')
@login_required
@require_workspace
def index():
    conn = get_db()
    campaigns = get_campaigns_by_workspace(conn, g.workspace['id'])

    # Aggregate delivery metrics across all campaigns
    total_sent = 0
    total_delivered = 0
    total_opened = 0
    total_clicked = 0
    total_bounced = 0

    for c in campaigns:
        total_sent += c['sent_count'] or 0
        total_delivered += c['delivered_count'] or 0
        total_opened += c['opened_count'] or 0
        total_clicked += c['clicked_count'] or 0
        total_bounced += c['bounced_count'] or 0

    # Recent campaigns (last 10) for the table
    recent_campaigns = campaigns[:10]

    return render_template('delivery_dashboard/index.html',
        total_sent=total_sent,
        total_delivered=total_delivered,
        total_opened=total_opened,
        total_clicked=total_clicked,
        total_bounced=total_bounced,
        recent_campaigns=recent_campaigns,
        total_campaigns=len(campaigns),
    )


@delivery_dashboard_bp.route('/export')
@login_required
@require_workspace
def export_csv():
    conn = get_db()
    campaigns = get_campaigns_by_workspace(conn, g.workspace['id'])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Campaign Name', 'Sent', 'Delivered', 'Opened', 'Clicked', 'Bounced'])

    for c in campaigns:
        name = sanitize_csv_cell(str(c['name']))
        writer.writerow([
            name,
            c['sent_count'] or 0,
            c['delivered_count'] or 0,
            c['opened_count'] or 0,
            c['clicked_count'] or 0,
            c['bounced_count'] or 0,
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename=delivery_report.csv',
        },
    )
