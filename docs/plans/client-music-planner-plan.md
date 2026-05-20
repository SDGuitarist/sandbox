---
title: "feat: Client Music Planner"
type: feat
status: active
date: 2026-05-19
origin: docs/brainstorms/2026-05-19-client-music-planner-brainstorm.md
swarm: true
agents: 20
run: "048"
feed_forward:
  risk: "Token-based portal access is novel territory. The @require_portal_token decorator is the critical security boundary. Drag-and-drop reorder persistence flow untested in this repo."
  verify_first: true
---

# Client Music Planner

## Plan Quality Gate

1. **What exactly is changing?** New app `client-music-planner/` with 20-agent swarm: two-sided portal where musicians manage repertoire and create shareable event portals for clients to browse, build playlists, flag songs, and approve timelines.
2. **What must not change?** No other sandbox apps are modified. No global config changes. No production data access.
3. **How will we know it worked?** All 20 agents complete, assembly merges cleanly, smoke tests pass on all routes, spec contract check passes, EARS acceptance tests pass.
4. **What is the most likely way this plan is wrong?** The portal token decorator + approval gate interaction. Multiple portal blueprints depend on `g.portal_event` and `g.portal_is_approved` being set by the decorator. If any portal agent accesses these before the decorator runs, or uses a different variable name, the entire client side breaks silently.

## Enhancement Summary

**Deepened on:** 2026-05-19
**Research agents used:** SortableJS best practices, Flask CSRF+AJAX, CSV import edge cases, token-based access security, SQLite concurrency patterns

### Key Improvements
1. **SQLite**: `timeout=5.0` on connect, WAL set once at startup (not per-connection), `PRAGMA synchronous=NORMAL` (2x faster writes, safe with WAL)
2. **Security headers**: `Referrer-Policy: no-referrer` (prevents token leakage via Referer), HSTS, X-Content-Type-Options, X-Frame-Options, `Cache-Control: no-store` on portal pages
3. **SortableJS**: `forceFallback: true` for consistent cross-browser behavior, `handle: ".drag-handle"` to prevent click conflicts, snapshot+revert error recovery pattern, move up/down buttons for WCAG 2.5.7 accessibility
4. **CSV import**: UTF-8-SIG encoding (handles Excel BOM), `csv.Sniffer` for delimiter detection, formula-prefix sanitization (`=+\-@`), `MAX_CONTENT_LENGTH = 2MB`
5. **CSRF**: Flask-WTF auto-validates `X-CSRFToken` header (no extra config), `CSRFError` handler returns JSON for AJAX + HTML for forms, session cookie security settings

## Overview

Two-sided portal for wedding/event musicians (see brainstorm: docs/brainstorms/2026-05-19-client-music-planner-brainstorm.md).

- **Musician side:** Register/login, manage song repertoire (CRUD + CSV import), create events with shareable portal links, view client selections, export setlists
- **Client side:** Zero-friction access via token URL (no login), browse repertoire with filters, build playlist with drag-and-drop, flag must-play/do-not-play, submit song requests, approve timeline

**Stack:** Flask + SQLite + Jinja2 + Bootstrap 5 + SortableJS

## App Configuration

### config.py

```python
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DATABASE = None  # Set in create_app based on instance_path
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB upload limit (CSV import)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour (default)
```

### app/__init__.py (App Factory)

```python
import os
from flask import Flask
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object('app.config.Config')
    app.config['DATABASE'] = os.path.join(app.instance_path, 'music_planner.db')
    os.makedirs(app.instance_path, exist_ok=True)

    csrf.init_app(app)

    from .db import init_app
    init_app(app)

    from .filters import register_filters
    register_filters(app)

    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

    from .repertoire import bp as repertoire_bp
    app.register_blueprint(repertoire_bp, url_prefix='/repertoire')

    from .repertoire_import import bp as repertoire_import_bp
    app.register_blueprint(repertoire_import_bp, url_prefix='/repertoire/import')

    from .events import bp as events_bp
    app.register_blueprint(events_bp, url_prefix='/events')

    from .event_dashboard import bp as event_dashboard_bp
    app.register_blueprint(event_dashboard_bp, url_prefix='/events')

    from .event_export import bp as event_export_bp
    app.register_blueprint(event_export_bp, url_prefix='/events')

    from .portal_browse import bp as portal_browse_bp
    app.register_blueprint(portal_browse_bp, url_prefix='/portal')

    from .portal_playlist import bp as portal_playlist_bp
    app.register_blueprint(portal_playlist_bp, url_prefix='/portal')

    from .portal_flags import bp as portal_flags_bp
    app.register_blueprint(portal_flags_bp, url_prefix='/portal')

    from .portal_requests import bp as portal_requests_bp
    app.register_blueprint(portal_requests_bp, url_prefix='/portal')

    from .portal_approve import bp as portal_approve_bp
    app.register_blueprint(portal_approve_bp, url_prefix='/portal')

    from .api_playlist import bp as api_playlist_bp
    app.register_blueprint(api_playlist_bp, url_prefix='/api/playlist')

    from .api_filters import bp as api_filters_bp
    app.register_blueprint(api_filters_bp, url_prefix='/api/filters')

    # Security headers (token leakage prevention + standard hardening)
    @app.after_request
    def set_security_headers(response):
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    # CSRF error handler -- JSON for AJAX, HTML for forms
    from flask_wtf.csrf import CSRFError
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask import request as req
        if req.is_json or req.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from flask import jsonify
            return jsonify(error='csrf_error', message=e.description), 400
        flash("Session expired. Please try again.", "warning")
        return redirect(req.url), 400

    @app.route('/')
    def index():
        from flask import redirect, url_for, session
        if 'user_id' in session:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))

    return app
```

### db.py

```python
import sqlite3
from contextlib import contextmanager
from flask import current_app


def _init_db_pragmas():
    """Set persistent PRAGMAs once at startup. WAL mode survives reconnection."""
    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()


@contextmanager
def get_db(immediate=False):
    """Yields a database connection scoped to a single operation.

    Args:
        immediate: If True, starts a write transaction with BEGIN IMMEDIATE.
                   Use for any INSERT/UPDATE/DELETE. Reads leave this False.
    """
    conn = sqlite3.connect(
        current_app.config['DATABASE'],
        timeout=5.0,  # busy_timeout: wait up to 5s for locks
    )
    conn.row_factory = sqlite3.Row
    # Per-connection PRAGMAs (do NOT persist across connections)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")  # safe with WAL, ~2x faster writes
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables from schema.sql. Called once at app startup."""
    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    with current_app.open_resource('schema.sql') as f:
        conn.executescript(f.read().decode('utf-8'))
    conn.close()


def init_app(app):
    with app.app_context():
        _init_db_pragmas()
        init_db()
```

### Blueprint __init__.py Template (ALL blueprint agents copy this exactly)

```python
from flask import Blueprint

bp = Blueprint('{blueprint_name}', __name__)

from . import routes  # noqa: E402, F401
```

Replace `{blueprint_name}` with the blueprint name from the Agent Assignment table. The name must match the url_for prefix column exactly.

### run.py

```python
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

### requirements.txt

```
flask>=3.0
flask-wtf>=1.2
werkzeug>=3.0
email-validator>=2.0
```

### .gitignore

```
__pycache__/
*.pyc
instance/
.venv/
*.db
test_smoke.py
```

## Database Schema

### schema.sql

```sql
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS song (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    artist TEXT NOT NULL DEFAULT '',
    genre TEXT NOT NULL DEFAULT 'other',
    musical_key TEXT NOT NULL DEFAULT '',
    tempo INTEGER,
    energy INTEGER NOT NULL DEFAULT 3 CHECK (energy BETWEEN 1 AND 5),
    duration_seconds INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'wedding',
    venue TEXT NOT NULL DEFAULT '',
    client_name TEXT NOT NULL,
    client_email TEXT NOT NULL DEFAULT '',
    portal_token TEXT UNIQUE NOT NULL,
    client_approved INTEGER NOT NULL DEFAULT 0,
    approved_at TEXT,
    notes TEXT NOT NULL DEFAULT '',
    is_archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS playlist_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    song_id INTEGER NOT NULL REFERENCES song(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    is_must_play INTEGER NOT NULL DEFAULT 0,
    is_do_not_play INTEGER NOT NULL DEFAULT 0,
    client_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(event_id, song_id)
);

CREATE TABLE IF NOT EXISTS song_request (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    artist TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_song_user ON song(user_id);
CREATE INDEX IF NOT EXISTS idx_song_genre ON song(user_id, genre);
CREATE INDEX IF NOT EXISTS idx_event_user ON event(user_id);
CREATE INDEX IF NOT EXISTS idx_event_token ON event(portal_token);
CREATE INDEX IF NOT EXISTS idx_playlist_event ON playlist_item(event_id);
CREATE INDEX IF NOT EXISTS idx_playlist_position ON playlist_item(event_id, position);
CREATE INDEX IF NOT EXISTS idx_song_request_event ON song_request(event_id);
```

### Enum Values

**genre** (used in song table and filter dropdowns):

```python
GENRES = [
    'rock', 'pop', 'jazz', 'blues', 'country', 'r_and_b',
    'classical', 'latin', 'folk', 'funk', 'soul', 'reggae',
    'electronic', 'hip_hop', 'other'
]
```

**event_type** (used in event table and form):

```python
EVENT_TYPES = ['wedding', 'corporate', 'birthday', 'private_party', 'concert', 'other']
```

**energy** (1-5 scale): 1=Low/Ambient, 2=Mellow, 3=Moderate, 4=Upbeat, 5=High Energy

These constants are defined in `models.py` and imported by any agent that needs them.

## Data Ownership

| Table | Writer Agent(s) | Reader Agent(s) |
|-------|----------------|-----------------|
| user | auth | auth, decorators (login_required reads session) |
| song | repertoire, repertoire-import | repertoire, portal-browse, api-filters, event-dashboard, event-export |
| event | events | events, event-dashboard, event-export, all portal-* agents (via decorator) |
| playlist_item | portal-playlist, portal-flags, api-playlist | portal-playlist, portal-browse, portal-approve, event-dashboard, event-export |
| song_request | portal-requests | portal-requests, portal-playlist, portal-approve, event-dashboard, event-export |

## Decorators

### decorators.py

```python
from functools import wraps
from flask import session, flash, redirect, url_for, abort, g
from .db import get_db
from .models import get_event_by_token


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def require_portal_token(f):
    """Validates portal token and sets g.portal_event and g.portal_is_approved.
    Returns 404 for invalid/archived tokens (no information leak).
    Does NOT open a database connection for the route -- route must open its own."""
    @wraps(f)
    def decorated_function(token, *args, **kwargs):
        with get_db() as db:
            event = get_event_by_token(db, token)
        if event is None:
            abort(404)
        if event['is_archived']:
            abort(404)
        g.portal_event = event
        g.portal_is_approved = bool(event['client_approved'])
        return f(token, *args, **kwargs)
    return decorated_function


def require_portal_writable(f):
    """Must be used AFTER @require_portal_token.
    Blocks all writes when event is approved."""
    @wraps(f)
    def decorated_function(token, *args, **kwargs):
        if g.portal_is_approved:
            flash("This event has been approved and is now locked.", "warning")
            return redirect(url_for('portal_browse.browse', token=token))
        return f(token, *args, **kwargs)
    return decorated_function
```

**Decorator stacking order for portal write routes:**
```python
@bp.route('/<token>/playlist/add', methods=['POST'])
@require_portal_token
@require_portal_writable
def add_to_playlist(token):
    ...
```

**Decorator stacking order for portal read routes:**
```python
@bp.route('/<token>')
@require_portal_token
def browse(token):
    ...
```

## Jinja2 Filters

### filters.py

```python
def format_date(value):
    """Format ISO date string as 'January 15, 2026'."""
    if not value:
        return ''
    from datetime import datetime
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    return dt.strftime('%B %d, %Y')


def format_duration(seconds):
    """Format seconds as 'M:SS'."""
    if not seconds:
        return ''
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def format_genre(genre):
    """Format genre slug as display name: 'r_and_b' -> 'R&B'."""
    special = {'r_and_b': 'R&B', 'hip_hop': 'Hip Hop'}
    if genre in special:
        return special[genre]
    return genre.replace('_', ' ').title()


def format_energy(energy):
    """Format energy level as label."""
    labels = {1: 'Low', 2: 'Mellow', 3: 'Moderate', 4: 'Upbeat', 5: 'High'}
    return labels.get(energy, str(energy))


def register_filters(app):
    app.jinja_env.filters['format_date'] = format_date
    app.jinja_env.filters['format_duration'] = format_duration
    app.jinja_env.filters['format_genre'] = format_genre
    app.jinja_env.filters['format_energy'] = format_energy
```

**Usage in templates:**
```html
{{ event.event_date|format_date }}
{{ song.duration_seconds|format_duration }}
{{ song.genre|format_genre }}
{{ song.energy|format_energy }}
```

## Model Functions

All functions are in `models.py`. **Transaction rule: NO function commits. The route handler controls the transaction boundary.** (FC29 prevention)

### User Functions

```python
def get_user_by_email(db, email):
    """Returns: Row or None"""
    return db.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()

def get_user_by_id(db, user_id):
    """Returns: Row or None"""
    return db.execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()

def create_user(db, email, password_hash, display_name):
    """Returns: int (user_id). Does NOT commit."""
    cursor = db.execute(
        "INSERT INTO user (email, password_hash, display_name) VALUES (?, ?, ?)",
        (email, password_hash, display_name)
    )
    return cursor.lastrowid
```

**Usage example (auth agent):**
```python
with get_db(immediate=True) as db:
    user_id = create_user(db, email, hashed, name)  # int, not Row
    db.commit()
```

### Song Functions

```python
GENRES = [
    'rock', 'pop', 'jazz', 'blues', 'country', 'r_and_b',
    'classical', 'latin', 'folk', 'funk', 'soul', 'reggae',
    'electronic', 'hip_hop', 'other'
]

def get_songs_by_user(db, user_id, genre=None, energy=None, search=None):
    """Returns: list[Row]. Supports optional filtering."""
    query = "SELECT * FROM song WHERE user_id = ?"
    params = [user_id]
    if genre:
        query += " AND genre = ?"
        params.append(genre)
    if energy:
        query += " AND energy = ?"
        params.append(int(energy))
    if search:
        query += " AND (title LIKE ? OR artist LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term])
    query += " ORDER BY title ASC"
    return db.execute(query, params).fetchall()

def get_song(db, song_id, user_id):
    """Returns: Row or None. Enforces ownership via user_id."""
    return db.execute(
        "SELECT * FROM song WHERE id = ? AND user_id = ?",
        (song_id, user_id)
    ).fetchone()

def get_song_for_portal(db, song_id, user_id):
    """Returns: Row or None. Used by portal agents to read musician's song.
    Same as get_song but named distinctly for clarity."""
    return db.execute(
        "SELECT * FROM song WHERE id = ? AND user_id = ?",
        (song_id, user_id)
    ).fetchone()

def create_song(db, user_id, title, artist, genre, musical_key, tempo, energy, duration_seconds, notes):
    """Returns: int (song_id). Does NOT commit."""
    cursor = db.execute(
        """INSERT INTO song (user_id, title, artist, genre, musical_key, tempo, energy, duration_seconds, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, title, artist, genre, musical_key, tempo, int(energy), duration_seconds, notes)
    )
    return cursor.lastrowid

def update_song(db, song_id, user_id, title, artist, genre, musical_key, tempo, energy, duration_seconds, notes):
    """Returns: None. Does NOT commit. Enforces ownership."""
    db.execute(
        """UPDATE song SET title=?, artist=?, genre=?, musical_key=?, tempo=?, energy=?,
           duration_seconds=?, notes=?, updated_at=datetime('now')
           WHERE id=? AND user_id=?""",
        (title, artist, genre, musical_key, tempo, int(energy), duration_seconds, notes, song_id, user_id)
    )

def delete_song(db, song_id, user_id):
    """Returns: None. Does NOT commit. Cascades to playlist_items."""
    db.execute("DELETE FROM song WHERE id = ? AND user_id = ?", (song_id, user_id))

def bulk_create_songs(db, user_id, songs_list):
    """Returns: int (count of songs created). Does NOT commit.
    songs_list is list[dict] with keys: title, artist, genre, musical_key, tempo, energy, duration_seconds, notes"""
    count = 0
    for s in songs_list:
        db.execute(
            """INSERT INTO song (user_id, title, artist, genre, musical_key, tempo, energy, duration_seconds, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, s['title'], s.get('artist', ''), s.get('genre', 'other'),
             s.get('musical_key', ''), s.get('tempo'), int(s.get('energy', 3)),
             s.get('duration_seconds'), s.get('notes', ''))
        )
        count += 1
    return count
```

### Event Functions

```python
EVENT_TYPES = ['wedding', 'corporate', 'birthday', 'private_party', 'concert', 'other']

def get_events_by_user(db, user_id, include_archived=False):
    """Returns: list[Row]."""
    if include_archived:
        return db.execute(
            "SELECT * FROM event WHERE user_id = ? ORDER BY event_date DESC",
            (user_id,)
        ).fetchall()
    return db.execute(
        "SELECT * FROM event WHERE user_id = ? AND is_archived = 0 ORDER BY event_date DESC",
        (user_id,)
    ).fetchall()

def get_event(db, event_id, user_id):
    """Returns: Row or None. Enforces ownership."""
    return db.execute(
        "SELECT * FROM event WHERE id = ? AND user_id = ?",
        (event_id, user_id)
    ).fetchone()

def get_event_by_token(db, token):
    """Returns: Row or None. Used by @require_portal_token decorator."""
    return db.execute(
        "SELECT * FROM event WHERE portal_token = ?",
        (token,)
    ).fetchone()

def create_event(db, user_id, name, event_date, event_type, venue, client_name, client_email, portal_token, notes=''):
    """Returns: int (event_id). Does NOT commit."""
    cursor = db.execute(
        """INSERT INTO event (user_id, name, event_date, event_type, venue, client_name, client_email, portal_token, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, event_date, event_type, venue, client_name, client_email, portal_token, notes)
    )
    return cursor.lastrowid

def update_event(db, event_id, user_id, name, event_date, event_type, venue, client_name, client_email, notes):
    """Returns: None. Does NOT commit."""
    db.execute(
        """UPDATE event SET name=?, event_date=?, event_type=?, venue=?, client_name=?,
           client_email=?, notes=?, updated_at=datetime('now')
           WHERE id=? AND user_id=?""",
        (name, event_date, event_type, venue, client_name, client_email, notes, event_id, user_id)
    )

def delete_event(db, event_id, user_id):
    """Returns: None. Does NOT commit. Cascades to playlist_items, song_requests."""
    db.execute("DELETE FROM event WHERE id = ? AND user_id = ?", (event_id, user_id))

def archive_event(db, event_id, user_id):
    """Returns: None. Does NOT commit. Toggles is_archived."""
    db.execute(
        "UPDATE event SET is_archived = 1 - is_archived, updated_at=datetime('now') WHERE id = ? AND user_id = ?",
        (event_id, user_id)
    )

def regenerate_token(db, event_id, user_id, new_token):
    """Returns: None. Does NOT commit."""
    db.execute(
        "UPDATE event SET portal_token = ?, updated_at=datetime('now') WHERE id = ? AND user_id = ?",
        (new_token, event_id, user_id)
    )

def approve_event(db, event_id):
    """Returns: None. Does NOT commit. Sets client_approved=1 and approved_at."""
    db.execute(
        "UPDATE event SET client_approved = 1, approved_at = datetime('now'), updated_at=datetime('now') WHERE id = ?",
        (event_id,)
    )
```

### Playlist Functions

```python
def get_playlist_items(db, event_id):
    """Returns: list[Row] ordered by position. Joins song table for display data."""
    return db.execute(
        """SELECT pi.*, s.title, s.artist, s.genre, s.musical_key, s.tempo,
                  s.energy, s.duration_seconds
           FROM playlist_item pi
           JOIN song s ON pi.song_id = s.id
           WHERE pi.event_id = ?
           ORDER BY pi.position ASC""",
        (event_id,)
    ).fetchall()

def get_playlist_song_ids(db, event_id):
    """Returns: list[int]. Used by portal-browse to mark songs already in playlist."""
    rows = db.execute(
        "SELECT song_id FROM playlist_item WHERE event_id = ?",
        (event_id,)
    ).fetchall()
    return [row['song_id'] for row in rows]

def get_next_position(db, event_id):
    """Returns: int. Next position value for new playlist item."""
    row = db.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM playlist_item WHERE event_id = ?",
        (event_id,)
    ).fetchone()
    return row['next_pos']

def add_playlist_item(db, event_id, song_id, position):
    """Returns: int (item_id). Does NOT commit.
    Raises IntegrityError if song already in playlist (UNIQUE constraint)."""
    cursor = db.execute(
        "INSERT INTO playlist_item (event_id, song_id, position) VALUES (?, ?, ?)",
        (event_id, song_id, position)
    )
    return cursor.lastrowid

def remove_playlist_item(db, event_id, song_id):
    """Returns: None. Does NOT commit."""
    db.execute(
        "DELETE FROM playlist_item WHERE event_id = ? AND song_id = ?",
        (event_id, song_id)
    )

def update_playlist_positions(db, event_id, item_ids_in_order):
    """Returns: None. Does NOT commit.
    item_ids_in_order is list[int] of playlist_item.id values in new order.
    IMPORTANT: Caller MUST validate len(item_ids_in_order) matches actual count."""
    for position, item_id in enumerate(item_ids_in_order):
        db.execute(
            "UPDATE playlist_item SET position = ? WHERE id = ? AND event_id = ?",
            (position, item_id, event_id)
        )

def toggle_playlist_flag(db, event_id, song_id, flag_type):
    """Returns: dict with keys 'is_must_play', 'is_do_not_play'.
    Does NOT commit.
    flag_type must be 'must_play' or 'do_not_play'.
    Toggling must_play clears do_not_play and vice versa."""
    item = db.execute(
        "SELECT * FROM playlist_item WHERE event_id = ? AND song_id = ?",
        (event_id, song_id)
    ).fetchone()
    if item is None:
        return None
    if flag_type == 'must_play':
        new_must = 0 if item['is_must_play'] else 1
        db.execute(
            "UPDATE playlist_item SET is_must_play = ?, is_do_not_play = 0 WHERE event_id = ? AND song_id = ?",
            (new_must, event_id, song_id)
        )
        return {'is_must_play': new_must, 'is_do_not_play': 0}
    elif flag_type == 'do_not_play':
        new_dnp = 0 if item['is_do_not_play'] else 1
        db.execute(
            "UPDATE playlist_item SET is_do_not_play = ?, is_must_play = 0 WHERE event_id = ? AND song_id = ?",
            (new_dnp, event_id, song_id)
        )
        return {'is_must_play': 0, 'is_do_not_play': new_dnp}
    return None

def get_playlist_stats(db, event_id):
    """Returns: dict with keys 'total', 'must_play', 'do_not_play'."""
    row = db.execute(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN is_must_play = 1 THEN 1 ELSE 0 END) as must_play,
                  SUM(CASE WHEN is_do_not_play = 1 THEN 1 ELSE 0 END) as do_not_play
           FROM playlist_item WHERE event_id = ?""",
        (event_id,)
    ).fetchone()
    return {'total': row['total'], 'must_play': row['must_play'] or 0, 'do_not_play': row['do_not_play'] or 0}
```

### Song Request Functions

```python
def get_song_requests(db, event_id):
    """Returns: list[Row]."""
    return db.execute(
        "SELECT * FROM song_request WHERE event_id = ? ORDER BY created_at DESC",
        (event_id,)
    ).fetchall()

def add_song_request(db, event_id, title, artist, notes):
    """Returns: int (request_id). Does NOT commit."""
    cursor = db.execute(
        "INSERT INTO song_request (event_id, title, artist, notes) VALUES (?, ?, ?, ?)",
        (event_id, title, artist, notes)
    )
    return cursor.lastrowid

def delete_song_request(db, request_id, event_id):
    """Returns: None. Does NOT commit. Enforces event scope."""
    db.execute(
        "DELETE FROM song_request WHERE id = ? AND event_id = ?",
        (request_id, event_id)
    )

def get_song_request_count(db, event_id):
    """Returns: int."""
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM song_request WHERE event_id = ?",
        (event_id,)
    ).fetchone()
    return row['cnt']
```

## Transaction Boundary Rules

1. **Functions do NOT commit.** Route handler wraps in `with get_db(immediate=True) as db:` for writes.
2. **Read-only routes** use `with get_db() as db:` (no immediate).
3. **Multi-step writes** are a SINGLE transaction block. The route calls multiple model functions, then calls `db.commit()` once.
4. **If a function must commit, it is a spec violation.** Flag it.

```python
# CORRECT -- route handler commits
@bp.route('/<token>/approve/confirm', methods=['POST'])
@require_portal_token
@require_portal_writable
def confirm_approval(token):
    with get_db(immediate=True) as db:
        approve_event(db, g.portal_event['id'])  # does NOT commit
        db.commit()
    flash("Your selections have been approved!", "success")
    return redirect(url_for('portal_browse.browse', token=token))

# WRONG -- helper function commits
def approve_event(db, event_id):
    db.execute(...)
    db.commit()  # NEVER do this
```

## Endpoint Registry

Route paths are RELATIVE to the blueprint url_prefix. `@bp.route("/")` NOT `@bp.route("/auth/")`. (FC7 prevention)

### auth (prefix: /auth)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| login | GET,POST | /login | auth.login | Login form + handler |
| register | GET,POST | /register | auth.register | Registration form + handler |
| logout | POST | /logout | auth.logout | Clear session |

### dashboard (prefix: /dashboard)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| index | GET | / | dashboard.index | Musician home with event summary |

### repertoire (prefix: /repertoire)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| index | GET | / | repertoire.index | List songs with search/filter |
| create | GET,POST | /new | repertoire.create | Add new song |
| detail | GET | /\<int:song_id\> | repertoire.detail | View song details |
| edit | GET,POST | /\<int:song_id\>/edit | repertoire.edit | Edit song |
| delete | POST | /\<int:song_id\>/delete | repertoire.delete | Delete song |

### repertoire_import (prefix: /repertoire/import)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| import_form | GET | / | repertoire_import.import_form | Upload CSV form |
| import_preview | POST | /preview | repertoire_import.import_preview | Preview parsed CSV |
| import_confirm | POST | /confirm | repertoire_import.import_confirm | Confirm and save import |

**CSV format (header row required):**
```
title,artist,genre,musical_key,tempo,energy,duration_seconds,notes
```

**CSV Import Research Insights (agents must follow):**
- **Encoding:** Decode with `utf-8-sig` first (handles Excel BOM), then `latin-1` fallback
- **Delimiter detection:** Use `csv.Sniffer().sniff(sample, delimiters=',;\t')` with comma fallback
- **Formula sanitization:** Sanitize cells starting with `=`, `+`, `-`, `@` by prefixing with `'` (single quote)
- **Validation:** Return ALL row errors at once (not fail-on-first). Return `{'valid_rows': [...], 'errors': [{'row': N, 'messages': [...]}]}`
- **Preview storage:** Store parsed results in temp file with UUID key (NOT Flask session -- 4KB cookie limit). Validate UUID format `^[a-f0-9]{32}$` to prevent path traversal
- **Duplicates:** Check `LOWER(title) = LOWER(?) AND LOWER(artist) = LOWER(?)` and report count of skipped duplicates
- **Max file size:** Enforced by `MAX_CONTENT_LENGTH = 2MB` in config (Flask auto-returns 413)

### events (prefix: /events)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| index | GET | / | events.index | List all events |
| create | GET,POST | /new | events.create | Create event |
| detail | GET | /\<int:event_id\> | events.detail | View event with portal link |
| edit | GET,POST | /\<int:event_id\>/edit | events.edit | Edit event |
| delete | POST | /\<int:event_id\>/delete | events.delete | Delete event |
| regenerate_token | POST | /\<int:event_id\>/regenerate-token | events.regenerate_token | New portal token |
| toggle_archive | POST | /\<int:event_id\>/archive | events.toggle_archive | Archive/unarchive |

### event_dashboard (prefix: /events)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| dashboard | GET | /\<int:event_id\>/dashboard | event_dashboard.dashboard | View client selections |

### event_export (prefix: /events)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| export_preview | GET | /\<int:event_id\>/export | event_export.export_preview | Preview setlist for print |
| export_csv | GET | /\<int:event_id\>/export/csv | event_export.export_csv | Download CSV |

### portal_browse (prefix: /portal)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| browse | GET | /\<token\> | portal_browse.browse | Client browses repertoire |
| song_detail | GET | /\<token\>/song/\<int:song_id\> | portal_browse.song_detail | Client views song detail |

### portal_playlist (prefix: /portal)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| playlist | GET | /\<token\>/playlist | portal_playlist.playlist | Client playlist builder page |
| add_to_playlist | POST | /\<token\>/playlist/add | portal_playlist.add_to_playlist | Add song to playlist |
| remove_from_playlist | POST | /\<token\>/playlist/remove | portal_playlist.remove_from_playlist | Remove from playlist |

**Form fields for add_to_playlist:** `song_id` (int, from hidden input), `client_note` (str, optional textarea)
**Form fields for remove_from_playlist:** `song_id` (int, from hidden input)

### portal_flags (prefix: /portal)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| toggle_flag | POST | /\<token\>/flags/toggle | portal_flags.toggle_flag | Toggle must-play/do-not-play |

**Form fields:** `song_id` (int), `flag_type` (str: 'must_play' or 'do_not_play')
**Returns:** JSON `{"success": true, "is_must_play": 0, "is_do_not_play": 1}` or `{"error": "message"}`

### portal_requests (prefix: /portal)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| requests | GET | /\<token\>/requests | portal_requests.requests | View + add song requests |
| add_request | POST | /\<token\>/requests/add | portal_requests.add_request | Submit request |
| delete_request | POST | /\<token\>/requests/\<int:request_id\>/delete | portal_requests.delete_request | Retract request |

**Form fields for add_request:** `title` (str, required), `artist` (str), `notes` (str)

### portal_approve (prefix: /portal)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| approve | GET | /\<token\>/approve | portal_approve.approve | Review summary before approval |
| confirm_approval | POST | /\<token\>/approve/confirm | portal_approve.confirm_approval | Submit approval |

### api_playlist (prefix: /api/playlist)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| reorder | POST | /reorder | api_playlist.reorder | Update playlist positions (JSON) |

**Request body:** `{"token": "abc123", "item_ids": [5, 3, 1, 4, 2]}`
**Response:** `{"success": true}` or `{"error": "message"}`
**Validation:** `len(item_ids)` must equal actual playlist count for event. (FC recipe-organizer parallel array check)

### api_filters (prefix: /api/filters)

| Function | Method | Path | url_for Name | Description |
|----------|--------|------|-------------|-------------|
| filter_songs | GET | /songs | api_filters.filter_songs | Filter songs (returns JSON) |

**Query params:** `token` (required), `genre` (optional), `energy` (optional), `search` (optional)
**Response:** `{"songs": [{"id": 1, "title": "...", "artist": "...", "genre": "...", "energy": 3, "duration_seconds": 240, "in_playlist": true}, ...]}` 

## Template Render Context

Every `render_template()` call with exact variable names and types. Agents MUST use these names.

### auth

```python
# auth/login.html
render_template('auth/login.html')
# No variables -- form fields: email, password

# auth/register.html
render_template('auth/register.html')
# No variables -- form fields: email, password, confirm_password, display_name
```

**Form field names for auth (FC9):**
- login: `email`, `password`
- register: `email`, `password`, `confirm_password`, `display_name`

### dashboard

```python
# dashboard/index.html
render_template('dashboard/index.html',
    events=events,           # list[Row] -- active events sorted by date
    active_count=active_count,  # int
    total_songs=total_songs,    # int
    recent_approvals=recent)    # list[Row] -- events where client_approved=1, limit 5
```

### repertoire

```python
# repertoire/index.html
render_template('repertoire/index.html',
    songs=songs,       # list[Row]
    search=search,     # str -- current search term or ''
    genre=genre,       # str -- current genre filter or ''
    energy=energy,     # str -- current energy filter or ''
    genres=GENRES)     # list[str] -- for filter dropdown

# repertoire/detail.html
render_template('repertoire/detail.html',
    song=song)         # Row

# repertoire/form.html
render_template('repertoire/form.html',
    song=song,         # Row or None (None = create mode)
    genres=GENRES)     # list[str]
```

**Form field names for repertoire (FC9):**
- create/edit: `title`, `artist`, `genre`, `musical_key`, `tempo`, `energy`, `duration_seconds`, `notes`

### repertoire_import

```python
# repertoire_import/form.html
render_template('repertoire_import/form.html')
# No variables -- file upload field: csv_file

# repertoire_import/preview.html
render_template('repertoire_import/preview.html',
    songs=parsed_songs,     # list[dict] with keys: title, artist, genre, musical_key, tempo, energy, duration_seconds, notes
    filename=filename,      # str
    error_rows=error_rows,  # list[dict] with keys: row_number, error
    valid_count=valid_count)  # int
```

**Form field names:** `csv_file` (file input)

### events

```python
# events/index.html
render_template('events/index.html',
    events=events,          # list[Row]
    show_archived=show_archived)  # bool

# events/detail.html
render_template('events/detail.html',
    event=event,            # Row
    portal_url=portal_url,  # str -- full URL: request.host_url + 'portal/' + token
    playlist_count=playlist_count,  # int
    request_count=request_count)    # int

# events/form.html
render_template('events/form.html',
    event=event,            # Row or None (None = create mode)
    event_types=EVENT_TYPES)  # list[str]
```

**Form field names for events (FC9):**
- create/edit: `name`, `event_date`, `event_type`, `venue`, `client_name`, `client_email`, `notes`

### event_dashboard

```python
# event_dashboard/dashboard.html
render_template('event_dashboard/dashboard.html',
    event=event,                # Row
    playlist_items=playlist_items,  # list[Row] (joined with song data)
    song_requests=song_requests,    # list[Row]
    stats=stats)                    # dict: {total, must_play, do_not_play}
```

### event_export

```python
# event_export/preview.html
render_template('event_export/preview.html',
    event=event,                # Row
    playlist_items=playlist_items,  # list[Row] ordered by position
    song_requests=song_requests)    # list[Row]
```

### portal_browse

```python
# portal_browse/browse.html
render_template('portal_browse/browse.html',
    event=g.portal_event,          # Row (set by decorator)
    songs=songs,                   # list[Row] -- musician's repertoire
    genres=GENRES,                 # list[str] -- for filter dropdown
    search=search,                 # str
    genre_filter=genre_filter,     # str
    energy_filter=energy_filter,   # str
    playlist_song_ids=playlist_song_ids,  # list[int] -- songs already in playlist
    is_approved=g.portal_is_approved)     # bool

# portal_browse/song_detail.html
render_template('portal_browse/song_detail.html',
    event=g.portal_event,    # Row
    song=song,               # Row
    in_playlist=in_playlist, # bool
    is_approved=g.portal_is_approved)  # bool
```

### portal_playlist

```python
# portal_playlist/playlist.html
render_template('portal_playlist/playlist.html',
    event=g.portal_event,          # Row
    playlist_items=playlist_items,  # list[Row] ordered by position
    song_requests=song_requests,    # list[Row]
    is_approved=g.portal_is_approved)  # bool
```

### portal_requests

```python
# portal_requests/requests.html
render_template('portal_requests/requests.html',
    event=g.portal_event,      # Row
    requests=requests,         # list[Row]
    is_approved=g.portal_is_approved)  # bool
```

### portal_approve

```python
# portal_approve/approve.html
render_template('portal_approve/approve.html',
    event=g.portal_event,          # Row
    playlist_items=playlist_items,  # list[Row]
    song_requests=song_requests,    # list[Row]
    stats=stats,                    # dict: {total, must_play, do_not_play}
    is_approved=g.portal_is_approved)  # bool
```

## Cross-Boundary Wiring Table

### portal_browse -> portal_playlist (Add Song to Playlist)

**Trigger:** Client clicks "Add to Playlist" button on browse page
**Action:** Form POST to `url_for('portal_playlist.add_to_playlist', token=token)` with hidden `song_id`

```html
<!-- In portal_browse/browse.html: -->
<form method="POST" action="{{ url_for('portal_playlist.add_to_playlist', token=event.portal_token) }}">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="hidden" name="song_id" value="{{ song.id }}">
    <button type="submit">Add to Playlist</button>
</form>
```

```python
# In portal_playlist/routes.py:
@bp.route('/<token>/playlist/add', methods=['POST'])
@require_portal_token
@require_portal_writable
def add_to_playlist(token):
    song_id = request.form.get('song_id', type=int)
    if not song_id:
        flash("Invalid song.", "error")
        return redirect(url_for('portal_browse.browse', token=token))
    with get_db(immediate=True) as db:
        position = get_next_position(db, g.portal_event['id'])
        try:
            add_playlist_item(db, g.portal_event['id'], song_id, position)
            db.commit()
            flash("Song added to playlist.", "success")
        except Exception:
            flash("Song is already in your playlist.", "warning")
    return redirect(url_for('portal_playlist.playlist', token=token))
```

### portal_playlist -> api_playlist (Drag-and-Drop Reorder)

**Trigger:** SortableJS `onEnd` event fires in browser
**Action:** JS sends POST to `/api/playlist/reorder` with JSON body

```javascript
// In static/js/playlist.js:
const playlistEl = document.getElementById('playlist-container');
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
let lastKnownOrder = [];  // snapshot for revert on error

document.addEventListener('DOMContentLoaded', function() {
    // Snapshot initial server-rendered order
    lastKnownOrder = Array.from(
        playlistEl.querySelectorAll('.playlist-item')
    ).map(function(el) { return el.dataset.itemId; });

    // Move up/down buttons always work (accessibility, WCAG 2.5.7)
    initMoveButtons();

    // Drag-and-drop only if SortableJS loaded
    if (typeof Sortable !== 'undefined') {
        initSortable();
        playlistEl.querySelectorAll('.drag-handle').forEach(function(el) {
            el.classList.remove('d-none');
        });
    }
});

function initSortable() {
    var sortable = Sortable.create(playlistEl, {
        animation: 200,
        handle: '.drag-handle',
        ghostClass: 'playlist-ghost',
        chosenClass: 'playlist-chosen',
        dragClass: 'playlist-drag',
        forceFallback: true,
        fallbackTolerance: 3,
        dataIdAttr: 'data-item-id',
        draggable: '.playlist-item',
        onEnd: function(evt) {
            if (evt.oldIndex === evt.newIndex) return;
            savePlaylistOrder(sortable.toArray(), sortable);
        }
    });
}

function savePlaylistOrder(itemIds, sortableInstance) {
    var token = playlistEl.dataset.token;
    fetch('/api/playlist/reorder', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({token: token, item_ids: itemIds.map(Number)})
    }).then(function(r) {
        return r.json().then(function(data) { return {ok: r.ok, data: data}; });
    }).then(function(result) {
        if (result.ok && result.data.success) {
            lastKnownOrder = itemIds;
        } else {
            // Revert DOM to last known good state
            if (sortableInstance) sortableInstance.sort(lastKnownOrder, true);
            showToast(result.data.error || 'Save failed. Reverted.', 'danger');
        }
    }).catch(function() {
        if (sortableInstance) sortableInstance.sort(lastKnownOrder, true);
        showToast('Network error. Reverted.', 'danger');
    });
}
```

```python
# In api_playlist/routes.py:
from app import csrf

@bp.route('/reorder', methods=['POST'])
def reorder():
    data = request.get_json()
    if not data or 'token' not in data or 'item_ids' not in data:
        return jsonify(error="Missing token or item_ids"), 400
    token = data['token']
    item_ids = data['item_ids']
    with get_db() as db:
        event = get_event_by_token(db, token)
    if event is None or event['is_archived']:
        return jsonify(error="Invalid portal"), 404
    if event['client_approved']:
        return jsonify(error="Event is approved and locked"), 403
    # Validate array length matches actual playlist count
    with get_db(immediate=True) as db:
        actual_items = get_playlist_items(db, event['id'])
        if len(item_ids) != len(actual_items):
            return jsonify(error="Playlist changed. Please refresh."), 409
        actual_ids = {item['id'] for item in actual_items}
        if set(item_ids) != actual_ids:
            return jsonify(error="Invalid item IDs."), 400
        update_playlist_positions(db, event['id'], item_ids)
        db.commit()
    return jsonify(success=True)
```

**CSRF for JSON endpoints:** The `api_playlist` and `api_filters` blueprints must include CSRF token via `X-CSRFToken` header from a `<meta>` tag. Portal base template includes:
```html
<meta name="csrf-token" content="{{ csrf_token() }}">
```

### portal_flags -> portal_playlist (Flag Toggle via AJAX)

**Trigger:** Client clicks flag button on playlist page
**Action:** JS sends POST to portal_flags.toggle_flag

```javascript
// In static/js/flags.js:
function toggleFlag(token, songId, flagType) {
    const formData = new FormData();
    formData.append('song_id', songId);
    formData.append('flag_type', flagType);
    fetch(`/portal/${token}/flags/toggle`, {
        method: 'POST',
        headers: {'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
        body: formData
    }).then(r => r.json()).then(data => {
        if (data.success) {
            updateFlagUI(songId, data.is_must_play, data.is_do_not_play);
        }
    });
}
```

```python
# In portal_flags/routes.py:
@bp.route('/<token>/flags/toggle', methods=['POST'])
@require_portal_token
@require_portal_writable
def toggle_flag(token):
    song_id = request.form.get('song_id', type=int)
    flag_type = request.form.get('flag_type')
    if not song_id or flag_type not in ('must_play', 'do_not_play'):
        return jsonify(error="Invalid request"), 400
    with get_db(immediate=True) as db:
        result = toggle_playlist_flag(db, g.portal_event['id'], song_id, flag_type)
        if result is None:
            return jsonify(error="Song not in playlist"), 404
        db.commit()
    return jsonify(success=True, **result)
```

### portal_approve -> all portal agents (Approval Gate)

**Trigger:** Client submits approval
**Effect:** All portal write routes check `g.portal_is_approved` via `@require_portal_writable`

```python
# In portal_approve/routes.py:
@bp.route('/<token>/approve/confirm', methods=['POST'])
@require_portal_token
@require_portal_writable
def confirm_approval(token):
    with get_db(immediate=True) as db:
        approve_event(db, g.portal_event['id'])
        db.commit()
    flash("Your selections have been approved! Thank you.", "success")
    return redirect(url_for('portal_browse.browse', token=token))
```

All portal write routes already use `@require_portal_writable` which checks `g.portal_is_approved`. No additional wiring needed -- the decorator handles it.

### event_dashboard -> all portal data (Musician Reads Client Selections)

```python
# In event_dashboard/routes.py:
@bp.route('/<int:event_id>/dashboard')
@login_required
def dashboard(event_id):
    with get_db() as db:
        event = get_event(db, event_id, session['user_id'])
        if event is None:
            abort(404)
        playlist_items = get_playlist_items(db, event_id)
        song_requests = get_song_requests(db, event_id)
        stats = get_playlist_stats(db, event_id)
    return render_template('event_dashboard/dashboard.html',
        event=event, playlist_items=playlist_items,
        song_requests=song_requests, stats=stats)
```

### events -> portal_browse (Portal Link Display)

```python
# In events/routes.py detail():
portal_url = request.host_url.rstrip('/') + url_for('portal_browse.browse', token=event['portal_token'])
```

### api_filters -> portal_browse (AJAX Song Filtering)

```javascript
// In static/js/filters.js:
let debounceTimer;
function filterSongs(token) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        const genre = document.getElementById('genre-filter').value;
        const energy = document.getElementById('energy-filter').value;
        const search = document.getElementById('search-input').value;
        const params = new URLSearchParams({token, genre, energy, search});
        fetch(`/api/filters/songs?${params}`)
            .then(r => r.json())
            .then(data => renderSongList(data.songs));
    }, 300);
}
```

```python
# In api_filters/routes.py:
@bp.route('/songs')
def filter_songs():
    token = request.args.get('token', '')
    genre = request.args.get('genre', '')
    energy = request.args.get('energy', '')
    search = request.args.get('search', '')
    with get_db() as db:
        event = get_event_by_token(db, token)
        if event is None or event['is_archived']:
            return jsonify(error="Invalid portal"), 404
        songs = get_songs_by_user(db, event['user_id'], genre=genre or None,
                                   energy=energy or None, search=search or None)
        playlist_ids = get_playlist_song_ids(db, event['id'])
    result = [{'id': s['id'], 'title': s['title'], 'artist': s['artist'],
               'genre': s['genre'], 'energy': s['energy'],
               'duration_seconds': s['duration_seconds'],
               'in_playlist': s['id'] in playlist_ids} for s in songs]
    return jsonify(songs=result)
```

## Coordinated Behaviors

| Behavior | Pattern | All agents must follow |
|----------|---------|----------------------|
| Flash messages | `flash("message", "category")` where category is `success`, `error`, `warning`, `info` | Bootstrap 5 alert with dismiss button |
| Flash on create | `flash("{Type} created successfully.", "success")` | All CRUD agents |
| Flash on delete | `flash("{Type} deleted.", "success")` | All CRUD agents |
| Flash on error | `flash("Specific field error message.", "error")` | All form agents |
| Empty states | `<p class="text-muted">No {items} yet. <a href="...">Add one</a>.</p>` | All list views |
| Error display (HTML) | Flash for form errors | Never expose stack traces |
| Error display (JSON) | `{"error": "User-friendly message"}` | API endpoints only |
| Date formatting | `{{ value\|format_date }}` | All templates displaying dates |
| Duration formatting | `{{ value\|format_duration }}` | All templates displaying song duration |
| Genre formatting | `{{ value\|format_genre }}` | All templates displaying genre |
| Energy display | `{{ value\|format_energy }}` | All templates displaying energy |
| Loading states | `.loading` CSS class on buttons during AJAX | Disable button + spinner icon |
| Token validation | `@require_portal_token` decorator | All portal routes |
| Auth validation | `@login_required` decorator | All musician routes |
| Write guard | `@require_portal_writable` decorator | All portal write routes |
| CSRF (forms) | `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` | Every HTML form |
| CSRF (AJAX) | `'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content` | Every fetch() call |
| Page titles | `{% block title %}Page Name - GigList{% endblock %}` | All templates |
| Navbar active | `{% set active_page = 'page_name' %}` before extends | All musician templates |
| Portal nav active | `{% set active_portal = 'page_name' %}` before extends | All portal templates |

## Directory Structure

```
client-music-planner/
├── run.py
├── requirements.txt
├── seed.py
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── decorators.py
│   ├── filters.py
│   ├── schema.sql
│   ├── auth/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── dashboard/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── repertoire/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── repertoire_import/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── events/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── event_dashboard/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── event_export/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── portal_browse/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── portal_playlist/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── portal_flags/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── portal_requests/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── portal_approve/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── api_playlist/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── api_filters/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── portal_base.html
│   │   ├── _navbar.html
│   │   ├── _flash.html
│   │   ├── _portal_nav.html
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   ├── dashboard/
│   │   │   └── index.html
│   │   ├── repertoire/
│   │   │   ├── index.html
│   │   │   ├── detail.html
│   │   │   └── form.html
│   │   ├── repertoire_import/
│   │   │   ├── form.html
│   │   │   └── preview.html
│   │   ├── events/
│   │   │   ├── index.html
│   │   │   ├── detail.html
│   │   │   └── form.html
│   │   ├── event_dashboard/
│   │   │   └── dashboard.html
│   │   ├── event_export/
│   │   │   └── preview.html
│   │   ├── portal_browse/
│   │   │   ├── browse.html
│   │   │   └── song_detail.html
│   │   ├── portal_playlist/
│   │   │   └── playlist.html
│   │   ├── portal_requests/
│   │   │   └── requests.html
│   │   ├── portal_approve/
│   │   │   └── approve.html
│   │   └── dashboard/
│   │       └── index.html
│   └── static/
│       ├── css/
│       │   ├── style.css
│       │   └── portal.css
│       └── js/
│           ├── sortable.min.js
│           ├── playlist.js
│           ├── filters.js
│           └── flags.js
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_auth.py
    ├── test_repertoire.py
    ├── test_events.py
    ├── test_portal.py
    └── test_api.py
```

## Swarm Agent Assignment

### Agent: core-infra

**Files:**
- `client-music-planner/app/__init__.py`
- `client-music-planner/app/config.py`
- `client-music-planner/app/db.py`
- `client-music-planner/app/models.py`
- `client-music-planner/app/decorators.py`
- `client-music-planner/app/filters.py`
- `client-music-planner/app/schema.sql`
- `client-music-planner/requirements.txt`
- `client-music-planner/run.py`
- `client-music-planner/.gitignore`

**Responsibility:** App factory, database layer, all model functions, decorators, Jinja2 filters, schema, config. This agent creates the foundation all others depend on.

### Agent: auth

**Files:**
- `client-music-planner/app/auth/__init__.py`
- `client-music-planner/app/auth/routes.py`
- `client-music-planner/app/templates/auth/login.html`
- `client-music-planner/app/templates/auth/register.html`

**Responsibility:** Musician login, registration, logout routes and templates.

### Agent: layout-static

**Files:**
- `client-music-planner/app/templates/base.html`
- `client-music-planner/app/templates/_navbar.html`
- `client-music-planner/app/templates/_flash.html`
- `client-music-planner/app/static/css/style.css`

**Responsibility:** Musician-side base template with Bootstrap 5 CDN, navigation bar, flash message partial, main CSS.

### Agent: repertoire

**Files:**
- `client-music-planner/app/repertoire/__init__.py`
- `client-music-planner/app/repertoire/routes.py`
- `client-music-planner/app/templates/repertoire/index.html`
- `client-music-planner/app/templates/repertoire/detail.html`
- `client-music-planner/app/templates/repertoire/form.html`

**Responsibility:** Song CRUD (list, create, detail, edit, delete) for musician.

### Agent: repertoire-import

**Files:**
- `client-music-planner/app/repertoire_import/__init__.py`
- `client-music-planner/app/repertoire_import/routes.py`
- `client-music-planner/app/templates/repertoire_import/form.html`
- `client-music-planner/app/templates/repertoire_import/preview.html`

**Responsibility:** CSV bulk import flow -- upload, parse, preview, confirm.

### Agent: events

**Files:**
- `client-music-planner/app/events/__init__.py`
- `client-music-planner/app/events/routes.py`
- `client-music-planner/app/templates/events/index.html`
- `client-music-planner/app/templates/events/detail.html`
- `client-music-planner/app/templates/events/form.html`

**Responsibility:** Event CRUD, portal token generation, archive toggle.

### Agent: event-dashboard

**Files:**
- `client-music-planner/app/event_dashboard/__init__.py`
- `client-music-planner/app/event_dashboard/routes.py`
- `client-music-planner/app/templates/event_dashboard/dashboard.html`

**Responsibility:** Musician views client selections, flags, song requests for a specific event.

### Agent: event-export

**Files:**
- `client-music-planner/app/event_export/__init__.py`
- `client-music-planner/app/event_export/routes.py`
- `client-music-planner/app/templates/event_export/preview.html`

**Responsibility:** Setlist export as printable HTML and downloadable CSV.

### Agent: portal-browse

**Files:**
- `client-music-planner/app/portal_browse/__init__.py`
- `client-music-planner/app/portal_browse/routes.py`
- `client-music-planner/app/templates/portal_browse/browse.html`
- `client-music-planner/app/templates/portal_browse/song_detail.html`

**Responsibility:** Client browses musician's repertoire, views song details.

### Agent: portal-playlist

**Files:**
- `client-music-planner/app/portal_playlist/__init__.py`
- `client-music-planner/app/portal_playlist/routes.py`
- `client-music-planner/app/templates/portal_playlist/playlist.html`

**Responsibility:** Client playlist builder page, add/remove songs.

### Agent: portal-flags

**Files:**
- `client-music-planner/app/portal_flags/__init__.py`
- `client-music-planner/app/portal_flags/routes.py`

**Responsibility:** AJAX endpoint for toggling must-play/do-not-play flags.

### Agent: portal-requests

**Files:**
- `client-music-planner/app/portal_requests/__init__.py`
- `client-music-planner/app/portal_requests/routes.py`
- `client-music-planner/app/templates/portal_requests/requests.html`

**Responsibility:** Client song request form, list, and delete.

### Agent: portal-approve

**Files:**
- `client-music-planner/app/portal_approve/__init__.py`
- `client-music-planner/app/portal_approve/routes.py`
- `client-music-planner/app/templates/portal_approve/approve.html`

**Responsibility:** Client reviews and approves their selections.

### Agent: portal-layout

**Files:**
- `client-music-planner/app/templates/portal_base.html`
- `client-music-planner/app/templates/_portal_nav.html`
- `client-music-planner/app/static/css/portal.css`

**Responsibility:** Client-side base template, portal navigation, portal-specific CSS.

### Agent: dashboard

**Files:**
- `client-music-planner/app/dashboard/__init__.py`
- `client-music-planner/app/dashboard/routes.py`
- `client-music-planner/app/templates/dashboard/index.html`

**Responsibility:** Musician home page with event summaries, quick stats.

### Agent: api-playlist

**Files:**
- `client-music-planner/app/api_playlist/__init__.py`
- `client-music-planner/app/api_playlist/routes.py`

**Responsibility:** JSON endpoint for drag-and-drop reorder.

### Agent: api-filters

**Files:**
- `client-music-planner/app/api_filters/__init__.py`
- `client-music-planner/app/api_filters/routes.py`

**Responsibility:** JSON endpoint for AJAX song filtering.

### Agent: static-assets

**Files:**
- `client-music-planner/app/static/js/sortable.min.js`
- `client-music-planner/app/static/js/playlist.js`
- `client-music-planner/app/static/js/filters.js`
- `client-music-planner/app/static/js/flags.js`

**Responsibility:** SortableJS library bundle (v1.15.6), custom JavaScript for playlist drag-and-drop, AJAX filtering, and flag toggling.

**SortableJS configuration requirements:**
- `forceFallback: true` (consistent cross-browser drag behavior)
- `handle: '.drag-handle'` (prevents conflict with click-to-select actions)
- `dataIdAttr: 'data-item-id'` (toArray() reads playlist_item.id, not song_id)
- `ghostClass: 'playlist-ghost'`, `chosenClass: 'playlist-chosen'`, `dragClass: 'playlist-drag'`
- `animation: 200`, `fallbackTolerance: 3`
- Error recovery: snapshot `lastKnownOrder` before drag, call `sortable.sort(lastKnownOrder, true)` on server error
- Move up/down button handlers (`initMoveButtons()`) for keyboard accessibility (WCAG 2.5.7)
- ARIA live region announcements via `#sr-announcer`
- All fetch() calls include `'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content`

### Agent: tests

**Files:**
- `client-music-planner/tests/__init__.py`
- `client-music-planner/tests/conftest.py`
- `client-music-planner/tests/test_auth.py`
- `client-music-planner/tests/test_repertoire.py`
- `client-music-planner/tests/test_events.py`
- `client-music-planner/tests/test_portal.py`
- `client-music-planner/tests/test_api.py`

**Responsibility:** Pytest test suite covering auth, CRUD, portal access, API endpoints.

**IMPORTANT (FC9):** Test form submissions MUST use the exact field names from the Form Field Names sections above. Do not infer field names from descriptions.

### Agent: seed-data

**Files:**
- `client-music-planner/seed.py`

**Responsibility:** Sample data script: creates a demo musician, 30 songs across genres, 2 events with portal tokens, some playlist items and song requests.

## Template Requirements

### base.html (Musician Side)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>{% block title %}GigList{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    {% include '_navbar.html' %}
    <div class="container mt-4">
        {% include '_flash.html' %}
        {% block content %}{% endblock %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### portal_base.html (Client Side)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>{% block title %}{{ event.name }} - GigList{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/portal.css') }}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    {% include '_portal_nav.html' %}
    <div class="container mt-4">
        {% include '_flash.html' %}
        {% block content %}{% endblock %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### _portal_nav.html

Must include links to: Browse (`portal_browse.browse`), My Playlist (`portal_playlist.playlist`), Song Requests (`portal_requests.requests`), Approve (`portal_approve.approve`). All links pass `token=event.portal_token`. Show approval status badge if approved.

### Portal Security Notes
- Portal templates include `<meta name="referrer" content="no-referrer">` as belt-and-suspenders (global header covers most cases)
- External links in portal templates use `rel="noopener noreferrer"`
- Portal playlist template includes `<div id="sr-announcer" class="visually-hidden" aria-live="polite" aria-atomic="true"></div>` for screen reader announcements
- Playlist items include move up/down buttons (hidden behind `d-none` by default, visible for all users as WCAG 2.5.7 requires single-pointer alternative to drag)
- Drag handles use `class="drag-handle d-none"` -- shown only when SortableJS loads (progressive enhancement)
- Each playlist item uses `data-item-id="{{ item.id }}"` attribute (SortableJS reads this via `dataIdAttr`)
- Playlist container uses `data-token="{{ event.portal_token }}"` for JS to read

### Musician templates extend `base.html`. Portal templates extend `portal_base.html`.

## Acceptance Tests (EARS)

### Happy Path

- WHEN a musician registers with email/password/display_name THE SYSTEM SHALL create the account and redirect to /dashboard
- WHEN a musician logs in with valid credentials THE SYSTEM SHALL set session and redirect to /dashboard
- WHEN a musician creates a song with title/artist/genre/energy THE SYSTEM SHALL save it and redirect to repertoire index
- WHEN a musician uploads a valid CSV THE SYSTEM SHALL show preview with parsed songs and allow confirmation
- WHEN a musician confirms CSV import THE SYSTEM SHALL create all songs and show count in flash message
- WHEN a musician creates an event with name/date/client_name THE SYSTEM SHALL generate a portal_token and show the shareable link
- WHEN a client visits /portal/\<valid-token\> THE SYSTEM SHALL display the musician's repertoire
- WHEN a client clicks "Add to Playlist" on a song THE SYSTEM SHALL add it to the playlist at the next position
- WHEN a client drags a playlist item to a new position THE SYSTEM SHALL update all positions atomically via /api/playlist/reorder
- WHEN a client clicks "Must Play" on a playlist item THE SYSTEM SHALL toggle is_must_play and clear is_do_not_play
- WHEN a client submits a song request with title THE SYSTEM SHALL create a song_request row
- WHEN a client clicks "Approve" THE SYSTEM SHALL set client_approved=1 and approved_at timestamp
- WHEN a musician views event dashboard THE SYSTEM SHALL display all playlist items, flags, and song requests
- WHEN a musician exports a setlist as CSV THE SYSTEM SHALL return a downloadable file with song data ordered by position

### Error Cases

- WHEN a client visits /portal/\<invalid-token\> THE SYSTEM SHALL return 404
- WHEN a client tries to add a song to an approved event's playlist THE SYSTEM SHALL flash warning and redirect to browse
- WHEN a client submits reorder with mismatched item_ids length THE SYSTEM SHALL return 409 with "Playlist changed" message
- WHEN a musician tries to access another musician's event THE SYSTEM SHALL return 404
- WHEN a musician uploads a malformed CSV THE SYSTEM SHALL show error_rows with row numbers and error descriptions
- WHEN a client visits an archived event portal THE SYSTEM SHALL return 404

### Verification Commands

```bash
cd client-music-planner
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -v
```

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-05-19-client-music-planner-brainstorm.md](docs/brainstorms/2026-05-19-client-music-planner-brainstorm.md)
- Key decisions carried forward: token-based client access, SortableJS for DnD, separate song_request table, binary approval flow, 20-agent swarm

### Prior Build References

- Endpoint Registry pattern: docs/solutions/2026-05-19-solopreneur-command-center-swarm-build.md
- Cross-Boundary Wiring: docs/solutions/2026-05-19-invoice-crm-15-agent-swarm-build.md
- Parallel array desync: docs/solutions/2026-04-09-recipe-organizer-swarm-build.md
- Transaction boundary: docs/solutions/2026-05-13-workshop-registration-hub-swarm-build.md
- Template Render Context: docs/solutions/2026-04-07-flask-swarm-acid-test.md

## Feed-Forward

- **Hardest decision:** The token-based portal access pattern is novel for this repo. The `@require_portal_token` decorator sets `g.portal_event` and `g.portal_is_approved` -- all 6 portal blueprints depend on these exact variable names. A mismatch in any portal agent means silent failure.
- **Rejected alternatives:** PIN codes (guessable), magic links (email infra), OAuth for clients (overkill), flags in a separate table (unnecessary complexity).
- **Least confident:** The SortableJS -> /api/playlist/reorder -> batch UPDATE flow. Three things must align across 3 agents (static-assets, api-playlist, portal-playlist): the `data-item-id` attribute name in HTML, the `item_ids` JSON key in the POST body, and the `update_playlist_positions` function's parameter format. The Cross-Boundary Wiring section prescribes all three, but this is the most likely place for a mismatch.
