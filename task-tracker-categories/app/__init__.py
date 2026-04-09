import os

from flask import Flask
from flask_wtf import CSRFProtect
from app.db import init_db

csrf = CSRFProtect()


def create_app(db_path=None):
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-task-tracker')

    if db_path:
        app.config['DB_PATH'] = db_path
    else:
        app.config['DB_PATH'] = 'task_tracker_categories.db'

    csrf.init_app(app)

    with app.app_context():
        init_db(app)

    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.projects import projects_bp
    from app.blueprints.tasks import tasks_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(tasks_bp)

    return app
