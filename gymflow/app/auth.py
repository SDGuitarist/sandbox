import os
import hmac
import functools
from flask import session, redirect, url_for, flash, request

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'dev-password-123')


def login_required(f):
    """Decorator: redirect to login if not authenticated."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in.', 'error')
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated


def check_password(password):
    """Check if password matches admin password. Returns bool.
    Uses hmac.compare_digest for timing-safe comparison."""
    return hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode())
