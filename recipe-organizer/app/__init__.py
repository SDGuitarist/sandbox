import secrets
from flask import Flask, session, request, abort, redirect, url_for, render_template


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = secrets.token_hex(24)

    if db_path is None:
        db_path = "recipes.db"
    app.config["DB_PATH"] = db_path

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
        return render_template("errors/404.html",
                               message="Page not found."), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html",
                               message="Request forbidden. Your session may "
                                       "have expired. Please go back and try "
                                       "again."), 403

    from .blueprints.recipes import recipes_bp
    from .blueprints.ingredients import ingredients_bp
    from .blueprints.search import search_bp
    app.register_blueprint(recipes_bp, url_prefix="/recipes")
    app.register_blueprint(ingredients_bp, url_prefix="/ingredients")
    app.register_blueprint(search_bp, url_prefix="/search")

    @app.route("/")
    def home():
        return redirect(url_for("recipes.index"))

    return app
