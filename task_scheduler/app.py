"""
Flask application factory for the distributed task scheduler.
"""
from flask import Flask
from db import init_db
from routes import bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(bp)
    return app


if __name__ == "__main__":
    init_db()
    app = create_app()
    app.run(port=5005, debug=False)
