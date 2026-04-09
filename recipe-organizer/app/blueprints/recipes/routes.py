import math

from flask import abort, flash, redirect, render_template, request, url_for

from app.blueprints.recipes import recipes_bp
from app.db import get_db
from app.models import (
    ITEMS_PER_PAGE,
    create_recipe,
    delete_recipe,
    get_all_ingredients,
    get_all_recipes,
    get_ingredients_for_recipe,
    get_ingredients_for_recipes,
    get_recipe,
    get_recipe_count,
    set_recipe_ingredients,
    update_recipe,
)


@recipes_bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    if page < 1:
        return redirect(url_for("recipes.index", page=1))
    offset = (page - 1) * ITEMS_PER_PAGE
    with get_db() as conn:
        recipes = get_all_recipes(conn, limit=ITEMS_PER_PAGE, offset=offset)
        total = get_recipe_count(conn)
        total_pages = max(1, math.ceil(total / ITEMS_PER_PAGE))
        recipe_ids = [r["id"] for r in recipes]
        ingredients_map = get_ingredients_for_recipes(conn, recipe_ids)
    return render_template(
        "recipes/list.html",
        recipes=recipes,
        ingredients_map=ingredients_map,
        page=page,
        total_pages=total_pages,
    )


@recipes_bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        with get_db() as conn:
            all_ingredients = get_all_ingredients(conn, limit=1000, offset=0)
        return render_template(
            "recipes/form.html",
            recipe=None,
            all_ingredients=all_ingredients,
            selected_ingredients=[],
            is_edit=False,
        )

    title = request.form.get("title", "").strip()
    instructions = request.form.get("instructions", "").strip()
    description = request.form.get("description", "").strip()
    servings_raw = request.form.get("servings", "")
    prep_time_raw = request.form.get("prep_time_min", "")
    cook_time_raw = request.form.get("cook_time_min", "")

    with get_db() as conn:
        all_ingredients = get_all_ingredients(conn, limit=1000, offset=0)

    def rerender(**extra):
        ctx = dict(
            recipe=None,
            all_ingredients=all_ingredients,
            selected_ingredients=[],
            is_edit=False,
        )
        ctx.update(extra)
        return render_template("recipes/form.html", **ctx)

    if not title:
        flash("Title is required.", "error")
        return rerender()
    if len(title) > 200:
        flash("Title must be 200 characters or fewer.", "error")
        return rerender()
    if not instructions:
        flash("Instructions are required.", "error")
        return rerender()
    if len(instructions) > 10000:
        flash("Instructions must be 10000 characters or fewer.", "error")
        return rerender()
    if len(description) > 2000:
        flash("Description must be 2000 characters or fewer.", "error")
        return rerender()

    try:
        servings = int(servings_raw)
        if servings <= 0:
            flash("Servings must be greater than zero.", "error")
            return rerender()
    except (ValueError, TypeError):
        flash("Servings must be a valid number.", "error")
        return rerender()

    prep_time_min = None
    if prep_time_raw.strip():
        try:
            prep_time_min = int(prep_time_raw)
            if prep_time_min < 0:
                flash("Prep time cannot be negative.", "error")
                return rerender()
        except (ValueError, TypeError):
            flash("Prep time must be a valid number.", "error")
            return rerender()

    cook_time_min = None
    if cook_time_raw.strip():
        try:
            cook_time_min = int(cook_time_raw)
            if cook_time_min < 0:
                flash("Cook time cannot be negative.", "error")
                return rerender()
        except (ValueError, TypeError):
            flash("Cook time must be a valid number.", "error")
            return rerender()

    ingredient_ids = request.form.getlist("ingredient_id")
    quantities = request.form.getlist("quantity")
    units = request.form.getlist("unit")
    if not (len(ingredient_ids) == len(quantities) == len(units)):
        flash("Ingredient data is malformed.", "error")
        return rerender()
    ingredients_data = []
    seen_ids = set()
    for ing_id, qty, unit in zip(ingredient_ids, quantities, units):
        if not ing_id or not qty:
            continue
        try:
            parsed_id = int(ing_id)
            parsed_qty = float(qty)
        except (ValueError, TypeError):
            flash("Invalid ingredient data. Check quantities.", "error")
            return rerender()
        if parsed_qty <= 0:
            flash("Quantity must be greater than zero.", "error")
            return rerender()
        if parsed_id in seen_ids:
            continue
        seen_ids.add(parsed_id)
        ingredients_data.append(
            {"ingredient_id": parsed_id, "quantity": parsed_qty, "unit": unit.strip()}
        )

    with get_db(immediate=True) as conn:
        recipe_id = create_recipe(
            conn,
            title=title,
            description=description,
            instructions=instructions,
            servings=servings,
            prep_time_min=prep_time_min,
            cook_time_min=cook_time_min,
        )
        set_recipe_ingredients(conn, recipe_id, ingredients_data)

    flash("Recipe created successfully.", "success")
    return redirect(url_for("recipes.detail", recipe_id=recipe_id))


@recipes_bp.route("/<int:recipe_id>")
def detail(recipe_id):
    with get_db() as conn:
        recipe = get_recipe(conn, recipe_id)
        if recipe is None:
            abort(404)
        ingredients = get_ingredients_for_recipe(conn, recipe_id)
    return render_template(
        "recipes/detail.html", recipe=recipe, ingredients=ingredients
    )


@recipes_bp.route("/<int:recipe_id>/edit", methods=["GET", "POST"])
def edit(recipe_id):
    if request.method == "GET":
        with get_db() as conn:
            recipe = get_recipe(conn, recipe_id)
            if recipe is None:
                abort(404)
            all_ingredients = get_all_ingredients(conn, limit=1000, offset=0)
            raw_ingredients = get_ingredients_for_recipe(conn, recipe_id)
            selected_ingredients = [
                {
                    "ingredient_id": ing["ingredient_id"],
                    "quantity": ing["quantity"],
                    "unit": ing["unit"],
                }
                for ing in raw_ingredients
            ]
        return render_template(
            "recipes/form.html",
            recipe=recipe,
            all_ingredients=all_ingredients,
            selected_ingredients=selected_ingredients,
            is_edit=True,
        )

    with get_db() as conn:
        recipe = get_recipe(conn, recipe_id)
        if recipe is None:
            abort(404)
        all_ingredients = get_all_ingredients(conn, limit=1000, offset=0)

    title = request.form.get("title", "").strip()
    instructions = request.form.get("instructions", "").strip()
    description = request.form.get("description", "").strip()
    servings_raw = request.form.get("servings", "")
    prep_time_raw = request.form.get("prep_time_min", "")
    cook_time_raw = request.form.get("cook_time_min", "")

    def rerender(**extra):
        ctx = dict(
            recipe=recipe,
            all_ingredients=all_ingredients,
            selected_ingredients=[],
            is_edit=True,
        )
        ctx.update(extra)
        return render_template("recipes/form.html", **ctx)

    if not title:
        flash("Title is required.", "error")
        return rerender()
    if len(title) > 200:
        flash("Title must be 200 characters or fewer.", "error")
        return rerender()
    if not instructions:
        flash("Instructions are required.", "error")
        return rerender()
    if len(instructions) > 10000:
        flash("Instructions must be 10000 characters or fewer.", "error")
        return rerender()
    if len(description) > 2000:
        flash("Description must be 2000 characters or fewer.", "error")
        return rerender()

    try:
        servings = int(servings_raw)
        if servings <= 0:
            flash("Servings must be greater than zero.", "error")
            return rerender()
    except (ValueError, TypeError):
        flash("Servings must be a valid number.", "error")
        return rerender()

    prep_time_min = None
    if prep_time_raw.strip():
        try:
            prep_time_min = int(prep_time_raw)
            if prep_time_min < 0:
                flash("Prep time cannot be negative.", "error")
                return rerender()
        except (ValueError, TypeError):
            flash("Prep time must be a valid number.", "error")
            return rerender()

    cook_time_min = None
    if cook_time_raw.strip():
        try:
            cook_time_min = int(cook_time_raw)
            if cook_time_min < 0:
                flash("Cook time cannot be negative.", "error")
                return rerender()
        except (ValueError, TypeError):
            flash("Cook time must be a valid number.", "error")
            return rerender()

    ingredient_ids = request.form.getlist("ingredient_id")
    quantities = request.form.getlist("quantity")
    units = request.form.getlist("unit")
    if not (len(ingredient_ids) == len(quantities) == len(units)):
        flash("Ingredient data is malformed.", "error")
        return rerender()
    ingredients_data = []
    seen_ids = set()
    for ing_id, qty, unit in zip(ingredient_ids, quantities, units):
        if not ing_id or not qty:
            continue
        try:
            parsed_id = int(ing_id)
            parsed_qty = float(qty)
        except (ValueError, TypeError):
            flash("Invalid ingredient data. Check quantities.", "error")
            return rerender()
        if parsed_qty <= 0:
            flash("Quantity must be greater than zero.", "error")
            return rerender()
        if parsed_id in seen_ids:
            continue
        seen_ids.add(parsed_id)
        ingredients_data.append(
            {"ingredient_id": parsed_id, "quantity": parsed_qty, "unit": unit.strip()}
        )

    with get_db(immediate=True) as conn:
        update_recipe(
            conn,
            recipe_id,
            title=title,
            description=description,
            instructions=instructions,
            servings=servings,
            prep_time_min=prep_time_min,
            cook_time_min=cook_time_min,
        )
        set_recipe_ingredients(conn, recipe_id, ingredients_data)

    flash("Recipe updated successfully.", "success")
    return redirect(url_for("recipes.detail", recipe_id=recipe_id))


@recipes_bp.route("/<int:recipe_id>/delete", methods=["POST"])
def delete(recipe_id):
    with get_db(immediate=True) as conn:
        delete_recipe(conn, recipe_id)
    flash("Recipe deleted.", "success")
    return redirect(url_for("recipes.index"))
