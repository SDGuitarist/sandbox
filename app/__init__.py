import functools
import os
import sqlite3
import uuid

from flask import (
    Blueprint,
    Flask,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_wtf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);
"""


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(conn):
    from app.venue_models import init_venue_schema
    from app.gig_models import init_gig_schema
    from app.outcome_models import init_outcome_schema
    from app.contact_models import init_contact_schema
    from app.debrief_models import init_debrief_schema

    with conn:
        conn.execute(USERS_SCHEMA)
        init_venue_schema(conn)
        init_gig_schema(conn)
        init_outcome_schema(conn)
        init_contact_schema(conn)
        init_debrief_schema(conn)


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get('user_id') is None:
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)

    return wrapped_view


auth = Blueprint('auth', __name__, url_prefix='/auth')


@auth.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username:
            flash('Username is required', 'error')
            return render_template('auth/register.html')
        if len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return render_template('auth/register.html')

        db = get_db()
        try:
            with db:
                db.execute(
                    'INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)',
                    (uuid.uuid4().hex[:8], username, generate_password_hash(password)),
                )
        except sqlite3.IntegrityError:
            flash('Username already taken', 'error')
            return render_template('auth/register.html')

        flash('Account created, please log in', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()

        if user is None or not check_password_hash(user['password_hash'], password):
            flash('Invalid username or password', 'error')
            return render_template('auth/login.html')

        session.clear()
        session['user_id'] = user['id']
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')


@auth.route('/logout', methods=('POST',))
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


def create_app():
    app = Flask(__name__)

    if 'SECRET_KEY' not in os.environ:
        raise RuntimeError('SECRET_KEY environment variable is required')
    if 'DATABASE' not in os.environ:
        raise RuntimeError('DATABASE environment variable is required')

    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    app.config['DATABASE'] = os.environ['DATABASE']
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'

    CSRFProtect(app)

    from app.venue_routes import venues_bp
    from app.gig_routes import gigs_bp
    from app.outcome_routes import outcomes_bp
    from app.contact_routes import contacts_bp
    from app.debrief_routes import debriefs_bp
    from app.dashboard_routes import dashboard_bp

    app.register_blueprint(auth)
    app.register_blueprint(venues_bp)
    app.register_blueprint(gigs_bp)
    app.register_blueprint(outcomes_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(debriefs_bp)
    app.register_blueprint(dashboard_bp)

    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db(get_db())

    return app
