from functools import wraps
from flask import session, g, redirect, url_for, abort, flash


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'error')
            return redirect(url_for('auth.login'))
        from app.db import get_db
        from app.models import get_user_by_id
        conn = get_db()
        user = get_user_by_id(conn, session['user_id'])
        if user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        g.user = user
        return f(*args, **kwargs)
    return decorated


def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.user['role'] != role:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
