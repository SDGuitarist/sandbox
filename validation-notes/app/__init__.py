"""Application factory for the Snippets CRUD app."""

import os

from flask import Flask

from app.db import get_db
from app.models import init_db
from app.snippets.routes import snippets_bp


def create_app() -> Flask:
    """Create, configure, and return the Flask application."""
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-snippets-079")

    # Initialize the database schema once at startup. get_db() returns a plain
    # connection (not a context manager); init_db commits internally.
    conn = get_db()
    try:
        init_db(conn)
    finally:
        conn.close()

    app.register_blueprint(snippets_bp)

    return app
