import os
from flask import Flask, g, redirect, url_for, session
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

SECRET_KEY_BLOCKLIST = ['dev-fallback', 'change-me', 'secret', '']


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    secret = os.environ.get('SECRET_KEY', 'dev-fallback')
    if secret in SECRET_KEY_BLOCKLIST and not app.debug:
        raise RuntimeError('Set a real SECRET_KEY in production')
    app.config['SECRET_KEY'] = secret
    app.config['DATABASE'] = os.path.join(app.instance_path, 'venueconnect.db')

    if app.debug or app.testing:
        app.config['WTF_CSRF_ENABLED'] = False

    csrf.init_app(app)
    limiter.init_app(app)

    from app.db import close_db, init_db_command
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    from app.filters import register_filters
    register_filters(app)

    # Register all 18 blueprints
    _register_blueprints(app)

    # Security headers
    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # CSRF error handler
    from flask_wtf.csrf import CSRFError
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask import request, jsonify
        if request.is_json:
            return jsonify(error='CSRF token missing or invalid'), 400
        from flask import flash
        flash('Form expired. Please try again.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    # Root route -- redirect by role
    @app.route('/')
    def index():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        role = session.get('role', 'musician')
        dashboard_map = {
            'venue_manager': 'dashboard_venue',
            'musician': 'dashboard_musician',
            'promoter': 'dashboard_promoter',
        }
        dashboard = dashboard_map.get(role, 'dashboard_musician')
        return redirect(url_for(f'{dashboard}.index'))

    @app.route('/health')
    def health():
        from flask import jsonify
        return jsonify(status='ok')

    return app


def _register_blueprints(app):
    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    from app.venues.routes import venues_bp
    app.register_blueprint(venues_bp, url_prefix='/venues')
    from app.rooms.routes import rooms_bp
    app.register_blueprint(rooms_bp, url_prefix='/rooms')
    from app.availability.routes import availability_bp
    app.register_blueprint(availability_bp, url_prefix='/availability')
    from app.booking_create.routes import booking_create_bp
    app.register_blueprint(booking_create_bp, url_prefix='/bookings')
    from app.booking_manage.routes import booking_manage_bp
    app.register_blueprint(booking_manage_bp, url_prefix='/manage')
    from app.events.routes import events_bp
    app.register_blueprint(events_bp, url_prefix='/events')
    from app.tickets.routes import tickets_bp
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    from app.settlements.routes import settlements_bp
    app.register_blueprint(settlements_bp, url_prefix='/settlements')
    from app.search.routes import search_bp
    app.register_blueprint(search_bp, url_prefix='/search')
    from app.notification_views.routes import notification_views_bp
    app.register_blueprint(notification_views_bp, url_prefix='/notifications')
    from app.analytics_venue.routes import analytics_venue_bp
    app.register_blueprint(analytics_venue_bp, url_prefix='/analytics/venue')
    from app.analytics_musician.routes import analytics_musician_bp
    app.register_blueprint(analytics_musician_bp, url_prefix='/analytics/musician')
    from app.analytics_promoter.routes import analytics_promoter_bp
    app.register_blueprint(analytics_promoter_bp, url_prefix='/analytics/promoter')
    from app.dashboard_venue.routes import dashboard_venue_bp
    app.register_blueprint(dashboard_venue_bp, url_prefix='/dashboard/venue')
    from app.dashboard_musician.routes import dashboard_musician_bp
    app.register_blueprint(dashboard_musician_bp, url_prefix='/dashboard/musician')
    from app.dashboard_promoter.routes import dashboard_promoter_bp
    app.register_blueprint(dashboard_promoter_bp, url_prefix='/dashboard/promoter')
