import os
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object('app.config.Config')
    app.config['DATABASE'] = os.path.join(app.instance_path, 'music_planner.db')
    os.makedirs(app.instance_path, exist_ok=True)

    csrf.init_app(app)
    limiter.init_app(app)

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

    @app.after_request
    def set_security_headers(response):
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    from flask_wtf.csrf import CSRFError
    from flask import flash, redirect

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
