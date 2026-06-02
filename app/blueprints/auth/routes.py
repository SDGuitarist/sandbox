"""Auth blueprint: login, register, logout, and auth decorators."""

from functools import wraps
from flask import Blueprint, request, session, g, redirect, url_for, flash, abort, render_template

bp = Blueprint('auth', __name__)


# ---------------------------------------------------------------------------
# Auth decorators (exported for all blueprints)
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        from app.database import get_db
        from app.models.auth_models import get_user
        conn = get_db()
        g.user = get_user(conn, session['user_id'])
        if g.user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def require_project_member(f):
    """Sets g.project and g.member. All project-scoped routes MUST use this."""
    @wraps(f)
    def decorated(*args, **kwargs):
        project_id = kwargs.get('project_id')
        from app.database import get_db
        conn = get_db()
        from app.models.project_models import get_project
        g.project = get_project(conn, project_id)
        if g.project is None:
            abort(404)
        member = conn.execute(
            'SELECT * FROM project_members WHERE project_id = ? AND user_id = ?',
            (project_id, g.user['id'])
        ).fetchone()
        if member is None:
            abort(403)
        g.member = dict(member)
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """Check g.member['role'] is in allowed roles. Use AFTER require_project_member."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.member['role'] not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route('/login', methods=['GET'])
def login():
    return render_template('auth/login.html')


@bp.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        flash('Invalid credentials', 'error')
        return redirect(url_for('auth.login'))

    from app.database import get_db
    from app.models.auth_models import authenticate
    conn = get_db()
    user = authenticate(conn, username, password)

    if user is None:
        flash('Invalid credentials', 'error')
        return redirect(url_for('auth.login'))

    # Clear session before setting new keys (prevent session fixation)
    session.clear()
    session['user_id'] = user['id']
    session['username'] = user['username']

    flash('Logged in successfully', 'success')
    return redirect(url_for('index'))


@bp.route('/register', methods=['GET'])
def register():
    return render_template('auth/register.html')


@bp.route('/register', methods=['POST'])
def register_post():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    display_name = request.form.get('display_name', '').strip()

    # Validate username: 3-50 chars
    if not username or len(username) < 3 or len(username) > 50:
        flash('Username must be between 3 and 50 characters', 'error')
        return redirect(url_for('auth.register'))

    # Validate password: 8+ chars
    if len(password) < 8:
        flash('Password must be at least 8 characters', 'error')
        return redirect(url_for('auth.register'))

    # Validate display_name: 1-100 chars
    if not display_name or len(display_name) > 100:
        flash('Display name must be between 1 and 100 characters', 'error')
        return redirect(url_for('auth.register'))

    from app.database import get_db
    from app.models.auth_models import create_user
    conn = get_db()

    try:
        create_user(conn, username, password, display_name)
    except Exception:
        flash('Username already taken', 'error')
        return redirect(url_for('auth.register'))

    flash('Account created. Please log in.', 'success')
    return redirect(url_for('auth.login'))


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    flash('Logged out', 'success')
    return redirect(url_for('auth.login'))
