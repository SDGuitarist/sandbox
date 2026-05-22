import functools
from flask import session, redirect, url_for, flash


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
