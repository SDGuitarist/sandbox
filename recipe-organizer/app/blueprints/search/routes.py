import math

from flask import render_template, request

from app.blueprints.search import search_bp
from app.db import get_db
from app.models import (
    ITEMS_PER_PAGE,
    get_ingredients_for_recipes,
    search_recipe_count,
    search_recipes_by_ingredients,
)


@search_bp.route("/")
def search():
    query = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    offset = (page - 1) * ITEMS_PER_PAGE
    with get_db() as conn:
        recipes = search_recipes_by_ingredients(conn, query, ITEMS_PER_PAGE, offset)
        total = search_recipe_count(conn, query)
        total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
        recipe_ids = [r["id"] for r in recipes]
        ingredients_map = get_ingredients_for_recipes(conn, recipe_ids)
    return render_template(
        "search/results.html",
        recipes=recipes,
        ingredients_map=ingredients_map,
        query=query,
        page=page,
        total_pages=total_pages,
    )
