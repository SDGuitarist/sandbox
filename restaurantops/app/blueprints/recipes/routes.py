from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.db import get_db
from app.models.recipe_models import (
    calculate_recipe_cost,
    create_recipe,
    delete_recipe,
    get_all_recipes,
    get_recipe,
    get_recipe_allergens,
    get_recipe_ingredients,
    set_recipe_ingredients,
    update_recipe,
)
from app.models.ingredient_models import get_all_ingredients

bp = Blueprint('recipes', __name__)


@bp.route('/')
def list_recipes():
    conn = get_db()
    recipes = get_all_recipes(conn)
    return render_template('recipes/list.html', recipes=recipes)


@bp.route('/create', methods=['GET'])
def create_form():
    conn = get_db()
    ingredients = get_all_ingredients(conn)
    return render_template(
        'recipes/form.html',
        recipe=None,
        ingredients=ingredients,
        recipe_ingredients=[],
    )


@bp.route('/create', methods=['POST'])
def create():
    conn = get_db()

    # Validate name
    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Name is required.', 'error')
        return redirect(request.url)

    description = request.form.get('description', '').strip()[:2000]
    instructions = request.form.get('instructions', '').strip()[:5000]

    # Integer fields with safe parsing
    try:
        prep_time_minutes = int(request.form.get('prep_time_minutes', 0))
        if prep_time_minutes < 0:
            prep_time_minutes = 0
    except (ValueError, TypeError):
        prep_time_minutes = 0

    try:
        cook_time_minutes = int(request.form.get('cook_time_minutes', 0))
        if cook_time_minutes < 0:
            cook_time_minutes = 0
    except (ValueError, TypeError):
        cook_time_minutes = 0

    try:
        servings = int(request.form.get('servings', 1))
        if servings < 1:
            servings = 1
    except (ValueError, TypeError):
        servings = 1

    # Parallel arrays: ingredient_ids[], quantities[], units[]
    ingredient_ids = request.form.getlist('ingredient_ids[]')
    quantities = request.form.getlist('quantities[]')
    units = request.form.getlist('units[]')

    # FC4: MUST validate len equality before zip
    if not (len(ingredient_ids) == len(quantities) == len(units)):
        flash('Form data mismatch. Please try again.', 'error')
        return redirect(request.url)

    # Parse parallel arrays
    parsed_ids = []
    parsed_qtys = []
    parsed_units = []
    for raw_id, raw_qty, raw_unit in zip(ingredient_ids, quantities, units):
        try:
            parsed_ids.append(int(raw_id))
        except (ValueError, TypeError):
            flash('Invalid ingredient selected.', 'error')
            return redirect(request.url)
        try:
            qty = float(raw_qty)
            if qty <= 0:
                flash('Quantities must be positive.', 'error')
                return redirect(request.url)
            parsed_qtys.append(qty)
        except (ValueError, TypeError):
            flash('Invalid quantity value.', 'error')
            return redirect(request.url)
        parsed_units.append(raw_unit.strip()[:20])

    conn.execute("BEGIN")
    recipe_id = create_recipe(
        conn, name, description, instructions,
        prep_time_minutes, cook_time_minutes, servings,
    )
    if parsed_ids:
        set_recipe_ingredients(conn, recipe_id, parsed_ids, parsed_qtys, parsed_units)
    conn.commit()

    flash('Recipe created successfully.', 'success')
    return redirect(url_for('recipes.detail', id=recipe_id))


@bp.route('/<int:id>')
def detail(id):
    conn = get_db()
    recipe = get_recipe(conn, id)
    if recipe is None:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    ingredients = get_recipe_ingredients(conn, id)
    allergens = get_recipe_allergens(conn, id)
    cost_cents = calculate_recipe_cost(conn, id)

    return render_template(
        'recipes/detail.html',
        recipe=recipe,
        ingredients=ingredients,
        allergens=allergens,
        cost_cents=cost_cents,
    )


@bp.route('/<int:id>/edit', methods=['GET'])
def edit_form(id):
    conn = get_db()
    recipe = get_recipe(conn, id)
    if recipe is None:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    ingredients = get_all_ingredients(conn)
    recipe_ingredients = get_recipe_ingredients(conn, id)

    return render_template(
        'recipes/form.html',
        recipe=recipe,
        ingredients=ingredients,
        recipe_ingredients=recipe_ingredients,
    )


@bp.route('/<int:id>/edit', methods=['POST'])
def edit(id):
    conn = get_db()
    recipe = get_recipe(conn, id)
    if recipe is None:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    # Validate name
    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Name is required.', 'error')
        return redirect(request.url)

    description = request.form.get('description', '').strip()[:2000]
    instructions = request.form.get('instructions', '').strip()[:5000]

    # Integer fields with safe parsing
    try:
        prep_time_minutes = int(request.form.get('prep_time_minutes', 0))
        if prep_time_minutes < 0:
            prep_time_minutes = 0
    except (ValueError, TypeError):
        prep_time_minutes = 0

    try:
        cook_time_minutes = int(request.form.get('cook_time_minutes', 0))
        if cook_time_minutes < 0:
            cook_time_minutes = 0
    except (ValueError, TypeError):
        cook_time_minutes = 0

    try:
        servings = int(request.form.get('servings', 1))
        if servings < 1:
            servings = 1
    except (ValueError, TypeError):
        servings = 1

    # Parallel arrays: ingredient_ids[], quantities[], units[]
    ingredient_ids = request.form.getlist('ingredient_ids[]')
    quantities = request.form.getlist('quantities[]')
    units = request.form.getlist('units[]')

    # FC4: MUST validate len equality before zip
    if not (len(ingredient_ids) == len(quantities) == len(units)):
        flash('Form data mismatch. Please try again.', 'error')
        return redirect(request.url)

    # Parse parallel arrays
    parsed_ids = []
    parsed_qtys = []
    parsed_units = []
    for raw_id, raw_qty, raw_unit in zip(ingredient_ids, quantities, units):
        try:
            parsed_ids.append(int(raw_id))
        except (ValueError, TypeError):
            flash('Invalid ingredient selected.', 'error')
            return redirect(request.url)
        try:
            qty = float(raw_qty)
            if qty <= 0:
                flash('Quantities must be positive.', 'error')
                return redirect(request.url)
            parsed_qtys.append(qty)
        except (ValueError, TypeError):
            flash('Invalid quantity value.', 'error')
            return redirect(request.url)
        parsed_units.append(raw_unit.strip()[:20])

    conn.execute("BEGIN")
    update_recipe(
        conn, id, name, description, instructions,
        prep_time_minutes, cook_time_minutes, servings,
    )
    set_recipe_ingredients(conn, id, parsed_ids, parsed_qtys, parsed_units)
    conn.commit()

    flash('Recipe updated successfully.', 'success')
    return redirect(url_for('recipes.detail', id=id))


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    conn = get_db()
    recipe = get_recipe(conn, id)
    if recipe is None:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    conn.execute("BEGIN")
    delete_recipe(conn, id)
    conn.commit()

    flash('Recipe deleted successfully.', 'success')
    return redirect(url_for('recipes.list_recipes'))
