import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(get_remote_address, default_limits=["60 per minute"])


def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-fallback-key")

    from app.db import init_db
    init_db()

    limiter.init_app(app)

    try:
        from app.registration.routes import registration_bp
        app.register_blueprint(registration_bp)
    except ImportError:
        logger.warning("registration blueprint not available")

    try:
        from app.payments.routes import payments_bp
        app.register_blueprint(payments_bp)
    except ImportError:
        logger.warning("payments blueprint not available")

    try:
        from app.waitlist.routes import waitlist_bp
        app.register_blueprint(waitlist_bp)
    except ImportError:
        logger.warning("waitlist blueprint not available")

    try:
        from app.admin.routes import admin_bp
        app.register_blueprint(admin_bp)
    except ImportError:
        logger.warning("admin blueprint not available")

    try:
        from app.scheduler.jobs import register_commands
        register_commands(app)
    except ImportError:
        logger.warning("scheduler commands not available")

    @app.route("/api/health", methods=["GET"])
    def health():
        from app.db import get_db
        db_status = "connected"
        try:
            with get_db() as conn:
                conn.execute("SELECT 1")
        except Exception:
            db_status = "disconnected"

        supabase_status = "disconnected"
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if supabase_url and supabase_key:
            supabase_status = "connected"

        return jsonify({"status": "ok", "db": db_status, "supabase": supabase_status})

    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "code": "INTERNAL_ERROR"}), 500

    return app
