import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_wtf import CSRFProtect
from werkzeug.exceptions import HTTPException

csrf = CSRFProtect()


def create_app(db_path: str | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)

    # SECRET_KEY: fail-closed in production (no silent fallback)
    secret = os.environ.get("SECRET_KEY")
    if not secret:
        if app.debug:
            secret = "dev-only-not-for-production"
        else:
            raise RuntimeError("SECRET_KEY environment variable must be set")
    app.config["SECRET_KEY"] = secret

    app.config["DB_PATH"] = db_path or os.environ.get(
        "DB_PATH", str(Path(__file__).resolve().parent.parent / "habits.db")
    )

    # Disable CSRF token expiry. Default is 3600s (1 hour), which causes
    # 400 errors if a dashboard/calendar page is left open and toggled later.
    app.config["WTF_CSRF_TIME_LIMIT"] = None

    csrf.init_app(app)

    from app.db import init_db

    with app.app_context():
        init_db(app)

    from app.blueprints.habits import habits_bp

    app.register_blueprint(habits_bp)

    @app.route("/health")
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
