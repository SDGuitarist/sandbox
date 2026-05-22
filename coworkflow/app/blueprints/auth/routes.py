import time

from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from app.auth import check_password

bp = Blueprint('auth', __name__)

_fail_count: int = 0
_first_fail: float = 0.0
_MAX_ATTEMPTS: int = 5
_LOCKOUT_SECONDS: int = 60


@bp.route('/login')
def login_page():
    return render_template('auth/login.html')


@bp.route('/login', methods=['POST'])
def login():
    global _fail_count, _first_fail
    now = time.time()
    # Reset counter if lockout window has passed
    if now - _first_fail > _LOCKOUT_SECONDS:
        _fail_count = 0
    # Check lockout
    if _fail_count >= _MAX_ATTEMPTS:
        flash('Too many attempts. Try again later.', 'error')
        return redirect(url_for('auth.login_page'))
    password = request.form.get('password', '')
    if not password or not check_password(password):
        if _fail_count == 0:
            _first_fail = now
        _fail_count += 1
        flash('Invalid password.', 'error')
        return redirect(url_for('auth.login_page'))
    # Success -- clear counter, prevent session fixation, set session
    _fail_count = 0
    session.clear()
    session['logged_in'] = True
    session.permanent = True
    return redirect(url_for('dashboard.index'))


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('auth.login_page'))
