import os

from flask import Flask


def create_app():
    app = Flask(__name__, static_folder='../static')

    # DB at project root: cpaa-shadow-lab/instance/shadow_lab.db
    # app.root_path is always the app/ package dir, CWD-independent
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
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    return app
