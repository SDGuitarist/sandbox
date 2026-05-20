import os
import secrets
from flask import Flask
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(24))
    app.config['DATABASE'] = os.path.join(app.instance_path, 'invoicecrm.db')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    os.makedirs(app.instance_path, exist_ok=True)

    csrf.init_app(app)

    from .db import close_db, init_db
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    from .helpers import register_filters
    register_filters(app)

    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .clients import bp as clients_bp
    app.register_blueprint(clients_bp, url_prefix='/clients')

    from .activities import bp as activities_bp
    app.register_blueprint(activities_bp, url_prefix='/clients')

    from .pipeline import bp as pipeline_bp
    app.register_blueprint(pipeline_bp, url_prefix='/pipeline')

    from .catalog import bp as catalog_bp
    app.register_blueprint(catalog_bp, url_prefix='/catalog')

    from .invoices import bp as invoices_bp
    app.register_blueprint(invoices_bp, url_prefix='/invoices')

    from .recurring import bp as recurring_bp
    app.register_blueprint(recurring_bp, url_prefix='/recurring')

    from .payments import bp as payments_bp
    app.register_blueprint(payments_bp, url_prefix='/payments')

    from .dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/')

    from .reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')

    from .settings_bp import bp as settings_bp
    app.register_blueprint(settings_bp, url_prefix='/settings')

    from .search import bp as search_bp
    app.register_blueprint(search_bp, url_prefix='/search')

    return app
