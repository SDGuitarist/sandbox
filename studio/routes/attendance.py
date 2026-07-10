"""Attendance blueprint — per-lesson attendance view + single-student mark route.

The student is ALWAYS derived from ``lessons.student_id`` (a lesson is 1:1 with a
student); it is never supplied by the client. See spec §3 and the attendance Route
Table.
"""
from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from studio.auth import current_user, role_required
from studio.models import attendance_models, lesson_models
from studio.models.audit_models import record

bp = Blueprint('attendance', __name__, url_prefix='/attendance')


# Accepted string forms for the boolean ``present`` field (simplest per spec §4).
_TRUE_VALUES = {'1', 'true'}
_FALSE_VALUES = {'0', 'false'}


@bp.route('/lesson/<int:lid>')
@role_required('admin', 'instructor')
def lesson_attendance(lid):
    """Show a lesson's ONE student and its current attendance mark."""
    lesson = lesson_models.get_lesson(lid) or abort(404)
    # Single-student per lesson: at most one attendance row for this lesson.
    rows = attendance_models.list_attendance(lesson_id=lid)
    attendance = rows[0] if rows else None
    return render_template(
        'attendance/lesson.html',
        lesson=lesson,
        attendance=attendance,
    )


@bp.route('/lesson/<int:lid>/mark', methods=['POST'])
@role_required('admin', 'instructor')
def mark_attendance(lid):
    """Mark the lesson's single student present/absent (student derived from lesson)."""
    raw = (request.form.get('present') or '').strip().lower()
    if raw in _TRUE_VALUES:
        present = 1
    elif raw in _FALSE_VALUES:
        present = 0
    else:
        abort(400)

    try:
        attendance_models.mark_attendance(
            lid, present, marked_by=current_user()['id']
        )
    except ValueError:
        # Missing lesson.
        abort(404)

    record(current_user()['id'], 'update', 'attendance', lid,
           detail='present' if present else 'absent')
    flash('Attendance updated.', 'success')
    return redirect(url_for('attendance.lesson_attendance', lid=lid))
