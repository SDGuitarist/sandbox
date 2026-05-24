from flask import Blueprint

habits_bp = Blueprint("habits", __name__)

from app.blueprints.habits import routes  # noqa: E402, F401
