import os, sqlite3
from flask import Flask, g

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('bookmarks.db')
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev')
    app.teardown_appcontext(close_db)
    from flask_wtf import CSRFProtect
    CSRFProtect(app)
    with app.app_context():
        db = get_db()
        with open('schema.sql') as f:
            db.executescript(f.read())
    from routes import bp
    app.register_blueprint(bp)
    return app

if __name__ == '__main__':
    create_app().run(debug=True)
