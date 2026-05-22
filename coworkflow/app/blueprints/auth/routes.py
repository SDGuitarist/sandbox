from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from app.auth import check_password

bp = Blueprint('auth', __name__)


@bp.route('/login')
def login_page():
    return render_template('auth/login.html')


@bp.route('/login', methods=['POST'])
def login():
    password = request.form.get('password', '')
    if not password or not check_password(password):
        flash('Invalid password.', 'error')
        return redirect(url_for('auth.login_page'))
    session['logged_in'] = True
    return redirect(url_for('dashboard.index'))


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('auth.login_page'))
