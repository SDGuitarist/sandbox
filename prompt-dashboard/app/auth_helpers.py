from functools import wraps
from flask import session, redirect, url_for, abort, g
from app.database import get_db


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ?',
                            (session['user_id'],)).fetchone()
        if user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        g.user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        # Short-circuit: check role from session before DB query.
        # Avoids an unnecessary SELECT for the common case of a non-admin
        # probing admin routes.
        if session.get('role') != 'admin':
            abort(403)
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ?',
                            (session['user_id'],)).fetchone()
        if user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        g.user = user
        return f(*args, **kwargs)
    return decorated
