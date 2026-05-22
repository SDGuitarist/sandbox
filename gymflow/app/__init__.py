import os
from flask import Flask, jsonify
from flask_wtf import CSRFProtect

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key')
    if not app.debug and app.config['SECRET_KEY'] == 'dev-fallback-key':
        raise RuntimeError('SECRET_KEY must be set in production')
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

    from app.auth import ADMIN_PASSWORD
    if not app.debug and ADMIN_PASSWORD == 'dev-password-123':
        raise RuntimeError('ADMIN_PASSWORD must be set in production')

    # Health check route (no auth required)
    @app.route('/health')
    def health():
        return jsonify(status='ok')

    # Blueprint registration -- exact order
    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.dashboard.routes import bp as dashboard_bp
    from app.blueprints.members.routes import bp as members_bp
    from app.blueprints.trainers.routes import bp as trainers_bp
    from app.blueprints.membership_types.routes import bp as membership_types_bp
    from app.blueprints.class_types.routes import bp as class_types_bp
    from app.blueprints.schedules.routes import bp as schedules_bp
    from app.blueprints.attendance.routes import bp as attendance_bp
    from app.blueprints.equipment.routes import bp as equipment_bp
    from app.blueprints.maintenance.routes import bp as maintenance_bp
    from app.blueprints.billing.routes import bp as billing_bp
    from app.blueprints.payments.routes import bp as payments_bp
    from app.blueprints.assessments.routes import bp as assessments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(members_bp, url_prefix='/members')
    app.register_blueprint(trainers_bp, url_prefix='/trainers')
    app.register_blueprint(membership_types_bp, url_prefix='/membership-types')
    app.register_blueprint(class_types_bp, url_prefix='/class-types')
    app.register_blueprint(schedules_bp, url_prefix='/schedules')
    app.register_blueprint(attendance_bp, url_prefix='/attendance')
    app.register_blueprint(equipment_bp, url_prefix='/equipment')
    app.register_blueprint(maintenance_bp, url_prefix='/maintenance')
    app.register_blueprint(billing_bp, url_prefix='/billing')
    app.register_blueprint(payments_bp, url_prefix='/payments')
    app.register_blueprint(assessments_bp, url_prefix='/assessments')

    return app
