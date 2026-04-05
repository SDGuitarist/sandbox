from flask import Flask

from .db import init_db
from .routes import bp


def create_app(db_path=None, migrations_dir=None):
    app = Flask(__name__)
    if db_path:
        app.config["DB_PATH"] = db_path
    if migrations_dir:
        app.config["MIGRATIONS_DIR"] = migrations_dir
    with app.app_context():
        if db_path:
            init_db(path=db_path)
    app.register_blueprint(bp)
    return app
