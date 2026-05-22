import math
import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, url_for, abort

from app.db import get_db
from app.auth import login_required
from app.models.ingredient_models import (
    get_all_ingredients,
    get_ingredient,
    create_ingredient,
    update_ingredient,
    delete_ingredient,
)

bp = Blueprint('ingredients', __name__)

VALID_CATEGORIES = ('grain', 'hops', 'yeast', 'adjunct', 'other')


@bp.route('/')
@login_required
def list():
    conn = get_db()
    ingredients = get_all_ingredients(conn)
    return render_template('ingredients/list.html', ingredients=ingredients)


@bp.route('/new')
@login_required
def new():
    return render_template('ingredients/form.html', ingredient=None, categories=VALID_CATEGORIES)


@bp.route('/', methods=['POST'])
@login_required
def create():
    name = request.form.get('name', '').strip()
    if not name or len(name) > 200:
        flash('Ingredient name is required', 'error')
        return redirect(url_for('ingredients.new'))

    category = request.form.get('category', '')
    if category not in VALID_CATEGORIES:
        flash('Invalid category', 'error')
        return redirect(url_for('ingredients.new'))

    try:
        stock_qty = float(request.form.get('stock_qty', '0'))
        if not math.isfinite(stock_qty) or stock_qty < 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid stock quantity', 'error')
        return redirect(url_for('ingredients.new'))

    unit = request.form.get('unit', 'lb').strip()
    if not unit:
        unit = 'lb'

    try:
        low_stock_threshold = float(request.form.get('low_stock_threshold', '5.0'))
        if not math.isfinite(low_stock_threshold) or low_stock_threshold < 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid low stock threshold', 'error')
        return redirect(url_for('ingredients.new'))

    conn = get_db()
    try:
        ingredient_id = create_ingredient(conn, name, category, stock_qty, unit, low_stock_threshold)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Name already exists', 'error')
        return redirect(url_for('ingredients.new'))

    flash('Ingredient created successfully', 'success')
    return redirect(url_for('ingredients.detail', ingredient_id=ingredient_id))


@bp.route('/<int:ingredient_id>')
@login_required
def detail(ingredient_id):
    conn = get_db()
    ingredient = get_ingredient(conn, ingredient_id)
    if ingredient is None:
        abort(404)
    return render_template('ingredients/detail.html', ingredient=ingredient)


@bp.route('/<int:ingredient_id>/edit')
@login_required
def edit(ingredient_id):
    conn = get_db()
    ingredient = get_ingredient(conn, ingredient_id)
    if ingredient is None:
        abort(404)
    return render_template('ingredients/form.html', ingredient=ingredient, categories=VALID_CATEGORIES)


@bp.route('/<int:ingredient_id>/edit', methods=['POST'])
@login_required
def update(ingredient_id):
    conn = get_db()
    ingredient = get_ingredient(conn, ingredient_id)
    if ingredient is None:
        abort(404)

    name = request.form.get('name', '').strip()
    if not name or len(name) > 200:
        flash('Ingredient name is required', 'error')
        return redirect(url_for('ingredients.edit', ingredient_id=ingredient_id))

    category = request.form.get('category', '')
    if category not in VALID_CATEGORIES:
        flash('Invalid category', 'error')
        return redirect(url_for('ingredients.edit', ingredient_id=ingredient_id))

    try:
        stock_qty = float(request.form.get('stock_qty', '0'))
        if not math.isfinite(stock_qty) or stock_qty < 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid stock quantity', 'error')
        return redirect(url_for('ingredients.edit', ingredient_id=ingredient_id))

    unit = request.form.get('unit', 'lb').strip()
    if not unit:
        unit = 'lb'

    try:
        low_stock_threshold = float(request.form.get('low_stock_threshold', '5.0'))
        if not math.isfinite(low_stock_threshold) or low_stock_threshold < 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid low stock threshold', 'error')
        return redirect(url_for('ingredients.edit', ingredient_id=ingredient_id))

    try:
        update_ingredient(conn, ingredient_id, name, category, stock_qty, unit, low_stock_threshold)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Name already exists', 'error')
        return redirect(url_for('ingredients.edit', ingredient_id=ingredient_id))

    flash('Ingredient updated successfully', 'success')
    return redirect(url_for('ingredients.detail', ingredient_id=ingredient_id))


@bp.route('/<int:ingredient_id>/delete', methods=['POST'])
@login_required
def delete(ingredient_id):
    conn = get_db()
    ingredient = get_ingredient(conn, ingredient_id)
    if ingredient is None:
        abort(404)

    try:
        delete_ingredient(conn, ingredient_id)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Cannot delete: ingredient is used in recipes', 'error')
        return redirect(url_for('ingredients.detail', ingredient_id=ingredient_id))

    flash('Ingredient deleted successfully', 'success')
    return redirect(url_for('ingredients.list'))
