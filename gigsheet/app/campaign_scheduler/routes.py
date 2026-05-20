from flask import Blueprint, request, g, flash, redirect, url_for, render_template, abort

from app.db import get_db
from app.models import get_campaign, update_campaign_status, update_campaign_schedule, log_activity
from app.decorators import login_required, require_workspace

campaign_scheduler_bp = Blueprint('campaign_scheduler', __name__)


@campaign_scheduler_bp.route('/<int:id>', methods=['POST'])
@login_required
@require_workspace
def set_schedule(id):
    """Set a schedule on a draft campaign."""
    conn = get_db()

    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    scheduled_at = request.form.get('scheduled_at', '').strip()
    timezone = request.form.get('timezone', 'UTC').strip()

    if not scheduled_at:
        flash('Scheduled date/time is required.', 'error')
        return redirect(url_for('campaign_scheduler.view', id=id))

    if not timezone:
        timezone = 'UTC'

    # Update the campaign's scheduled_at and timezone fields
    update_campaign_schedule(conn, id, scheduled_at, timezone)
    conn.commit()

    # Transition status to 'scheduled'
    update_campaign_status(conn, id, 'scheduled')

    log_activity(conn, g.workspace['id'], g.user['id'],
                 'scheduled_campaign', 'campaign', id,
                 f'Campaign: {campaign["name"]}')
    conn.commit()

    flash('Campaign scheduled successfully.', 'success')
    return redirect(url_for('campaign_scheduler.view', id=id))


@campaign_scheduler_bp.route('/<int:id>', methods=['GET'])
@login_required
@require_workspace
def view(id):
    """View the schedule for a campaign."""
    conn = get_db()

    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    return render_template('campaign_scheduler/view.html', campaign=campaign)


@campaign_scheduler_bp.route('/<int:id>/cancel', methods=['POST'])
@login_required
@require_workspace
def cancel(id):
    """Cancel a scheduled campaign."""
    conn = get_db()

    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    update_campaign_status(conn, id, 'cancelled')

    log_activity(conn, g.workspace['id'], g.user['id'],
                 'cancelled_campaign', 'campaign', id,
                 f'Campaign: {campaign["name"]}')
    conn.commit()

    flash('Campaign cancelled.', 'success')
    return redirect(url_for('campaign_scheduler.view', id=id))
