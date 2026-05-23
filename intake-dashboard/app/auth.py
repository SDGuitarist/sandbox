import functools
from flask import (
    Blueprint, flash, redirect, render_template, request,
    session, url_for, current_app
)
from werkzeug.security import check_password_hash
from app import limiter

auth_bp = Blueprint('auth', __name__)


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if (username == current_app.config['ADMIN_USERNAME']
                and check_password_hash(
                    current_app.config['ADMIN_PASSWORD_HASH'], password)):
            session.clear()
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('dashboard.index'))
        flash('Invalid credentials', 'error')
    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
