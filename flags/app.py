from flask import Flask

from .db import init_db
from .routes import bp


def create_app(db_path=None):
    app = Flask(__name__)
    if db_path:
        app.config["DB_PATH"] = db_path
    with app.app_context():
        init_db(path=db_path)
    app.register_blueprint(bp)
    return app
