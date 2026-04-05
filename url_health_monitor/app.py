"""Flask application factory for the URL health monitor."""
import os
from flask import Flask
from db import init_db
from routes import bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # 64 KB
    app.register_blueprint(bp)
    return app


if __name__ == "__main__":
    init_db()
    app = create_app()
    app.run(port=5006, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
