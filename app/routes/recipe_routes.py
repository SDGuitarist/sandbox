import sqlite3
import math
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app.db import get_db
from app.auth import login_required
from app.models.recipe_models import (
    get_all_recipes, get_recipe, create_recipe, update_recipe, delete_recipe
)
from app.models.recipe_ingredient_models import (
    get_recipe_ingredients, add_recipe_ingredient, remove_recipe_ingredient
)
from app.models.ingredient_models import get_all_ingredients, get_ingredient

bp = Blueprint('recipes', __name__)


# GET /recipes/ -> recipes.list
@bp.route('/')
@login_required
def list():
    conn = get_db()
    recipes = get_all_recipes(conn)
    return render_template('recipes/list.html', recipes=recipes)


# GET /recipes/new -> recipes.new
@bp.route('/new')
@login_required
def new():
    return render_template('recipes/form.html', recipe=None)


# POST /recipes/ -> recipes.create
@bp.route('/', methods=['POST'])
@login_required
def create():
    name = request.form.get('name', '').strip()
    style = request.form.get('style', '').strip()[:100]
    target_abv_str = request.form.get('target_abv', '').strip()
    notes = request.form.get('notes', '').strip()

    # Validate name: required, 1-200 chars
    if not name or len(name) > 200:
        flash('Recipe name is required', 'error')
        return redirect(url_for('recipes.new'))

    # Validate target_abv: optional float 0-100
    target_abv = None
    if target_abv_str:
        try:
            target_abv = float(target_abv_str)
            if not math.isfinite(target_abv) or target_abv < 0 or target_abv > 100:
                raise ValueError
        except (ValueError, TypeError):
            flash('Invalid ABV', 'error')
            return redirect(url_for('recipes.new'))

    conn = get_db()
    try:
        recipe_id = create_recipe(conn, name, style, target_abv, notes)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Name already exists', 'error')
        return redirect(url_for('recipes.new'))

    flash('Recipe created successfully', 'success')
    return redirect(url_for('recipes.detail', recipe_id=recipe_id))


# GET /recipes/<int:recipe_id> -> recipes.detail
@bp.route('/<int:recipe_id>')
@login_required
def detail(recipe_id):
    conn = get_db()
    recipe = get_recipe(conn, recipe_id)
    if recipe is None:
        abort(404)
    ingredients = get_recipe_ingredients(conn, recipe_id)
    all_ingredients = get_all_ingredients(conn)
    return render_template('recipes/detail.html',
                           recipe=recipe,
                           ingredients=ingredients,
                           all_ingredients=all_ingredients)


# GET /recipes/<int:recipe_id>/edit -> recipes.edit
@bp.route('/<int:recipe_id>/edit')
@login_required
def edit(recipe_id):
    conn = get_db()
    recipe = get_recipe(conn, recipe_id)
    if recipe is None:
        abort(404)
    return render_template('recipes/form.html', recipe=recipe)


# POST /recipes/<int:recipe_id>/edit -> recipes.update
@bp.route('/<int:recipe_id>/edit', methods=['POST'])
@login_required
def update(recipe_id):
    conn = get_db()
    recipe = get_recipe(conn, recipe_id)
    if recipe is None:
        abort(404)

    name = request.form.get('name', '').strip()
    style = request.form.get('style', '').strip()[:100]
    target_abv_str = request.form.get('target_abv', '').strip()
    notes = request.form.get('notes', '').strip()

    # Validate name: required, 1-200 chars
    if not name or len(name) > 200:
        flash('Recipe name is required', 'error')
        return redirect(url_for('recipes.edit', recipe_id=recipe_id))

    # Validate target_abv: optional float 0-100
    target_abv = None
    if target_abv_str:
        try:
            target_abv = float(target_abv_str)
            if not math.isfinite(target_abv) or target_abv < 0 or target_abv > 100:
                raise ValueError
        except (ValueError, TypeError):
            flash('Invalid ABV', 'error')
            return redirect(url_for('recipes.edit', recipe_id=recipe_id))

    try:
        update_recipe(conn, recipe_id, name, style, target_abv, notes)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Name already exists', 'error')
        return redirect(url_for('recipes.edit', recipe_id=recipe_id))

    flash('Recipe updated successfully', 'success')
    return redirect(url_for('recipes.detail', recipe_id=recipe_id))


# POST /recipes/<int:recipe_id>/delete -> recipes.delete
@bp.route('/<int:recipe_id>/delete', methods=['POST'])
@login_required
def delete(recipe_id):
    conn = get_db()
    recipe = get_recipe(conn, recipe_id)
    if recipe is None:
        abort(404)

    try:
        delete_recipe(conn, recipe_id)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Cannot delete: recipe is used in batches', 'error')
        return redirect(url_for('recipes.detail', recipe_id=recipe_id))

    flash('Recipe deleted successfully', 'success')
    return redirect(url_for('recipes.list'))


# POST /recipes/<int:recipe_id>/ingredients -> recipes.add_ingredient
@bp.route('/<int:recipe_id>/ingredients', methods=['POST'])
@login_required
def add_ingredient(recipe_id):
    conn = get_db()
    recipe = get_recipe(conn, recipe_id)
    if recipe is None:
        abort(404)

    # Validate ingredient_id
    try:
        ingredient_id = int(request.form.get('ingredient_id', ''))
    except (ValueError, TypeError):
        flash('Invalid ingredient', 'error')
        return redirect(url_for('recipes.detail', recipe_id=recipe_id))

    # Validate quantity: float > 0
    try:
        quantity = float(request.form.get('quantity', ''))
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Quantity must be positive', 'error')
        return redirect(url_for('recipes.detail', recipe_id=recipe_id))

    unit = request.form.get('unit', 'lb').strip()

    # Verify ingredient exists
    ingredient = get_ingredient(conn, ingredient_id)
    if ingredient is None:
        flash('Invalid ingredient', 'error')
        return redirect(url_for('recipes.detail', recipe_id=recipe_id))

    try:
        add_recipe_ingredient(conn, recipe_id, ingredient_id, quantity, unit)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('This ingredient is already in the recipe', 'error')
        return redirect(url_for('recipes.detail', recipe_id=recipe_id))

    flash('Ingredient added to recipe', 'success')
    return redirect(url_for('recipes.detail', recipe_id=recipe_id))


# POST /recipes/<int:recipe_id>/ingredients/<int:ri_id>/delete -> recipes.remove_ingredient
@bp.route('/<int:recipe_id>/ingredients/<int:ri_id>/delete', methods=['POST'])
@login_required
def remove_ingredient(recipe_id, ri_id):
    conn = get_db()
    recipe = get_recipe(conn, recipe_id)
    if recipe is None:
        abort(404)

    if not remove_recipe_ingredient(conn, ri_id, recipe_id):
        abort(404)
    conn.commit()

    flash('Ingredient removed from recipe', 'success')
    return redirect(url_for('recipes.detail', recipe_id=recipe_id))
