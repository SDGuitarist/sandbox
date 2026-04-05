"""Flask application factory for the API gateway."""
import os
from flask import Flask, jsonify
from db import init_db
from routes_admin import admin_bp, ADMIN_TOKEN
from routes_proxy import proxy_bp


def create_app() -> Flask:
    if not ADMIN_TOKEN:
        raise RuntimeError(
            "GATEWAY_ADMIN_TOKEN environment variable must be set before starting the server. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

    app.register_blueprint(admin_bp)
    app.register_blueprint(proxy_bp)

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": str(e.description)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "request body too large (max 10 MB)"}), 413

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": str(e.description)}), 401

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "internal server error"}), 500

    return app


if __name__ == "__main__":
    init_db()
    app = create_app()
    app.run(port=5008, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
