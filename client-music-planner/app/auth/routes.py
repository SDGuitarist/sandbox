from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

from ..db import get_db
from ..models import get_user_by_email, create_user
from . import bp


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template('auth/login.html')

        with get_db() as db:
            user = get_user_by_email(db, email)

        if user is None or not check_password_hash(user['password_hash'], password):
            flash("Invalid email or password.", "error")
            return render_template('auth/login.html')

        session.clear()
        session['user_id'] = user['id']
        flash("Welcome back!", "success")
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        display_name = request.form.get('display_name', '').strip()

        if not email or not password or not confirm_password or not display_name:
            flash("All fields are required.", "error")
            return render_template('auth/register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template('auth/register.html')

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template('auth/register.html')

        with get_db() as db:
            existing = get_user_by_email(db, email)

        if existing is not None:
            flash("An account with that email already exists.", "error")
            return render_template('auth/register.html')

        password_hash = generate_password_hash(password)

        with get_db(immediate=True) as db:
            user_id = create_user(db, email, password_hash, display_name)
            db.commit()

        session.clear()
        session['user_id'] = user_id
        flash("Account created successfully.", "success")
        return redirect(url_for('dashboard.index'))

    return render_template('auth/register.html')


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('auth.login'))
