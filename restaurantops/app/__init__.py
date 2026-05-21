import os
from flask import Flask, redirect, url_for, session
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

csrf = CSRFProtect()

SECRET_KEY_BLOCKLIST = ['dev-fallback-key', 'change-me', 'secret', '']
ADMIN_PASSWORD_BLOCKLIST = ['admin', 'password', '1234', '']

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key')
    app.config['DATABASE'] = os.path.join(app.instance_path, 'restaurant.db')
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = not app.debug

    if not app.debug and app.config['SECRET_KEY'] in SECRET_KEY_BLOCKLIST:
        raise RuntimeError('Set a strong SECRET_KEY environment variable for production.')

    admin_pw = os.environ.get('ADMIN_PASSWORD', 'admin')
    if not app.debug and admin_pw in ADMIN_PASSWORD_BLOCKLIST:
        raise RuntimeError('Set a strong ADMIN_PASSWORD environment variable for production.')

    csrf.init_app(app)

    from app.db import close_db, get_db
    app.teardown_appcontext(close_db)

    from app.filters import register_filters
    register_filters(app)

    @app.before_request
    def require_login():
        from flask import request
        allowed = ['/auth/login', '/static/', '/health']
        if any(request.path.startswith(p) for p in allowed):
            return
        if not session.get('authenticated'):
            return redirect(url_for('auth.login'))

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask import flash
        flash('Form expired. Please try again.', 'error')
        return redirect(url_for('dashboard.index'))

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' cdn.jsdelivr.net; "
            "style-src 'self' cdn.jsdelivr.net 'unsafe-inline'"
        )
        return response

    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.dashboard.routes import bp as dashboard_bp
    from app.blueprints.menu.routes import bp as menu_bp
    from app.blueprints.recipes.routes import bp as recipes_bp
    from app.blueprints.ingredients.routes import bp as ingredients_bp
    from app.blueprints.inventory.routes import bp as inventory_bp
    from app.blueprints.suppliers.routes import bp as suppliers_bp
    from app.blueprints.purchase_orders.routes import bp as po_bp
    from app.blueprints.orders.routes import bp as orders_bp
    from app.blueprints.tables.routes import bp as tables_bp
    from app.blueprints.reservations.routes import bp as reservations_bp
    from app.blueprints.staff.routes import bp as staff_bp
    from app.blueprints.specials.routes import bp as specials_bp
    from app.blueprints.reviews.routes import bp as reviews_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(menu_bp, url_prefix='/menu')
    app.register_blueprint(recipes_bp, url_prefix='/recipes')
    app.register_blueprint(ingredients_bp, url_prefix='/ingredients')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(suppliers_bp, url_prefix='/suppliers')
    app.register_blueprint(po_bp, url_prefix='/purchase-orders')
    app.register_blueprint(orders_bp, url_prefix='/orders')
    app.register_blueprint(tables_bp, url_prefix='/tables')
    app.register_blueprint(reservations_bp, url_prefix='/reservations')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    app.register_blueprint(specials_bp, url_prefix='/specials')
    app.register_blueprint(reviews_bp, url_prefix='/reviews')

    @app.route('/health')
    def health():
        return {'status': 'ok'}, 200

    return app
