import os
from flask import Flask, session, redirect, url_for
from flask_wtf import CSRFProtect

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # SECRET_KEY -- fail closed, never fall back to dev string
    secret = os.environ.get('SECRET_KEY')
    if not secret:
        raise RuntimeError('SECRET_KEY environment variable is required')
    app.config['SECRET_KEY'] = secret
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'

    # DATABASE override (smoke tests set DATABASE=:memory:) -- FC49
    app.config['DATABASE'] = os.environ.get('DATABASE', 'filmpm.db')

    csrf.init_app(app)

    # Security headers
    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:;"
        )
        return response

    # Database
    from app.database import init_app
    init_app(app)

    # Blueprint registration -- exact order
    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.projects.routes import bp as projects_bp
    from app.blueprints.scenes.routes import bp as scenes_bp
    from app.blueprints.cast.routes import bp as cast_bp
    from app.blueprints.crew.routes import bp as crew_bp
    from app.blueprints.departments.routes import bp as departments_bp
    from app.blueprints.locations.routes import bp as locations_bp
    from app.blueprints.schedule.routes import bp as schedule_bp
    from app.blueprints.callsheets.routes import bp as callsheets_bp
    from app.blueprints.budget.routes import bp as budget_bp
    from app.blueprints.expenses.routes import bp as expenses_bp
    from app.blueprints.reports.routes import bp as reports_bp
    from app.blueprints.search.routes import bp as search_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(scenes_bp, url_prefix='/scenes')
    app.register_blueprint(cast_bp, url_prefix='/cast')
    app.register_blueprint(crew_bp, url_prefix='/crew')
    app.register_blueprint(departments_bp, url_prefix='/departments')
    app.register_blueprint(locations_bp, url_prefix='/locations')
    app.register_blueprint(schedule_bp, url_prefix='/schedule')
    app.register_blueprint(callsheets_bp, url_prefix='/call-sheets')
    app.register_blueprint(budget_bp, url_prefix='/budget')
    app.register_blueprint(expenses_bp, url_prefix='/expenses')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(search_bp, url_prefix='/search')

    # Dashboard route on root -- simple redirect, auth checked at destination
    @app.route('/')
    def index():
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        from app.database import get_db
        from app.models.project_models import get_active_project
        conn = get_db()
        project = get_active_project(conn)
        if project is None:
            return redirect(url_for('projects.new'))
        return redirect(url_for('projects.dashboard', project_id=project['id']))

    # Template filters
    @app.template_filter('dollars')
    def dollars_filter(cents):
        """Convert integer cents to dollar string: 150000 -> '$1,500.00'"""
        if cents is None:
            return '$0.00'
        return f'${cents / 100:,.2f}'

    @app.template_filter('page_count')
    def page_count_filter(eighths):
        """Convert 1/8th page count to display: 12 -> '1 4/8'"""
        if eighths is None:
            return '0'
        whole = eighths // 8
        remainder = eighths % 8
        if remainder == 0:
            return str(whole)
        if whole == 0:
            return f'{remainder}/8'
        return f'{whole} {remainder}/8'

    return app
