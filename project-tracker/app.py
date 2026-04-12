import os
import sqlite3
from flask import Flask, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('project-tracker.db')
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def create_app():
    app = Flask(__name__)
    # WARNING: dev-only fallback. Set SECRET_KEY env var in production.
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')
    app.teardown_appcontext(close_db)

    from flask_wtf import CSRFProtect
    CSRFProtect(app)

    with app.app_context():
        db = get_db()
        with open('schema.sql') as f:
            db.executescript(f.read())

    from routes.tasks import bp as tasks_bp
    from routes.categories import bp as categories_bp
    from routes.members import bp as members_bp
    from routes.dashboard import bp as dashboard_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tasks_bp, url_prefix='/tasks')
    app.register_blueprint(categories_bp, url_prefix='/categories')
    app.register_blueprint(members_bp, url_prefix='/members')

    return app


if __name__ == '__main__':
    create_app().run(debug=True)
