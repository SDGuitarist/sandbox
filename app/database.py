# app/database.py (database agent owns this file)
import sqlite3
import os
from flask import g, current_app
from werkzeug.security import generate_password_hash

DATABASE = 'filmpm.db'


def get_db():
    """Get database connection. Sets PRAGMAs on every connection (FC40)."""
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE', DATABASE)
        g.db = sqlite3.connect(db_path, autocommit=True)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=5000')
        g.db.execute('PRAGMA synchronous=NORMAL')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Create tables from schema.sql and seed default data."""
    db_path = os.environ.get('DATABASE', DATABASE)
    conn = sqlite3.connect(db_path, autocommit=True)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA synchronous=NORMAL')
    with open(os.path.join(os.path.dirname(__file__), '..', 'schema.sql')) as f:
        conn.executescript(f.read())
    seed_data(conn)
    conn.close()


def seed_data(conn):
    """Seed defaults in FK-safe order. ON CONFLICT DO NOTHING for idempotency."""
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
    if not os.path.exists(app.config.get('DATABASE', DATABASE)):
        with app.app_context():
            init_db()
