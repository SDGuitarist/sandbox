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

    @app.errorhandler(404)
    def page_not_found(e):
        from flask import render_template
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        from flask import render_template
        return render_template('500.html'), 500

    @app.context_processor
    def inject_globals():
        ctx = {}
        ctx['user'] = getattr(g, 'user', None)
        ctx['workspace'] = getattr(g, 'workspace', None)
        ctx['workspace_role'] = getattr(g, 'workspace_role', None)
        unread_count = 0
        if 'user_id' in session and 'workspace_id' in session:
            try:
                from app.db import get_db
                from app.models import get_unread_notifications
                conn = get_db()
                notifications = get_unread_notifications(conn, session['user_id'])
                unread_count = len(notifications)
            except Exception:
                pass
        ctx['unread_notification_count'] = unread_count
        return ctx

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
