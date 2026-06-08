# app/database.py (database agent owns this file)
import sqlite3
import os
from flask import g, current_app
from werkzeug.security import generate_password_hash

DATABASE = 'filmpm.db'


def _make_conn(db_path):
    """Create a configured SQLite connection."""
    conn = sqlite3.connect(db_path, autocommit=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


def get_db():
    """Get database connection. Sets PRAGMAs on every connection (FC40).
    For :memory: databases, returns the app-level shared connection to avoid
    data loss across request contexts."""
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE', DATABASE)
        if db_path == ':memory:':
            # Reuse the shared in-memory connection stored in app.config
            g.db = current_app.config['_MEMORY_DB']
            g._db_is_shared = True
        else:
            g.db = _make_conn(db_path)
            g._db_is_shared = False
    return g.db


def close_db(e=None):
    is_shared = g.pop('_db_is_shared', False)
    db = g.pop('db', None)
    # Never close the shared in-memory connection; it belongs to the app object.
    if db is not None and not is_shared:
        db.close()


def init_db():
    """Create tables from schema.sql and seed default data."""
    db_path = os.environ.get('DATABASE', DATABASE)
    conn = _make_conn(db_path)
    with open(os.path.join(os.path.dirname(__file__), '..', 'schema.sql')) as f:
        conn.executescript(f.read())
    seed_data(conn)
    conn.close()


def seed_data(conn):
    """Seed defaults in FK-safe order. INSERT OR IGNORE for idempotency."""
    # 1. Departments (17 standard)
    depts = ['Producing', 'Directing', 'Camera', 'Lighting/Electrical', 'Grip',
             'Sound', 'Art/Production Design', 'Wardrobe/Costume', 'Hair & Makeup',
             'Locations', 'Transportation', 'Stunts', 'SFX', 'VFX',
             'Editorial/Post', 'Casting', 'Accounting']
    # Departments need a project_id -- seeded after project creation below

    # 2. Budget categories (seeded after project creation)

    # 3. Users -- one producer
    admin_pw = os.environ.get('ADMIN_PASSWORD', '')
    if not admin_pw:
        raise RuntimeError('ADMIN_PASSWORD environment variable is required')
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute('''INSERT OR IGNORE INTO users (username, password_hash, display_name)
                        VALUES (?, ?, ?)''',
                     ('producer', generate_password_hash(admin_pw), 'Lead Producer'))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    user = conn.execute('SELECT id FROM users WHERE username = ?', ('producer',)).fetchone()
    user_id = user['id']

    # 4. Projects -- one active production
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute('''INSERT OR IGNORE INTO projects (id, title, phase, total_budget_cents, created_by)
                        VALUES (1, ?, ?, ?, ?)''',
                     ('Untitled Production', 'development', 0, user_id))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
    project_id = 1

    # 5. Project members
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute('''INSERT OR IGNORE INTO project_members (project_id, user_id, role)
                        VALUES (?, ?, 'producer')''', (project_id, user_id))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    # 1b. Departments (now with project_id)
    conn.execute('BEGIN IMMEDIATE')
    try:
        for dept_name in depts:
            conn.execute('''INSERT OR IGNORE INTO departments (project_id, name)
                            VALUES (?, ?)''', (project_id, dept_name))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    # 2b. Budget categories
    categories = [
        ('1100', 'Story & Rights', 'ATL'), ('1200', 'Producer', 'ATL'),
        ('1300', 'Director', 'ATL'), ('1400', 'Cast', 'ATL'),
        ('2000', 'Production Staff', 'BTL_PRODUCTION'), ('2100', 'Extras', 'BTL_PRODUCTION'),
        ('2200', 'Art Department', 'BTL_PRODUCTION'), ('2300', 'Construction', 'BTL_PRODUCTION'),
        ('2400', 'Set Operations', 'BTL_PRODUCTION'), ('2500', 'SFX', 'BTL_PRODUCTION'),
        ('2600', 'Wardrobe', 'BTL_PRODUCTION'), ('2700', 'Makeup/Hair', 'BTL_PRODUCTION'),
        ('2800', 'Lighting', 'BTL_PRODUCTION'), ('2900', 'Camera', 'BTL_PRODUCTION'),
        ('3000', 'Sound', 'BTL_PRODUCTION'), ('3100', 'Transport', 'BTL_PRODUCTION'),
        ('3200', 'Locations', 'BTL_PRODUCTION'), ('3300', 'Media/Stock', 'BTL_PRODUCTION'),
        ('4000', 'Editing', 'BTL_POST'), ('4100', 'Music', 'BTL_POST'),
        ('4200', 'Post Sound', 'BTL_POST'), ('4300', 'Deliverables', 'BTL_POST'),
        ('4400', 'VFX', 'BTL_POST'), ('4500', 'Titles', 'BTL_POST'),
        ('5000', 'Insurance', 'OTHER'), ('5100', 'General/Admin', 'OTHER'),
        ('5200', 'Publicity', 'OTHER'), ('5300', 'Contingency 10%', 'OTHER'),
        ('5400', 'Completion Bond', 'OTHER'), ('5500', 'Overhead', 'OTHER'),
    ]
    conn.execute('BEGIN IMMEDIATE')
    try:
        for acct, name, group in categories:
            conn.execute('''INSERT OR IGNORE INTO budget_categories (project_id, account_number, name, parent_group)
                            VALUES (?, ?, ?, ?)''', (project_id, acct, name, group))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise


def init_app(app):
    app.teardown_appcontext(close_db)
    db_path = app.config.get('DATABASE', DATABASE)
    if db_path == ':memory:':
        # For in-memory databases, create ONE persistent connection shared across
        # all request contexts (stored in app.config). Each get_db() returns
        # this same connection so schema and seed data survive request boundaries.
        shared = _make_conn(':memory:')
        app.config['_MEMORY_DB'] = shared
        with open(os.path.join(os.path.dirname(__file__), '..', 'schema.sql')) as f:
            shared.executescript(f.read())
        seed_data(shared)
    elif not os.path.exists(db_path):
        with app.app_context():
            init_db()
