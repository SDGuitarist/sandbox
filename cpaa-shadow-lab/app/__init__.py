import os

from flask import Flask


def create_app():
    app = Flask(__name__)

    # DB lives at project root: cpaa-shadow-lab/instance/shadow_lab.db
    # (matches where generate_scenario.py writes)
    project_root = os.path.dirname(app.root_path)
    instance_dir = os.path.join(project_root, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    app.config['DATABASE'] = os.path.join(instance_dir, 'shadow_lab.db')

    from app.db import close_db, init_db
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    from app.blueprints.dashboard.routes import dashboard_bp
    app.register_blueprint(dashboard_bp)

    @app.after_request
    def set_security_headers(response):
        response.headers['Content-Security-Policy'] = "default-src 'self'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    return app
