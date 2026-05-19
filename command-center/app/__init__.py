import os
import secrets
from flask import Flask
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(24))
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['DATABASE'] = os.path.join(app.instance_path, 'command_center.db')
    app.config['SCHEMA_PATH'] = os.path.join(os.path.dirname(__file__), 'schema.sql')

    os.makedirs(app.instance_path, exist_ok=True)

    csrf.init_app(app)

    from . import db
    db.init_app(app)
    db.init_db(app)

    from . import filters
    filters.init_app(app)

    # Register blueprints -- paths are RELATIVE to url_prefix
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .contacts import bp as contacts_bp
    app.register_blueprint(contacts_bp, url_prefix='/contacts')

    from .companies import bp as companies_bp
    app.register_blueprint(companies_bp, url_prefix='/companies')

    from .pipeline import bp as pipeline_bp
    app.register_blueprint(pipeline_bp, url_prefix='/pipeline')

    from .projects import bp as projects_bp
    app.register_blueprint(projects_bp, url_prefix='/projects')

    from .tasks import bp as tasks_bp
    app.register_blueprint(tasks_bp, url_prefix='/tasks')

    from .time_tracking import bp as time_bp
    app.register_blueprint(time_bp, url_prefix='/time')

    from .revenue import bp as revenue_bp
    app.register_blueprint(revenue_bp, url_prefix='/revenue')

    from .goals import bp as goals_bp
    app.register_blueprint(goals_bp, url_prefix='/goals')

    from .notes import bp as notes_bp
    app.register_blueprint(notes_bp, url_prefix='/notes')

    from .reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')

    from .search import bp as search_bp
    app.register_blueprint(search_bp, url_prefix='/search')

    from .settings import bp as settings_bp
    app.register_blueprint(settings_bp, url_prefix='/settings')

    from .dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

    # Root redirect
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('dashboard.index'))

    return app
