from functools import wraps
from flask import session, redirect, url_for, flash
from .db import get_db


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def setup_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if not session.get('setup_complete'):
            with get_db() as db:
                user = db.execute("SELECT setup_complete FROM user WHERE id = ?",
                                  (session['user_id'],)).fetchone()
                if not user or not user['setup_complete']:
                    return redirect(url_for('auth.setup'))
                session['setup_complete'] = True
        return f(*args, **kwargs)
    return decorated
