from flask import Blueprint

tags_bp = Blueprint('tags', __name__)

from app.blueprints.tags import routes  # noqa: E402, F401
