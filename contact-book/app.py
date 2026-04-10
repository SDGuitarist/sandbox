import os
import sqlite3
from flask import Flask, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('contacts.db')
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')
    app.teardown_appcontext(close_db)
    with app.app_context():
        from models import init_db
        init_db(get_db())
    from routes import bp
    app.register_blueprint(bp)
    return app


if __name__ == '__main__':
    create_app().run(debug=True)
