"""Auth blueprint: login, register, logout, and the shared auth decorators.

The decorators (login_required, require_project_member, require_role) are
imported by ALL other blueprints. Their signatures must not change.

Decorator stacking order (outermost first):
    @login_required
    @require_project_member
    @require_role('producer')
login_required runs first (sets g.user), then require_project_member (sets
g.project and g.member), then require_role (reads g.member['role']).
"""
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    session, g, abort,
)

from app.database import get_db
from app.models.auth_models import (
    create_user, authenticate, get_user, DuplicateUsernameError,
)

bp = Blueprint('auth', __name__)


# --------------------------------------------------------------------------
# Decorators (exported, consumed by every other blueprint)
# --------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        conn = get_db()
        g.user = get_user(conn, session['user_id'])
        if g.user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def require_project_member(f):
    """Sets g.project and g.member. All project-scoped routes MUST use this.

    Must be stacked INSIDE login_required (login_required sets g.user).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        project_id = kwargs.get('project_id')
        conn = get_db()
        from app.models.project_models import get_project
        g.project = get_project(conn, project_id)
        if g.project is None:
            abort(404)
        member = conn.execute(
            'SELECT * FROM project_members WHERE project_id = ? AND user_id = ?',
            (project_id, g.user['id']),
        ).fetchone()
        if member is None:
            abort(403)
        g.member = dict(member)
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """Check g.member['role'] is in allowed roles. Use AFTER require_project_member.

    Valid roles: 'producer', 'ad', 'department_head', 'crew_member'.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.member['role'] not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@bp.route('/login', methods=['GET'])
def login():
    return render_template('auth/login.html')


@bp.route('/login', methods=['POST'])
def login_post():
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''
    if not username or not password:
        flash('Invalid credentials', 'error')
        return redirect(url_for('auth.login'))
    conn = get_db()
    user = authenticate(conn, username, password)
    if user is None:
        flash('Invalid credentials', 'error')
        return redirect(url_for('auth.login'))
    session.clear()
    session['user_id'] = user['id']
    session['username'] = user['username']
    return redirect(url_for('index'))


@bp.route('/register', methods=['GET'])
def register():
    return render_template('auth/register.html')


@bp.route('/register', methods=['POST'])
def register_post():
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''
    display_name = (request.form.get('display_name') or '').strip()

    if not 3 <= len(username) <= 50:
        flash('Username must be 3-50 characters', 'error')
        return redirect(url_for('auth.register'))
    if len(password) < 8:
        flash('Password must be at least 8 characters', 'error')
        return redirect(url_for('auth.register'))
    if not 1 <= len(display_name) <= 100:
        flash('Display name must be 1-100 characters', 'error')
        return redirect(url_for('auth.register'))

    conn = get_db()
    try:
        create_user(conn, username, password, display_name)
    except DuplicateUsernameError:
        flash('Username already taken', 'error')
        return redirect(url_for('auth.register'))

    flash('Account created. Please log in.', 'success')
    return redirect(url_for('auth.login'))


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
