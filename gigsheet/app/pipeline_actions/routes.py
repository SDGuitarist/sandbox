from flask import Blueprint, request, jsonify, g, abort, flash, redirect, url_for

from app.db import get_db
from app.models import get_lead, update_lead_stage, add_pipeline_note, log_activity
from app.decorators import login_required, require_workspace
from app import PIPELINE_STAGES

pipeline_actions_bp = Blueprint('pipeline_actions', __name__)


@pipeline_actions_bp.route('/move', methods=['POST'])
@login_required
@require_workspace
def move():
    """Move a single lead to a new pipeline stage. Expects JSON: {lead_id, stage}."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    lead_id = data.get('lead_id')
    stage = data.get('stage', '').strip()

    if not lead_id:
        return jsonify({'error': 'lead_id is required'}), 400
    if stage not in PIPELINE_STAGES:
        return jsonify({'error': f'Invalid stage. Must be one of: {PIPELINE_STAGES}'}), 400

    conn = get_db()
    lead = get_lead(conn, lead_id)
    if lead is None:
        abort(404)
    if lead['workspace_id'] != g.workspace['id']:
        abort(403)

    update_lead_stage(conn, lead_id, stage)
    log_activity(conn, g.workspace['id'], g.user['id'],
                 'moved_lead_stage', 'lead', lead_id,
                 f"Moved to {stage}")
    conn.commit()

    return jsonify({'status': 'ok'})


@pipeline_actions_bp.route('/bulk', methods=['POST'])
@login_required
@require_workspace
def bulk_move():
    """Move multiple leads to a new pipeline stage. Expects JSON: {lead_ids, stage}."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    lead_ids = data.get('lead_ids', [])
    stage = data.get('stage', '').strip()

    if not lead_ids or not isinstance(lead_ids, list):
        return jsonify({'error': 'lead_ids must be a non-empty list'}), 400
    if stage not in PIPELINE_STAGES:
        return jsonify({'error': f'Invalid stage. Must be one of: {PIPELINE_STAGES}'}), 400

    conn = get_db()

    # Batch validate all lead IDs belong to this workspace (avoids N+1)
    placeholders = ','.join('?' for _ in lead_ids)
    valid_leads = conn.execute(
        f'SELECT id FROM leads WHERE id IN ({placeholders}) AND workspace_id = ?',
        (*lead_ids, g.workspace['id'])
    ).fetchall()
    valid_ids = {row['id'] for row in valid_leads}

    if len(valid_ids) != len(lead_ids):
        invalid = [lid for lid in lead_ids if lid not in valid_ids]
        return jsonify({'error': f'Invalid or unauthorized lead IDs: {invalid}'}), 400

    for lid in lead_ids:
        update_lead_stage(conn, lid, stage)
        log_activity(conn, g.workspace['id'], g.user['id'],
                     'moved_lead_stage', 'lead', lid,
                     f"Moved to {stage}")

    conn.commit()

    return jsonify({'status': 'ok', 'moved': len(lead_ids)})


@pipeline_actions_bp.route('/note', methods=['POST'])
@login_required
@require_workspace
def add_note():
    """Add a note to a lead. Expects form data: lead_id, content."""
    lead_id = request.form.get('lead_id', type=int)
    content = request.form.get('content', '').strip()

    if not lead_id:
        flash('Lead ID is required.', 'error')
        return redirect(request.referrer or url_for('pipeline_board.index'))
    if not content:
        flash('Note content is required.', 'error')
        return redirect(request.referrer or url_for('pipeline_board.index'))

    conn = get_db()
    lead = get_lead(conn, lead_id)
    if lead is None:
        abort(404)
    if lead['workspace_id'] != g.workspace['id']:
        abort(403)

    add_pipeline_note(conn, lead_id, g.user['id'], content)
    log_activity(conn, g.workspace['id'], g.user['id'],
                 'added_note', 'lead', lead_id,
                 f"Note on {lead['venue_name']}")
    conn.commit()

    flash('Note added.', 'success')
    return redirect(request.referrer or url_for('pipeline_board.index'))
