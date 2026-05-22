import os
import time

from flask import Blueprint, flash, redirect, render_template, request, session, url_for, current_app

bp = Blueprint('auth', __name__)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')


def _is_locked_out():
    """Check if brute-force lockout is active (5 attempts in 60 seconds)."""
    attempts = current_app.login_attempts
    if attempts['count'] >= 5:
        elapsed = time.monotonic() - attempts['first_attempt']
        if elapsed < 60:
            return True
        # Window expired -- reset
        attempts['count'] = 0
        attempts['first_attempt'] = 0.0
    return False


def _record_attempt():
    """Record a failed login attempt for brute-force tracking."""
    attempts = current_app.login_attempts
    now = time.monotonic()

    if attempts['count'] == 0:
        # First attempt -- start the window
        attempts['first_attempt'] = now

    elapsed = now - attempts['first_attempt']
    if elapsed >= 60:
        # Window expired -- reset and start new window
        attempts['count'] = 1
        attempts['first_attempt'] = now
    else:
        attempts['count'] += 1


@bp.route('/login', methods=['GET'])
def login():
    """Display the login form."""
    if session.get('logged_in'):
        return redirect(url_for('dashboard.index'))
    return render_template('auth/login.html')


@bp.route('/login', methods=['POST'])
def login_post():
    """Process login form submission."""
    if _is_locked_out():
        flash('Too many attempts. Try again later.', 'error')
        return redirect(url_for('auth.login'))

    password = request.form.get('password', '').strip()

    if not password:
        flash('Password is required.', 'error')
        return redirect(url_for('auth.login'))

    if password != ADMIN_PASSWORD:
        _record_attempt()
        flash('Invalid password.', 'error')
        return redirect(url_for('auth.login'))

    # Successful login -- reset attempt counter
    current_app.login_attempts['count'] = 0
    current_app.login_attempts['first_attempt'] = 0.0

    session['logged_in'] = True
    session.permanent = True

    flash('Logged in successfully.', 'success')
    return redirect(url_for('dashboard.index'))


@bp.route('/logout', methods=['POST'])
def logout():
    """Log out the admin user."""
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('auth.login'))
