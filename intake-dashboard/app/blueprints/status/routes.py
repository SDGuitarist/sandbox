from flask import Blueprint, abort, flash, redirect, request, url_for
from app.db import get_db
from app.auth import login_required
from app.models.submissions import get_submission, update_status, toggle_audit_fit, VALID_STATUSES, TERMINAL_STATUSES

status_bp = Blueprint('status', __name__)


@status_bp.route('/<int:submission_id>/status', methods=['POST'])
@login_required
def change_status(submission_id):
    conn = get_db()
    submission = get_submission(conn, submission_id)
    if submission is None:
        abort(404)
    new_status = request.form.get('new_status', '').strip()
    if new_status not in VALID_STATUSES:
        flash('Invalid status', 'error')
        return redirect(url_for('detail.view_submission', submission_id=submission_id))
    success = update_status(conn, submission_id, new_status)
    if not success:
        flash('Cannot change status of completed/declined/archived submission', 'error')
    else:
        flash(f'Status updated to {new_status}', 'success')
    return redirect(url_for('detail.view_submission', submission_id=submission_id))


@status_bp.route('/<int:submission_id>/audit-fit', methods=['POST'])
@login_required
def toggle_fit(submission_id):
    conn = get_db()
    submission = get_submission(conn, submission_id)
    if submission is None:
        abort(404)
    toggle_audit_fit(conn, submission_id)
    flash('Audit fit updated', 'success')
    return redirect(url_for('detail.view_submission', submission_id=submission_id))
