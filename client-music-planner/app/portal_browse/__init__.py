from flask import Blueprint

bp = Blueprint('portal_browse', __name__)

from . import routes  # noqa: E402, F401
