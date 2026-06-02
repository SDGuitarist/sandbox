import os
from flask import Flask
from flask_wtf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']  # NO fallback (FC10)
    # NOTE: ANTHROPIC_API_KEY is NOT stored in app.config (visible in debugger).
    # Testing routes read it directly from os.environ.

    csrf.init_app(app)

    from .database import init_db, close_db
    init_db()
    app.teardown_appcontext(close_db)  # MANDATORY — closes SQLite connections

    from .blueprints.dashboard.routes import bp as dashboard_bp
    from .blueprints.prompts.routes import bp as prompts_bp
    from .blueprints.testing.routes import bp as testing_bp

    app.register_blueprint(dashboard_bp)          # url_prefix='/'
    app.register_blueprint(prompts_bp)             # url_prefix='/prompts'
    app.register_blueprint(testing_bp)             # url_prefix='/testing'

    @app.context_processor
    def inject_api_key_status():
        return dict(api_key_configured=bool(os.environ.get('ANTHROPIC_API_KEY', '')))

    from .seed import register_seed_command
    register_seed_command(app)

    return app
