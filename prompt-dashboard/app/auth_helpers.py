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
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ?',
                            (session['user_id'],)).fetchone()
        if user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        if user['role'] != 'admin':
            abort(403)
        g.user = user
        return f(*args, **kwargs)
    return decorated
