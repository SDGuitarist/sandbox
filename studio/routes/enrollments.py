"""Enrollments blueprint — list, enroll, withdraw.

Fronts the enroll→invoice atomic transaction. Route-level checks are
PRESENCE/advisory only; the authoritative guards (already-enrolled UNIQUE,
capacity, active re-check) run INSIDE enrollment_models.enroll's BEGIN IMMEDIATE.
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

from studio.auth import login_required, role_required, current_user

# Import model MODULES (not names) — qualified calls avoid shadowing the view
# function `enroll` with the model function `enroll`.
from studio.models import enrollment_models, course_models, student_models
from studio.models import audit_models

bp = Blueprint('enrollments', __name__, url_prefix='/enrollments')


@bp.route('/')
@login_required
@role_required('admin', 'instructor')
def list_enrollments():
    """List all enrollments plus the enroll form's student/course dropdowns."""
    status = request.args.get('status') or None
    enrollments = enrollment_models.list_enrollments(status=status)
    students = student_models.list_students(active_only=True)
    courses = course_models.list_courses(active_only=True)
    return render_template(
        'enrollments/list.html',
        enrollments=enrollments,
        students=students,
        courses=courses,
        status=status,
    )


@bp.route('/enroll', methods=['POST'])
@login_required
@role_required('admin', 'instructor')
def enroll():
    """Enroll a student in a course.

    Route-level validation is PRESENCE/advisory only. The authoritative
    already-enrolled / capacity / active guards live inside
    enrollment_models.enroll's BEGIN IMMEDIATE — not duplicated here.
    """

    def _error(message):
        """Flash an advisory error and re-render the enroll form with 400."""
        flash(message, 'error')
        return (
            render_template(
                'enrollments/enroll.html',
                students=student_models.list_students(active_only=True),
                courses=course_models.list_courses(active_only=True),
            ),
            400,
        )

    # Parse ids (presence + int).
    try:
        student_id = int(request.form.get('student_id', ''))
        course_id = int(request.form.get('course_id', ''))
    except (TypeError, ValueError):
        return _error('Student and course are required.')

    # Presence checks (advisory only — friendly 400 flash).
    if student_models.get_student(student_id) is None:
        return _error('Student not found.')

    course = course_models.get_course(course_id)
    if course is None:
        return _error('Course not found.')
    if not course['active']:
        return _error('Course is not active.')

    # Authoritative guards run INSIDE enroll's transaction; surface ValueError
    # ("already enrolled" / "course full" / "course inactive").
    try:
        eid = enrollment_models.enroll(
            student_id,
            course_id,
            created_by=current_user()['id'],
        )
    except ValueError as exc:
        return _error(str(exc))

    # Audit exactly once, post-commit.
    audit_models.record(
        current_user()['id'],
        'create',
        'enrollment',
        entity_id=eid,
        detail='course_id={} student_id={}'.format(course_id, student_id),
    )
    flash('Student enrolled.', 'success')
    return redirect(url_for('enrollments.list_enrollments'))


@bp.route('/<int:eid>/withdraw', methods=['POST'])
@login_required
@role_required('admin', 'instructor')
def withdraw(eid):
    """Withdraw an enrollment (soft status change)."""
    enrollment = enrollment_models.get_enrollment(eid)
    if enrollment is None:
        abort(404)

    enrollment_models.set_enrollment_status(eid, 'withdrawn')

    # Audit exactly once, post-commit.
    audit_models.record(
        current_user()['id'],
        'update',
        'enrollment',
        entity_id=eid,
        detail='withdrawn',
    )
    flash('Enrollment withdrawn.', 'success')
    return redirect(url_for('enrollments.list_enrollments'))
