import os

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.db import get_db

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET'])
def login():
    """Show the login form."""
    return render_template('auth/login.html')


@bp.route('/login', methods=['POST'])
def login_post():
    """Validate the admin password and create a session."""
    password = request.form.get('password', '')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'admin')

    if password == admin_password:
        session['authenticated'] = True
        return redirect(url_for('dashboard.index'))

    flash('Invalid password.', 'error')
    return render_template('auth/login.html')


@bp.route('/logout', methods=['POST'])
def logout():
    """Clear the session and redirect to login."""
    session.clear()
    return redirect(url_for('auth.login'))
