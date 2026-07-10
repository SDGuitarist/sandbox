"""Dashboard blueprint — owns the site root (`/`) and the admin audit log (`/audit`).

The SOLE prefix-less blueprint (see spec Route Table / Coordinated Behaviors):
registered as ``Blueprint('dashboard', __name__)`` with NO ``url_prefix`` so that
``index`` serves ``/`` and ``audit_log_view`` serves ``/audit``.

READ-only blueprint: no mutations, no audit-record writes, no CSRF forms.
"""

from flask import Blueprint, render_template, request

from studio.auth import (
    login_required,
    role_required,
    current_user,
    current_instructor_id,
    current_student_id,
)
from studio.models.dashboard_models import (
    admin_summary,
    instructor_summary,
    student_summary,
)
from studio.models.audit_models import list_audit

bp = Blueprint('dashboard', __name__)


@bp.route('/')
@login_required
def index():
    """Role-dispatched summary index.

    admin      -> admin_summary()
    instructor -> instructor_summary(current_instructor_id())
    student    -> student_summary(current_student_id())

    A logged-in user whose role has no matching identity row (e.g. a staff user
    with no instructor row, or a mislabelled account) has no summary to build, so
    we render with an empty summary rather than crash — see SPEC_ISSUES.
    """
    user = current_user()
    role = user['role']

    if role == 'admin':
        summary = admin_summary()
    elif role == 'instructor':
        instructor_id = current_instructor_id()
        summary = instructor_summary(instructor_id) if instructor_id is not None else {}
    elif role == 'student':
        student_id = current_student_id()
        summary = student_summary(student_id) if student_id is not None else {}
    else:
        summary = {}

    return render_template('dashboard/index.html', role=role, summary=summary)


@bp.route('/audit')
@role_required('admin')
def audit_log_view():
    """Admin-only audit log view, optionally filtered by entity_type."""
    entity_type = request.args.get('entity_type')
    entries = list_audit(entity_type=entity_type, limit=200)
    return render_template(
        'dashboard/audit.html',
        entries=entries,
        entity_type=entity_type,
    )
