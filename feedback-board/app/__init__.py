import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

csrf = CSRFProtect()
limiter = Limiter(get_remote_address, default_limits=["60 per minute"])


def create_app(db_path: str | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)

    # SECRET_KEY: fail-closed in production
    secret = os.environ.get("SECRET_KEY")
    if not secret:
        if app.debug:
            secret = "dev-only-not-for-production"
        else:
            raise RuntimeError("SECRET_KEY environment variable must be set")
    app.config["SECRET_KEY"] = secret

    app.config["DB_PATH"] = db_path or os.environ.get(
        "DB_PATH", str(Path(__file__).resolve().parent.parent / "feedback.db")
    )

    # ADMIN_PASSWORD: reject weak defaults at startup
    admin_pw = os.environ.get("ADMIN_PASSWORD", "")
    if admin_pw and admin_pw in ("change-me", "changeme", "password", "admin"):
        raise RuntimeError("ADMIN_PASSWORD is too weak -- set a strong password")

    if os.environ.get("BEHIND_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

    csrf.init_app(app)
    limiter.init_app(app)

    from app.db import init_db

    with app.app_context():
        init_db(app)

    from app.blueprints.public import public_bp

    app.register_blueprint(public_bp)

    from app.blueprints.admin import admin_bp

    app.register_blueprint(admin_bp)

    @app.route("/health")
    @limiter.exempt
    def health():
        from app.db import get_db

        db_status = "connected"
        status_label = "ok"
        try:
            with get_db() as conn:
                conn.execute("SELECT 1")
        except Exception:
            db_status = "disconnected"
            status_label = "degraded"
        code = 200 if db_status == "connected" else 503
        return jsonify({"status": status_label, "db": db_status}), code

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return e
        app.logger.error(f"Unhandled exception: {e}", exc_info=True)
        return "Internal server error", 500

    return app
