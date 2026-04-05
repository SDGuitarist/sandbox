"""Flask application factory for the file upload service."""
import os
from flask import Flask, jsonify
from db import init_db
from routes import bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB
    app.register_blueprint(bp)

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "file too large (max 16 MB)"}), 413

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": str(e.description)}), 400

    return app


if __name__ == "__main__":
    init_db()
    app = create_app()
    app.run(port=5007, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
