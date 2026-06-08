import functools

from flask import (
    Blueprint,
    Flask,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    render_template_string,
    request,
    session,
    url_for,
)
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

from app.config import Config

csrf = CSRFProtect()

_API_BLUEPRINTS = ("ingest", "replay", "validate")

_LOGIN_TEMPLATE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>CPAA Replay - Login</title></head>
<body>
  <h1>CPAA Replay Login</h1>
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% for category, message in messages %}
      <p class="flash {{ category }}">{{ message }}</p>
    {% endfor %}
  {% endwith %}
  <form method="post" action="{{ url_for('auth.login') }}">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label for="password">Password</label>
    <input type="password" id="password" name="password" autocomplete="current-password">
    <button type="submit">Log in</button>
  </form>
</body>
</html>"""


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password and password == current_app.config["APP_PASSWORD"]:
            session.clear()
            session["user"] = "lab"
            return redirect(url_for("dashboard.index"))
        flash("Invalid password.", "error")
        return render_template_string(_LOGIN_TEMPLATE), 401
    return render_template_string(_LOGIN_TEMPLATE)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


def _is_api_request() -> bool:
    return request.blueprint in _API_BLUEPRINTS


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    csrf.init_app(app)

    _register_blueprints(app)
    _register_error_handlers(app)

    return app


def _register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.ingest_routes import ingest_bp
    app.register_blueprint(ingest_bp, url_prefix="/ingest")

    from app.replay_routes import replay_bp
    app.register_blueprint(replay_bp, url_prefix="/replay")

    from app.validator_routes import validate_bp
    app.register_blueprint(validate_bp, url_prefix="/validate")

    from app.dashboard_routes import dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix="/")


def _register_error_handlers(app):
    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return jsonify(error="CSRF token missing or invalid"), 403

    @app.errorhandler(400)
    def handle_bad_request(error):
        if _is_api_request():
            return jsonify(error="bad request"), 400
        return render_template("400.html"), 400

    @app.errorhandler(404)
    def handle_not_found(error):
        if _is_api_request():
            return jsonify(error="not found"), 404
        return render_template("404.html"), 404

    @app.errorhandler(409)
    def handle_conflict(error):
        return jsonify(error="a run is already in progress"), 409

    @app.errorhandler(413)
    def handle_payload_too_large(error):
        return jsonify(error="payload too large"), 413

    @app.errorhandler(500)
    def handle_internal_error(error):
        return jsonify(error="internal error"), 500
