"""Practice-log blueprint (/practice).

Ownership-scoped list, student-only create, guarded delete. All ownership
enforcement lives in practice_log_models (SQL WHERE predicates); routes never
fetch-then-compare. CSRF is validated globally by the scaffold before_request.
"""
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
)

from studio.auth import login_required, current_user, current_student_id
from studio.models import practice_log_models
from studio.models.audit_models import record

bp = Blueprint('practice', __name__, url_prefix='/practice')


@bp.route('/')
@login_required
def list_practice_logs():
    """List practice logs scoped to the actor.

    Students always see only their own (target_student_id is ignored by the
    model for students); staff may widen via ?target_student_id.
    """
    actor = current_user()
    target_student_id = request.args.get('target_student_id')
    logs = practice_log_models.list_practice_logs_for(actor, target_student_id)
    # current_student_id() is None for staff/admin; drives the create-form gate.
    can_log = current_student_id() is not None
    return render_template('practice/list.html', logs=logs, can_log=can_log)


@bp.route('/new', methods=['POST'])
@login_required
def create_practice_log():
    """Student self-service ONLY. Staff/admin have no student identity -> 403.

    student_id is ALWAYS the actor's own; any client-supplied student_id is
    ignored.
    """
    sid = current_student_id()
    if sid is None:
        # Staff/admin cannot log practice on a student's behalf.
        abort(403)

    minutes_raw = request.form.get('minutes', '').strip()
    notes = request.form.get('notes') or None
    try:
        minutes = int(minutes_raw)
    except (TypeError, ValueError):
        minutes = 0
    if minutes <= 0:
        flash('Minutes must be a whole number greater than 0.', 'error')
        return redirect(url_for('practice.list_practice_logs'))

    log_id = practice_log_models.create_practice_log(sid, minutes, notes)
    record(
        current_user()['id'],
        'create',
        'practice_log',
        log_id,
        f'{minutes} minutes',
    )
    flash('Practice log added.', 'success')
    return redirect(url_for('practice.list_practice_logs'))


@bp.route('/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_practice_log(log_id):
    """Guarded delete: ownership-scoped getter must return the row first.

    A non-owner (or missing row) yields None -> 404, never a delete.
    """
    actor = current_user()
    practice_log_models.get_practice_log_for(log_id, actor) or abort(404)

    practice_log_models.delete_practice_log(log_id)
    record(actor['id'], 'delete', 'practice_log', log_id)
    flash('Practice log deleted.', 'success')
    return redirect(url_for('practice.list_practice_logs'))
