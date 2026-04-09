import os
import secrets
from flask import Flask, session, request, abort, render_template
from .utils import format_dollars


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(24))
    if db_path is None:
        db_path = "finance.db"
    app.config["DB_PATH"] = db_path
    app.jinja_env.filters["dollars"] = format_dollars

    from .db import init_db
    with app.app_context():
        init_db(app)

    @app.before_request
    def csrf_protect():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        if request.method == "POST":
            token = request.form.get("csrf_token")
            if not token or token != session.get("csrf_token"):
                abort(403)

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": session.get("csrf_token", "")}

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html", message="Page not found."), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html",
                               message="Request forbidden. Your session may have expired. Please go back and try again."), 403

    from .blueprints.categories import categories_bp
    from .blueprints.transactions import transactions_bp
    from .blueprints.views import views_bp
    app.register_blueprint(categories_bp, url_prefix="/categories")
    app.register_blueprint(transactions_bp, url_prefix="/transactions")
    app.register_blueprint(views_bp)

    return app
