"""Application factory for Lesson-Studio Manager."""
import logging
import os
import secrets

from flask import Flask, current_app, g, request, session

from studio.database import init_db

logger = logging.getLogger(__name__)

_DEV_SECRET_KEY = "dev-insecure-key-not-for-production"

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _cents_filter(value):
    """Render integer cents as a dollar amount, e.g. 1250 -> $12.50."""
    if value is None:
        return ""
    cents = int(value)
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return "%s$%d.%02d" % (sign, cents // 100, cents % 100)


def _dt_filter(value):
    """Render an ISO-8601 timestamp for display."""
    if value is None:
        return ""
    text = str(value)
    return text.replace("T", " ")


def _get_csrf_token():
    """Return the per-session CSRF token, creating one if absent."""
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def create_app():
    app = Flask(__name__)

    flask_env = os.environ.get("FLASK_ENV")
    is_development = flask_env == "development"

    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        if is_development:
            logger.warning(
                "SECRET_KEY unset; using an insecure development key. "
                "Do NOT use this in production."
            )
            secret_key = _DEV_SECRET_KEY
        else:
            raise RuntimeError(
                "SECRET_KEY environment variable is required when "
                "FLASK_ENV != 'development'."
            )
    app.config["SECRET_KEY"] = secret_key

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = not is_development

    app.config["DATABASE"] = os.environ.get("DATABASE", "studio.db")

    app.jinja_env.filters["cents"] = _cents_filter
    app.jinja_env.filters["dt"] = _dt_filter

    from studio.auth import current_user

    @app.context_processor
    def inject_globals():
        return {"current_user": current_user(), "csrf_token": _get_csrf_token}

    app.jinja_env.globals["csrf_token"] = _get_csrf_token

    @app.before_request
    def validate_csrf():
        if request.method in _MUTATING_METHODS:
            expected = session.get("_csrf_token")
            supplied = request.form.get("_csrf")
            if not expected or not supplied or not secrets.compare_digest(
                str(expected), str(supplied)
            ):
                return "Invalid CSRF token", 400

    from studio.routes.dashboard import bp as dashboard_bp
    from studio.routes.auth import bp as auth_bp
    from studio.routes.students import bp as students_bp
    from studio.routes.instructors import bp as instructors_bp
    from studio.routes.rooms import bp as rooms_bp
    from studio.routes.instruments import bp as instruments_bp
    from studio.routes.courses import bp as courses_bp
    from studio.routes.enrollments import bp as enrollments_bp
    from studio.routes.lessons import bp as lessons_bp
    from studio.routes.attendance import bp as attendance_bp
    from studio.routes.invoices import bp as invoices_bp
    from studio.routes.practice import bp as practice_bp
    from studio.routes.announcements import bp as announcements_bp
    from studio.routes.search import bp as search_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(instructors_bp)
    app.register_blueprint(rooms_bp)
    app.register_blueprint(instruments_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(enrollments_bp)
    app.register_blueprint(lessons_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(practice_bp)
    app.register_blueprint(announcements_bp)
    app.register_blueprint(search_bp)

    if not os.path.exists(app.config["DATABASE"]):
        with app.app_context():
            init_db()

    return app
