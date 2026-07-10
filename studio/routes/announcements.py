"""Announcements blueprint — role-scoped list, create, delete.

Route agent for the /announcements cluster. Content is role-scoped via
announcement_models.list_for_role; create/delete are staff-only. Every
mutation records one post-commit audit_log row (audit is never nested in a
model transaction — announcements are class-A commit-internally writers).
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from studio.auth import current_user, login_required, role_required
from studio.models import announcement_models
from studio.models.audit_models import record

bp = Blueprint('announcements', __name__, url_prefix='/announcements')

_AUDIENCES = ('all', 'students', 'instructors')


@bp.route('/')
@login_required
def list_announcements():
    """Role-scoped announcement list (any logged-in user)."""
    actor = current_user()
    announcements = announcement_models.list_for_role(actor['role'])
    return render_template('announcements/list.html', announcements=announcements)


@bp.route('/new', methods=('GET', 'POST'))
@role_required('admin', 'instructor')
def create_announcement():
    """Create an announcement (admin/instructor only)."""
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        body = (request.form.get('body') or '').strip()
        audience = (request.form.get('audience') or 'all').strip()

        if not title or not body or audience not in _AUDIENCES:
            flash('Title and body are required, and audience must be valid.', 'error')
            return render_template(
                'announcements/new.html',
                title=title,
                body=body,
                audience=audience,
                audiences=_AUDIENCES,
            ), 400

        actor = current_user()
        aid = announcement_models.create_announcement(
            actor['id'], title, body, audience
        )
        record(actor['id'], 'create', 'announcement', aid)
        flash('Announcement posted.', 'success')
        return redirect(url_for('announcements.list_announcements'))

    return render_template(
        'announcements/new.html',
        title='',
        body='',
        audience='all',
        audiences=_AUDIENCES,
    )


@bp.route('/<int:aid>/delete', methods=('POST',))
@role_required('admin', 'instructor')
def delete_announcement(aid):
    """Delete an announcement (admin/instructor only)."""
    if announcement_models.get_announcement(aid) is None:
        abort(404)

    actor = current_user()
    announcement_models.delete_announcement(aid)
    record(actor['id'], 'delete', 'announcement', aid)
    flash('Announcement deleted.', 'success')
    return redirect(url_for('announcements.list_announcements'))
