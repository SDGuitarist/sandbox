"""Auth blueprint: register, login, logout.

Owned by the auth-core agent. Registered in studio/__init__.py as
Blueprint('auth', __name__, url_prefix='/auth').
"""
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from studio.auth import current_user, login_required, login_user, logout_user
from studio.models.audit_models import record
from studio.models.auth_models import create_user, verify_credentials

bp = Blueprint('auth', __name__, url_prefix='/auth')

VALID_ROLES = ('student', 'instructor', 'admin')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    # Authenticated users have no reason to register -> send them home.
    if current_user() is not None:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        name = (request.form.get('name') or '').strip()
        role = (request.form.get('role') or '').strip()

        # The FIRST user is forced to admin (bootstrap the studio).
        first_user = current_user_count() == 0
        if first_user:
            role = 'admin'

        errors = []
        if not email or '@' not in email:
            errors.append('A valid email is required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if not name:
            errors.append('Name is required.')
        if role not in VALID_ROLES:
            errors.append('Invalid role.')

        if errors:
            for message in errors:
                flash(message, 'error')
            return render_template('auth/register.html'), 400

        try:
            user_id = create_user(email, password, role, name)
        except ValueError:
            flash('That email is already registered.', 'error')
            return render_template('auth/register.html'), 400

        # Post-commit audit (create action) -- exactly once, after create_user commits.
        record(user_id, 'create', 'user', user_id, 'registered %s' % role)
        flash('Account created. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user() is not None:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''

        if not email or not password:
            # No field-level leak: one generic message.
            flash('Invalid credentials.', 'error')
            return render_template('auth/login.html'), 401

        user = verify_credentials(email, password)
        if user is None:
            flash('Invalid credentials.', 'error')
            return render_template('auth/login.html'), 401

        login_user(user)
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    # POST-only; _csrf is validated by the scaffold's before_request.
    logout_user()
    return redirect(url_for('auth.login'))


def current_user_count():
    """Count existing users (drives the first-user-forced-admin rule)."""
    from studio.database import get_db
    row = get_db().execute("SELECT COUNT(*) AS n FROM users").fetchone()
    return row['n']
