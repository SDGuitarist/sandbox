---
title: "feat: GigSheet -- Outreach + Booking Pipeline for Musicians"
type: feat
status: active
date: 2026-05-20
origin: docs/brainstorms/2026-05-20-gigsheet-brainstorm.md
swarm: true
agents: 31
run_id: "050"
feed_forward:
  risk: "6-agent email send chain (campaign-sender → job_queue → email-queue → sendgrid-client → delivery-webhooks → sse-events) is the longest cross-boundary data flow ever attempted. Transaction boundary mismatches or field name divergence at any link silently drops emails."
  verify_first: true
---

## Enhancement Summary

**Deepened on:** 2026-05-20
**Research agents used:** SSE best-practices, SQLite job queue best-practices, security-sentinel, architecture-strategist

### P1 Fixes Applied
1. Added `get_stage_counts()` and `remove_workspace_member()` model functions (architecture gap)
2. Prescribed `werkzeug.security.generate_password_hash(method='scrypt')` for auth (security gap)
3. Added `@csrf.exempt` + signature verification for webhook endpoint (security gap)
4. Added per-endpoint rate limits: login 5/min, register 3/min, upload 10/min (security gap)
5. Switched file upload to ALLOWLIST (not denylist) + Content-Disposition: attachment (security gap)
6. Fixed send_worker.py to use models functions via app context (architecture shadow-write)

### P2 Fixes Applied
7. SSE: single connection + heartbeat + 5-minute timeout + try/finally cleanup
8. Job queue: CTE+RETURNING atomic claim, PRAGMA busy_timeout=5000, signal handlers
9. HTML-escape merge field values with `markupsafe.escape()` (email injection prevention)
10. Added CSP header, CSV row limit (5000), CSV temp file cleanup

---

# GigSheet -- Shared Interface Spec

Outreach and booking pipeline platform for gigging musicians. Musicians
import leads, build email templates with merge fields, send batch campaigns,
track delivery, and manage a kanban pipeline from first contact through booking.

**Stack:** Flask + SQLite + Jinja2 + Bootstrap 5
**Agents:** 31 (vertical blueprint split)
**Origin:** [brainstorm](docs/brainstorms/2026-05-20-gigsheet-brainstorm.md)

---

## App Configuration

```python
# app/__init__.py (scaffold agent 1)
import os
from flask import Flask, g, redirect, url_for, session
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

SECRET_KEY_BLOCKLIST = ['dev-fallback', 'change-me', 'secret', '']

PIPELINE_STAGES = ['new', 'contacted', 'responded', 'interested', 'booking_requested', 'booked', 'declined']

WORKSPACE_ROLES = ['owner', 'admin', 'member']

PLAN_TIERS = {
    'solo':   {'price_cents': 2900,  'monthly_email_quota': 500},
    'pro':    {'price_cents': 5900,  'monthly_email_quota': 2000},
    'agency': {'price_cents': 9900,  'monthly_email_quota': 10000},
}

MERGE_FIELDS = ['venue_name', 'contact_name', 'capacity', 'location', 'genre', 'phone', 'website']

ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', '.docx', '.mp3', '.wav', '.zip'}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    secret = os.environ.get('SECRET_KEY', 'dev-fallback')
    if secret in SECRET_KEY_BLOCKLIST and not app.debug:
        raise RuntimeError('Set a real SECRET_KEY in production')
    app.config['SECRET_KEY'] = secret
    app.config['DATABASE'] = os.path.join(app.instance_path, 'gigsheet.db')
    app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, 'uploads')
    app.config['SENDGRID_MODE'] = os.environ.get('SENDGRID_MODE', 'mock')
    app.config['SENDGRID_API_KEY'] = os.environ.get('SENDGRID_API_KEY', '')
    app.config['SENDGRID_FROM_EMAIL'] = os.environ.get('SENDGRID_FROM_EMAIL', 'noreply@gigsheet.local')
    app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_BYTES

    csrf.init_app(app)
    limiter.init_app(app)

    from app.db import close_db, init_db_command
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    from app.filters import register_filters
    register_filters(app)

    _register_blueprints(app)

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
        return response

    from flask_wtf.csrf import CSRFError
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask import request, jsonify, flash
        if request.is_json:
            return jsonify(error='CSRF token missing or invalid'), 400
        flash('Form expired. Please try again.', 'error')
        return redirect(request.referrer or url_for('auth.login'))

    @app.route('/')
    def index():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if 'workspace_id' not in session:
            return redirect(url_for('auth.select_workspace'))
        return redirect(url_for('dashboard.index'))

    @app.route('/health')
    def health():
        from flask import jsonify
        return jsonify(status='ok')

    return app
```

**requirements.txt:**
```
flask>=3.0
flask-wtf>=1.2
flask-limiter>=3.5
werkzeug>=3.0
email-validator>=2.0
Pillow>=10.0
```

**filters.py** (scaffold agent 1):
```python
def register_filters(app):
    @app.template_filter('dollars')
    def dollars_filter(cents):
        if cents is None:
            return '$0.00'
        return f'${cents / 100:.2f}'

    @app.template_filter('stage_label')
    def stage_label_filter(stage):
        return stage.replace('_', ' ').title()
```

---

## Blueprint Registry

Every blueprint is registered in `_register_blueprints(app)` in `app/__init__.py`.
Route decorator paths are RELATIVE to the prefix (FC7 prevention).

| Blueprint Name | Variable | url_prefix | Agent |
|---------------|----------|------------|-------|
| main | (app routes) | / | scaffold (1) |
| auth | auth_bp | /auth | auth (2) |
| dashboard | dashboard_bp | /dashboard | scaffold (1) |
| lead_list | lead_list_bp | /leads | lead-list (5) |
| lead_detail | lead_detail_bp | /lead | lead-crud (6) |
| lead_import | lead_import_bp | /import | lead-import (7) |
| lead_tags | lead_tags_bp | /tags | lead-tags (8) |
| template_list | template_list_bp | /templates | template-list (9) |
| template_editor | template_editor_bp | /template | template-editor (10) |
| template_preview | template_preview_bp | /preview | template-preview (11) |
| campaign_list | campaign_list_bp | /campaigns | campaign-list (12) |
| campaign_editor | campaign_editor_bp | /campaign | campaign-editor (13) |
| campaign_sender | campaign_sender_bp | /send | campaign-sender (14) |
| campaign_scheduler | campaign_scheduler_bp | /schedule | campaign-scheduler (15) |
| delivery_webhooks | delivery_webhooks_bp | /webhooks | delivery-webhooks (16) |
| delivery_stats | delivery_stats_bp | /delivery | delivery-stats (17) |
| delivery_dashboard | delivery_dashboard_bp | /reports | delivery-dashboard (18) |
| pipeline_board | pipeline_board_bp | /pipeline | pipeline-board (19) |
| pipeline_actions | pipeline_actions_bp | /pipeline/actions | pipeline-actions (20) |
| pipeline_detail | pipeline_detail_bp | /pipeline/lead | pipeline-detail (21) |
| analytics_overview | analytics_overview_bp | /analytics | analytics-overview (22) |
| analytics_campaigns | analytics_campaigns_bp | /analytics/campaign | analytics-campaigns (23) |
| workspace_settings | workspace_settings_bp | /workspace | workspace-settings (24) |
| workspace_members | workspace_members_bp | /members | workspace-members (25) |
| file_uploads | file_uploads_bp | /files | file-uploads (28) |
| sse | sse_bp | /sse | sse-events (29) |

**Registration code** (in `_register_blueprints`):
```python
def _register_blueprints(app):
    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.dashboard.routes import dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

    from app.lead_list.routes import lead_list_bp
    app.register_blueprint(lead_list_bp, url_prefix='/leads')

    from app.lead_detail.routes import lead_detail_bp
    app.register_blueprint(lead_detail_bp, url_prefix='/lead')

    from app.lead_import.routes import lead_import_bp
    app.register_blueprint(lead_import_bp, url_prefix='/import')

    from app.lead_tags.routes import lead_tags_bp
    app.register_blueprint(lead_tags_bp, url_prefix='/tags')

    from app.template_list.routes import template_list_bp
    app.register_blueprint(template_list_bp, url_prefix='/templates')

    from app.template_editor.routes import template_editor_bp
    app.register_blueprint(template_editor_bp, url_prefix='/template')

    from app.template_preview.routes import template_preview_bp
    app.register_blueprint(template_preview_bp, url_prefix='/preview')

    from app.campaign_list.routes import campaign_list_bp
    app.register_blueprint(campaign_list_bp, url_prefix='/campaigns')

    from app.campaign_editor.routes import campaign_editor_bp
    app.register_blueprint(campaign_editor_bp, url_prefix='/campaign')

    from app.campaign_sender.routes import campaign_sender_bp
    app.register_blueprint(campaign_sender_bp, url_prefix='/send')

    from app.campaign_scheduler.routes import campaign_scheduler_bp
    app.register_blueprint(campaign_scheduler_bp, url_prefix='/schedule')

    from app.delivery_webhooks.routes import delivery_webhooks_bp
    app.register_blueprint(delivery_webhooks_bp, url_prefix='/webhooks')

    from app.delivery_stats.routes import delivery_stats_bp
    app.register_blueprint(delivery_stats_bp, url_prefix='/delivery')

    from app.delivery_dashboard.routes import delivery_dashboard_bp
    app.register_blueprint(delivery_dashboard_bp, url_prefix='/reports')

    from app.pipeline_board.routes import pipeline_board_bp
    app.register_blueprint(pipeline_board_bp, url_prefix='/pipeline')

    from app.pipeline_actions.routes import pipeline_actions_bp
    app.register_blueprint(pipeline_actions_bp, url_prefix='/pipeline/actions')

    from app.pipeline_detail.routes import pipeline_detail_bp
    app.register_blueprint(pipeline_detail_bp, url_prefix='/pipeline/lead')

    from app.analytics_overview.routes import analytics_overview_bp
    app.register_blueprint(analytics_overview_bp, url_prefix='/analytics')

    from app.analytics_campaigns.routes import analytics_campaigns_bp
    app.register_blueprint(analytics_campaigns_bp, url_prefix='/analytics/campaign')

    from app.workspace_settings.routes import workspace_settings_bp
    app.register_blueprint(workspace_settings_bp, url_prefix='/workspace')

    from app.workspace_members.routes import workspace_members_bp
    app.register_blueprint(workspace_members_bp, url_prefix='/members')

    from app.file_uploads.routes import file_uploads_bp
    app.register_blueprint(file_uploads_bp, url_prefix='/files')

    from app.sse.routes import sse_bp
    app.register_blueprint(sse_bp, url_prefix='/sse')
```

---

## Database Schema

```sql
-- app/schema.sql (models agent 3)

-- Users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Workspaces (multi-tenant)
CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_tier TEXT NOT NULL DEFAULT 'solo' CHECK (plan_tier IN ('solo', 'pro', 'agency')),
    monthly_email_quota INTEGER NOT NULL DEFAULT 500,
    emails_sent_this_month INTEGER NOT NULL DEFAULT 0,
    quota_reset_date TEXT NOT NULL DEFAULT (date('now', 'start of month', '+1 month')),
    from_email TEXT NOT NULL DEFAULT '',
    from_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_workspaces_owner ON workspaces(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_workspaces_slug ON workspaces(slug);

-- Workspace members (user-workspace join with roles)
CREATE TABLE IF NOT EXISTS workspace_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    invited_at TEXT NOT NULL DEFAULT (datetime('now')),
    joined_at TEXT,
    UNIQUE(workspace_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_wm_workspace ON workspace_members(workspace_id);
CREATE INDEX IF NOT EXISTS idx_wm_user ON workspace_members(user_id);

-- Leads (venue/promoter contacts)
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    email TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    venue_name TEXT NOT NULL DEFAULT '',
    capacity INTEGER NOT NULL DEFAULT 0,
    location TEXT NOT NULL DEFAULT '',
    genre_tags TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'csv', 'api')),
    pipeline_stage TEXT NOT NULL DEFAULT 'new' CHECK (pipeline_stage IN ('new', 'contacted', 'responded', 'interested', 'booking_requested', 'booked', 'declined')),
    notes TEXT NOT NULL DEFAULT '',
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_leads_workspace ON leads(workspace_id);
CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(workspace_id, pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(workspace_id, email);

-- Tags
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#6366f1',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(workspace_id, name)
);
CREATE INDEX IF NOT EXISTS idx_tags_workspace ON tags(workspace_id);

-- Lead-tag assignments (many-to-many)
CREATE TABLE IF NOT EXISTS lead_tags (
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (lead_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_lead_tags_tag ON lead_tags(tag_id);

-- Email templates
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    subject_line TEXT NOT NULL DEFAULT '',
    html_body TEXT NOT NULL DEFAULT '',
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_templates_workspace ON templates(workspace_id);

-- Campaigns
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'sending', 'sent', 'paused', 'cancelled')),
    total_recipients INTEGER NOT NULL DEFAULT 0,
    sent_count INTEGER NOT NULL DEFAULT 0,
    delivered_count INTEGER NOT NULL DEFAULT 0,
    opened_count INTEGER NOT NULL DEFAULT 0,
    clicked_count INTEGER NOT NULL DEFAULT 0,
    bounced_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    scheduled_at TEXT,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    started_at TEXT,
    completed_at TEXT,
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_campaigns_workspace ON campaigns(workspace_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(workspace_id, status);

-- Campaign recipients (which leads are in a campaign)
CREATE TABLE IF NOT EXISTS campaign_recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'delivered', 'opened', 'clicked', 'bounced', 'failed')),
    sent_at TEXT,
    message_id TEXT NOT NULL DEFAULT '',
    UNIQUE(campaign_id, lead_id)
);
CREATE INDEX IF NOT EXISTS idx_cr_campaign ON campaign_recipients(campaign_id);
CREATE INDEX IF NOT EXISTS idx_cr_lead ON campaign_recipients(lead_id);
CREATE INDEX IF NOT EXISTS idx_cr_message_id ON campaign_recipients(message_id);

-- Job queue (SQLite-backed async email sends)
CREATE TABLE IF NOT EXISTS job_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    recipient_id INTEGER NOT NULL REFERENCES campaign_recipients(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    worker_id TEXT NOT NULL DEFAULT '',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    scheduled_at TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at TEXT,
    completed_at TEXT,
    error_message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_jq_status ON job_queue(status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_jq_campaign ON job_queue(campaign_id);

-- Campaign progress (single row per campaign for SSE polling)
CREATE TABLE IF NOT EXISTS campaign_progress (
    campaign_id INTEGER PRIMARY KEY REFERENCES campaigns(id) ON DELETE CASCADE,
    total INTEGER NOT NULL DEFAULT 0,
    sent INTEGER NOT NULL DEFAULT 0,
    delivered INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'sending' CHECK (status IN ('sending', 'paused', 'completed')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Email events (delivery tracking from SendGrid webhooks)
CREATE TABLE IF NOT EXISTS email_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    recipient_id INTEGER REFERENCES campaign_recipients(id) ON DELETE SET NULL,
    message_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL CHECK (event_type IN ('delivered', 'opened', 'clicked', 'bounced', 'dropped', 'unsubscribed')),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    received_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ee_campaign ON email_events(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ee_message_id ON email_events(message_id);

-- Pipeline notes (notes on leads in pipeline context)
CREATE TABLE IF NOT EXISTS pipeline_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pn_lead ON pipeline_notes(lead_id);

-- Files (uploaded press kits, logos, EPKs)
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    filename_original TEXT NOT NULL,
    filename_stored TEXT NOT NULL,
    file_ext TEXT NOT NULL DEFAULT '',
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    uploaded_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_files_workspace ON files(workspace_id);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    link TEXT NOT NULL DEFAULT '',
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read);

-- Activity log (audit trail)
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT '',
    entity_id INTEGER,
    details TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_activity_workspace ON activity_log(workspace_id, created_at);

-- FTS5 for lead search
CREATE VIRTUAL TABLE IF NOT EXISTS leads_fts USING fts5(
    venue_name, contact_name, email, location, genre_tags,
    content='leads',
    content_rowid='id'
);

-- FTS5 sync triggers
CREATE TRIGGER IF NOT EXISTS leads_fts_insert AFTER INSERT ON leads BEGIN
    INSERT INTO leads_fts(rowid, venue_name, contact_name, email, location, genre_tags)
    VALUES (new.id, new.venue_name, new.contact_name, new.email, new.location, new.genre_tags);
END;

CREATE TRIGGER IF NOT EXISTS leads_fts_update AFTER UPDATE ON leads BEGIN
    DELETE FROM leads_fts WHERE rowid = old.id;
    INSERT INTO leads_fts(rowid, venue_name, contact_name, email, location, genre_tags)
    VALUES (new.id, new.venue_name, new.contact_name, new.email, new.location, new.genre_tags);
END;

CREATE TRIGGER IF NOT EXISTS leads_fts_delete AFTER DELETE ON leads BEGIN
    DELETE FROM leads_fts WHERE rowid = old.id;
END;
```

---

## Data Ownership

No two agents write to the same table. The "Owner Agent" column identifies
which agent contains the INSERT/UPDATE/DELETE operations for each table.

| Table | Owner Agent | Owner Module | Read By |
|-------|-----------|-------------|---------|
| users | models (3) | app.models | auth (2), decorators (4), all route agents |
| workspaces | models (3) | app.models | auth (2), workspace-settings (24), workspace-members (25), all route agents via g.workspace |
| workspace_members | models (3) | app.models | auth (2), workspace-members (25), decorators (4) |
| leads (INSERT) | models (3) | app.models | lead-crud (6), lead-import (7) call create_lead() |
| leads (UPDATE fields) | models (3) | app.models | lead-crud (6) calls update_lead() |
| leads (UPDATE pipeline_stage) | models (3) | app.models | pipeline-actions (20) calls update_lead_stage() |
| tags | models (3) | app.models | lead-tags (8) calls create_tag/delete_tag |
| lead_tags | models (3) | app.models | lead-tags (8), lead-import (7) call assign_tag/remove_tag |
| templates | models (3) | app.models | template-editor (10) calls create_template/update_template |
| campaigns (INSERT, field UPDATE) | models (3) | app.models | campaign-editor (13) calls create_campaign/update_campaign |
| campaigns (status UPDATE) | models (3) | app.models | campaign-sender (14), campaign-scheduler (15) call update_campaign_status() |
| campaigns (counter UPDATE) | models (3) | app.models | delivery-webhooks (16) calls increment_campaign_counter() |
| campaign_recipients | models (3) | app.models | campaign-editor (13) calls add_recipients(), delivery-webhooks (16) calls update_recipient_status() |
| job_queue (INSERT) | models (3) | app.models | campaign-sender (14) calls enqueue_send_jobs() |
| job_queue (UPDATE status) | email-queue (26) | app.email_queue | email-queue worker claims and updates |
| campaign_progress | email-queue (26) | app.email_queue | sse-events (29) reads, email-queue (26) writes |
| email_events | models (3) | app.models | delivery-webhooks (16) calls record_email_event() |
| pipeline_notes | models (3) | app.models | pipeline-actions (20) calls add_pipeline_note() |
| files | models (3) | app.models | file-uploads (28) calls create_file_record/delete_file_record |
| notifications | models (3) | app.models | multiple agents call create_notification() |
| activity_log | models (3) | app.models | multiple agents call log_activity() |
| leads_fts | triggers in schema.sql | auto-sync | lead-list (5) reads via FTS5 MATCH |

---

## Model Functions (app/models.py -- models agent 3)

### Database (app/db.py)

```python
import sqlite3
from flask import g, current_app
import click

def get_db():
    """Returns the request-scoped database connection.
    Usage:
        conn = get_db()
        leads = get_leads_by_workspace(conn, workspace_id)
    For atomic writes, start a transaction:
        conn = get_db()
        conn.execute('BEGIN IMMEDIATE')
        # ... operations ...
        conn.commit()
    NOTE: get_db() is NOT a context manager. Do NOT use `with`.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = get_db()
    with current_app.open_resource('schema.sql') as f:
        conn.executescript(f.read().decode('utf8'))

@click.command('init-db')
def init_db_command():
    init_db()
    click.echo('Initialized the database.')
```

### User Functions

```python
# Returns: int (the new user's ID)
# Usage:
#   user_id = create_user(conn, email, password_hash, display_name)
#   session['user_id'] = user_id
def create_user(conn, email: str, password_hash: str, display_name: str) -> int:
    cur = conn.execute(
        'INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)',
        (email, password_hash, display_name)
    )
    return cur.lastrowid

# Returns: sqlite3.Row or None
# Usage:
#   user = get_user_by_email(conn, email)
#   if user is None: flash('Invalid credentials', 'error')
def get_user_by_email(conn, email: str):
    return conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

# Returns: sqlite3.Row or None
# Usage:
#   user = get_user_by_id(conn, user_id)
#   if user is None: abort(404)
def get_user_by_id(conn, user_id: int):
    return conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
```

### Workspace Functions

```python
# Returns: int (the new workspace's ID)
# Usage:
#   workspace_id = create_workspace(conn, name, slug, owner_user_id)
#   add_workspace_member(conn, workspace_id, owner_user_id, 'owner')
# Does NOT commit -- caller commits after adding owner as member
def create_workspace(conn, name: str, slug: str, owner_user_id: int) -> int:
    cur = conn.execute(
        'INSERT INTO workspaces (name, slug, owner_user_id) VALUES (?, ?, ?)',
        (name, slug, owner_user_id)
    )
    return cur.lastrowid

# Returns: sqlite3.Row or None
def get_workspace_by_id(conn, workspace_id: int):
    return conn.execute('SELECT * FROM workspaces WHERE id = ?', (workspace_id,)).fetchone()

# Returns: list[sqlite3.Row]
# Usage:
#   workspaces = get_user_workspaces(conn, user_id)
#   for ws in workspaces: ...
def get_user_workspaces(conn, user_id: int):
    return conn.execute('''
        SELECT w.* FROM workspaces w
        JOIN workspace_members wm ON wm.workspace_id = w.id
        WHERE wm.user_id = ? AND wm.joined_at IS NOT NULL
        ORDER BY w.name
    ''', (user_id,)).fetchall()

# Returns: None
# Does NOT commit -- caller commits
def add_workspace_member(conn, workspace_id: int, user_id: int, role: str) -> None:
    conn.execute(
        'INSERT INTO workspace_members (workspace_id, user_id, role, joined_at) VALUES (?, ?, ?, datetime(\'now\'))',
        (workspace_id, user_id, role)
    )

# Returns: sqlite3.Row or None
def get_workspace_member(conn, workspace_id: int, user_id: int):
    return conn.execute(
        'SELECT * FROM workspace_members WHERE workspace_id = ? AND user_id = ?',
        (workspace_id, user_id)
    ).fetchone()

# Returns: list[sqlite3.Row]
def get_workspace_members(conn, workspace_id: int):
    return conn.execute('''
        SELECT wm.*, u.email, u.display_name FROM workspace_members wm
        JOIN users u ON u.id = wm.user_id
        WHERE wm.workspace_id = ? ORDER BY wm.role, u.display_name
    ''', (workspace_id,)).fetchall()
```

### Lead Functions

```python
# Returns: int (the new lead's ID)
# Does NOT commit -- caller commits
def create_lead(conn, workspace_id: int, email: str, contact_name: str,
                venue_name: str, capacity: int, location: str, genre_tags: str,
                phone: str, website: str, source: str, created_by_user_id: int) -> int:
    cur = conn.execute('''
        INSERT INTO leads (workspace_id, email, contact_name, venue_name, capacity,
            location, genre_tags, phone, website, source, created_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (workspace_id, email, contact_name, venue_name, capacity,
          location, genre_tags, phone, website, source, created_by_user_id))
    return cur.lastrowid

# Returns: sqlite3.Row or None
def get_lead(conn, lead_id: int):
    return conn.execute('SELECT * FROM leads WHERE id = ?', (lead_id,)).fetchone()

# Returns: list[sqlite3.Row]
# Paginated lead listing for a workspace with optional stage filter
def get_leads_by_workspace(conn, workspace_id: int, page: int = 1, per_page: int = 25,
                           stage: str = None, tag_id: int = None):
    query = 'SELECT l.* FROM leads l'
    params = []
    if tag_id:
        query += ' JOIN lead_tags lt ON lt.lead_id = l.id'
    query += ' WHERE l.workspace_id = ?'
    params.append(workspace_id)
    if stage:
        query += ' AND l.pipeline_stage = ?'
        params.append(stage)
    if tag_id:
        query += ' AND lt.tag_id = ?'
        params.append(tag_id)
    query += ' ORDER BY l.created_at DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    return conn.execute(query, params).fetchall()

# Returns: int (count)
def count_leads_by_workspace(conn, workspace_id: int, stage: str = None, tag_id: int = None) -> int:
    query = 'SELECT COUNT(*) FROM leads l'
    params = []
    if tag_id:
        query += ' JOIN lead_tags lt ON lt.lead_id = l.id'
    query += ' WHERE l.workspace_id = ?'
    params.append(workspace_id)
    if stage:
        query += ' AND l.pipeline_stage = ?'
        params.append(stage)
    if tag_id:
        query += ' AND lt.tag_id = ?'
        params.append(tag_id)
    return conn.execute(query, params).fetchone()[0]

# Returns: None
# Does NOT commit -- caller commits
def update_lead(conn, lead_id: int, **kwargs) -> None:
    allowed = {'email', 'contact_name', 'venue_name', 'capacity', 'location',
               'genre_tags', 'phone', 'website', 'notes'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    fields['updated_at'] = "datetime('now')"
    sets = ', '.join(f'{k} = ?' for k in fields if k != 'updated_at')
    sets += ", updated_at = datetime('now')"
    vals = [v for k, v in fields.items() if k != 'updated_at']
    vals.append(lead_id)
    conn.execute(f'UPDATE leads SET {sets} WHERE id = ?', vals)

# Returns: None
# Does NOT commit -- caller commits
def update_lead_stage(conn, lead_id: int, new_stage: str) -> None:
    conn.execute(
        "UPDATE leads SET pipeline_stage = ?, updated_at = datetime('now') WHERE id = ?",
        (new_stage, lead_id)
    )

# Returns: None
# Does NOT commit -- caller commits
def delete_lead(conn, lead_id: int) -> None:
    conn.execute('DELETE FROM leads WHERE id = ?', (lead_id,))

# FTS5 search -- sanitize input before MATCH (FC36 prevention)
# Returns: list[sqlite3.Row]
def search_leads(conn, workspace_id: int, query: str, limit: int = 50):
    import re
    cleaned = re.sub(r'[*"():^]', '', query).strip()
    if not cleaned:
        return []
    safe_query = f'"{cleaned}"'
    return conn.execute('''
        SELECT l.* FROM leads l
        JOIN leads_fts ON leads_fts.rowid = l.id
        WHERE l.workspace_id = ? AND leads_fts MATCH ?
        ORDER BY rank LIMIT ?
    ''', (workspace_id, safe_query, limit)).fetchall()

# Returns: list[sqlite3.Row] (leads grouped by pipeline_stage for kanban board)
def get_leads_by_stage(conn, workspace_id: int):
    return conn.execute('''
        SELECT * FROM leads WHERE workspace_id = ?
        ORDER BY pipeline_stage, updated_at DESC
    ''', (workspace_id,)).fetchall()
```

### Tag Functions

```python
# Returns: int (the new tag's ID)
# Does NOT commit
def create_tag(conn, workspace_id: int, name: str, color: str) -> int:
    cur = conn.execute(
        'INSERT INTO tags (workspace_id, name, color) VALUES (?, ?, ?)',
        (workspace_id, name, color)
    )
    return cur.lastrowid

# Returns: list[sqlite3.Row]
def get_tags_by_workspace(conn, workspace_id: int):
    return conn.execute('SELECT * FROM tags WHERE workspace_id = ? ORDER BY name', (workspace_id,)).fetchall()

# Returns: None -- Does NOT commit
def assign_tag(conn, lead_id: int, tag_id: int) -> None:
    conn.execute('INSERT OR IGNORE INTO lead_tags (lead_id, tag_id) VALUES (?, ?)', (lead_id, tag_id))

# Returns: None -- Does NOT commit
def remove_tag(conn, lead_id: int, tag_id: int) -> None:
    conn.execute('DELETE FROM lead_tags WHERE lead_id = ? AND tag_id = ?', (lead_id, tag_id))

# Returns: None -- Does NOT commit
def delete_tag(conn, tag_id: int) -> None:
    conn.execute('DELETE FROM tags WHERE id = ?', (tag_id,))

# Returns: list[sqlite3.Row] (tags for a specific lead)
def get_lead_tags(conn, lead_id: int):
    return conn.execute('''
        SELECT t.* FROM tags t
        JOIN lead_tags lt ON lt.tag_id = t.id
        WHERE lt.lead_id = ? ORDER BY t.name
    ''', (lead_id,)).fetchall()
```

### Template Functions

```python
# Returns: int (new template ID) -- Does NOT commit
def create_template(conn, workspace_id: int, name: str, subject_line: str,
                    html_body: str, created_by_user_id: int) -> int:
    cur = conn.execute('''
        INSERT INTO templates (workspace_id, name, subject_line, html_body, created_by_user_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (workspace_id, name, subject_line, html_body, created_by_user_id))
    return cur.lastrowid

# Returns: sqlite3.Row or None
def get_template(conn, template_id: int):
    return conn.execute('SELECT * FROM templates WHERE id = ?', (template_id,)).fetchone()

# Returns: list[sqlite3.Row]
def get_templates_by_workspace(conn, workspace_id: int):
    return conn.execute(
        'SELECT * FROM templates WHERE workspace_id = ? ORDER BY updated_at DESC',
        (workspace_id,)
    ).fetchall()

# Returns: None -- Does NOT commit
def update_template(conn, template_id: int, name: str, subject_line: str, html_body: str) -> None:
    conn.execute('''
        UPDATE templates SET name = ?, subject_line = ?, html_body = ?, updated_at = datetime('now')
        WHERE id = ?
    ''', (name, subject_line, html_body, template_id))

# Returns: None -- Does NOT commit
def delete_template(conn, template_id: int) -> None:
    conn.execute('DELETE FROM templates WHERE id = ?', (template_id,))

# Render template with merge fields replaced
# Returns: tuple(str, str) -- (rendered_subject, rendered_body)
def render_template_with_lead(template_row, lead_row) -> tuple:
    from markupsafe import escape
    subject = template_row['subject_line']
    body = template_row['html_body']
    replacements = {
        '{{venue_name}}': str(escape(lead_row['venue_name'] or '')),
        '{{contact_name}}': str(escape(lead_row['contact_name'] or '')),
        '{{capacity}}': str(lead_row['capacity']),
        '{{location}}': str(escape(lead_row['location'] or '')),
        '{{genre}}': str(escape(lead_row['genre_tags'] or '')),
        '{{phone}}': str(escape(lead_row['phone'] or '')),
        '{{website}}': str(escape(lead_row['website'] or '')),
    }
    for placeholder, value in replacements.items():
        subject = subject.replace(placeholder, value)
        body = body.replace(placeholder, value)
    return subject, body
```

### Campaign Functions

```python
# Returns: int (new campaign ID) -- Does NOT commit
def create_campaign(conn, workspace_id: int, name: str, template_id: int,
                    created_by_user_id: int) -> int:
    cur = conn.execute('''
        INSERT INTO campaigns (workspace_id, name, template_id, created_by_user_id)
        VALUES (?, ?, ?, ?)
    ''', (workspace_id, name, template_id, created_by_user_id))
    return cur.lastrowid

# Returns: sqlite3.Row or None
def get_campaign(conn, campaign_id: int):
    return conn.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,)).fetchone()

# Returns: list[sqlite3.Row]
def get_campaigns_by_workspace(conn, workspace_id: int, status: str = None):
    if status:
        return conn.execute(
            'SELECT * FROM campaigns WHERE workspace_id = ? AND status = ? ORDER BY created_at DESC',
            (workspace_id, status)
        ).fetchall()
    return conn.execute(
        'SELECT * FROM campaigns WHERE workspace_id = ? ORDER BY created_at DESC',
        (workspace_id,)
    ).fetchall()

# Returns: None -- Does NOT commit
def update_campaign(conn, campaign_id: int, **kwargs) -> None:
    allowed = {'name', 'template_id'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    sets = ', '.join(f'{k} = ?' for k in fields)
    sets += ", updated_at = datetime('now')"
    vals = list(fields.values())
    vals.append(campaign_id)
    conn.execute(f'UPDATE campaigns SET {sets} WHERE id = ?', vals)

# Returns: None -- COMMITS (independent status transition)
def update_campaign_status(conn, campaign_id: int, status: str) -> None:
    extra = ''
    if status == 'sending':
        extra = ", started_at = datetime('now')"
    elif status in ('sent', 'cancelled'):
        extra = ", completed_at = datetime('now')"
    conn.execute(f"UPDATE campaigns SET status = ?, updated_at = datetime('now'){extra} WHERE id = ?",
                 (status, campaign_id))
    conn.commit()

# Returns: None -- Does NOT commit
def add_recipients(conn, campaign_id: int, lead_ids: list) -> None:
    for lead_id in lead_ids:
        conn.execute(
            'INSERT OR IGNORE INTO campaign_recipients (campaign_id, lead_id) VALUES (?, ?)',
            (campaign_id, lead_id)
        )
    count = conn.execute(
        'SELECT COUNT(*) FROM campaign_recipients WHERE campaign_id = ?', (campaign_id,)
    ).fetchone()[0]
    conn.execute('UPDATE campaigns SET total_recipients = ? WHERE id = ?', (count, campaign_id))

# Returns: list[sqlite3.Row]
def get_campaign_recipients(conn, campaign_id: int):
    return conn.execute('''
        SELECT cr.*, l.email, l.contact_name, l.venue_name
        FROM campaign_recipients cr
        JOIN leads l ON l.id = cr.lead_id
        WHERE cr.campaign_id = ?
    ''', (campaign_id,)).fetchall()

# Returns: None -- Does NOT commit
def update_recipient_status(conn, recipient_id: int, status: str, message_id: str = None) -> None:
    if message_id:
        conn.execute(
            "UPDATE campaign_recipients SET status = ?, message_id = ?, sent_at = datetime('now') WHERE id = ?",
            (status, message_id, recipient_id)
        )
    else:
        conn.execute('UPDATE campaign_recipients SET status = ? WHERE id = ?', (status, recipient_id))

# Returns: None -- Does NOT commit
def increment_campaign_counter(conn, campaign_id: int, counter_name: str) -> None:
    allowed = {'sent_count', 'delivered_count', 'opened_count', 'clicked_count', 'bounced_count', 'failed_count'}
    if counter_name not in allowed:
        return
    conn.execute(f'UPDATE campaigns SET {counter_name} = {counter_name} + 1 WHERE id = ?', (campaign_id,))
```

### Job Queue Functions

```python
# Returns: None -- Does NOT commit (caller commits after enqueuing all jobs)
# Called by campaign-sender (14)
def enqueue_send_jobs(conn, campaign_id: int, scheduled_at: str = None) -> None:
    recipients = conn.execute(
        'SELECT id FROM campaign_recipients WHERE campaign_id = ? AND status = ?',
        (campaign_id, 'pending')
    ).fetchall()
    sched = scheduled_at or "datetime('now')"
    for r in recipients:
        conn.execute('''
            INSERT INTO job_queue (campaign_id, recipient_id, scheduled_at)
            VALUES (?, ?, ?)
        ''', (campaign_id, r['id'], sched if scheduled_at else conn.execute("SELECT datetime('now')").fetchone()[0]))

# Returns: sqlite3.Row or None (the claimed job)
# Called ONLY by email-queue worker (26)
# COMMITS after claim (independent transaction)
def claim_next_job(conn, worker_id: str):
    conn.execute('BEGIN IMMEDIATE')
    job = conn.execute('''
        SELECT id FROM job_queue
        WHERE status = 'pending' AND scheduled_at <= datetime('now')
        ORDER BY created_at LIMIT 1
    ''').fetchone()
    if job is None:
        conn.rollback()
        return None
    updated = conn.execute('''
        UPDATE job_queue SET status = 'running', worker_id = ?, claimed_at = datetime('now')
        WHERE id = ? AND status = 'pending'
    ''', (worker_id, job['id']))
    if updated.rowcount != 1:
        conn.rollback()
        return None
    conn.commit()
    return conn.execute('SELECT * FROM job_queue WHERE id = ?', (job['id'],)).fetchone()

# Returns: None -- COMMITS (each job completion is independent)
def complete_job(conn, job_id: int, success: bool, error_message: str = '') -> None:
    status = 'completed' if success else 'failed'
    conn.execute('''
        UPDATE job_queue SET status = ?, completed_at = datetime('now'), error_message = ?
        WHERE id = ?
    ''', (status, error_message, job_id))
    conn.commit()

# Reclaim timed-out jobs (claimed_at older than 5 minutes, still running)
# Returns: int (number of jobs reclaimed)
# COMMITS
def reclaim_timed_out_jobs(conn) -> int:
    cur = conn.execute('''
        UPDATE job_queue SET status = 'pending', claimed_at = NULL, worker_id = '',
            attempt_count = attempt_count + 1
        WHERE status = 'running' AND claimed_at < datetime('now', '-5 minutes')
            AND attempt_count + 1 < max_attempts
    ''')
    failed = conn.execute('''
        UPDATE job_queue SET status = 'failed', error_message = 'max attempts exceeded',
            completed_at = datetime('now')
        WHERE status = 'running' AND claimed_at < datetime('now', '-5 minutes')
            AND attempt_count + 1 >= max_attempts
    ''')
    conn.commit()
    return cur.rowcount + failed.rowcount
```

### Campaign Progress Functions

```python
# Returns: None -- COMMITS (called by email-queue worker after each job)
def update_campaign_progress(conn, campaign_id: int, sent_delta: int = 0,
                             delivered_delta: int = 0, failed_delta: int = 0) -> None:
    conn.execute('''
        INSERT INTO campaign_progress (campaign_id, total, sent, delivered, failed)
        VALUES (?, (SELECT total_recipients FROM campaigns WHERE id = ?), ?, ?, ?)
        ON CONFLICT(campaign_id) DO UPDATE SET
            sent = sent + excluded.sent,
            delivered = delivered + excluded.delivered,
            failed = failed + excluded.failed,
            updated_at = datetime('now')
    ''', (campaign_id, campaign_id, sent_delta, delivered_delta, failed_delta))
    # Check if campaign is complete
    progress = conn.execute('SELECT * FROM campaign_progress WHERE campaign_id = ?', (campaign_id,)).fetchone()
    if progress and (progress['sent'] + progress['failed']) >= progress['total']:
        conn.execute("UPDATE campaign_progress SET status = 'completed' WHERE campaign_id = ?", (campaign_id,))
        update_campaign_status(conn, campaign_id, 'sent')  # This also commits
    else:
        conn.commit()

# Returns: sqlite3.Row or None
def get_campaign_progress(conn, campaign_id: int):
    return conn.execute('SELECT * FROM campaign_progress WHERE campaign_id = ?', (campaign_id,)).fetchone()
```

### Email Event Functions

```python
# Returns: int (event ID) -- Does NOT commit
def record_email_event(conn, campaign_id: int, recipient_id: int,
                       message_id: str, event_type: str, metadata_json: str = '{}') -> int:
    cur = conn.execute('''
        INSERT INTO email_events (campaign_id, recipient_id, message_id, event_type, metadata_json)
        VALUES (?, ?, ?, ?, ?)
    ''', (campaign_id, recipient_id, message_id, event_type, metadata_json))
    return cur.lastrowid
```

### Pipeline Note Functions

```python
# Returns: int (note ID) -- Does NOT commit
def add_pipeline_note(conn, lead_id: int, user_id: int, content: str) -> int:
    cur = conn.execute(
        'INSERT INTO pipeline_notes (lead_id, user_id, content) VALUES (?, ?, ?)',
        (lead_id, user_id, content)
    )
    return cur.lastrowid

# Returns: list[sqlite3.Row]
def get_pipeline_notes(conn, lead_id: int):
    return conn.execute('''
        SELECT pn.*, u.display_name FROM pipeline_notes pn
        JOIN users u ON u.id = pn.user_id
        WHERE pn.lead_id = ? ORDER BY pn.created_at DESC
    ''', (lead_id,)).fetchall()
```

### File Functions

```python
# Returns: int (file ID) -- Does NOT commit
def create_file_record(conn, workspace_id: int, filename_original: str,
                       filename_stored: str, file_ext: str, file_size_bytes: int,
                       content_type: str, uploaded_by_user_id: int) -> int:
    cur = conn.execute('''
        INSERT INTO files (workspace_id, filename_original, filename_stored, file_ext,
            file_size_bytes, content_type, uploaded_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (workspace_id, filename_original, filename_stored, file_ext,
          file_size_bytes, content_type, uploaded_by_user_id))
    return cur.lastrowid

# Returns: sqlite3.Row or None
def get_file(conn, file_id: int):
    return conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()

# Returns: list[sqlite3.Row]
def get_files_by_workspace(conn, workspace_id: int):
    return conn.execute(
        'SELECT * FROM files WHERE workspace_id = ? ORDER BY created_at DESC',
        (workspace_id,)
    ).fetchall()

# Returns: None -- Does NOT commit
def delete_file_record(conn, file_id: int) -> None:
    conn.execute('DELETE FROM files WHERE id = ?', (file_id,))
```

### Workspace Member Management

```python
# Returns: None -- Does NOT commit
def remove_workspace_member(conn, workspace_id: int, user_id: int) -> None:
    conn.execute(
        'DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?',
        (workspace_id, user_id)
    )

# Returns: None -- Does NOT commit
def update_member_role(conn, workspace_id: int, user_id: int, role: str) -> None:
    conn.execute(
        'UPDATE workspace_members SET role = ? WHERE workspace_id = ? AND user_id = ?',
        (role, workspace_id, user_id)
    )
```

### Dashboard Stats

```python
# Returns: dict (stage -> count)
# Usage:
#   stage_counts = get_stage_counts(conn, workspace_id)
#   # stage_counts = {'new': 12, 'contacted': 5, ...}
def get_stage_counts(conn, workspace_id: int) -> dict:
    rows = conn.execute(
        'SELECT pipeline_stage, COUNT(*) as cnt FROM leads WHERE workspace_id = ? GROUP BY pipeline_stage',
        (workspace_id,)
    ).fetchall()
    return {row['pipeline_stage']: row['cnt'] for row in rows}
```

### Notification & Activity Functions

```python
# Returns: int (notification ID) -- Does NOT commit
def create_notification(conn, workspace_id: int, user_id: int, message: str, link: str = '') -> int:
    cur = conn.execute(
        'INSERT INTO notifications (workspace_id, user_id, message, link) VALUES (?, ?, ?, ?)',
        (workspace_id, user_id, message, link)
    )
    return cur.lastrowid

# Returns: list[sqlite3.Row]
def get_unread_notifications(conn, user_id: int, limit: int = 20):
    return conn.execute(
        'SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()

# Returns: None -- Does NOT commit
def mark_notification_read(conn, notification_id: int) -> None:
    conn.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notification_id,))

# Returns: None -- Does NOT commit
def log_activity(conn, workspace_id: int, user_id: int, action: str,
                 entity_type: str = '', entity_id: int = None, details: str = '') -> None:
    conn.execute('''
        INSERT INTO activity_log (workspace_id, user_id, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (workspace_id, user_id, action, entity_type, entity_id, details))
```

---

## Auth Prescriptions (auth agent 2)

**Password hashing (MANDATORY):**
```python
from werkzeug.security import generate_password_hash, check_password_hash

# Registration:
password_hash = generate_password_hash(password, method='scrypt')
user_id = create_user(conn, email, password_hash, display_name)

# Login:
user = get_user_by_email(conn, email)
if user is None or not check_password_hash(user['password_hash'], password):
    flash('Invalid credentials.', 'error')
    return redirect(url_for('auth.login'))
```

**Rate limits on auth routes:**
```python
from app import limiter

@auth_bp.route('/login', methods=['POST'])
@limiter.limit('5/minute')
def login_post(): ...

@auth_bp.route('/register', methods=['POST'])
@limiter.limit('3/minute')
def register_post(): ...
```

---

## Decorators (app/decorators.py -- decorators agent 4)

```python
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
```

**Decorator guard chain for ALL routes (FC27 prevention):**
```python
@bp.route('/some-route')
@login_required          # 1. Check user is logged in, set g.user
@require_workspace       # 2. Check workspace selected, set g.workspace, g.workspace_role
def some_route():
    conn = get_db()
    # 3. Workspace isolation: EVERY query includes workspace_id
    items = conn.execute('SELECT * FROM table WHERE workspace_id = ?',
                        (g.workspace['id'],)).fetchall()
    # 4. For detail/edit/delete: ownership check AFTER 404 check
    item = get_item(conn, item_id)
    if item is None:
        abort(404)
    if item['workspace_id'] != g.workspace['id']:
        abort(403)
    ...
```

---

## SendGrid Client (app/sendgrid_client.py -- sendgrid-client agent 27)

```python
import uuid
import json
from flask import current_app

def send_email(to_email: str, from_email: str, subject: str, html_body: str,
               tracking_id: str = '') -> dict:
    """Send an email via SendGrid or mock.
    Returns: {"status": "accepted", "message_id": "sg-xxx" or "mock-xxx"}
    Does NOT write to DB. Pure function.
    """
    mode = current_app.config.get('SENDGRID_MODE', 'mock')
    if mode == 'live':
        return _send_live(to_email, from_email, subject, html_body, tracking_id)
    return _send_mock(to_email, from_email, subject, html_body, tracking_id)

def _send_mock(to_email, from_email, subject, html_body, tracking_id):
    message_id = f'mock-{uuid.uuid4().hex[:12]}'
    current_app.logger.info(f'[MOCK SEND] to={to_email} subject={subject} id={message_id}')
    return {'status': 'accepted', 'message_id': message_id}

def _send_live(to_email, from_email, subject, html_body, tracking_id):
    import urllib.request
    api_key = current_app.config['SENDGRID_API_KEY']
    payload = json.dumps({
        'personalizations': [{'to': [{'email': to_email}]}],
        'from': {'email': from_email},
        'subject': subject,
        'content': [{'type': 'text/html', 'value': html_body}],
        'custom_args': {'tracking_id': tracking_id}
    }).encode()
    req = urllib.request.Request(
        'https://api.sendgrid.com/v3/mail/send',
        data=payload,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        message_id = resp.headers.get('X-Message-Id', f'sg-{uuid.uuid4().hex[:12]}')
        return {'status': 'accepted', 'message_id': message_id}
    except Exception as e:
        return {'status': 'failed', 'message_id': '', 'error': str(e)}
```

---

## Email Queue Worker (send_worker.py -- email-queue agent 26)

```python
"""
Email queue worker -- run separately from Flask app.
Usage: .venv/bin/python send_worker.py

Polls job_queue table every 2 seconds, claims pending jobs, sends via sendgrid_client.
"""
import os
import sys
import time
import uuid
import sqlite3

os.environ.setdefault('SECRET_KEY', 'worker-key')

WORKER_ID = f'worker-{uuid.uuid4().hex[:8]}'
POLL_INTERVAL = 2  # seconds
DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'gigsheet.db')

shutdown = False

def handle_signal(sig, frame):
    global shutdown
    shutdown = True

import signal
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

def get_worker_db():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn

def process_one_job(conn):
    """Claim and process one job. Returns True if a job was processed."""
    from app import create_app
    app = create_app()

    # Atomic claim using CTE+RETURNING (single statement)
    conn.execute('BEGIN IMMEDIATE')
    claimed = conn.execute('''
        WITH candidate AS (
            SELECT id FROM job_queue
            WHERE status = 'pending' AND scheduled_at <= datetime('now')
            ORDER BY created_at LIMIT 1
        )
        UPDATE job_queue SET status = 'running', worker_id = ?, claimed_at = datetime('now')
        WHERE id = (SELECT id FROM candidate) AND status = 'pending'
        RETURNING id
    ''', (WORKER_ID,)).fetchone()
    if claimed is None:
        conn.rollback()
        return False
    conn.commit()

    # Fetch full job + recipient + lead + template
    job_row = conn.execute('SELECT * FROM job_queue WHERE id = ?', (claimed['id'],)).fetchone()
    recipient = conn.execute('''
        SELECT cr.*, l.email, l.contact_name, l.venue_name, l.capacity,
               l.location, l.genre_tags, l.phone, l.website
        FROM campaign_recipients cr
        JOIN leads l ON l.id = cr.lead_id
        WHERE cr.id = ?
    ''', (job_row['recipient_id'],)).fetchone()

    campaign = conn.execute('SELECT * FROM campaigns WHERE id = ?', (job_row['campaign_id'],)).fetchone()
    template = conn.execute('SELECT * FROM templates WHERE id = ?', (campaign['template_id'],)).fetchone()

    # Render template
    from app.models import render_template_with_lead
    subject, body = render_template_with_lead(template, recipient)

    # Send via SendGrid client
    with app.app_context():
        from app.sendgrid_client import send_email
        from_email = app.config['SENDGRID_FROM_EMAIL']
        result = send_email(recipient['email'], from_email, subject, body, str(job_row['id']))

    # Update via models functions (NO shadow SQL -- use app context)
    success = result['status'] == 'accepted'
    error_msg = result.get('error', '')
    message_id = result.get('message_id', '')

    with app.app_context():
        from app.models import (update_recipient_status, increment_campaign_counter,
                                update_campaign_progress)
        from app.db import get_db
        db = get_db()

        # Update job status via models function (no shadow SQL)
        from app.models import complete_job
        complete_job(db, job_row['id'], success, error_msg)  # COMMITS independently

        # Update recipient + campaign counters via models
        if success:
            update_recipient_status(db, recipient['id'], 'sent', message_id)
            increment_campaign_counter(db, job_row['campaign_id'], 'sent_count')
        else:
            update_recipient_status(db, recipient['id'], 'failed')
            increment_campaign_counter(db, job_row['campaign_id'], 'failed_count')

        # Note: complete_job already committed. Now update counters + progress.
        sent_delta = 1 if success else 0
        failed_delta = 0 if success else 1
        update_campaign_progress(db, job_row['campaign_id'],
                                 sent_delta=sent_delta, failed_delta=failed_delta)
    return True

def reclaim_timed_out_jobs(conn):
    """Reclaim jobs stuck in 'running' for > 5 minutes."""
    conn.execute('''
        UPDATE job_queue SET status = 'pending', claimed_at = NULL, worker_id = '',
            attempt_count = attempt_count + 1
        WHERE status = 'running' AND claimed_at < datetime('now', '-5 minutes')
            AND attempt_count + 1 < max_attempts
    ''')
    conn.execute('''
        UPDATE job_queue SET status = 'failed', error_message = 'max attempts exceeded',
            completed_at = datetime('now')
        WHERE status = 'running' AND claimed_at < datetime('now', '-5 minutes')
            AND attempt_count + 1 >= max_attempts
    ''')
    conn.commit()

if __name__ == '__main__':
    print(f'[{WORKER_ID}] Starting email queue worker...')
    conn = get_worker_db()
    cycle = 0
    while not shutdown:
        try:
            processed = process_one_job(conn)
            if not processed:
                time.sleep(POLL_INTERVAL)
            cycle += 1
            if cycle % 30 == 0:  # Every ~60 seconds
                reclaim_timed_out_jobs(conn)
            if cycle % 150 == 0:  # Every ~5 minutes
                conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        except Exception as e:
            print(f'[{WORKER_ID}] Error: {e}')
            time.sleep(POLL_INTERVAL)
    print(f'[{WORKER_ID}] Shutting down gracefully.')
    conn.close()
```

---

## Route Table

| Method | Path | Blueprint.Handler | Status | Template / Response |
|--------|------|-------------------|--------|---------------------|
| GET | / | (app) index | 302 | redirect to dashboard or login |
| GET | /health | (app) health | 200 | JSON {"status":"ok"} |
| GET | /auth/login | auth.login | 200 | auth/login.html |
| POST | /auth/login | auth.login_post | 302 | redirect |
| GET | /auth/register | auth.register | 200 | auth/register.html |
| POST | /auth/register | auth.register_post | 302 | redirect |
| GET | /auth/logout | auth.logout | 302 | redirect |
| GET | /auth/workspaces | auth.select_workspace | 200 | auth/workspaces.html |
| POST | /auth/workspaces | auth.create_workspace | 302 | redirect |
| POST | /auth/workspaces/select | auth.set_workspace | 302 | redirect |
| GET | /dashboard/ | dashboard.index | 200 | dashboard/index.html |
| GET | /leads/ | lead_list.index | 200 | lead_list/index.html |
| GET | /lead/new | lead_detail.new | 200 | lead_detail/form.html |
| POST | /lead/new | lead_detail.create | 302 | redirect |
| GET | /lead/<id> | lead_detail.detail | 200 | lead_detail/detail.html |
| GET | /lead/<id>/edit | lead_detail.edit | 200 | lead_detail/form.html |
| POST | /lead/<id>/edit | lead_detail.update | 302 | redirect |
| POST | /lead/<id>/delete | lead_detail.delete | 302 | redirect |
| GET | /import/ | lead_import.index | 200 | lead_import/index.html |
| POST | /import/upload | lead_import.upload | 200 | lead_import/preview.html |
| POST | /import/commit | lead_import.commit | 302 | redirect |
| GET | /tags/ | lead_tags.index | 200 | lead_tags/index.html |
| POST | /tags/ | lead_tags.create | 302 | redirect |
| POST | /tags/<id>/delete | lead_tags.delete | 302 | redirect |
| POST | /tags/assign | lead_tags.assign | 302 | redirect (from lead detail) |
| POST | /tags/remove | lead_tags.remove | 302 | redirect (from lead detail) |
| GET | /templates/ | template_list.index | 200 | template_list/index.html |
| GET | /template/new | template_editor.new | 200 | template_editor/form.html |
| POST | /template/new | template_editor.create | 302 | redirect |
| GET | /template/<id> | template_editor.detail | 200 | template_editor/detail.html |
| GET | /template/<id>/edit | template_editor.edit | 200 | template_editor/form.html |
| POST | /template/<id>/edit | template_editor.update | 302 | redirect |
| POST | /template/<id>/delete | template_editor.delete | 302 | redirect |
| POST | /preview/render | template_preview.render | 200 | JSON rendered HTML |
| POST | /preview/send | template_preview.send_test | 200 | JSON result |
| GET | /campaigns/ | campaign_list.index | 200 | campaign_list/index.html |
| GET | /campaign/new | campaign_editor.new | 200 | campaign_editor/form.html |
| POST | /campaign/new | campaign_editor.create | 302 | redirect |
| GET | /campaign/<id> | campaign_editor.detail | 200 | campaign_editor/detail.html |
| GET | /campaign/<id>/edit | campaign_editor.edit | 200 | campaign_editor/form.html |
| POST | /campaign/<id>/edit | campaign_editor.update | 302 | redirect |
| POST | /campaign/<id>/delete | campaign_editor.delete | 302 | redirect |
| POST | /campaign/<id>/recipients | campaign_editor.manage_recipients | 302 | redirect |
| POST | /send/<id> | campaign_sender.send | 302 | redirect to send status |
| GET | /send/<id>/status | campaign_sender.status | 200 | campaign_sender/status.html |
| POST | /schedule/<id> | campaign_scheduler.set_schedule | 302 | redirect |
| GET | /schedule/<id> | campaign_scheduler.view | 200 | campaign_scheduler/view.html |
| POST | /schedule/<id>/cancel | campaign_scheduler.cancel | 302 | redirect |
| POST | /webhooks/sendgrid | delivery_webhooks.handle | 200 | JSON {"status":"ok"} (CSRF EXEMPT) |
| GET | /delivery/<id> | delivery_stats.detail | 200 | delivery_stats/detail.html |
| GET | /reports/ | delivery_dashboard.index | 200 | delivery_dashboard/index.html |
| GET | /reports/export | delivery_dashboard.export_csv | 200 | CSV file download |
| GET | /pipeline/ | pipeline_board.index | 200 | pipeline_board/index.html |
| POST | /pipeline/actions/move | pipeline_actions.move | 200 | JSON {"status":"ok"} |
| POST | /pipeline/actions/bulk | pipeline_actions.bulk_move | 200 | JSON |
| POST | /pipeline/actions/note | pipeline_actions.add_note | 302 | redirect |
| GET | /pipeline/lead/<id> | pipeline_detail.detail | 200 | pipeline_detail/detail.html |
| GET | /analytics/ | analytics_overview.index | 200 | analytics_overview/index.html |
| GET | /analytics/campaign/<id> | analytics_campaigns.detail | 200 | analytics_campaigns/detail.html |
| GET | /workspace/ | workspace_settings.index | 200 | workspace_settings/index.html |
| POST | /workspace/ | workspace_settings.update | 302 | redirect |
| GET | /members/ | workspace_members.index | 200 | workspace_members/index.html |
| POST | /members/invite | workspace_members.invite | 302 | redirect |
| POST | /members/<id>/remove | workspace_members.remove | 302 | redirect |
| POST | /members/<id>/role | workspace_members.change_role | 302 | redirect |
| POST | /files/upload | file_uploads.upload | 302 | redirect |
| GET | /files/ | file_uploads.index | 200 | file_uploads/index.html |
| GET | /files/<id> | file_uploads.serve | 200 | file content |
| POST | /files/<id>/delete | file_uploads.delete | 302 | redirect |
| GET | /sse/campaign/<id> | sse.campaign_progress | 200 | text/event-stream |

---

## Template Render Context

```python
# ALL templates receive these via base context (scaffold injects via context_processor):
# g.user, g.workspace, g.workspace_role, unread_notification_count

# dashboard/index.html
render_template('dashboard/index.html',
    total_leads=count_leads_by_workspace(conn, g.workspace['id']),
    active_campaigns=get_campaigns_by_workspace(conn, g.workspace['id'], status='sending'),
    recent_campaigns=get_campaigns_by_workspace(conn, g.workspace['id'])[:5],
    stage_counts=get_stage_counts(conn, g.workspace['id']),
)

# lead_list/index.html
render_template('lead_list/index.html',
    leads=leads,   # list[Row] from get_leads_by_workspace
    tags=tags,      # list[Row] from get_tags_by_workspace
    total=total,    # int from count_leads_by_workspace
    page=page,      # int
    per_page=per_page,  # int
    stage=stage,    # str or None (current filter)
    tag_id=tag_id,  # int or None (current filter)
    stages=PIPELINE_STAGES,  # list[str]
)

# lead_detail/detail.html
render_template('lead_detail/detail.html',
    lead=lead,      # Row from get_lead
    tags=lead_tags, # list[Row] from get_lead_tags
    all_tags=all_tags,  # list[Row] for tag assignment dropdown
    stages=PIPELINE_STAGES,
)

# lead_detail/form.html
render_template('lead_detail/form.html',
    lead=lead,  # Row or None (None for new)
    is_edit=True,  # bool
)

# lead_import/preview.html
render_template('lead_import/preview.html',
    preview_rows=preview_rows,  # list[dict] parsed from CSV
    filename=filename,          # str (temp file identifier)
    total_rows=total_rows,      # int
    error_rows=error_rows,      # list[dict] with validation errors
)

# template_editor/form.html
render_template('template_editor/form.html',
    template=template,  # Row or None
    is_edit=True,       # bool
    merge_fields=MERGE_FIELDS,  # list[str]
)

# campaign_editor/detail.html
render_template('campaign_editor/detail.html',
    campaign=campaign,          # Row
    template=template,          # Row (the linked template)
    recipients=recipients,      # list[Row] from get_campaign_recipients
    total_recipients=len(recipients),
    available_leads=available_leads,  # leads not yet in campaign
)

# campaign_sender/status.html
render_template('campaign_sender/status.html',
    campaign=campaign,  # Row
    progress=progress,  # Row from get_campaign_progress (or None)
)

# pipeline_board/index.html
render_template('pipeline_board/index.html',
    stages=PIPELINE_STAGES,
    leads_by_stage=leads_by_stage,  # dict[str, list[Row]]
)

# analytics_overview/index.html
render_template('analytics_overview/index.html',
    total_leads=total_leads,
    total_campaigns=total_campaigns,
    total_sent=total_sent,
    total_opened=total_opened,
    total_bounced=total_bounced,
    conversion_funnel=conversion_funnel,  # list[dict] with stage counts
    recent_campaigns=recent_campaigns,
)
```

---

## Export Names Table (FC1 Prevention)

Every exported function, route name, template path, CSS class, and JS function
that crosses agent boundaries. Use EXACT names -- no synonyms.

| Name | Type | Defined By | Used By |
|------|------|-----------|---------|
| get_db | function | models (3) | ALL route agents |
| get_user_by_id | function | models (3) | decorators (4), auth (2) |
| get_user_by_email | function | models (3) | auth (2) |
| create_user | function | models (3) | auth (2) |
| get_workspace_by_id | function | models (3) | decorators (4) |
| get_user_workspaces | function | models (3) | auth (2) |
| create_workspace | function | models (3) | auth (2) |
| add_workspace_member | function | models (3) | auth (2), workspace-members (25) |
| get_workspace_member | function | models (3) | decorators (4), workspace-members (25) |
| get_workspace_members | function | models (3) | workspace-members (25) |
| create_lead | function | models (3) | lead-crud (6), lead-import (7) |
| get_lead | function | models (3) | lead-crud (6), pipeline-detail (21), lead-tags (8) |
| get_leads_by_workspace | function | models (3) | lead-list (5) |
| count_leads_by_workspace | function | models (3) | lead-list (5), analytics-overview (22), dashboard (1) |
| update_lead | function | models (3) | lead-crud (6) |
| update_lead_stage | function | models (3) | pipeline-actions (20) |
| delete_lead | function | models (3) | lead-crud (6) |
| search_leads | function | models (3) | lead-list (5) |
| get_leads_by_stage | function | models (3) | pipeline-board (19) |
| create_tag | function | models (3) | lead-tags (8) |
| get_tags_by_workspace | function | models (3) | lead-tags (8), lead-list (5), lead-crud (6) |
| assign_tag | function | models (3) | lead-tags (8), lead-import (7) |
| remove_tag | function | models (3) | lead-tags (8) |
| delete_tag | function | models (3) | lead-tags (8) |
| get_lead_tags | function | models (3) | lead-crud (6), pipeline-detail (21) |
| create_template | function | models (3) | template-editor (10) |
| get_template | function | models (3) | template-editor (10), campaign-editor (13), template-preview (11) |
| get_templates_by_workspace | function | models (3) | template-list (9), campaign-editor (13) |
| update_template | function | models (3) | template-editor (10) |
| delete_template | function | models (3) | template-editor (10) |
| render_template_with_lead | function | models (3) | template-preview (11), email-queue (26) |
| create_campaign | function | models (3) | campaign-editor (13) |
| get_campaign | function | models (3) | campaign-editor (13), campaign-sender (14), campaign-scheduler (15), delivery-stats (17), analytics-campaigns (23) |
| get_campaigns_by_workspace | function | models (3) | campaign-list (12), analytics-overview (22), dashboard (1) |
| update_campaign | function | models (3) | campaign-editor (13) |
| update_campaign_status | function | models (3) | campaign-sender (14), campaign-scheduler (15), email-queue (26) |
| add_recipients | function | models (3) | campaign-editor (13) |
| get_campaign_recipients | function | models (3) | campaign-editor (13), delivery-stats (17) |
| update_recipient_status | function | models (3) | delivery-webhooks (16), email-queue (26) |
| complete_job | function | models (3) | email-queue (26) |
| increment_campaign_counter | function | models (3) | delivery-webhooks (16), email-queue (26) |
| enqueue_send_jobs | function | models (3) | campaign-sender (14) |
| get_campaign_progress | function | models (3) | sse-events (29), campaign-sender (14) |
| update_campaign_progress | function | models (3) | email-queue (26) |
| record_email_event | function | models (3) | delivery-webhooks (16) |
| add_pipeline_note | function | models (3) | pipeline-actions (20) |
| get_pipeline_notes | function | models (3) | pipeline-detail (21) |
| create_file_record | function | models (3) | file-uploads (28) |
| get_file | function | models (3) | file-uploads (28) |
| get_files_by_workspace | function | models (3) | file-uploads (28) |
| delete_file_record | function | models (3) | file-uploads (28) |
| create_notification | function | models (3) | campaign-sender (14), delivery-webhooks (16), workspace-members (25) |
| get_unread_notifications | function | models (3) | scaffold (1) context_processor |
| mark_notification_read | function | models (3) | scaffold (1) |
| log_activity | function | models (3) | ALL route agents that modify data |
| login_required | decorator | decorators (4) | ALL route agents |
| require_workspace | decorator | decorators (4) | ALL route agents except auth (2) |
| require_role | decorator | decorators (4) | workspace-settings (24), workspace-members (25) |
| get_stage_counts | function | models (3) | scaffold (1) dashboard |
| remove_workspace_member | function | models (3) | workspace-members (25) |
| update_member_role | function | models (3) | workspace-members (25) |
| send_email | function | sendgrid-client (27) | email-queue (26) |
| PIPELINE_STAGES | constant | scaffold (1) __init__.py | pipeline-board (19), pipeline-actions (20), lead-list (5), lead-crud (6) |
| MERGE_FIELDS | constant | scaffold (1) __init__.py | template-editor (10), template-preview (11) |
| ALLOWED_EXTENSIONS | constant | scaffold (1) __init__.py | file-uploads (28) |
| MAX_UPLOAD_BYTES | constant | scaffold (1) __init__.py | file-uploads (28) |

---

## Cross-Boundary Wiring Table (FC3 Prevention)

Every function call that crosses agent ownership boundaries.

| Caller Agent | Calls | Defined In Agent | Purpose |
|-------------|-------|-----------------|---------|
| auth (2) | create_user, get_user_by_email | models (3) | User registration/login |
| auth (2) | create_workspace, add_workspace_member, get_user_workspaces | models (3) | Workspace creation |
| lead-list (5) | get_leads_by_workspace, count_leads_by_workspace, search_leads, get_tags_by_workspace | models (3) | Lead listing |
| lead-crud (6) | create_lead, get_lead, update_lead, delete_lead, get_tags_by_workspace, get_lead_tags | models (3) | Lead CRUD |
| lead-import (7) | create_lead, assign_tag | models (3) | CSV import |
| lead-tags (8) | create_tag, delete_tag, assign_tag, remove_tag, get_tags_by_workspace, get_lead | models (3) | Tag management |
| template-editor (10) | create_template, get_template, update_template, delete_template | models (3) | Template CRUD |
| template-preview (11) | get_template, render_template_with_lead, get_lead | models (3) | Preview rendering |
| template-preview (11) | send_email | sendgrid-client (27) | Test send |
| campaign-editor (13) | create_campaign, get_campaign, update_campaign, add_recipients, get_campaign_recipients, get_templates_by_workspace, get_leads_by_workspace | models (3) | Campaign CRUD |
| campaign-sender (14) | get_campaign, enqueue_send_jobs, update_campaign_status, get_campaign_progress, create_notification | models (3) | Batch send |
| campaign-scheduler (15) | get_campaign, update_campaign_status | models (3) | Scheduling |
| delivery-webhooks (16) | record_email_event, update_recipient_status, increment_campaign_counter, create_notification | models (3) | Webhook processing |
| delivery-stats (17) | get_campaign, get_campaign_recipients | models (3) | Stats display |
| pipeline-board (19) | get_leads_by_stage | models (3) | Kanban display |
| pipeline-actions (20) | update_lead_stage, add_pipeline_note, get_lead, log_activity | models (3) | Stage moves |
| pipeline-detail (21) | get_lead, get_pipeline_notes, get_lead_tags | models (3) | Lead detail |
| analytics-overview (22) | count_leads_by_workspace, get_campaigns_by_workspace | models (3) | Stats |
| analytics-campaigns (23) | get_campaign, get_campaign_recipients | models (3) | Per-campaign stats |
| workspace-members (25) | add_workspace_member, get_workspace_members, remove_workspace_member, update_member_role, create_notification | models (3) | Member management |
| email-queue (26) | render_template_with_lead, update_campaign_progress, complete_job, update_recipient_status, increment_campaign_counter | models (3) | Job processing |
| email-queue (26) | send_email | sendgrid-client (27) | Email delivery |
| file-uploads (28) | create_file_record, get_file, get_files_by_workspace, delete_file_record | models (3) | File management |
| sse-events (29) | get_campaign_progress | models (3) | SSE polling |
| scaffold (1) | get_unread_notifications, mark_notification_read, count_leads_by_workspace, get_campaigns_by_workspace, get_stage_counts | models (3) | Dashboard + notification badge |
| template-list (9) | get_templates_by_workspace | models (3) | Template listing |
| campaign-list (12) | get_campaigns_by_workspace | models (3) | Campaign listing |
| ALL route agents | log_activity | models (3) | Audit trail |
| ALL route agents | login_required, require_workspace | decorators (4) | Auth guards |

---

## Coordinated Behaviors Table (FC5 + FC35 Prevention)

These behaviors MUST be identical across all agents. Copy the code block exactly.

### 1. Flash Messages

```python
# Success: green
flash('Lead created successfully.', 'success')
# Error: red
flash('Name is required.', 'error')
# Info: blue
flash('CSV imported: 42 leads added.', 'info')
# Warning: yellow
flash('3 rows skipped due to missing email.', 'warning')
```

**Template (in base.html):**
```html
{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}
<div class="flash-container">
    {% for category, message in messages %}
    <div class="alert alert-{{ category }}">{{ message }}</div>
    {% endfor %}
</div>
{% endif %}
{% endwith %}
```

### 2. Workspace Isolation (MANDATORY on every query)

```python
# EVERY query on tenant-scoped tables MUST include workspace_id
items = conn.execute(
    'SELECT * FROM leads WHERE workspace_id = ? AND ...',
    (g.workspace['id'], ...)
).fetchall()
```

Tables that REQUIRE workspace_id filter: leads, tags, lead_tags (via JOIN), templates, campaigns, campaign_recipients (via JOIN), files, notifications, activity_log, pipeline_notes (via JOIN on leads).

Tables that do NOT need workspace_id: users, workspaces, workspace_members (filtered by workspace_id in decorator).

### 3. Ownership Check on Detail/Edit/Delete (FC35)

```python
# After fetching a resource, verify it belongs to the current workspace
lead = get_lead(conn, lead_id)
if lead is None:
    abort(404)
if lead['workspace_id'] != g.workspace['id']:
    abort(403)
```

**This check is MANDATORY on every route that takes a resource ID parameter.**

### 4. Activity Logging

```python
# Log after every successful create/update/delete
from app.models import log_activity

log_activity(conn, g.workspace['id'], g.user['id'],
             'created_lead', 'lead', lead_id, f'Lead: {venue_name}')
# action values: created_lead, updated_lead, deleted_lead, imported_leads,
#   created_template, updated_template, deleted_template,
#   created_campaign, sent_campaign, scheduled_campaign, cancelled_campaign,
#   moved_lead_stage, added_note, uploaded_file, deleted_file,
#   invited_member, removed_member, changed_role, updated_workspace
```

### 5. CSRF in Forms

```html
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <!-- form fields -->
</form>
```

### 6. Pagination Pattern

```python
page = request.args.get('page', 1, type=int)
per_page = 25
items = get_leads_by_workspace(conn, g.workspace['id'], page=page, per_page=per_page)
total = count_leads_by_workspace(conn, g.workspace['id'])
total_pages = (total + per_page - 1) // per_page
```

### 7. Error Handling on Forms

```python
name = request.form.get('name', '').strip()[:100]
if not name:
    flash('Name is required.', 'error')
    return redirect(request.referrer or url_for('lead_list.index'))
```

### 8. Money Display

```python
# In templates: {{ amount_cents|dollars }}
# In forms: accept dollar input, convert to cents
cents = int(round(float(request.form.get('amount', '0')) * 100))
```

---

## Transaction Boundary Annotations (FC29 Prevention)

Functions that **COMMIT** (independent transactions):
- `update_campaign_status()` -- status transitions are atomic and final
- `claim_next_job()` in email-queue worker -- claim must be committed before processing
- `complete_job()` in email-queue worker -- each job completion is independent
- `reclaim_timed_out_jobs()` -- bulk reclaim is atomic
- `update_campaign_progress()` -- progress updates are independent of job completion

Functions that **DO NOT COMMIT** (caller commits):
- `create_lead()`, `update_lead()`, `delete_lead()`, `update_lead_stage()`
- `create_tag()`, `delete_tag()`, `assign_tag()`, `remove_tag()`
- `create_template()`, `update_template()`, `delete_template()`
- `create_campaign()`, `update_campaign()`, `add_recipients()`
- `enqueue_send_jobs()` -- caller commits after ALL jobs are enqueued
- `update_recipient_status()`
- `record_email_event()`
- `increment_campaign_counter()`
- `add_pipeline_note()`
- `create_file_record()`, `delete_file_record()`
- `create_notification()`
- `log_activity()`
- `create_workspace()`, `add_workspace_member()`
- `create_user()`

**Route handler commit pattern:**
```python
@bp.route('/create', methods=['POST'])
@login_required
@require_workspace
def create():
    conn = get_db()
    # ... validate input ...
    lead_id = create_lead(conn, ...)  # Does NOT commit
    log_activity(conn, ...)            # Does NOT commit
    conn.commit()                      # Single commit for the whole operation
    flash('Lead created.', 'success')
    return redirect(url_for('lead_detail.detail', id=lead_id))
```

---

## Form Field Names (FC9 Prevention)

Every POST route lists exact `request.form.get()` field names.

| Route | Method | Field Names |
|-------|--------|-------------|
| auth.login_post | POST | email, password |
| auth.register_post | POST | email, password, confirm_password, display_name |
| auth.create_workspace | POST | name |
| auth.set_workspace | POST | workspace_id |
| lead_detail.create | POST | email, contact_name, venue_name, capacity, location, genre_tags, phone, website, notes |
| lead_detail.update | POST | email, contact_name, venue_name, capacity, location, genre_tags, phone, website, notes |
| lead_import.upload | POST | csv_file (file), has_header (checkbox) |
| lead_import.commit | POST | filename, lead_ids[] (hidden, list) |
| lead_tags.create | POST | name, color |
| lead_tags.assign | POST | lead_id, tag_id |
| lead_tags.remove | POST | lead_id, tag_id |
| template_editor.create | POST | name, subject_line, html_body |
| template_editor.update | POST | name, subject_line, html_body |
| template_preview.render | POST (JSON) | template_id, lead_id |
| template_preview.send_test | POST (JSON) | template_id, to_email |
| campaign_editor.create | POST | name, template_id |
| campaign_editor.update | POST | name, template_id |
| campaign_editor.manage_recipients | POST | lead_ids[] (checkbox list) |
| campaign_sender.send | POST | (no fields -- campaign_id from URL) |
| campaign_scheduler.set_schedule | POST | scheduled_at, timezone |
| pipeline_actions.move | POST (JSON) | lead_id, stage |
| pipeline_actions.bulk_move | POST (JSON) | lead_ids (list), stage |
| pipeline_actions.add_note | POST | lead_id, content |
| workspace_settings.update | POST | name, from_email, from_name |
| workspace_members.invite | POST | email, role |
| workspace_members.change_role | POST | role |
| file_uploads.upload | POST | file (file) |

---

## Webhook Security (delivery-webhooks agent 16)

```python
# delivery_webhooks routes.py
from app import csrf

# CSRF MUST be exempted -- SendGrid cannot provide CSRF tokens
@delivery_webhooks_bp.before_request
def exempt_csrf():
    pass

# Apply exemption at blueprint level:
csrf.exempt(delivery_webhooks_bp)

# In mock mode, skip signature verification.
# In live mode, verify SendGrid webhook signature:
# pip install sendgrid (add to requirements.txt for live mode)
# from sendgrid.helpers.eventwebhook import EventWebhook, EventWebhookHeader
# public_key = app.config.get('SENDGRID_WEBHOOK_VERIFICATION_KEY', '')
# if public_key:
#     eh = EventWebhook(public_key)
#     signature = request.headers.get(EventWebhookHeader.SIGNATURE, '')
#     timestamp = request.headers.get(EventWebhookHeader.TIMESTAMP, '')
#     if not eh.verify_signature(request.data.decode(), signature, timestamp):
#         abort(403)
```

**Rate limit:** `@limiter.limit('100/minute')` on the webhook handler.

---

## File Upload Security (file-uploads agent 28)

```python
import os
import uuid
import unicodedata
from PIL import Image

# Set at module import level (NOT inside function) -- FC pitfall
Image.MAX_IMAGE_PIXELS = 50_000_000

ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', '.docx', '.mp3', '.wav', '.zip'}

def sanitize_filename(filename: str) -> str:
    """NFKC normalize, strip null bytes, cap length."""
    name = unicodedata.normalize('NFKC', filename)
    name = name.replace('\x00', '')
    name = os.path.basename(name)  # Strip path components
    return name[:200]

def allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS

# Serve with Content-Disposition: attachment to prevent browser execution
@file_uploads_bp.route('/<int:file_id>')
@login_required
@require_workspace
def serve(file_id):
    from flask import send_from_directory, g, abort
    f = get_file(get_db(), file_id)
    if f is None: abort(404)
    if f['workspace_id'] != g.workspace['id']: abort(403)
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(g.workspace['id']))
    return send_from_directory(upload_dir, f['filename_stored'],
                              as_attachment=True, download_name=f['filename_original'])
```

**Rate limit:** `@limiter.limit('10/minute')` on the upload handler.

---

## CSV Import Security (FC36 + formula injection)

```python
# In lead-import agent (7):
import csv
import re
import os
import uuid

FORMULA_CHARS = set('=-+@|')

def sanitize_csv_cell(value: str) -> str:
    """Prevent formula injection in CSV values."""
    if value and value[0] in FORMULA_CHARS:
        return "'" + value
    return value

def parse_csv_upload(file_storage, has_header: bool) -> tuple:
    """Parse uploaded CSV, return (preview_rows, error_rows, temp_filename).
    Saves raw CSV to temp file for commit step.
    """
    temp_name = f'import_{uuid.uuid4().hex[:12]}.csv'
    temp_path = os.path.join('/tmp', temp_name)
    file_storage.save(temp_path)

    preview_rows = []
    error_rows = []
    with open(temp_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f) if has_header else csv.reader(f)
        for i, row in enumerate(reader):
            if i >= 100:  # Preview limit (full import capped at MAX_CSV_ROWS=5000)
                break
            # Validate: email required
            email = (row.get('email', '') if has_header else (row[0] if len(row) > 0 else '')).strip()
            if not email or '@' not in email:
                error_rows.append({'row': i + 1, 'reason': 'Missing or invalid email', 'data': row})
                continue
            preview_rows.append(row)
    return preview_rows, error_rows, temp_name
```

---

## SSE Endpoint (sse-events agent 29)

```python
# app/sse/routes.py
import json
import time
from flask import Blueprint, Response, stream_with_context
from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import get_campaign, get_campaign_progress

sse_bp = Blueprint('sse', __name__)

@sse_bp.route('/campaign/<int:campaign_id>')
@login_required
@require_workspace
def campaign_progress(campaign_id):
    from flask import g
    conn = get_db()
    campaign = get_campaign(conn, campaign_id)
    if campaign is None or campaign['workspace_id'] != g.workspace['id']:
        return Response('Not found', status=404)

    def generate():
        import sqlite3
        from flask import current_app
        db_path = current_app.config['DATABASE']
        poll_conn = sqlite3.connect(db_path)
        poll_conn.row_factory = sqlite3.Row
        max_polls = 300  # 5-minute timeout (300 * 1s)
        poll_count = 0
        try:
            while poll_count < max_polls:
                progress = poll_conn.execute(
                    'SELECT * FROM campaign_progress WHERE campaign_id = ?',
                    (campaign_id,)
                ).fetchone()

                if progress:
                    data = json.dumps({
                        'total': progress['total'],
                        'sent': progress['sent'],
                        'delivered': progress['delivered'],
                        'failed': progress['failed'],
                        'status': progress['status'],
                    })
                    yield f'event: progress\ndata: {data}\n\n'
                    if progress['status'] == 'completed':
                        yield f'event: done\ndata: {{}}\n\n'
                        break
                else:
                    yield f'event: waiting\ndata: {{}}\n\n'

                poll_count += 1
                if poll_count % 15 == 0:
                    yield ': ping\n\n'  # heartbeat every 15s
                time.sleep(1)

            if poll_count >= max_polls:
                yield f'event: timeout\ndata: {{"message":"SSE timeout after 5 minutes"}}\n\n'
        except GeneratorExit:
            pass  # client disconnected
        finally:
            poll_conn.close()

    return stream_with_context(generate()), {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    }
```

**Client-side (in campaign_sender/status.html):**
```javascript
const source = new EventSource('/sse/campaign/{{ campaign.id }}');
source.addEventListener('progress', function(e) {
    const data = JSON.parse(e.data);
    document.getElementById('sent-count').textContent = data.sent;
    document.getElementById('failed-count').textContent = data.failed;
    const pct = Math.round((data.sent + data.failed) / data.total * 100);
    document.getElementById('progress-bar').style.width = pct + '%';
});
source.addEventListener('done', function(e) {
    source.close();
    document.getElementById('status-text').textContent = 'Campaign sent!';
});
```

---

## Swarm Agent Assignment

31 agents with strict file ownership. No file appears in two agents.

### Agent 1: scaffold
```
app/__init__.py
app/filters.py
app/static/style.css
app/static/app.js
app/templates/base.html
app/templates/404.html
app/templates/500.html
app/dashboard/__init__.py
app/dashboard/routes.py
app/templates/dashboard/index.html
requirements.txt
run.py
.gitignore
```

### Agent 2: auth
```
app/auth/__init__.py
app/auth/routes.py
app/templates/auth/login.html
app/templates/auth/register.html
app/templates/auth/workspaces.html
```

### Agent 3: models
```
app/db.py
app/models.py
app/schema.sql
```

### Agent 4: decorators
```
app/decorators.py
```

### Agent 5: lead-list
```
app/lead_list/__init__.py
app/lead_list/routes.py
app/templates/lead_list/index.html
```

### Agent 6: lead-crud
```
app/lead_detail/__init__.py
app/lead_detail/routes.py
app/templates/lead_detail/detail.html
app/templates/lead_detail/form.html
```

### Agent 7: lead-import
```
app/lead_import/__init__.py
app/lead_import/routes.py
app/templates/lead_import/index.html
app/templates/lead_import/preview.html
```

### Agent 8: lead-tags
```
app/lead_tags/__init__.py
app/lead_tags/routes.py
app/templates/lead_tags/index.html
```

### Agent 9: template-list
```
app/template_list/__init__.py
app/template_list/routes.py
app/templates/template_list/index.html
```

### Agent 10: template-editor
```
app/template_editor/__init__.py
app/template_editor/routes.py
app/templates/template_editor/detail.html
app/templates/template_editor/form.html
```

### Agent 11: template-preview
```
app/template_preview/__init__.py
app/template_preview/routes.py
```

### Agent 12: campaign-list
```
app/campaign_list/__init__.py
app/campaign_list/routes.py
app/templates/campaign_list/index.html
```

### Agent 13: campaign-editor
```
app/campaign_editor/__init__.py
app/campaign_editor/routes.py
app/templates/campaign_editor/detail.html
app/templates/campaign_editor/form.html
```

### Agent 14: campaign-sender
```
app/campaign_sender/__init__.py
app/campaign_sender/routes.py
app/templates/campaign_sender/status.html
```

### Agent 15: campaign-scheduler
```
app/campaign_scheduler/__init__.py
app/campaign_scheduler/routes.py
app/templates/campaign_scheduler/view.html
```

### Agent 16: delivery-webhooks
```
app/delivery_webhooks/__init__.py
app/delivery_webhooks/routes.py
```

### Agent 17: delivery-stats
```
app/delivery_stats/__init__.py
app/delivery_stats/routes.py
app/templates/delivery_stats/detail.html
```

### Agent 18: delivery-dashboard
```
app/delivery_dashboard/__init__.py
app/delivery_dashboard/routes.py
app/templates/delivery_dashboard/index.html
```

### Agent 19: pipeline-board
```
app/pipeline_board/__init__.py
app/pipeline_board/routes.py
app/templates/pipeline_board/index.html
```

### Agent 20: pipeline-actions
```
app/pipeline_actions/__init__.py
app/pipeline_actions/routes.py
```

### Agent 21: pipeline-detail
```
app/pipeline_detail/__init__.py
app/pipeline_detail/routes.py
app/templates/pipeline_detail/detail.html
```

### Agent 22: analytics-overview
```
app/analytics_overview/__init__.py
app/analytics_overview/routes.py
app/templates/analytics_overview/index.html
```

### Agent 23: analytics-campaigns
```
app/analytics_campaigns/__init__.py
app/analytics_campaigns/routes.py
app/templates/analytics_campaigns/detail.html
```

### Agent 24: workspace-settings
```
app/workspace_settings/__init__.py
app/workspace_settings/routes.py
app/templates/workspace_settings/index.html
```

### Agent 25: workspace-members
```
app/workspace_members/__init__.py
app/workspace_members/routes.py
app/templates/workspace_members/index.html
```

### Agent 26: email-queue
```
app/email_queue.py
send_worker.py
```

### Agent 27: sendgrid-client
```
app/sendgrid_client.py
```

### Agent 28: file-uploads
```
app/file_uploads/__init__.py
app/file_uploads/routes.py
app/templates/file_uploads/index.html
```

### Agent 29: sse-events
```
app/sse/__init__.py
app/sse/routes.py
```

### Agent 30: seed
```
seed.py
```

### Agent 31: tests
```
test_smoke.py
```

**Total files:** ~87

---

## Acceptance Tests (EARS Format)

### Happy Path
- WHEN a user registers with valid email and password THE SYSTEM SHALL create the user and redirect to workspace selection
- WHEN a user creates a workspace THE SYSTEM SHALL create the workspace with the user as owner and redirect to dashboard
- WHEN a user imports a CSV with 50 valid leads THE SYSTEM SHALL create 50 lead records with source='csv' and pipeline_stage='new'
- WHEN a user creates a campaign and clicks Send THE SYSTEM SHALL enqueue jobs for all recipients and show progress via SSE
- WHEN the email queue processes a job THE SYSTEM SHALL call send_email and update campaign_progress
- WHEN a user drags a lead to 'responded' on the pipeline board THE SYSTEM SHALL update the lead's pipeline_stage to 'responded'
- WHEN a user visits /analytics/ THE SYSTEM SHALL display total leads, campaigns, and conversion funnel

### Error Cases
- WHEN a user submits a login with wrong password THE SYSTEM SHALL return to login page with 'Invalid credentials' flash
- WHEN a user imports a CSV with missing email columns THE SYSTEM SHALL show preview with error_rows listing validation failures
- WHEN a non-member tries to access a workspace resource THE SYSTEM SHALL return 403
- WHEN a lead's workspace_id does not match g.workspace['id'] THE SYSTEM SHALL return 403 (IDOR prevention)
- WHEN a user uploads a file with .exe extension THE SYSTEM SHALL reject with 'File type not allowed' flash
- WHEN a user uploads a file > 10MB THE SYSTEM SHALL reject with 413 error

### Verification Commands
- `.venv/bin/python gigsheet/test_smoke.py` -- all smoke tests pass
- `curl -s http://localhost:5000/health | python3 -m json.tool` -- returns {"status": "ok"}

---

## Feed-Forward

- **Hardest decision:** Replacing Celery/Redis with SQLite job queue and SSE instead of WebSocket. Both simplify infrastructure but are untested in swarm builds. The job queue's atomic claim pattern must be implemented exactly or emails silently fail.
- **Rejected alternatives:** Celery+Redis (too much infrastructure risk), WebSocket via Flask-SocketIO (overkill for one-way updates), Jinja2 for email templates (security risk), customizable pipeline stages (scope creep).
- **Least confident:** The 6-agent email send chain (campaign-sender → job_queue → email-queue → sendgrid-client → delivery-webhooks → sse-events) is the longest cross-boundary data flow attempted. Every link must match field names exactly. Transaction boundaries are prescribed but have never been validated at this scale. The flow-trace reviewer MUST trace this chain end-to-end post-assembly.

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-05-20-gigsheet-brainstorm.md](docs/brainstorms/2026-05-20-gigsheet-brainstorm.md)
- **Spec template:** [docs/templates/shared-spec-flask.md](docs/templates/shared-spec-flask.md)
- **VenueConnect plan (25-agent precedent):** [docs/plans/2026-05-19-venueconnect-plan.md](docs/plans/2026-05-19-venueconnect-plan.md)
- **Job queue pattern:** [docs/solutions/2026-04-05-job-queue-system.md](docs/solutions/2026-04-05-job-queue-system.md)
- **File upload pattern:** [docs/solutions/2026-04-05-file-upload-service.md](docs/solutions/2026-04-05-file-upload-service.md)
- **Multi-tenant pattern:** [docs/solutions/2026-04-05-multi-tenant-api-gateway.md](docs/solutions/2026-04-05-multi-tenant-api-gateway.md)
- **Agent pitfalls:** [~/.claude/docs/agent-pitfalls.md](~/.claude/docs/agent-pitfalls.md) (37 failure classes)
