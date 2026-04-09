from flask import Blueprint

recipes_bp = Blueprint("recipes", __name__)

from app.blueprints.recipes import routes
