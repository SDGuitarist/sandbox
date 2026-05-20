from flask import Blueprint, abort, flash, g, redirect, render_template, url_for

from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import (
    create_notification,
    enqueue_send_jobs,
    get_campaign,
    get_campaign_progress,
    log_activity,
    update_campaign_status,
)
from app import limiter

campaign_sender_bp = Blueprint('campaign_sender', __name__)


@campaign_sender_bp.route('/<int:id>', methods=['POST'])
@login_required
@require_workspace
@limiter.limit('5/minute')
def send(id):
    """Enqueue send jobs for a draft campaign and redirect to the status page."""
    conn = get_db()

    # Fetch campaign and verify ownership (FC35)
    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    # Only draft campaigns can be sent
    if campaign['status'] != 'draft':
        flash('Campaign has already been sent or is not in draft status.', 'warning')
        return redirect(url_for('campaign_editor.detail', id=id))

    # Enqueue all send jobs (does NOT commit)
    enqueue_send_jobs(conn, id)

    # Commit after all jobs are enqueued
    conn.commit()

    # Update status to 'sending' (commits independently)
    update_campaign_status(conn, id, 'sending')

    # Create notification for the user
    create_notification(
        conn,
        g.workspace['id'],
        g.user['id'],
        f'Campaign "{campaign["name"]}" is now sending.',
        url_for('campaign_sender.status', id=id),
    )

    # Log the activity
    log_activity(
        conn,
        g.workspace['id'],
        g.user['id'],
        'sent_campaign',
        'campaign',
        id,
        f'Campaign: {campaign["name"]}',
    )

    conn.commit()

    flash('Campaign is now sending!', 'success')
    return redirect(url_for('campaign_sender.status', id=id))


@campaign_sender_bp.route('/<int:id>/status')
@login_required
@require_workspace
def status(id):
    """Show the campaign send progress page with SSE-powered live updates."""
    conn = get_db()

    # Fetch campaign and verify ownership (FC35)
    campaign = get_campaign(conn, id)
    if campaign is None:
        abort(404)
    if campaign['workspace_id'] != g.workspace['id']:
        abort(403)

    progress = get_campaign_progress(conn, id)

    return render_template(
        'campaign_sender/status.html',
        campaign=campaign,
        progress=progress,
    )
