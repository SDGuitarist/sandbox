from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from app.auth import login_required, check_password

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET'])
def login_page():
    """Display the login form."""
    return render_template('auth/login.html')


@bp.route('/login', methods=['POST'])
def login():
    """Validate password and log in."""
    password = request.form.get('password', '')

    # FC4: Validate password is non-empty before checking
    if not password:
        flash('Invalid password', 'error')
        return redirect(url_for('auth.login_page'))

    if not check_password(password):
        flash('Invalid password', 'error')
        return redirect(url_for('auth.login_page'))

    session['logged_in'] = True
    return redirect(url_for('dashboard.index'))


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Clear session and redirect to login."""
    session.clear()
    return redirect(url_for('auth.login_page'))
