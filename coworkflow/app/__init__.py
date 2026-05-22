import os
from flask import Flask
from flask_wtf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key')
    if not app.debug and app.config['SECRET_KEY'] == 'dev-fallback-key':
        raise RuntimeError('SECRET_KEY must be set in production')

    from app.auth import ADMIN_PASSWORD
    if not app.debug and ADMIN_PASSWORD == 'dev-password-123':
        raise RuntimeError('ADMIN_PASSWORD must be set in production')

    app.config['SESSION_COOKIE_SECURE'] = not app.debug
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    csrf.init_app(app)

    from app.db import init_db, close_db
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    from app.filters import register_filters
    register_filters(app)

    # Blueprint registration -- exact order
    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.dashboard.routes import bp as dashboard_bp
    from app.blueprints.members.routes import bp as members_bp
    from app.blueprints.plans.routes import bp as plans_bp
    from app.blueprints.desks.routes import bp as desks_bp
    from app.blueprints.rooms.routes import bp as rooms_bp
    from app.blueprints.desk_bookings.routes import bp as desk_bookings_bp
    from app.blueprints.room_bookings.routes import bp as room_bookings_bp
    from app.blueprints.billing.routes import bp as billing_bp
    from app.blueprints.payments.routes import bp as payments_bp
    from app.blueprints.amenities.routes import bp as amenities_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(members_bp, url_prefix='/members')
    app.register_blueprint(plans_bp, url_prefix='/plans')
    app.register_blueprint(desks_bp, url_prefix='/desks')
    app.register_blueprint(rooms_bp, url_prefix='/rooms')
    app.register_blueprint(desk_bookings_bp, url_prefix='/desk-bookings')
    app.register_blueprint(room_bookings_bp, url_prefix='/room-bookings')
    app.register_blueprint(billing_bp, url_prefix='/billing')
    app.register_blueprint(payments_bp, url_prefix='/payments')
    app.register_blueprint(amenities_bp, url_prefix='/amenities')

    return app
