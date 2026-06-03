"""Auth blueprint: login, register, logout."""
import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.database import get_db
from app.models.auth_models import (
    create_user,
    get_user_by_id,
    get_user_by_username,
    verify_password,
)

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET'])
def login():
    return render_template('auth/login.html')


@bp.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username', '').strip()[:50]
    password = request.form.get('password', '')

    if not username:
        flash('Username is required', 'error')
        return redirect(url_for('auth.login'))

    if not password:
        flash('Password is required', 'error')
        return redirect(url_for('auth.login'))

    conn = get_db()
    user = get_user_by_username(conn, username)

    if user is None or not verify_password(password, user['password_hash']):
        flash('Invalid credentials', 'error')
        return redirect(url_for('auth.login'))

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']

    return redirect(url_for('library.index'))


@bp.route('/register', methods=['GET'])
def register():
    return render_template('auth/register.html')


@bp.route('/register', methods=['POST'])
def register_post():
    import re

    username = request.form.get('username', '').strip()[:50]
    email = request.form.get('email', '').strip()[:200]
    password = request.form.get('password', '')

    if not username or len(username) < 3 or not re.match(r'^[a-zA-Z0-9_]+$', username):
        flash('Username must be 3-50 alphanumeric characters or underscores', 'error')
        return redirect(url_for('auth.register'))

    if not email or '@' not in email:
        flash('Valid email is required', 'error')
        return redirect(url_for('auth.register'))

    if not password or len(password) < 8 or len(password) > 128:
        flash('Password must be 8-128 characters', 'error')
        return redirect(url_for('auth.register'))

    conn = get_db()
    try:
        user_id = create_user(conn, username, email, password)
    except sqlite3.IntegrityError:
        flash('Username or email already taken', 'error')
        return redirect(url_for('auth.register'))

    session['user_id'] = user_id
    session['username'] = username
    session['role'] = 'user'

    flash('Account created successfully', 'success')
    return redirect(url_for('library.index'))


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('auth.login'))
