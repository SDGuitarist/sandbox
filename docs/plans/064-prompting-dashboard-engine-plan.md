---
title: "feat: Prompting Dashboard Engine (Run 064)"
type: feat
status: active
date: 2026-06-02
origin: docs/brainstorms/064-prompting-dashboard-engine-brainstorm.md
swarm: true
feed_forward:
  risk: "Fernet encryption/decryption integration with wizard form flow — if key missing/wrong, all saved prompts unreadable"
  verify_first: true
---

# feat: Prompting Dashboard Engine (Run 064)

## Overview

A Flask + SQLite + Jinja2 + Bootstrap 5 web app for Amplify AI that turns Alex's 12-component expert-led prompting method into a guided dashboard. Three access modes: anonymous shared-template visitors, authenticated workshop users, and one admin (Alex). Creates, stores, formats, shares, and grades prompts. NO LLM/AI API integration.

(see brainstorm: docs/brainstorms/064-prompting-dashboard-engine-brainstorm.md)

## What Exactly Is Changing?

New app at `prompt-dashboard/` with:
- 10 blueprints: auth, wizard, components, templates, library, grading, sharing, admin, search, export
- 12 database tables + 1 FTS5 virtual table
- ~50 routes, ~25 templates, ~45 model functions
- Fernet encryption at rest for prompt content and component answers
- Share token system with hashed tokens

## What Must Not Change?

- No modifications to existing sandbox apps or shared files
- No LLM/AI API calls — this app creates, stores, and formats prompts only
- No production data access — local SQLite only
- No external service dependencies

## How Will We Know It Worked?

### Acceptance Tests (EARS)

#### Happy Path
- WHEN a user visits `/` THE SYSTEM SHALL redirect unauthenticated users to `/auth/login`
- WHEN an authenticated user visits `/` THE SYSTEM SHALL display their prompt library with title, industry, completeness, and grade
- WHEN a user visits `/wizard/new?industry_id=1` THE SYSTEM SHALL display a 12-component wizard form grouped into 4 clusters
- WHEN a user fills 6 of 12 components and clicks Generate THE SYSTEM SHALL display a formatted prompt preview showing 50% completeness
- WHEN a user saves a prompt THE SYSTEM SHALL encrypt component answers with Fernet before writing to DB
- WHEN an admin creates a template THE SYSTEM SHALL store it with encrypted component content
- WHEN an admin generates a share token THE SYSTEM SHALL return the raw token once and store only the SHA-256 hash
- WHEN an anonymous visitor opens `/share/<valid_token>` THE SYSTEM SHALL load the template into the wizard without requiring login
- WHEN a user grades a prompt with score=4 THE SYSTEM SHALL store the grade with encrypted text fields
- WHEN an admin visits `/admin/prompts` THE SYSTEM SHALL display all prompts from all users with filtering

#### Error Cases
- WHEN `PROMPT_ENCRYPTION_KEY` is not set THE SYSTEM SHALL refuse to start with RuntimeError
- WHEN `SECRET_KEY` is not set THE SYSTEM SHALL refuse to start with RuntimeError
- WHEN a user tries to access another user's prompt THE SYSTEM SHALL return 404 (not 403)
- WHEN an anonymous visitor tries to save a prompt THE SYSTEM SHALL redirect to login
- WHEN a non-admin visits `/admin/*` THE SYSTEM SHALL return 403
- WHEN a revoked share token is used THE SYSTEM SHALL return 404
- WHEN an invalid share token is used THE SYSTEM SHALL return 404 (not 403, to avoid confirming token existence)

#### Verification Commands
- `.venv/bin/python test_smoke.py` — all smoke tests pass
- `curl http://localhost:5050/auth/login` — returns 200 with login form
- `curl http://localhost:5050/share/invalid-token` — returns 404

## What Is the Most Likely Way This Plan Is Wrong?

The Fernet encryption integration with the wizard form flow. Every model function that reads encrypted fields must decrypt; every write must encrypt. If any model function forgets to encrypt/decrypt, data corruption occurs silently. The encryption module must be simple and every encrypted field must be explicitly listed in this spec. Additionally, FTS5 indexing on encrypted content requires special handling — plaintext must be indexed at write time before encryption, but the actual column stores ciphertext.

---

# Shared Interface Spec

## App Configuration

```python
# prompt-dashboard/app/__init__.py
import os
from flask import Flask
from flask_wtf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # SECRET_KEY -- fail closed (FC10)
    secret = os.environ.get('SECRET_KEY')
    if not secret:
        raise RuntimeError('SECRET_KEY environment variable is required')
    app.config['SECRET_KEY'] = secret

    # PROMPT_ENCRYPTION_KEY -- fail closed
    enc_key = os.environ.get('PROMPT_ENCRYPTION_KEY')
    if not enc_key:
        raise RuntimeError('PROMPT_ENCRYPTION_KEY environment variable is required')
    app.config['PROMPT_ENCRYPTION_KEY'] = enc_key

    # DATABASE -- map from env so smoke tests can override (FC49)
    app.config['DATABASE'] = os.environ.get('DATABASE', 'prompting.db')

    # Session cookie security
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'

    csrf.init_app(app)

    from .database import init_db, close_db
    init_db(app)
    app.teardown_appcontext(close_db)

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    # Blueprint registration -- order does not matter
    from .blueprints.auth.routes import bp as auth_bp
    from .blueprints.wizard.routes import bp as wizard_bp
    from .blueprints.library.routes import bp as library_bp
    from .blueprints.grading.routes import bp as grading_bp
    from .blueprints.sharing.routes import bp as sharing_bp
    from .blueprints.admin.routes import bp as admin_bp
    from .blueprints.search.routes import bp as search_bp
    from .blueprints.export.routes import bp as export_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(wizard_bp, url_prefix='/wizard')
    app.register_blueprint(library_bp, url_prefix='/library')
    app.register_blueprint(grading_bp, url_prefix='/grading')
    app.register_blueprint(sharing_bp, url_prefix='/share')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(search_bp, url_prefix='/search')
    app.register_blueprint(export_bp, url_prefix='/export')

    # Root route redirects to library
    @app.route('/')
    def index():
        from flask import redirect, url_for, session
        if session.get('user_id'):
            return redirect(url_for('library.index'))
        return redirect(url_for('auth.login'))

    # Health check
    @app.route('/health')
    def health():
        return 'ok', 200

    # Error handlers
    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template('errors/500.html'), 500

    from .seed import register_seed_command
    register_seed_command(app)

    return app
```

**Requirements (requirements.txt):**
```
flask>=3.0
flask-wtf>=1.2
markupsafe>=2.1
cryptography>=42.0
bcrypt>=4.1
email-validator>=2.0
```

**App Runner (prompt-dashboard/run.py):**
```python
from app import create_app
app = create_app()
app.run(host='127.0.0.1', port=5050, debug=True, threaded=True)
```

**Environment (.env.example):**
```
SECRET_KEY=change-me-to-random-string
PROMPT_ENCRYPTION_KEY=base64-encoded-fernet-key
FLASK_DEBUG=1
```

## Database Schema

```sql
-- prompt-dashboard/app/schema.sql

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS industries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS component_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    cluster TEXT NOT NULL CHECK(cluster IN ('Your Reality', 'Your Assignment', 'Your Voice', 'Your Contract')),
    position INTEGER NOT NULL UNIQUE CHECK(position BETWEEN 1 AND 12),
    description TEXT NOT NULL DEFAULT '',
    placeholder_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS industry_guidance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    industry_id INTEGER NOT NULL REFERENCES industries(id) ON DELETE CASCADE,
    component_id INTEGER NOT NULL REFERENCES component_definitions(id) ON DELETE CASCADE,
    guidance_text TEXT NOT NULL DEFAULT '',
    UNIQUE(industry_id, component_id)
);
CREATE INDEX IF NOT EXISTS idx_industry_guidance_industry ON industry_guidance(industry_id);

CREATE TABLE IF NOT EXISTS prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    industry_id INTEGER NOT NULL REFERENCES industries(id) ON DELETE RESTRICT,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_industry ON prompt_templates(industry_id);

CREATE TABLE IF NOT EXISTS template_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    component_id INTEGER NOT NULL REFERENCES component_definitions(id) ON DELETE CASCADE,
    content TEXT NOT NULL DEFAULT '',
    UNIQUE(template_id, component_id)
);
CREATE INDEX IF NOT EXISTS idx_template_components_template ON template_components(template_id);

CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    industry_id INTEGER NOT NULL REFERENCES industries(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    completeness REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_prompts_user ON prompts(user_id);
CREATE INDEX IF NOT EXISTS idx_prompts_industry ON prompts(industry_id);

CREATE TABLE IF NOT EXISTS prompt_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    component_id INTEGER NOT NULL REFERENCES component_definitions(id) ON DELETE CASCADE,
    content TEXT NOT NULL DEFAULT '',
    UNIQUE(prompt_id, component_id)
);
CREATE INDEX IF NOT EXISTS idx_prompt_components_prompt ON prompt_components(prompt_id);

CREATE TABLE IF NOT EXISTS prompt_grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL UNIQUE REFERENCES prompts(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
    worked_well TEXT NOT NULL DEFAULT '',
    needs_improvement TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS share_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_share_tokens_template ON share_tokens(template_id);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_events_user ON audit_events(user_id);

CREATE TABLE IF NOT EXISTS saved_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    export_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_saved_exports_user ON saved_exports(user_id);

-- FTS5 for prompt search (indexes title only -- content is encrypted)
CREATE VIRTUAL TABLE IF NOT EXISTS prompts_fts USING fts5(
    title,
    content='prompts',
    content_rowid='id'
);

-- FTS5 triggers -- use BEFORE (not AFTER) to avoid stale reads (Run 061 lesson)
CREATE TRIGGER IF NOT EXISTS prompts_ai BEFORE INSERT ON prompts BEGIN
    INSERT INTO prompts_fts(rowid, title) VALUES (NEW.id, NEW.title);
END;

CREATE TRIGGER IF NOT EXISTS prompts_ad BEFORE DELETE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, title) VALUES('delete', OLD.id, OLD.title);
END;

CREATE TRIGGER IF NOT EXISTS prompts_au BEFORE UPDATE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, title) VALUES('delete', OLD.id, OLD.title);
    INSERT INTO prompts_fts(rowid, title) VALUES (NEW.id, NEW.title);
END;
```

**Note on FTS5 triggers:** FTS5 external-content tables with BEFORE INSERT triggers need special handling — the NEW.id is not yet assigned at BEFORE INSERT time for AUTOINCREMENT tables. The trigger will use NULL for rowid on INSERT. Instead, use AFTER INSERT for the insert trigger only, and BEFORE for DELETE/UPDATE:

```sql
-- CORRECTED FTS5 triggers
CREATE TRIGGER IF NOT EXISTS prompts_ai AFTER INSERT ON prompts BEGIN
    INSERT INTO prompts_fts(rowid, title) VALUES (NEW.id, NEW.title);
END;

CREATE TRIGGER IF NOT EXISTS prompts_ad BEFORE DELETE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, title) VALUES('delete', OLD.id, OLD.title);
END;

CREATE TRIGGER IF NOT EXISTS prompts_au BEFORE UPDATE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, title) VALUES('delete', OLD.id, OLD.title);
END;

CREATE TRIGGER IF NOT EXISTS prompts_au2 AFTER UPDATE ON prompts BEGIN
    INSERT INTO prompts_fts(rowid, title) VALUES (NEW.id, NEW.title);
END;
```

## Encrypted Fields

These fields store Fernet-encrypted ciphertext. Every model function that reads them MUST decrypt. Every model function that writes them MUST encrypt.

| Table | Column | Encrypt on Write | Decrypt on Read |
|-------|--------|-----------------|-----------------|
| industry_guidance | guidance_text | Yes | Yes |
| template_components | content | Yes | Yes |
| prompt_components | content | Yes | Yes |
| prompt_grades | worked_well | Yes | Yes |
| prompt_grades | needs_improvement | Yes | Yes |
| prompt_grades | notes | Yes | Yes |

**Non-encrypted fields:** prompts.title, industries.name, users.username, users.email, component_definitions.* — these are metadata used for filtering and search.

## Database Connection

```python
# prompt-dashboard/app/database.py
import os
import sqlite3
from flask import g, current_app


def _connect(db_path):
    """Open a connection with correct PRAGMAs."""
    conn = sqlite3.connect(db_path, autocommit=True)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA synchronous=NORMAL')
    result = conn.execute('PRAGMA journal_mode=WAL').fetchone()
    assert result[0] == 'wal', f'WAL mode failed: got {result[0]}'
    return conn


def get_db():
    """Get per-request database connection. NOT a context manager."""
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE', 'prompting.db')
        g.db = _connect(db_path)
    return g.db


def close_db(e=None):
    """Teardown: close per-request connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """Initialize database schema. Uses raw sqlite3.connect(), NOT get_db().
    executescript() issues implicit COMMIT that would break context manager."""
    db_path = app.config.get('DATABASE', 'prompting.db')
    if not os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path) as f:
            conn.executescript(f.read())
        conn.close()
```

**Usage — plain function call (NOT a context manager):**
```python
conn = get_db()
prompts = get_prompts_for_user(conn, user_id)
```

**Rules:**
- `autocommit=True` (Python 3.12+), NOT `isolation_level=None`
- PRAGMAs on EVERY connection (FC40)
- `get_db()` is NOT a context manager — do NOT use `with get_db() as conn:`
- `init_db()` uses raw `sqlite3.connect()`, NOT `get_db()`
- WAL mode verified with assert after setting

## Encryption Module

```python
# prompt-dashboard/app/encryption.py
from cryptography.fernet import Fernet
from flask import current_app

_fernet = None


def get_fernet():
    """Get Fernet instance. Cached per process."""
    global _fernet
    if _fernet is None:
        key = current_app.config['PROMPT_ENCRYPTION_KEY']
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_field(plaintext):
    """Encrypt a string. Returns base64-encoded ciphertext string.
    Empty strings are stored as empty (no encryption needed)."""
    if not plaintext:
        return ''
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext):
    """Decrypt a ciphertext string. Returns plaintext.
    Empty strings return empty."""
    if not ciphertext:
        return ''
    return get_fernet().decrypt(ciphertext.encode()).decode()
```

**Usage:**
```python
from app.encryption import encrypt_field, decrypt_field

# Writing:
encrypted = encrypt_field(user_input)
conn.execute('INSERT INTO prompt_components (content) VALUES (?)', (encrypted,))

# Reading:
row = conn.execute('SELECT content FROM prompt_components WHERE id=?', (pc_id,)).fetchone()
plaintext = decrypt_field(row['content'])
```

## Auth Decorators

```python
# prompt-dashboard/app/auth_helpers.py
from functools import wraps
from flask import session, redirect, url_for, abort, g
from app.database import get_db


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ?',
                            (session['user_id'],)).fetchone()
        if user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        g.user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ?',
                            (session['user_id'],)).fetchone()
        if user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        if user['role'] != 'admin':
            abort(403)
        g.user = user
        return f(*args, **kwargs)
    return decorated
```

**Usage:**
```python
from app.auth_helpers import login_required, admin_required

@bp.route('/library')
@login_required
def index():
    # g.user is set by decorator
    ...

@bp.route('/admin/prompts')
@admin_required
def all_prompts():
    ...
```

## Data Ownership

| Table | Owner Module | Read By |
|-------|-------------|---------|
| users | auth models | auth, admin, library, wizard, grading, sharing, export |
| industries | seed (write), admin models (CRUD) | wizard, admin, library, search |
| component_definitions | seed (write only) | wizard, admin, grading |
| industry_guidance | admin models | wizard, admin |
| prompt_templates | admin models | wizard, sharing, admin |
| template_components | admin models | wizard, sharing, admin |
| prompts | wizard models (create), library models (update/delete) | library, grading, admin, search, export |
| prompt_components | wizard models (create/update) | library, wizard, grading, admin, export |
| prompt_grades | grading models | library, admin, export |
| share_tokens | sharing models | sharing, admin |
| audit_events | audit function (shared) | admin |
| saved_exports | export models | export, admin |

## Model Functions

### Auth Models (app/models/auth_models.py)

```python
import bcrypt

def create_user(conn, username, email, password):
    """Create a new user. Returns: int (user_id)
    Usage:
        user_id = create_user(conn, 'alex', 'alex@example.com', 'password123')
    """
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cursor = conn.execute(
        'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
        (username, email, password_hash)
    )
    conn.commit()
    return cursor.lastrowid


def create_admin_user(conn, username, email, password):
    """Create an admin user. Returns: int (user_id)
    Usage:
        admin_id = create_admin_user(conn, 'admin', 'admin@amplifyai.com', 'pw')
    """
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cursor = conn.execute(
        'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
        (username, email, password_hash, 'admin')
    )
    conn.commit()
    return cursor.lastrowid


def get_user_by_username(conn, username):
    """Returns: sqlite3.Row or None
    Usage:
        user = get_user_by_username(conn, 'alex')
        if user is None: flash('Invalid credentials')
    """
    return conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()


def get_user_by_id(conn, user_id):
    """Returns: sqlite3.Row or None
    Usage:
        user = get_user_by_id(conn, session['user_id'])
        if user is None: abort(404)
    """
    return conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()


def verify_password(plain_password, password_hash):
    """Returns: bool
    Usage:
        if not verify_password(form_password, user['password_hash']):
            flash('Invalid credentials')
    """
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())
```

### Component Models (app/models/component_models.py)

```python
def get_all_components(conn):
    """Returns: list[sqlite3.Row] ordered by position (1-12)
    Usage:
        components = get_all_components(conn)
        for comp in components: print(comp['name'], comp['cluster'])
    """
    return conn.execute(
        'SELECT * FROM component_definitions ORDER BY position'
    ).fetchall()


def get_components_grouped(conn):
    """Returns: dict[str, list[sqlite3.Row]] grouped by cluster
    Usage:
        clusters = get_components_grouped(conn)
        for cluster_name, comps in clusters.items(): ...
    """
    rows = get_all_components(conn)
    groups = {}
    for row in rows:
        cluster = row['cluster']
        if cluster not in groups:
            groups[cluster] = []
        groups[cluster].append(row)
    return groups


def get_component(conn, component_id):
    """Returns: sqlite3.Row or None
    Usage:
        comp = get_component(conn, component_id)
        if comp is None: abort(404)
    """
    return conn.execute(
        'SELECT * FROM component_definitions WHERE id = ?', (component_id,)
    ).fetchone()
```

### Industry Models (app/models/industry_models.py)

```python
from app.encryption import encrypt_field, decrypt_field


def get_all_industries(conn):
    """Returns: list[sqlite3.Row]
    Usage:
        industries = get_all_industries(conn)
    """
    return conn.execute('SELECT * FROM industries ORDER BY name').fetchall()


def get_industry(conn, industry_id):
    """Returns: sqlite3.Row or None
    Usage:
        industry = get_industry(conn, industry_id)
        if industry is None: abort(404)
    """
    return conn.execute('SELECT * FROM industries WHERE id = ?', (industry_id,)).fetchone()


def get_guidance_for_industry(conn, industry_id):
    """Returns: list[dict] with decrypted guidance_text
    Usage:
        guidance = get_guidance_for_industry(conn, industry_id)
        # Returns: [{'component_id': 1, 'guidance_text': 'plaintext...'}, ...]
    """
    rows = conn.execute(
        'SELECT component_id, guidance_text FROM industry_guidance WHERE industry_id = ?',
        (industry_id,)
    ).fetchall()
    return [{'component_id': r['component_id'],
             'guidance_text': decrypt_field(r['guidance_text'])} for r in rows]


def save_guidance(conn, industry_id, component_id, guidance_text):
    """Save/update industry guidance. Encrypts before storing.
    Returns: None. Commits internally.
    Usage:
        save_guidance(conn, industry_id, component_id, 'Helpful tip...')
    """
    encrypted = encrypt_field(guidance_text)
    conn.execute(
        '''INSERT INTO industry_guidance (industry_id, component_id, guidance_text)
           VALUES (?, ?, ?)
           ON CONFLICT(industry_id, component_id)
           DO UPDATE SET guidance_text = excluded.guidance_text''',
        (industry_id, component_id, encrypted)
    )
    conn.commit()
```

### Template Models (app/models/template_models.py)

```python
from app.encryption import encrypt_field, decrypt_field


def create_template(conn, name, description, industry_id, created_by):
    """Returns: int (template_id). Commits internally.
    Usage:
        template_id = create_template(conn, 'Marketing Brief', 'For marketers', 1, admin_id)
    """
    cursor = conn.execute(
        'INSERT INTO prompt_templates (name, description, industry_id, created_by) VALUES (?, ?, ?, ?)',
        (name, description, industry_id, created_by)
    )
    conn.commit()
    return cursor.lastrowid


def get_template(conn, template_id):
    """Returns: sqlite3.Row or None
    Usage:
        template = get_template(conn, template_id)
        if template is None: abort(404)
    """
    return conn.execute('SELECT * FROM prompt_templates WHERE id = ?', (template_id,)).fetchone()


def get_all_templates(conn):
    """Returns: list[sqlite3.Row]
    Usage:
        templates = get_all_templates(conn)
    """
    return conn.execute(
        '''SELECT pt.*, i.name as industry_name, u.username as creator_name
           FROM prompt_templates pt
           JOIN industries i ON pt.industry_id = i.id
           JOIN users u ON pt.created_by = u.id
           ORDER BY pt.created_at DESC'''
    ).fetchall()


def get_template_components(conn, template_id):
    """Returns: list[dict] with decrypted content
    Usage:
        components = get_template_components(conn, template_id)
        # Returns: [{'component_id': 1, 'content': 'plaintext...'}, ...]
    """
    rows = conn.execute(
        'SELECT component_id, content FROM template_components WHERE template_id = ?',
        (template_id,)
    ).fetchall()
    return [{'component_id': r['component_id'],
             'content': decrypt_field(r['content'])} for r in rows]


def save_template_component(conn, template_id, component_id, content):
    """Save/update a template component. Encrypts before storing.
    Returns: None. Commits internally.
    Usage:
        save_template_component(conn, template_id, 1, 'You are a marketing expert...')
    """
    encrypted = encrypt_field(content)
    conn.execute(
        '''INSERT INTO template_components (template_id, component_id, content)
           VALUES (?, ?, ?)
           ON CONFLICT(template_id, component_id)
           DO UPDATE SET content = excluded.content''',
        (template_id, component_id, encrypted)
    )
    conn.commit()


def delete_template(conn, template_id):
    """Delete a template and all its components (CASCADE). Commits internally.
    Returns: None
    Usage:
        delete_template(conn, template_id)
    """
    conn.execute('DELETE FROM prompt_templates WHERE id = ?', (template_id,))
    conn.commit()
```

### Prompt Models (app/models/prompt_models.py)

```python
from app.encryption import encrypt_field, decrypt_field


def create_prompt(conn, title, industry_id, user_id, component_data):
    """Create a prompt with all 12 component answers.
    component_data: list of (component_id, content) tuples.
    Encrypts content before storing. Calculates completeness.
    Returns: int (prompt_id). Commits internally.
    Usage:
        component_data = [(1, 'I am a marketer'), (2, ''), (3, 'Agency background'), ...]
        prompt_id = create_prompt(conn, 'My Prompt', 1, user_id, component_data)
    """
    completeness = sum(1 for _, content in component_data if content.strip()) / 12.0
    cursor = conn.execute(
        'INSERT INTO prompts (title, industry_id, user_id, completeness) VALUES (?, ?, ?, ?)',
        (title, industry_id, user_id, completeness)
    )
    prompt_id = cursor.lastrowid
    for component_id, content in component_data:
        encrypted = encrypt_field(content)
        conn.execute(
            'INSERT INTO prompt_components (prompt_id, component_id, content) VALUES (?, ?, ?)',
            (prompt_id, component_id, encrypted)
        )
    conn.commit()
    return prompt_id


def get_prompt(conn, prompt_id):
    """Returns: sqlite3.Row or None
    Usage:
        prompt = get_prompt(conn, prompt_id)
        if prompt is None: abort(404)
    """
    return conn.execute(
        '''SELECT p.*, i.name as industry_name, u.username
           FROM prompts p
           JOIN industries i ON p.industry_id = i.id
           JOIN users u ON p.user_id = u.id
           WHERE p.id = ?''',
        (prompt_id,)
    ).fetchone()


def get_prompt_components(conn, prompt_id):
    """Returns: list[dict] with decrypted content, joined with component definitions.
    Usage:
        components = get_prompt_components(conn, prompt_id)
        # Returns: [{'component_id': 1, 'name': 'Role', 'cluster': 'Your Reality',
        #            'position': 1, 'content': 'decrypted text...'}, ...]
    """
    rows = conn.execute(
        '''SELECT pc.component_id, pc.content, cd.name, cd.cluster, cd.position
           FROM prompt_components pc
           JOIN component_definitions cd ON pc.component_id = cd.id
           WHERE pc.prompt_id = ?
           ORDER BY cd.position''',
        (prompt_id,)
    ).fetchall()
    return [{'component_id': r['component_id'], 'name': r['name'],
             'cluster': r['cluster'], 'position': r['position'],
             'content': decrypt_field(r['content'])} for r in rows]


def get_prompts_for_user(conn, user_id):
    """Returns: list[sqlite3.Row]
    Usage:
        prompts = get_prompts_for_user(conn, user_id)
    """
    return conn.execute(
        '''SELECT p.*, i.name as industry_name,
                  pg.score as grade_score
           FROM prompts p
           JOIN industries i ON p.industry_id = i.id
           LEFT JOIN prompt_grades pg ON p.id = pg.prompt_id
           WHERE p.user_id = ?
           ORDER BY p.updated_at DESC''',
        (user_id,)
    ).fetchall()


def get_all_prompts(conn, industry_id=None, user_id=None):
    """Admin: get all prompts with optional filters. Returns: list[sqlite3.Row]
    Usage:
        all_prompts = get_all_prompts(conn)
        filtered = get_all_prompts(conn, industry_id=1)
    """
    query = '''SELECT p.*, i.name as industry_name, u.username,
                      pg.score as grade_score
               FROM prompts p
               JOIN industries i ON p.industry_id = i.id
               JOIN users u ON p.user_id = u.id
               LEFT JOIN prompt_grades pg ON p.id = pg.prompt_id
               WHERE 1=1'''
    params = []
    if industry_id:
        query += ' AND p.industry_id = ?'
        params.append(industry_id)
    if user_id:
        query += ' AND p.user_id = ?'
        params.append(user_id)
    query += ' ORDER BY p.updated_at DESC'
    return conn.execute(query, params).fetchall()


def update_prompt(conn, prompt_id, title, component_data):
    """Update a prompt's title and all components. Recalculates completeness.
    component_data: list of (component_id, content) tuples.
    Returns: None. Commits internally.
    Usage:
        update_prompt(conn, prompt_id, 'New Title', [(1, 'updated text'), ...])
    """
    completeness = sum(1 for _, content in component_data if content.strip()) / 12.0
    conn.execute(
        "UPDATE prompts SET title = ?, completeness = ?, updated_at = datetime('now') WHERE id = ?",
        (title, completeness, prompt_id)
    )
    for component_id, content in component_data:
        encrypted = encrypt_field(content)
        conn.execute(
            '''INSERT INTO prompt_components (prompt_id, component_id, content)
               VALUES (?, ?, ?)
               ON CONFLICT(prompt_id, component_id)
               DO UPDATE SET content = excluded.content''',
            (prompt_id, component_id, encrypted)
        )
    conn.commit()


def delete_prompt(conn, prompt_id):
    """Delete a prompt and all components/grades (CASCADE). Commits internally.
    Returns: None
    Usage:
        delete_prompt(conn, prompt_id)
    """
    conn.execute('DELETE FROM prompts WHERE id = ?', (prompt_id,))
    conn.commit()
```

### Grading Models (app/models/grading_models.py)

```python
from app.encryption import encrypt_field, decrypt_field


def save_grade(conn, prompt_id, score, worked_well, needs_improvement, notes):
    """Save or update a grade. Encrypts text fields. Commits internally.
    Returns: int (grade_id)
    Usage:
        grade_id = save_grade(conn, prompt_id, 4, 'Great tone', 'Needs more detail', 'Notes here')
    """
    cursor = conn.execute(
        '''INSERT INTO prompt_grades (prompt_id, score, worked_well, needs_improvement, notes)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(prompt_id)
           DO UPDATE SET score = excluded.score,
                         worked_well = excluded.worked_well,
                         needs_improvement = excluded.needs_improvement,
                         notes = excluded.notes''',
        (prompt_id, score, encrypt_field(worked_well),
         encrypt_field(needs_improvement), encrypt_field(notes))
    )
    conn.commit()
    return cursor.lastrowid


def get_grade(conn, prompt_id):
    """Returns: dict with decrypted fields, or None
    Usage:
        grade = get_grade(conn, prompt_id)
        if grade: print(grade['score'], grade['worked_well'])
    """
    row = conn.execute(
        'SELECT * FROM prompt_grades WHERE prompt_id = ?', (prompt_id,)
    ).fetchone()
    if row is None:
        return None
    return {
        'id': row['id'], 'prompt_id': row['prompt_id'],
        'score': row['score'],
        'worked_well': decrypt_field(row['worked_well']),
        'needs_improvement': decrypt_field(row['needs_improvement']),
        'notes': decrypt_field(row['notes']),
        'created_at': row['created_at']
    }


def get_all_grades(conn):
    """Admin: all grades with prompt info. Returns: list[dict] with decrypted fields.
    Usage:
        grades = get_all_grades(conn)
    """
    rows = conn.execute(
        '''SELECT pg.*, p.title, p.user_id, u.username
           FROM prompt_grades pg
           JOIN prompts p ON pg.prompt_id = p.id
           JOIN users u ON p.user_id = u.id
           ORDER BY pg.created_at DESC'''
    ).fetchall()
    return [{
        'id': r['id'], 'prompt_id': r['prompt_id'], 'score': r['score'],
        'worked_well': decrypt_field(r['worked_well']),
        'needs_improvement': decrypt_field(r['needs_improvement']),
        'notes': decrypt_field(r['notes']),
        'title': r['title'], 'username': r['username'],
        'created_at': r['created_at']
    } for r in rows]
```

### Sharing Models (app/models/sharing_models.py)

```python
import hashlib
import secrets


def generate_share_token(conn, template_id, created_by):
    """Generate a share token. Stores SHA-256 hash in DB.
    Returns: str (raw token -- shown ONCE to admin, never retrievable).
    Commits internally.
    Usage:
        raw_token = generate_share_token(conn, template_id, admin_id)
        # Display raw_token to admin. It cannot be retrieved later.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    conn.execute(
        'INSERT INTO share_tokens (template_id, token_hash, created_by) VALUES (?, ?, ?)',
        (template_id, token_hash, created_by)
    )
    conn.commit()
    return raw_token


def get_template_by_token(conn, raw_token):
    """Look up template by raw token. Returns: sqlite3.Row (template) or None.
    Usage:
        template = get_template_by_token(conn, raw_token)
        if template is None: abort(404)
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    row = conn.execute(
        '''SELECT st.template_id, pt.*
           FROM share_tokens st
           JOIN prompt_templates pt ON st.template_id = pt.id
           WHERE st.token_hash = ? AND st.revoked_at IS NULL''',
        (token_hash,)
    ).fetchone()
    return row


def revoke_token(conn, token_id):
    """Revoke a share token. Commits internally.
    Returns: None
    Usage:
        revoke_token(conn, token_id)
    """
    conn.execute(
        "UPDATE share_tokens SET revoked_at = datetime('now') WHERE id = ?",
        (token_id,)
    )
    conn.commit()


def get_all_tokens(conn):
    """Admin: all share tokens with template info. Returns: list[sqlite3.Row]
    Usage:
        tokens = get_all_tokens(conn)
    """
    return conn.execute(
        '''SELECT st.*, pt.name as template_name, u.username as creator_name
           FROM share_tokens st
           JOIN prompt_templates pt ON st.template_id = pt.id
           JOIN users u ON st.created_by = u.id
           ORDER BY st.created_at DESC'''
    ).fetchall()
```

### Search Models (app/models/search_models.py)

```python
import re


def search_prompts(conn, query, user_id=None):
    """Search prompts by title using FTS5. Sanitizes query (FC36).
    If user_id provided, filters to that user's prompts only.
    Returns: list[sqlite3.Row]
    Usage:
        results = search_prompts(conn, 'marketing', user_id=current_user_id)
    """
    safe_query = _sanitize_fts_query(query)
    if not safe_query:
        return []
    base = '''SELECT p.*, i.name as industry_name, u.username,
                     pg.score as grade_score
              FROM prompts_fts fts
              JOIN prompts p ON fts.rowid = p.id
              JOIN industries i ON p.industry_id = i.id
              JOIN users u ON p.user_id = u.id
              LEFT JOIN prompt_grades pg ON p.id = pg.prompt_id
              WHERE prompts_fts MATCH ?'''
    params = [safe_query]
    if user_id:
        base += ' AND p.user_id = ?'
        params.append(user_id)
    base += ' ORDER BY rank'
    return conn.execute(base, params).fetchall()


def _sanitize_fts_query(query):
    """Sanitize user input for FTS5 MATCH (FC36).
    Strip operators, wrap in double quotes as phrase.
    Returns: str or None if empty after sanitization.
    """
    cleaned = re.sub(r'[*"():\^\\]', '', query).strip()
    if not cleaned:
        return None
    return f'"{cleaned}"'
```

### Export Models (app/models/export_models.py)

```python
import csv
import io
import json
from app.encryption import decrypt_field


def export_user_prompts_csv(conn, user_id):
    """Export a user's prompts as CSV string. Decrypts content.
    Returns: str (CSV content)
    Usage:
        csv_data = export_user_prompts_csv(conn, user_id)
    """
    prompts = conn.execute(
        '''SELECT p.*, i.name as industry_name
           FROM prompts p JOIN industries i ON p.industry_id = i.id
           WHERE p.user_id = ? ORDER BY p.created_at''',
        (user_id,)
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title', 'Industry', 'Completeness', 'Components', 'Created'])

    for prompt in prompts:
        components = conn.execute(
            '''SELECT cd.name, pc.content
               FROM prompt_components pc
               JOIN component_definitions cd ON pc.component_id = cd.id
               WHERE pc.prompt_id = ? ORDER BY cd.position''',
            (prompt['id'],)
        ).fetchall()
        comp_text = '; '.join(
            f"{c['name']}: {decrypt_field(c['content'])}"
            for c in components if decrypt_field(c['content']).strip()
        )
        writer.writerow([
            prompt['title'], prompt['industry_name'],
            f"{prompt['completeness']:.0%}", comp_text, prompt['created_at']
        ])

    return output.getvalue()


def export_all_prompts_json(conn):
    """Admin: export all prompts as JSON string. Decrypts content.
    Returns: str (JSON)
    Usage:
        json_data = export_all_prompts_json(conn)
    """
    prompts = conn.execute(
        '''SELECT p.*, i.name as industry_name, u.username
           FROM prompts p
           JOIN industries i ON p.industry_id = i.id
           JOIN users u ON p.user_id = u.id
           ORDER BY p.created_at'''
    ).fetchall()

    result = []
    for prompt in prompts:
        components = conn.execute(
            '''SELECT cd.name, cd.cluster, pc.content
               FROM prompt_components pc
               JOIN component_definitions cd ON pc.component_id = cd.id
               WHERE pc.prompt_id = ? ORDER BY cd.position''',
            (prompt['id'],)
        ).fetchall()
        grade = conn.execute(
            'SELECT * FROM prompt_grades WHERE prompt_id = ?', (prompt['id'],)
        ).fetchone()

        result.append({
            'title': prompt['title'],
            'industry': prompt['industry_name'],
            'user': prompt['username'],
            'completeness': prompt['completeness'],
            'components': [
                {'name': c['name'], 'cluster': c['cluster'],
                 'content': decrypt_field(c['content'])}
                for c in components
            ],
            'grade': {
                'score': grade['score'],
                'worked_well': decrypt_field(grade['worked_well']),
                'needs_improvement': decrypt_field(grade['needs_improvement']),
                'notes': decrypt_field(grade['notes'])
            } if grade else None,
            'created_at': prompt['created_at']
        })

    return json.dumps(result, indent=2)
```

### Audit Models (app/models/audit_models.py)

```python
def log_audit_event(conn, user_id, action, resource_type, resource_id=None):
    """Log an audit event. Commits internally.
    Returns: None
    Usage:
        log_audit_event(conn, user_id, 'create', 'prompt', prompt_id)
        log_audit_event(conn, None, 'view_share', 'template', template_id)
    """
    conn.execute(
        'INSERT INTO audit_events (user_id, action, resource_type, resource_id) VALUES (?, ?, ?, ?)',
        (user_id, action, resource_type, resource_id)
    )
    conn.commit()
```

## Route Table

| Method | Path | Blueprint.Handler | Auth | Template |
|--------|------|-------------------|------|----------|
| GET | `/auth/login` | auth.login | public | auth/login.html |
| POST | `/auth/login` | auth.login_post | public | redirect |
| GET | `/auth/register` | auth.register | public | auth/register.html |
| POST | `/auth/register` | auth.register_post | public | redirect |
| POST | `/auth/logout` | auth.logout | login_required | redirect |
| GET | `/wizard` | wizard.select_industry | login_required | wizard/select_industry.html |
| GET | `/wizard/new` | wizard.new_prompt | login_required | wizard/wizard.html |
| GET | `/wizard/template/<int:template_id>` | wizard.from_template | login_required | wizard/wizard.html |
| POST | `/wizard/save` | wizard.save_prompt | login_required | redirect |
| GET | `/wizard/<int:prompt_id>/edit` | wizard.edit_prompt | login_required+owner | wizard/wizard.html |
| POST | `/wizard/<int:prompt_id>/update` | wizard.update_prompt | login_required+owner | redirect |
| POST | `/wizard/generate` | wizard.generate_preview | public (form POST) | wizard/preview.html |
| GET | `/library` | library.index | login_required | library/index.html |
| GET | `/library/<int:prompt_id>` | library.detail | login_required+owner | library/detail.html |
| POST | `/library/<int:prompt_id>/delete` | library.delete | login_required+owner | redirect |
| GET | `/grading/<int:prompt_id>` | grading.grade_form | login_required+owner | grading/form.html |
| POST | `/grading/<int:prompt_id>` | grading.save_grade | login_required+owner | redirect |
| GET | `/share/<token>` | sharing.view_share | public | wizard/wizard.html |
| GET | `/search` | search.search_page | login_required | search/results.html |
| GET | `/export/my-prompts` | export.my_prompts | login_required | file download |
| GET | `/admin` | admin.dashboard | admin_required | admin/dashboard.html |
| GET | `/admin/templates` | admin.templates_list | admin_required | admin/templates.html |
| GET | `/admin/templates/new` | admin.template_new | admin_required | admin/template_form.html |
| POST | `/admin/templates` | admin.template_create | admin_required | redirect |
| GET | `/admin/templates/<int:id>/edit` | admin.template_edit | admin_required | admin/template_form.html |
| POST | `/admin/templates/<int:id>` | admin.template_update | admin_required | redirect |
| POST | `/admin/templates/<int:id>/delete` | admin.template_delete | admin_required | redirect |
| GET | `/admin/guidance` | admin.guidance_list | admin_required | admin/guidance.html |
| POST | `/admin/guidance/<int:industry_id>/<int:component_id>` | admin.guidance_save | admin_required | redirect |
| GET | `/admin/prompts` | admin.all_prompts | admin_required | admin/prompts.html |
| GET | `/admin/grades` | admin.all_grades | admin_required | admin/grades.html |
| GET | `/admin/tokens` | admin.tokens_list | admin_required | admin/tokens.html |
| POST | `/admin/tokens/generate` | admin.token_generate | admin_required | redirect |
| POST | `/admin/tokens/<int:id>/revoke` | admin.token_revoke | admin_required | redirect |
| GET | `/admin/export` | admin.export_page | admin_required | admin/export.html |
| POST | `/admin/export` | admin.export_data | admin_required | file download |

## Template Render Context

```python
# auth/login.html expects:
render_template('auth/login.html')
# No extra context -- just the form

# auth/register.html expects:
render_template('auth/register.html')

# wizard/select_industry.html expects:
render_template('wizard/select_industry.html',
    industries=get_all_industries(conn),
    templates=get_all_templates(conn)
)

# wizard/wizard.html expects:
render_template('wizard/wizard.html',
    components=get_all_components(conn),
    clusters=get_components_grouped(conn),
    industry=get_industry(conn, industry_id),
    guidance=get_guidance_for_industry(conn, industry_id),
    prompt=prompt_data,        # None for new, dict for edit/template/share
    prompt_id=prompt_id,       # None for new, int for edit
    is_share=False,            # True for share token access
    template_name=None         # str for template-based, None otherwise
)

# wizard/preview.html expects:
render_template('wizard/preview.html',
    title=title,
    formatted_prompt=formatted_prompt,    # str: the clean copy-ready prompt text
    components=filled_components,          # list[dict] with name, cluster, content
    completeness=completeness,             # float 0.0-1.0
    cluster_completeness=cluster_scores,   # dict[str, float]
    industry_name=industry_name,
    prompt_id=prompt_id                    # int if saved, None if preview only
)

# library/index.html expects:
render_template('library/index.html',
    prompts=get_prompts_for_user(conn, g.user['id'])
)

# library/detail.html expects:
render_template('library/detail.html',
    prompt=get_prompt(conn, prompt_id),
    components=get_prompt_components(conn, prompt_id),
    grade=get_grade(conn, prompt_id),
    formatted_prompt=format_prompt(components),
    completeness=prompt['completeness'],
    cluster_completeness=calculate_cluster_completeness(components)
)

# grading/form.html expects:
render_template('grading/form.html',
    prompt=get_prompt(conn, prompt_id),
    grade=get_grade(conn, prompt_id)      # None if not yet graded
)

# search/results.html expects:
render_template('search/results.html',
    results=search_results,     # list[sqlite3.Row]
    query=query                 # str: the original search query
)

# admin/dashboard.html expects:
render_template('admin/dashboard.html',
    total_users=total_users,
    total_prompts=total_prompts,
    total_templates=total_templates,
    avg_completeness=avg_completeness
)

# admin/templates.html expects:
render_template('admin/templates.html',
    templates=get_all_templates(conn)
)

# admin/template_form.html expects:
render_template('admin/template_form.html',
    template=template,                     # None for new, Row for edit
    industries=get_all_industries(conn),
    components=get_all_components(conn),
    template_components=existing_components  # list[dict] for edit, [] for new
)

# admin/guidance.html expects:
render_template('admin/guidance.html',
    industries=get_all_industries(conn),
    components=get_all_components(conn),
    guidance=all_guidance                  # dict keyed by (industry_id, component_id)
)

# admin/prompts.html expects:
render_template('admin/prompts.html',
    prompts=get_all_prompts(conn, industry_id=filter_industry, user_id=filter_user),
    industries=get_all_industries(conn),
    users=conn.execute('SELECT id, username FROM users ORDER BY username').fetchall(),
    filter_industry=filter_industry,
    filter_user=filter_user
)

# admin/grades.html expects:
render_template('admin/grades.html',
    grades=get_all_grades(conn)
)

# admin/tokens.html expects:
render_template('admin/tokens.html',
    tokens=get_all_tokens(conn),
    templates=get_all_templates(conn),
    new_token=session.pop('new_token', None)   # raw token shown once after generation
)

# admin/export.html expects:
render_template('admin/export.html')

# errors/403.html, errors/404.html, errors/500.html expect:
# No extra context
```

## Prompt Formatting

```python
# Used by wizard preview and library detail -- define in wizard models or a shared helper

def format_prompt(components):
    """Format filled components into a clean, copy-ready prompt string.
    components: list[dict] with 'name', 'cluster', 'content' keys.
    Returns: str
    Usage:
        formatted = format_prompt(get_prompt_components(conn, prompt_id))
    """
    lines = []
    current_cluster = None
    for comp in components:
        if not comp['content'].strip():
            continue
        if comp['cluster'] != current_cluster:
            if current_cluster is not None:
                lines.append('')
            lines.append(f"## {comp['cluster']}")
            current_cluster = comp['cluster']
        lines.append(f"**{comp['name']}:** {comp['content']}")
    return '\n'.join(lines)


def calculate_cluster_completeness(components):
    """Calculate completeness per cluster.
    Returns: dict[str, float] -- e.g., {'Your Reality': 0.67, 'Your Assignment': 1.0, ...}
    Usage:
        cluster_scores = calculate_cluster_completeness(components)
    """
    clusters = {}
    for comp in components:
        cluster = comp['cluster']
        if cluster not in clusters:
            clusters[cluster] = {'filled': 0, 'total': 0}
        clusters[cluster]['total'] += 1
        if comp['content'].strip():
            clusters[cluster]['filled'] += 1
    return {k: v['filled'] / v['total'] for k, v in clusters.items()}
```

## CSRF in Templates

Every POST form MUST include:

```html
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <!-- form fields -->
</form>
```

**Rule:** `csrf_token()` requires parentheses. `{{ csrf_token }}` renders the function object as a string.

## Export Names Table

| Name | Type | Defined By | Used By |
|------|------|------------|---------|
| `create_user` | model function | `app/models/auth_models.py` | auth agent, seed agent |
| `create_admin_user` | model function | `app/models/auth_models.py` | seed agent |
| `get_user_by_username` | model function | `app/models/auth_models.py` | auth agent |
| `get_user_by_id` | model function | `app/models/auth_models.py` | auth agent |
| `verify_password` | model function | `app/models/auth_models.py` | auth agent |
| `get_all_components` | model function | `app/models/component_models.py` | wizard, admin, seed |
| `get_components_grouped` | model function | `app/models/component_models.py` | wizard, admin |
| `get_component` | model function | `app/models/component_models.py` | admin |
| `get_all_industries` | model function | `app/models/industry_models.py` | wizard, admin, seed |
| `get_industry` | model function | `app/models/industry_models.py` | wizard, admin |
| `get_guidance_for_industry` | model function | `app/models/industry_models.py` | wizard, admin |
| `save_guidance` | model function | `app/models/industry_models.py` | admin |
| `create_template` | model function | `app/models/template_models.py` | admin, seed |
| `get_template` | model function | `app/models/template_models.py` | wizard, admin, sharing |
| `get_all_templates` | model function | `app/models/template_models.py` | wizard, admin |
| `get_template_components` | model function | `app/models/template_models.py` | wizard, sharing, admin |
| `save_template_component` | model function | `app/models/template_models.py` | admin, seed |
| `delete_template` | model function | `app/models/template_models.py` | admin |
| `create_prompt` | model function | `app/models/prompt_models.py` | wizard |
| `get_prompt` | model function | `app/models/prompt_models.py` | library, wizard, grading, admin |
| `get_prompt_components` | model function | `app/models/prompt_models.py` | library, wizard, grading, export |
| `get_prompts_for_user` | model function | `app/models/prompt_models.py` | library |
| `get_all_prompts` | model function | `app/models/prompt_models.py` | admin |
| `update_prompt` | model function | `app/models/prompt_models.py` | wizard (edit) |
| `delete_prompt` | model function | `app/models/prompt_models.py` | library |
| `save_grade` | model function | `app/models/grading_models.py` | grading |
| `get_grade` | model function | `app/models/grading_models.py` | library, grading, admin |
| `get_all_grades` | model function | `app/models/grading_models.py` | admin |
| `generate_share_token` | model function | `app/models/sharing_models.py` | admin |
| `get_template_by_token` | model function | `app/models/sharing_models.py` | sharing |
| `revoke_token` | model function | `app/models/sharing_models.py` | admin |
| `get_all_tokens` | model function | `app/models/sharing_models.py` | admin |
| `search_prompts` | model function | `app/models/search_models.py` | search |
| `export_user_prompts_csv` | model function | `app/models/export_models.py` | export |
| `export_all_prompts_json` | model function | `app/models/export_models.py` | admin |
| `log_audit_event` | model function | `app/models/audit_models.py` | all write routes |
| `encrypt_field` | helper function | `app/encryption.py` | all model modules with encrypted fields |
| `decrypt_field` | helper function | `app/encryption.py` | all model modules with encrypted fields |
| `get_db` | helper function | `app/database.py` | ALL route agents |
| `init_db` | helper function | `app/database.py` | scaffold (app factory) |
| `close_db` | helper function | `app/database.py` | scaffold (app factory) |
| `login_required` | decorator | `app/auth_helpers.py` | wizard, library, grading, search, export |
| `admin_required` | decorator | `app/auth_helpers.py` | admin |
| `format_prompt` | helper function | `app/models/prompt_models.py` | wizard (preview), library (detail) |
| `calculate_cluster_completeness` | helper function | `app/models/prompt_models.py` | wizard, library |
| `auth.login` | endpoint | auth routes | scaffold (redirect), base.html (navbar) |
| `auth.register` | endpoint | auth routes | auth/login.html (link) |
| `auth.logout` | endpoint | auth routes | base.html (navbar) |
| `wizard.select_industry` | endpoint | wizard routes | library (new prompt link), base.html (navbar) |
| `wizard.new_prompt` | endpoint | wizard routes | wizard/select_industry.html |
| `wizard.from_template` | endpoint | wizard routes | wizard/select_industry.html |
| `wizard.save_prompt` | endpoint | wizard routes | wizard/wizard.html (form action) |
| `wizard.edit_prompt` | endpoint | wizard routes | library/detail.html (edit link) |
| `wizard.update_prompt` | endpoint | wizard routes | wizard/wizard.html (form action for edit) |
| `wizard.generate_preview` | endpoint | wizard routes | wizard/wizard.html (generate button) |
| `library.index` | endpoint | library routes | base.html (navbar), scaffold (root redirect) |
| `library.detail` | endpoint | library routes | library/index.html (prompt links) |
| `library.delete` | endpoint | library routes | library/detail.html (delete button) |
| `grading.grade_form` | endpoint | grading routes | library/detail.html (grade link) |
| `grading.save_grade` | endpoint | grading routes | grading/form.html (form action) |
| `sharing.view_share` | endpoint | sharing routes | share URL (external) |
| `search.search_page` | endpoint | search routes | base.html (search form) |
| `export.my_prompts` | endpoint | export routes | library/index.html (export button) |
| `admin.dashboard` | endpoint | admin routes | base.html (navbar, admin only) |
| `admin.templates_list` | endpoint | admin routes | admin/dashboard.html |
| `admin.template_new` | endpoint | admin routes | admin/templates.html |
| `admin.template_create` | endpoint | admin routes | admin/template_form.html |
| `admin.template_edit` | endpoint | admin routes | admin/templates.html |
| `admin.template_update` | endpoint | admin routes | admin/template_form.html |
| `admin.template_delete` | endpoint | admin routes | admin/templates.html |
| `admin.guidance_list` | endpoint | admin routes | admin/dashboard.html |
| `admin.guidance_save` | endpoint | admin routes | admin/guidance.html |
| `admin.all_prompts` | endpoint | admin routes | admin/dashboard.html |
| `admin.all_grades` | endpoint | admin routes | admin/dashboard.html |
| `admin.tokens_list` | endpoint | admin routes | admin/dashboard.html |
| `admin.token_generate` | endpoint | admin routes | admin/tokens.html |
| `admin.token_revoke` | endpoint | admin routes | admin/tokens.html |
| `admin.export_page` | endpoint | admin routes | admin/dashboard.html |
| `admin.export_data` | endpoint | admin routes | admin/export.html |
| `base.html` | template | scaffold agent | ALL template agents (extends) |

## Cross-Boundary Wiring Table

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| `app/database.py` | ALL route blueprints | `from app.database import get_db` |
| `app/encryption.py` | `app/models/industry_models.py` | `from app.encryption import encrypt_field, decrypt_field` |
| `app/encryption.py` | `app/models/template_models.py` | `from app.encryption import encrypt_field, decrypt_field` |
| `app/encryption.py` | `app/models/prompt_models.py` | `from app.encryption import encrypt_field, decrypt_field` |
| `app/encryption.py` | `app/models/grading_models.py` | `from app.encryption import encrypt_field, decrypt_field` |
| `app/encryption.py` | `app/models/export_models.py` | `from app.encryption import decrypt_field` |
| `app/auth_helpers.py` | wizard, library, grading, search, export routes | `from app.auth_helpers import login_required` |
| `app/auth_helpers.py` | admin routes | `from app.auth_helpers import admin_required` |
| `app/models/auth_models.py` | `app/blueprints/auth/routes.py` | `from app.models.auth_models import create_user, get_user_by_username, verify_password` |
| `app/models/component_models.py` | `app/blueprints/wizard/routes.py` | `from app.models.component_models import get_all_components, get_components_grouped` |
| `app/models/industry_models.py` | `app/blueprints/wizard/routes.py` | `from app.models.industry_models import get_all_industries, get_industry, get_guidance_for_industry` |
| `app/models/template_models.py` | `app/blueprints/wizard/routes.py` | `from app.models.template_models import get_template, get_template_components` |
| `app/models/template_models.py` | `app/blueprints/admin/routes.py` | `from app.models.template_models import create_template, get_template, get_all_templates, get_template_components, save_template_component, delete_template` |
| `app/models/prompt_models.py` | `app/blueprints/wizard/routes.py` | `from app.models.prompt_models import create_prompt, get_prompt, get_prompt_components, update_prompt, format_prompt, calculate_cluster_completeness` |
| `app/models/prompt_models.py` | `app/blueprints/library/routes.py` | `from app.models.prompt_models import get_prompt, get_prompt_components, get_prompts_for_user, delete_prompt, format_prompt, calculate_cluster_completeness` |
| `app/models/prompt_models.py` | `app/blueprints/admin/routes.py` | `from app.models.prompt_models import get_all_prompts` |
| `app/models/grading_models.py` | `app/blueprints/grading/routes.py` | `from app.models.grading_models import save_grade, get_grade` |
| `app/models/grading_models.py` | `app/blueprints/library/routes.py` | `from app.models.grading_models import get_grade` |
| `app/models/grading_models.py` | `app/blueprints/admin/routes.py` | `from app.models.grading_models import get_all_grades` |
| `app/models/sharing_models.py` | `app/blueprints/sharing/routes.py` | `from app.models.sharing_models import get_template_by_token` |
| `app/models/sharing_models.py` | `app/blueprints/admin/routes.py` | `from app.models.sharing_models import generate_share_token, revoke_token, get_all_tokens` |
| `app/models/search_models.py` | `app/blueprints/search/routes.py` | `from app.models.search_models import search_prompts` |
| `app/models/export_models.py` | `app/blueprints/export/routes.py` | `from app.models.export_models import export_user_prompts_csv` |
| `app/models/export_models.py` | `app/blueprints/admin/routes.py` | `from app.models.export_models import export_all_prompts_json` |
| `app/models/audit_models.py` | ALL write routes | `from app.models.audit_models import log_audit_event` |
| `app/models/auth_models.py` | `app/seed.py` | `from app.models.auth_models import create_user, create_admin_user` |
| `app/models/template_models.py` | `app/seed.py` | `from app.models.template_models import create_template, save_template_component` |
| `app/models/prompt_models.py` | `app/seed.py` | `from app.models.prompt_models import create_prompt` |
| `app/models/grading_models.py` | `app/seed.py` | `from app.models.grading_models import save_grade` |

## Input Validation Prescriptions

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| `POST /auth/login` | `username` (form) | Strip, 1-50 chars, required | Flash "Username is required", redirect back |
| `POST /auth/login` | `password` (form) | Required, non-empty | Flash "Password is required", redirect back |
| `POST /auth/register` | `username` (form) | Strip, 3-50 chars, alphanumeric+underscore, required | Flash specific error, redirect back |
| `POST /auth/register` | `email` (form) | Strip, valid email format, required | Flash "Valid email is required", redirect back |
| `POST /auth/register` | `password` (form) | 8-128 chars, required | Flash "Password must be 8-128 characters", redirect back |
| `POST /wizard/save` | `title` (form) | Strip, 1-200 chars, required | Flash "Title is required", redirect back |
| `POST /wizard/save` | `industry_id` (form) | Integer, must exist in industries | Flash "Invalid industry", redirect back |
| `POST /wizard/save` | `component_<N>` (form) | Strip, 0-5000 chars each | Silently truncate at 5000 |
| `POST /wizard/<int:prompt_id>/update` | `title` (form) | Strip, 1-200 chars, required | Flash "Title is required", redirect back |
| `POST /wizard/<int:prompt_id>/update` | `prompt_id` (URL) | Must exist, must be owned by user | `abort(404)` |
| `POST /wizard/generate` | `component_<N>` (form) | Strip, 0-5000 chars each | No validation needed (preview only) |
| `POST /library/<int:prompt_id>/delete` | `prompt_id` (URL) | Must exist, must be owned by user | `abort(404)` |
| `POST /grading/<int:prompt_id>` | `score` (form) | Integer 1-5, required | Flash "Score must be 1-5", redirect back |
| `POST /grading/<int:prompt_id>` | `worked_well` (form) | Strip, 0-2000 chars | Silently truncate |
| `POST /grading/<int:prompt_id>` | `needs_improvement` (form) | Strip, 0-2000 chars | Silently truncate |
| `POST /grading/<int:prompt_id>` | `notes` (form) | Strip, 0-2000 chars | Silently truncate |
| `POST /grading/<int:prompt_id>` | `prompt_id` (URL) | Must exist, must be owned by user | `abort(404)` |
| `GET /share/<token>` | `token` (URL) | Non-empty string | `abort(404)` |
| `GET /search` | `q` (query param) | Strip, 1-200 chars | Return empty results |
| `POST /admin/templates` | `name` (form) | Strip, 1-200 chars, required | Flash error, redirect back |
| `POST /admin/templates` | `industry_id` (form) | Integer, must exist | Flash error, redirect back |
| `POST /admin/guidance/<int:industry_id>/<int:component_id>` | `guidance_text` (form) | Strip, 0-5000 chars | Silently truncate |
| `POST /admin/tokens/generate` | `template_id` (form) | Integer, must exist | Flash error, redirect back |
| `POST /admin/tokens/<int:id>/revoke` | `id` (URL) | Must exist in share_tokens | `abort(404)` |
| `POST /admin/export` | `format` (form) | Must be 'csv' or 'json' | Flash "Invalid format", redirect back |
| `GET /wizard/new` | `industry_id` (query param) | Integer, must exist | Flash error, redirect to industry selection |
| `GET /wizard/template/<int:template_id>` | `template_id` (URL) | Must exist in prompt_templates | `abort(404)` |
| `GET /wizard/<int:prompt_id>/edit` | `prompt_id` (URL) | Must exist, must be owned by user | `abort(404)` |
| `GET /library/<int:prompt_id>` | `prompt_id` (URL) | Must exist, must be owned by user | `abort(404)` |
| `GET /grading/<int:prompt_id>` | `prompt_id` (URL) | Must exist, must be owned by user | `abort(404)` |
| `GET /admin/templates/<int:id>/edit` | `id` (URL) | Must exist | `abort(404)` |

## Coordinated Behaviors

| Surface | Rule | Owner |
|---------|------|-------|
| Blueprint registration | All blueprints registered in `create_app()` with prescribed `url_prefix` | scaffold agent |
| Navbar links | `base.html` shows: Library, New Prompt, Search (all users); Admin (admin only); Login/Register (anonymous) | scaffold agent |
| CSRF token syntax | `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` WITH parentheses | ALL route agents |
| Session keys | `session['user_id']` = int user ID; `session['username']` = str; `session['role']` = 'user' or 'admin' | auth agent sets, ALL agents read |
| Base template | `{% extends "base.html" %}` — never `layout.html` or `main.html` | ALL template agents |
| Block names | `{% block title %}`, `{% block content %}` | scaffold defines, ALL fill |
| Flash messages | `flash('message', 'success')` or `flash('message', 'error')` — always category 2nd arg | ALL route agents |
| Timestamps | SQL `datetime('now')` for all timestamps, never Python `datetime.now()` | ALL model agents |
| Error returns | IDOR returns `abort(404)` not `abort(403)` — never reveal resource existence | ALL route agents |
| Logout | `session.clear()` — never `session.pop()` | auth agent |
| Security headers | `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` | scaffold agent |
| Bootstrap CDN | `<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" ...>` | scaffold agent (base.html) |
| No `\|safe` | Never use `\|safe` filter on user-entered content | ALL template agents |
| No `Markup()` | Never use `Markup()` with user-entered content | ALL model/route agents |
| Completeness formula | `filled_count / 12.0` where filled = `content.strip()` non-empty | wizard models, client JS |
| DB connection | `conn = get_db()` — NOT `with get_db() as conn:` | ALL route agents |
| Audit logging | `log_audit_event(conn, user_id, action, resource_type, resource_id)` on all create/update/delete | ALL write route agents |

## Template Contracts

### Session Keys

| Key | Set By | Read By | Example |
|-----|--------|---------|---------|
| `session['user_id']` | auth (login) | `login_required`, `admin_required`, base.html | `session['user_id'] = user['id']` |
| `session['username']` | auth (login) | base.html (display name) | `session['username'] = user['username']` |
| `session['role']` | auth (login) | base.html (admin nav), `admin_required` | `session['role'] = user['role']` |

### CSS Framework

| Item | Value |
|------|-------|
| Framework | Bootstrap 5.3.3 (CDN with SRI hash) |
| Custom CSS | `app/static/style.css` |
| Theme | Light (calm, professional for creative pros) |

### Base Template Block Names

| Block | Purpose | Required |
|-------|---------|----------|
| `{% block title %}` | Page `<title>` | Yes |
| `{% block content %}` | Main content | Yes |
| `{% block scripts %}` | Page-specific JS | No |

## Transaction Contracts

| Function | SQL Operations | Commits | Error Handling |
|----------|---------------|---------|----------------|
| `create_user` | INSERT users | commits internally | let IntegrityError propagate (UNIQUE violation) |
| `create_admin_user` | INSERT users | commits internally | let IntegrityError propagate |
| `create_template` | INSERT prompt_templates | commits internally | N/A |
| `save_template_component` | INSERT OR UPDATE template_components | commits internally | N/A |
| `delete_template` | DELETE prompt_templates (CASCADE) | commits internally | N/A |
| `create_prompt` | INSERT prompts + N×INSERT prompt_components | commits internally (one commit after all inserts) | N/A |
| `update_prompt` | UPDATE prompts + N×INSERT OR UPDATE prompt_components | commits internally (one commit after all ops) | N/A |
| `delete_prompt` | DELETE prompts (CASCADE) | commits internally | N/A |
| `save_grade` | INSERT OR UPDATE prompt_grades | commits internally | N/A |
| `generate_share_token` | INSERT share_tokens | commits internally | N/A |
| `revoke_token` | UPDATE share_tokens | commits internally | N/A |
| `save_guidance` | INSERT OR UPDATE industry_guidance | commits internally | N/A |
| `log_audit_event` | INSERT audit_events | commits internally | N/A |

**Note:** All model functions commit internally because they are atomic single-table or single-logical-unit operations. No multi-step transactions requiring external commit control are needed in this app.

## Authorization Matrix

| Route | Mode | Ownership Check |
|-------|------|-----------------|
| `GET /health` | public | N/A |
| `GET /` | public (redirects) | N/A |
| `GET /auth/login` | public | N/A |
| `POST /auth/login` | public | N/A |
| `GET /auth/register` | public | N/A |
| `POST /auth/register` | public | N/A |
| `POST /auth/logout` | login_required | N/A |
| `GET /wizard` | login_required | N/A |
| `GET /wizard/new` | login_required | N/A |
| `GET /wizard/template/<int:template_id>` | login_required | N/A (templates are shared resources) |
| `POST /wizard/save` | login_required | N/A (creates new) |
| `GET /wizard/<int:prompt_id>/edit` | login_required + owner | `prompt['user_id'] == g.user['id']` else `abort(404)` |
| `POST /wizard/<int:prompt_id>/update` | login_required + owner | `prompt['user_id'] == g.user['id']` else `abort(404)` |
| `POST /wizard/generate` | public | N/A (stateless preview) |
| `GET /library` | login_required | N/A (filtered by user_id) |
| `GET /library/<int:prompt_id>` | login_required + owner | `prompt['user_id'] == g.user['id']` else `abort(404)` |
| `POST /library/<int:prompt_id>/delete` | login_required + owner | `prompt['user_id'] == g.user['id']` else `abort(404)` |
| `GET /grading/<int:prompt_id>` | login_required + owner | `prompt['user_id'] == g.user['id']` else `abort(404)` |
| `POST /grading/<int:prompt_id>` | login_required + owner | `prompt['user_id'] == g.user['id']` else `abort(404)` |
| `GET /share/<token>` | public | N/A (token-based access) |
| `GET /search` | login_required | N/A (filtered by user_id) |
| `GET /export/my-prompts` | login_required | N/A (filtered by user_id) |
| `GET /admin` | admin_required | N/A |
| `GET /admin/templates` | admin_required | N/A |
| `GET /admin/templates/new` | admin_required | N/A |
| `POST /admin/templates` | admin_required | N/A |
| `GET /admin/templates/<int:id>/edit` | admin_required | N/A |
| `POST /admin/templates/<int:id>` | admin_required | N/A |
| `POST /admin/templates/<int:id>/delete` | admin_required | N/A |
| `GET /admin/guidance` | admin_required | N/A |
| `POST /admin/guidance/<int:industry_id>/<int:component_id>` | admin_required | N/A |
| `GET /admin/prompts` | admin_required | N/A |
| `GET /admin/grades` | admin_required | N/A |
| `GET /admin/tokens` | admin_required | N/A |
| `POST /admin/tokens/generate` | admin_required | N/A |
| `POST /admin/tokens/<int:id>/revoke` | admin_required | N/A |
| `GET /admin/export` | admin_required | N/A |
| `POST /admin/export` | admin_required | N/A |

## Seed Data

```python
# prompt-dashboard/app/seed.py
import click
from flask import current_app
from app.database import get_db
from app.models.auth_models import create_admin_user, create_user
from app.models.template_models import create_template, save_template_component
from app.models.prompt_models import create_prompt
from app.models.grading_models import save_grade
from app.encryption import encrypt_field


def register_seed_command(app):
    @app.cli.command('seed')
    def seed_db():
        """Seed the database with initial data."""
        conn = get_db()

        # Check if already seeded
        if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] > 0:
            click.echo('Database already seeded.')
            return

        # 1. Seed component definitions (12 components, 4 clusters)
        components = [
            (1, 'Role', 'Your Reality', 1, 'Define who you are in this context', 'I am a [role] who...'),
            (2, 'Background', 'Your Reality', 2, 'Relevant experience and expertise', 'My background includes...'),
            (3, 'Client Context', 'Your Reality', 3, 'Who you are working for and their situation', 'My client is...'),
            (4, 'Task', 'Your Assignment', 4, 'What specific task needs to be done', 'I need to...'),
            (5, 'Goal', 'Your Assignment', 5, 'The desired outcome of this task', 'The goal is to...'),
            (6, 'Audience', 'Your Assignment', 6, 'Who will consume the output', 'The audience is...'),
            (7, 'Key Complexity', 'Your Voice', 7, 'The main challenge or nuance', 'The key complexity is...'),
            (8, 'Tone', 'Your Voice', 8, 'The voice and style for the output', 'Use a [tone] tone...'),
            (9, 'Avoid', 'Your Voice', 9, 'What to stay away from', 'Avoid...'),
            (10, 'Definition of Done', 'Your Contract', 10, 'How to know when the task is complete', 'Done means...'),
            (11, 'Format', 'Your Contract', 11, 'Structure and format of the output', 'Format as...'),
            (12, 'Process', 'Your Contract', 12, 'Steps or approach to follow', 'Follow these steps...'),
        ]
        for comp_id, name, cluster, position, description, placeholder in components:
            conn.execute(
                '''INSERT INTO component_definitions (id, name, cluster, position, description, placeholder_text)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (comp_id, name, cluster, position, description, placeholder)
            )
        conn.commit()

        # 2. Seed industries (4+)
        industries = [
            (1, 'Marketing & Advertising', 'Campaigns, copy, branding, social media'),
            (2, 'Healthcare & Wellness', 'Patient communication, health content, compliance'),
            (3, 'Technology & SaaS', 'Product docs, user guides, developer content'),
            (4, 'Education & Training', 'Curriculum, course materials, assessments'),
            (5, 'Finance & Professional Services', 'Reports, analysis, client communication'),
        ]
        for ind_id, name, description in industries:
            conn.execute(
                'INSERT INTO industries (id, name, description) VALUES (?, ?, ?)',
                (ind_id, name, description)
            )
        conn.commit()

        # 3. Seed users (1 admin, 1 normal)
        admin_id = create_admin_user(conn, 'alex', 'alex@amplifyai.com', 'admin-password-123')
        user_id = create_user(conn, 'workshop_user', 'user@example.com', 'user-password-123')

        # 4. Seed one template (Marketing Brief)
        template_id = create_template(conn, 'Marketing Campaign Brief', 'A starter template for marketing campaigns', 1, admin_id)
        save_template_component(conn, template_id, 1, 'I am a senior marketing strategist')
        save_template_component(conn, template_id, 4, 'Create a comprehensive marketing campaign brief')
        save_template_component(conn, template_id, 6, 'Marketing team and client stakeholders')
        save_template_component(conn, template_id, 11, 'Professional brief document with sections for objectives, target audience, messaging, channels, timeline, and budget')

        # 5. Seed 5 graded example prompts
        example_prompts = [
            ('Email Campaign for Product Launch', 1, [
                (1, 'Senior email marketing specialist'), (4, 'Write a 5-email drip campaign for a SaaS product launch'),
                (5, 'Generate 40% open rate and 5% click-through'), (6, 'B2B decision makers in mid-market companies'),
                (8, 'Professional but approachable'), (10, 'Five complete emails with subject lines, preview text, and body'),
                (11, 'One email per section with clear headers'),
            ], 4, 'Strong subject lines, good segmentation', 'CTA could be more specific', 'Used for Q3 campaign'),
            ('Patient Education Brochure', 2, [
                (1, 'Health communication specialist'), (2, 'MPH with 10 years in patient education'),
                (3, 'Regional hospital system'), (4, 'Create a diabetes management brochure'),
                (6, 'Patients newly diagnosed with Type 2 diabetes'), (7, 'Must be readable at 6th grade level'),
                (8, 'Warm, supportive, non-clinical'), (9, 'Medical jargon, scare tactics'),
                (10, 'Brochure content ready for design team'), (11, 'Tri-fold brochure format'),
            ], 5, 'Perfect reading level, empathetic tone', 'Could include more visual cues', 'Best example so far'),
            ('API Documentation Guide', 3, [
                (1, 'Technical writer'), (4, 'Document REST API endpoints'),
                (5, 'Developers can integrate within 30 minutes'), (6, 'Junior to mid-level developers'),
                (10, 'Complete endpoint documentation with examples'), (11, 'OpenAPI-style with code samples'),
                (12, 'Start with authentication, then CRUD operations'),
            ], 3, 'Good structure', 'Missing error response examples', 'Needs another pass'),
            ('Course Syllabus Builder', 4, [
                (1, 'Curriculum designer'), (2, 'EdD, 15 years in higher education'),
                (4, 'Design a 12-week online course syllabus'), (5, 'Students complete with measurable skills'),
                (6, 'Adult learners returning to education'), (8, 'Encouraging, structured'),
                (11, 'Week-by-week breakdown with objectives and assessments'),
            ], 4, 'Well-structured progression', 'Assessment rubrics need detail', 'Good starting template'),
            ('Quarterly Financial Report', 5, [
                (1, 'Financial analyst'), (3, 'Mid-size professional services firm'),
                (4, 'Write executive summary for Q2 financial report'), (5, 'Board understands financial position in 5 minutes'),
                (6, 'Board of directors, non-financial executives'), (7, 'Translate complex data into actionable insights'),
                (8, 'Authoritative, concise'), (9, 'Technical accounting terminology'),
                (10, 'One-page executive summary with key metrics'), (11, 'Bullet points with trend arrows'),
                (12, 'Open with headline metric, then trends, then outlook'),
            ], 5, 'Excellent conciseness', 'Minor formatting tweaks', 'Used as template for Q3'),
        ]

        for title, industry_id, comp_data, score, worked, needs, notes in example_prompts:
            prompt_id = create_prompt(conn, title, industry_id, user_id, comp_data)
            save_grade(conn, prompt_id, score, worked, needs, notes)

        click.echo('Database seeded successfully.')
```

## Smoke Test Pattern

```python
# prompt-dashboard/test_smoke.py
"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
import re
import tempfile
from cryptography.fernet import Fernet

os.environ.setdefault("SECRET_KEY", "test-smoke-key-not-production")
os.environ.setdefault("PROMPT_ENCRYPTION_KEY", Fernet.generate_key().decode())

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
os.unlink(_tmp.name)
os.environ.setdefault("DATABASE", _tmp.name)

from app import create_app

app = create_app()
client = app.test_client()

# Seed the database
with app.app_context():
    from app.database import get_db
    conn = get_db()
    # Quick seed: just check if component_definitions is empty
    if conn.execute('SELECT COUNT(*) FROM component_definitions').fetchone()[0] == 0:
        from click.testing import CliRunner
        runner = CliRunner()
        with app.app_context():
            result = runner.invoke(app.cli, ['seed'])

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"PASS: {name}")
        passed += 1
    else:
        print(f"FAIL: {name} -- {detail}")
        failed += 1

# Phase 1: Public routes
r = client.get("/health")
check("GET /health", r.status_code == 200, f"got {r.status_code}")

r = client.get("/")
check("GET / redirects to login", r.status_code == 302, f"got {r.status_code}")

r = client.get("/auth/login")
check("GET /auth/login", r.status_code == 200, f"got {r.status_code}")

r = client.get("/auth/register")
check("GET /auth/register", r.status_code == 200, f"got {r.status_code}")

r = client.get("/share/invalid-token-12345")
check("GET /share/invalid returns 404", r.status_code == 404, f"got {r.status_code}")

# Phase 2: Auth with CSRF
r = client.get("/auth/login")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
check("Login form has CSRF token", m is not None, "csrf_token input not found")

csrf_token = m.group(1) if m else ""
r = client.post("/auth/login", data={
    "username": "alex",
    "password": "admin-password-123",
    "csrf_token": csrf_token,
}, follow_redirects=False)
check("POST /auth/login redirects", r.status_code == 302, f"got {r.status_code}")

with client.session_transaction() as sess:
    check("Login sets session['user_id']", sess.get('user_id') is not None,
          f"session keys: {list(sess.keys())}")
    check("Login sets session['role']", sess.get('role') == 'admin',
          f"role: {sess.get('role')}")

# Phase 3: Authenticated routes
r = client.get("/library")
check("GET /library (authenticated)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/wizard")
check("GET /wizard (industry selection)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/wizard/new?industry_id=1")
check("GET /wizard/new", r.status_code == 200, f"got {r.status_code}")

r = client.get("/search?q=email")
check("GET /search", r.status_code == 200, f"got {r.status_code}")

# Phase 4: Admin routes
r = client.get("/admin")
check("GET /admin (admin user)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/admin/templates")
check("GET /admin/templates", r.status_code == 200, f"got {r.status_code}")

r = client.get("/admin/prompts")
check("GET /admin/prompts", r.status_code == 200, f"got {r.status_code}")

r = client.get("/admin/guidance")
check("GET /admin/guidance", r.status_code == 200, f"got {r.status_code}")

r = client.get("/admin/tokens")
check("GET /admin/tokens", r.status_code == 200, f"got {r.status_code}")

r = client.get("/admin/export")
check("GET /admin/export", r.status_code == 200, f"got {r.status_code}")

# Phase 5: Wizard save flow
r = client.get("/wizard/new?industry_id=1")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
csrf_token = m.group(1) if m else ""

r = client.post("/wizard/save", data={
    "title": "Smoke Test Prompt",
    "industry_id": "1",
    "component_1": "I am a tester",
    "component_4": "Test the wizard save flow",
    "csrf_token": csrf_token,
}, follow_redirects=False)
check("POST /wizard/save redirects", r.status_code == 302, f"got {r.status_code}")

# Phase 6: Verify encryption
with app.app_context():
    conn = get_db()
    row = conn.execute(
        "SELECT content FROM prompt_components WHERE prompt_id = (SELECT MAX(id) FROM prompts) AND component_id = 1"
    ).fetchone()
    check("Component content is encrypted", row is not None and row['content'] != 'I am a tester',
          f"content appears plaintext: {row['content'][:50] if row else 'NULL'}")

# Phase 7: IDOR check (log in as non-admin, try to access admin)
r = client.post("/auth/logout", data={"csrf_token": csrf_token}, follow_redirects=False)

r = client.get("/auth/login")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
csrf_token = m.group(1) if m else ""

r = client.post("/auth/login", data={
    "username": "workshop_user",
    "password": "user-password-123",
    "csrf_token": csrf_token,
}, follow_redirects=False)

r = client.get("/admin")
check("Non-admin blocked from /admin", r.status_code == 403, f"got {r.status_code}")

# Summary
print(f"\n{'=' * 40}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL SMOKE TESTS PASSED")
else:
    print("SMOKE TESTS FAILED")
    exit(1)
```

## File Assignment Boundaries

### Agent 1: database
| File | Purpose |
|------|---------|
| `prompt-dashboard/app/database.py` | get_db, init_db, close_db, _connect |
| `prompt-dashboard/app/encryption.py` | encrypt_field, decrypt_field, get_fernet |
| `prompt-dashboard/app/schema.sql` | All CREATE TABLE, CREATE INDEX, FTS5, triggers |
| `prompt-dashboard/app/models/__init__.py` | Barrel file re-exporting all model functions |

### Agent 2: scaffold
| File | Purpose |
|------|---------|
| `prompt-dashboard/app/__init__.py` | App factory, blueprint registration, error handlers, security headers |
| `prompt-dashboard/app/auth_helpers.py` | login_required, admin_required decorators |
| `prompt-dashboard/run.py` | App runner |
| `prompt-dashboard/requirements.txt` | Dependencies |
| `prompt-dashboard/.env.example` | Environment template |
| `prompt-dashboard/app/templates/base.html` | Base template with Bootstrap 5, navbar, flash messages |
| `prompt-dashboard/app/templates/errors/403.html` | Forbidden error page |
| `prompt-dashboard/app/templates/errors/404.html` | Not found error page |
| `prompt-dashboard/app/templates/errors/500.html` | Server error page |
| `prompt-dashboard/app/static/style.css` | Custom styles |

### Agent 3: auth
| File | Purpose |
|------|---------|
| `prompt-dashboard/app/models/auth_models.py` | User CRUD, password verification |
| `prompt-dashboard/app/blueprints/auth/__init__.py` | Empty init |
| `prompt-dashboard/app/blueprints/auth/routes.py` | Login, register, logout routes |
| `prompt-dashboard/app/templates/auth/login.html` | Login form |
| `prompt-dashboard/app/templates/auth/register.html` | Registration form |

### Agent 4: wizard
| File | Purpose |
|------|---------|
| `prompt-dashboard/app/models/component_models.py` | Component definition queries |
| `prompt-dashboard/app/models/industry_models.py` | Industry + guidance queries |
| `prompt-dashboard/app/blueprints/wizard/__init__.py` | Empty init |
| `prompt-dashboard/app/blueprints/wizard/routes.py` | Wizard flow routes |
| `prompt-dashboard/app/templates/wizard/select_industry.html` | Industry selection page |
| `prompt-dashboard/app/templates/wizard/wizard.html` | 12-component wizard form |
| `prompt-dashboard/app/templates/wizard/preview.html` | Generated prompt preview |

### Agent 5: library
| File | Purpose |
|------|---------|
| `prompt-dashboard/app/models/prompt_models.py` | Prompt + component CRUD, format_prompt, calculate_cluster_completeness |
| `prompt-dashboard/app/blueprints/library/__init__.py` | Empty init |
| `prompt-dashboard/app/blueprints/library/routes.py` | Library list, detail, delete |
| `prompt-dashboard/app/templates/library/index.html` | Prompt list |
| `prompt-dashboard/app/templates/library/detail.html` | Prompt detail with components |

### Agent 6: grading
| File | Purpose |
|------|---------|
| `prompt-dashboard/app/models/grading_models.py` | Grade CRUD |
| `prompt-dashboard/app/blueprints/grading/__init__.py` | Empty init |
| `prompt-dashboard/app/blueprints/grading/routes.py` | Grading form and save |
| `prompt-dashboard/app/templates/grading/form.html` | Grading form |

### Agent 7: sharing
| File | Purpose |
|------|---------|
| `prompt-dashboard/app/models/sharing_models.py` | Share token generation, lookup, revocation |
| `prompt-dashboard/app/blueprints/sharing/__init__.py` | Empty init |
| `prompt-dashboard/app/blueprints/sharing/routes.py` | Share view route |
| `prompt-dashboard/app/templates/sharing/expired.html` | Token expired/invalid page |

### Agent 8: admin
| File | Purpose |
|------|---------|
| `prompt-dashboard/app/models/template_models.py` | Template CRUD |
| `prompt-dashboard/app/models/admin_models.py` | Admin dashboard stats |
| `prompt-dashboard/app/blueprints/admin/__init__.py` | Empty init |
| `prompt-dashboard/app/blueprints/admin/routes.py` | All admin routes |
| `prompt-dashboard/app/templates/admin/dashboard.html` | Admin dashboard |
| `prompt-dashboard/app/templates/admin/templates.html` | Template list |
| `prompt-dashboard/app/templates/admin/template_form.html` | Template create/edit form |
| `prompt-dashboard/app/templates/admin/guidance.html` | Industry guidance editor |
| `prompt-dashboard/app/templates/admin/prompts.html` | All prompts table |
| `prompt-dashboard/app/templates/admin/grades.html` | All grades view |
| `prompt-dashboard/app/templates/admin/tokens.html` | Token management |
| `prompt-dashboard/app/templates/admin/export.html` | Export page |

### Agent 9: search
| File | Purpose |
|------|---------|
| `prompt-dashboard/app/models/search_models.py` | FTS5 search with sanitization |
| `prompt-dashboard/app/blueprints/search/__init__.py` | Empty init |
| `prompt-dashboard/app/blueprints/search/routes.py` | Search page |
| `prompt-dashboard/app/templates/search/results.html` | Search results |

### Agent 10: export
| File | Purpose |
|------|---------|
| `prompt-dashboard/app/models/export_models.py` | CSV/JSON export functions |
| `prompt-dashboard/app/blueprints/export/__init__.py` | Empty init |
| `prompt-dashboard/app/blueprints/export/routes.py` | Export routes |

### Agent 11: seed
| File | Purpose |
|------|---------|
| `prompt-dashboard/app/seed.py` | Seed script with all deterministic data |
| `prompt-dashboard/app/models/audit_models.py` | Audit event logging |

### Agent 12: tests
| File | Purpose |
|------|---------|
| `prompt-dashboard/test_smoke.py` | Smoke tests |
| `prompt-dashboard/.gitignore` | Git ignore (test_smoke.py NOT ignored — it ships) |

## Swarm Agent Assignment

| # | Role | Files | Dependencies |
|---|------|-------|-------------|
| 1 | database | schema.sql, database.py, encryption.py, models/__init__.py | None |
| 2 | scaffold | __init__.py, auth_helpers.py, run.py, requirements.txt, .env.example, base.html, error templates, style.css | database (imports) |
| 3 | auth | auth_models.py, auth routes, auth templates | database, scaffold (auth_helpers) |
| 4 | wizard | component_models.py, industry_models.py, wizard routes, wizard templates | database, encryption, auth_helpers, prompt_models, template_models |
| 5 | library | prompt_models.py, library routes, library templates | database, encryption, auth_helpers, grading_models |
| 6 | grading | grading_models.py, grading routes, grading templates | database, encryption, auth_helpers, prompt_models |
| 7 | sharing | sharing_models.py, sharing routes, sharing templates | database, template_models, component_models |
| 8 | admin | template_models.py, admin_models.py, admin routes, admin templates | database, encryption, auth_helpers, all model modules |
| 9 | search | search_models.py, search routes, search templates | database, auth_helpers |
| 10 | export | export_models.py, export routes | database, encryption, auth_helpers |
| 11 | seed | seed.py, audit_models.py | database, all model modules, encryption |
| 12 | tests | test_smoke.py, .gitignore | ALL (integration test) |

## Wizard Client-Side JavaScript

The wizard template (`wizard.html`) needs inline JavaScript for:
1. Real-time completeness tracking per cluster and overall
2. Showing which cluster is weakest

```javascript
// In wizard.html -- inline in <script> block
document.addEventListener('DOMContentLoaded', function() {
    const textareas = document.querySelectorAll('textarea[data-component]');
    const overallBar = document.getElementById('overall-completeness');
    const overallText = document.getElementById('completeness-text');

    function updateCompleteness() {
        let filled = 0;
        const clusterCounts = {};

        textareas.forEach(function(ta) {
            const cluster = ta.dataset.cluster;
            if (!clusterCounts[cluster]) {
                clusterCounts[cluster] = {filled: 0, total: 0};
            }
            clusterCounts[cluster].total++;
            if (ta.value.trim().length > 0) {
                filled++;
                clusterCounts[cluster].filled++;
            }
        });

        // Overall
        const pct = Math.round((filled / 12) * 100);
        overallBar.style.width = pct + '%';
        overallBar.setAttribute('aria-valuenow', pct);
        overallText.textContent = filled + ' of 12 components (' + pct + '%)';

        // Per-cluster bars
        let weakest = null;
        let weakestScore = 1.1;
        for (const [cluster, counts] of Object.entries(clusterCounts)) {
            const clusterPct = Math.round((counts.filled / counts.total) * 100);
            const bar = document.getElementById('cluster-bar-' + cluster.replace(/\s+/g, '-'));
            if (bar) {
                bar.style.width = clusterPct + '%';
                bar.setAttribute('aria-valuenow', clusterPct);
            }
            const score = counts.filled / counts.total;
            if (score < weakestScore) {
                weakestScore = score;
                weakest = cluster;
            }
        }

        // Highlight weakest cluster
        document.querySelectorAll('.cluster-section').forEach(function(section) {
            section.classList.remove('border-warning');
        });
        if (weakest && weakestScore < 1.0) {
            const weakSection = document.getElementById('section-' + weakest.replace(/\s+/g, '-'));
            if (weakSection) weakSection.classList.add('border-warning');
        }
    }

    textareas.forEach(function(ta) {
        ta.addEventListener('input', updateCompleteness);
    });

    updateCompleteness(); // Initial calculation
});
```

## Feed-Forward

- **Hardest decision:** Splitting model ownership. Template models are owned by admin agent (who does CRUD) but consumed by wizard and sharing agents. This creates wide cross-boundary wiring. The barrel file (`models/__init__.py`) mitigates this by providing a single import path.
- **Rejected alternatives:** (1) Centralized single `models.py` — too large at ~45 functions. (2) Each route agent owns only its routes, central models agent owns all models — creates a bottleneck agent. (3) No encryption — violates spec requirement.
- **Least confident:** The Fernet encryption integration. Every model function that touches encrypted fields must call `encrypt_field`/`decrypt_field`. If even one function forgets, data is silently corrupted (plaintext stored where ciphertext expected, or ciphertext displayed where plaintext expected). The smoke test Phase 6 specifically validates this, but it only checks one field.
