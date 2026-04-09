from flask import Blueprint

ingredients_bp = Blueprint("ingredients", __name__)

from app.blueprints.ingredients import routes
