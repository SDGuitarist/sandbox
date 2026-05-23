from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from app.db import get_db
from app.auth import login_required
from app.models.submissions import get_submission, VALID_STATUSES, TERMINAL_STATUSES
from app.models.assessments import get_assessment_by_submission
from app.models.notes import create_note, list_notes

detail_bp = Blueprint('detail', __name__)


@detail_bp.route('/<int:submission_id>')
@login_required
def view_submission(submission_id):
    conn = get_db()
    submission = get_submission(conn, submission_id)
    if submission is None:
        abort(404)
    assessment = get_assessment_by_submission(conn, submission_id)
    notes = list_notes(conn, submission_id)
    return render_template('detail/show.html',
        submission=submission,
        assessment=assessment,
        notes=notes,
        statuses=VALID_STATUSES,
        terminal_statuses=TERMINAL_STATUSES
    )


@detail_bp.route('/<int:submission_id>/notes', methods=['POST'])
@login_required
def add_note(submission_id):
    conn = get_db()
    submission = get_submission(conn, submission_id)
    if submission is None:
        abort(404)
    content = request.form.get('content', '').strip()[:2000]
    if not content:
        flash('Note content is required', 'error')
    else:
        create_note(conn, submission_id, content)
        flash('Note added', 'success')
    return redirect(url_for('detail.view_submission', submission_id=submission_id))
