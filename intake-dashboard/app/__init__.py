import os
from datetime import timedelta
from flask import Flask
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash

csrf = CSRFProtect()
limiter = Limiter(get_remote_address, storage_uri="memory://")


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.url_map.strict_slashes = False
    os.makedirs(app.instance_path, exist_ok=True)
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        raise RuntimeError("SECRET_KEY environment variable is required")
    app.config['SECRET_KEY'] = secret_key
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
    app.config['DATABASE'] = os.path.join(app.instance_path, 'intake.db')

    admin_password = os.environ.get('ADMIN_PASSWORD', '')
    if not admin_password:
        raise RuntimeError("ADMIN_PASSWORD environment variable is required")
    app.config['ADMIN_PASSWORD_HASH'] = generate_password_hash(admin_password)
    app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'admin')

    csrf.init_app(app)
    limiter.init_app(app)

    from app.db import close_db, init_db
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    from app.filters import register_filters
    register_filters(app)

    from app.auth import auth_bp
    from app.blueprints.intake.routes import intake_bp
    from app.blueprints.dashboard.routes import dashboard_bp
    from app.blueprints.submissions.routes import submissions_bp
    from app.blueprints.detail.routes import detail_bp
    from app.blueprints.status.routes import status_bp
    from app.blueprints.assessments.routes import assessments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(intake_bp, url_prefix='/intake')
    app.register_blueprint(dashboard_bp, url_prefix='/admin')
    app.register_blueprint(submissions_bp, url_prefix='/admin/submissions')
    app.register_blueprint(detail_bp, url_prefix='/admin/submissions')
    app.register_blueprint(status_bp, url_prefix='/admin/submissions')
    app.register_blueprint(assessments_bp, url_prefix='/admin/submissions')

    @app.route('/health')
    def health():
        return {'status': 'ok'}

    @app.after_request
    def add_security_headers(response):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    return app
