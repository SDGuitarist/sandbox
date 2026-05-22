import re

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app import limiter
from app.db import get_db
from app.models import (
    add_workspace_member,
    create_user,
    create_workspace as model_create_workspace,
    get_user_by_email,
    get_user_workspaces,
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login')
def login():
    return render_template('auth/login.html')


@auth_bp.route('/login', methods=['POST'])
@limiter.limit('5/minute')
def login_post():
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    if not email or not password:
        flash('Email and password are required.', 'error')
        return redirect(url_for('auth.login'))

    conn = get_db()
    user = get_user_by_email(conn, email)
    if user is None or not check_password_hash(user['password_hash'], password):
        flash('Invalid credentials.', 'error')
        return redirect(url_for('auth.login'))

    session.clear()
    session['user_id'] = user['id']
    flash('Logged in successfully.', 'success')
    return redirect(url_for('auth.select_workspace'))


@auth_bp.route('/register')
def register():
    return render_template('auth/register.html')


@auth_bp.route('/register', methods=['POST'])
@limiter.limit('3/minute')
def register_post():
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    display_name = request.form.get('display_name', '').strip()[:100]

    if not email or not password or not confirm_password or not display_name:
        flash('All fields are required.', 'error')
        return redirect(url_for('auth.register'))

    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('auth.register'))

    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return redirect(url_for('auth.register'))

    conn = get_db()
    existing = get_user_by_email(conn, email)
    if existing is not None:
        flash('An account with that email already exists.', 'error')
        return redirect(url_for('auth.register'))

    password_hash = generate_password_hash(password, method='scrypt')
    user_id = create_user(conn, email, password_hash, display_name)
    conn.commit()

    session.clear()
    session['user_id'] = user_id
    flash('Account created successfully.', 'success')
    return redirect(url_for('auth.select_workspace'))


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/workspaces')
def select_workspace():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db()
    workspaces = get_user_workspaces(conn, session['user_id'])
    return render_template('auth/workspaces.html', workspaces=workspaces)


@auth_bp.route('/workspaces', methods=['POST'])
def create_workspace():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    name = request.form.get('name', '').strip()[:100]
    if not name:
        flash('Workspace name is required.', 'error')
        return redirect(url_for('auth.select_workspace'))

    # Generate slug from name: lowercase, replace non-alphanumeric with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    if not slug:
        slug = 'workspace'

    conn = get_db()
    conn.execute('BEGIN IMMEDIATE')
    try:
        workspace_id = model_create_workspace(conn, name, slug, session['user_id'])
        add_workspace_member(conn, workspace_id, session['user_id'], 'owner')
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Could not create workspace. The name may already be taken.', 'error')
        return redirect(url_for('auth.select_workspace'))

    session['workspace_id'] = workspace_id
    flash('Workspace created.', 'success')
    return redirect(url_for('dashboard.index'))


@auth_bp.route('/workspaces/select', methods=['POST'])
def set_workspace():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    workspace_id = request.form.get('workspace_id', type=int)
    if workspace_id is None:
        flash('Please select a workspace.', 'error')
        return redirect(url_for('auth.select_workspace'))

    conn = get_db()
    # Verify user is a member of this workspace
    workspaces = get_user_workspaces(conn, session['user_id'])
    workspace_ids = [ws['id'] for ws in workspaces]
    if workspace_id not in workspace_ids:
        flash('You are not a member of that workspace.', 'error')
        return redirect(url_for('auth.select_workspace'))

    session['workspace_id'] = workspace_id
    return redirect(url_for('dashboard.index'))
