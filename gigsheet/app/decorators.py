from functools import wraps
from flask import session, g, redirect, url_for, flash, abort
from app.db import get_db
from app.models import get_user_by_id, get_workspace_by_id, get_workspace_member


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'error')
            return redirect(url_for('auth.login'))
        conn = get_db()
        user = get_user_by_id(conn, session['user_id'])
        if user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        g.user = user
        return f(*args, **kwargs)
    return decorated


def require_workspace(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'workspace_id' not in session:
            flash('Select a workspace.', 'error')
            return redirect(url_for('auth.select_workspace'))
        conn = get_db()
        workspace = get_workspace_by_id(conn, session['workspace_id'])
        if workspace is None:
            session.pop('workspace_id', None)
            return redirect(url_for('auth.select_workspace'))
        member = get_workspace_member(conn, workspace['id'], g.user['id'])
        if member is None:
            flash('You are not a member of this workspace.', 'error')
            session.pop('workspace_id', None)
            return redirect(url_for('auth.select_workspace'))
        g.workspace = workspace
        g.workspace_role = member['role']
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.workspace_role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
