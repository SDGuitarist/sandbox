"""Session helpers, identity mapping, and authorization decorators.

Owned by the auth-core agent. This is foundational infrastructure imported by
EVERY route agent; it deliberately imports NO entity models -- the
student/instructor identity lookups use direct get_db() queries (spec pins this,
keeps auth.py free of model coupling / import cycles).
"""
from functools import wraps

from flask import abort, g, redirect, session, url_for

from studio.database import get_db
from studio.models.auth_models import get_user


def login_user(user):
    """Establish a session for the given user dict.

    Clears any existing session BEFORE setting keys (session-fixation
    defense -- run-080 lesson).
    """
    session.clear()
    session['user_id'] = user['id']


def logout_user():
    """Clear the session."""
    session.clear()


def current_user():
    """Return the logged-in user row as a dict, or None. Cached on g per request."""
    if 'current_user' not in g:
        user_id = session.get('user_id')
        g.current_user = get_user(user_id) if user_id is not None else None
    return g.current_user


def current_student_id():
    """Return students.id for a logged-in student user (via students.user_id).

    None for staff/admin or anonymous. Direct get_db() query -- no entity-model
    import (keeps foundational auth.py free of model coupling).
    """
    user = current_user()
    if user is None or user['role'] != 'student':
        return None
    row = get_db().execute(
        "SELECT id FROM students WHERE user_id = ?", (user['id'],)
    ).fetchone()
    return row['id'] if row is not None else None


def current_instructor_id():
    """Return instructors.id for a logged-in instructor user (via instructors.user_id).

    None for admin/student or anonymous. Direct get_db() query.
    """
    user = current_user()
    if user is None or user['role'] != 'instructor':
        return None
    row = get_db().execute(
        "SELECT id FROM instructors WHERE user_id = ?", (user['id'],)
    ).fetchone()
    return row['id'] if row is not None else None


def login_required(view):
    """Redirect to /auth/login (302) when the caller is anonymous."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """Decorator factory: 403 when current_user().role not in roles.

    Also 302 -> /auth/login when anonymous (login is a precondition of role).
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for('auth.login'))
            if user['role'] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def require_self_or_staff(student_id):
    """Pre-write guard for role+own POST routes.

    Staff (admin/instructor) pass. A student actor passes only when the supplied
    student_id is their OWN students.id; otherwise abort(404) (hide existence,
    never leak via 403 -- run-080 IDOR lesson).
    """
    user = current_user()
    if user is None:
        abort(404)
    if user['role'] in ('admin', 'instructor'):
        return
    if current_student_id() != student_id:
        abort(404)
