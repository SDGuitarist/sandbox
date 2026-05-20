import sqlite3

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash

from app.db import get_db
from app.decorators import login_required
from app.models import create_user, get_user_by_id, get_user_by_username, update_user_profile

auth_bp = Blueprint('auth', __name__)

VALID_ROLES = ('venue_manager', 'musician', 'promoter')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', '').strip()
        display_name = request.form.get('display_name', '').strip()

        # Validate all inputs
        if not username:
            flash('Username is required.', 'error')
            return render_template('auth/register.html')
        if not email:
            flash('Email is required.', 'error')
            return render_template('auth/register.html')
        if not password:
            flash('Password is required.', 'error')
            return render_template('auth/register.html')
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('auth/register.html')
        if role not in VALID_ROLES:
            flash('Invalid role selected.', 'error')
            return render_template('auth/register.html')
        if not display_name:
            flash('Display name is required.', 'error')
            return render_template('auth/register.html')

        conn = get_db()
        password_hash = generate_password_hash(password)

        try:
            create_user(conn, username, email, password_hash, role, display_name)
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'error')
            return render_template('auth/register.html')

        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username:
            flash('Username is required.', 'error')
            return render_template('auth/login.html')
        if not password:
            flash('Password is required.', 'error')
            return render_template('auth/login.html')

        conn = get_db()
        user = get_user_by_username(conn, username)

        if user is None or not check_password_hash(user['password_hash'], password):
            flash('Invalid username or password.', 'error')
            return render_template('auth/login.html')

        session.clear()
        session['user_id'] = user['id']
        session['role'] = user['role']

        flash('Logged in successfully.', 'success')
        return redirect(url_for(f'dashboard_{user["role"]}.index'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        bio = request.form.get('bio', '').strip()
        genre_tags = request.form.get('genre_tags', '').strip()

        if not display_name:
            flash('Display name is required.', 'error')
            return render_template('auth/profile.html', user=g.user)

        conn = get_db()
        update_user_profile(conn, g.user['id'], display_name, bio, genre_tags)
        conn.commit()

        # Refresh g.user after update
        g.user = get_user_by_id(conn, g.user['id'])

        flash('Profile updated successfully.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html', user=g.user)
