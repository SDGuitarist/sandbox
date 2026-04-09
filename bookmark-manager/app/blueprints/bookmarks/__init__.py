from flask import Blueprint

bookmarks_bp = Blueprint('bookmarks', __name__)

from app.blueprints.bookmarks import routes  # noqa: E402, F401
