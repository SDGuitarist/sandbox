import os
from flask import Flask
from flask_wtf import CSRFProtect

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key')
    app.config['PERMANENT_SESSION_LIFETIME'] = 28800
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = not app.debug

    csrf.init_app(app)

    from app.db import init_app
    init_app(app)

    from app.filters import dollars, format_date
    app.jinja_env.filters['dollars'] = dollars
    app.jinja_env.filters['format_date'] = format_date

    from app.routes.auth_routes import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.recipe_routes import bp as recipe_bp
    app.register_blueprint(recipe_bp, url_prefix='/recipes')

    from app.routes.batch_routes import bp as batch_bp
    app.register_blueprint(batch_bp, url_prefix='/batches')

    from app.routes.ingredient_routes import bp as ingredient_bp
    app.register_blueprint(ingredient_bp, url_prefix='/ingredients')

    from app.routes.tank_routes import bp as tank_bp
    app.register_blueprint(tank_bp, url_prefix='/tanks')

    from app.routes.tap_routes import bp as tap_bp
    app.register_blueprint(tap_bp, url_prefix='/taps')

    from app.routes.sale_routes import bp as sale_bp
    app.register_blueprint(sale_bp, url_prefix='/sales')

    from app.routes.staff_routes import bp as staff_bp
    app.register_blueprint(staff_bp, url_prefix='/staff')

    from app.routes.dashboard_routes import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    @app.route('/health')
    def health():
        return {'status': 'ok'}

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    app.login_attempts = {'count': 0, 'first_attempt': 0.0}

    return app
