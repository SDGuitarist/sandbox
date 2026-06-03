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

    # PROMPT_ENCRYPTION_KEY -- fail closed, validate format
    enc_key = os.environ.get('PROMPT_ENCRYPTION_KEY')
    if not enc_key:
        raise RuntimeError('PROMPT_ENCRYPTION_KEY environment variable is required')
    # Validate key is a valid Fernet key (base64-encoded 32 bytes)
    from cryptography.fernet import Fernet
    try:
        Fernet(enc_key.encode() if isinstance(enc_key, str) else enc_key)
    except (ValueError, Exception) as e:
        raise RuntimeError(f'PROMPT_ENCRYPTION_KEY is not a valid Fernet key: {e}')
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
