from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.db import get_db
from app.models.ingredient_models import (
    create_ingredient,
    get_all_ingredients,
    get_ingredient,
    update_ingredient,
    delete_ingredient,
    set_ingredient_allergens,
    get_ingredient_allergens,
)
from app.models.core_models import get_all_allergens
from app.models.supplier_models import get_all_suppliers
from app.models.inventory_models import get_stock_movements

bp = Blueprint('ingredients', __name__)


@bp.route('/')
def list_ingredients():
    conn = get_db()
    ingredients = get_all_ingredients(conn)
    return render_template('ingredients/list.html', ingredients=ingredients)


@bp.route('/create', methods=['GET'])
def create_form():
    conn = get_db()
    suppliers = get_all_suppliers(conn)
    allergens = get_all_allergens(conn)
    return render_template(
        'ingredients/form.html',
        ingredient=None,
        suppliers=suppliers,
        allergens=allergens,
        ingredient_allergens=[],
    )


@bp.route('/create', methods=['POST'])
def create():
    conn = get_db()

    # Validate name
    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Name is required.', 'error')
        return redirect(request.url)

    # Unit
    unit = request.form.get('unit', 'g').strip()[:50]
    if not unit:
        unit = 'g'

    # Unit cost: decimal dollars -> integer cents
    raw_cost = request.form.get('unit_cost', '0')
    try:
        unit_cost_cents = int(round(float(raw_cost) * 100))
        if unit_cost_cents < 0:
            unit_cost_cents = 0
    except (ValueError, TypeError):
        unit_cost_cents = 0

    # Supplier ID (optional)
    raw_supplier = request.form.get('supplier_id', '')
    supplier_id = None
    if raw_supplier:
        try:
            supplier_id = int(raw_supplier)
        except (ValueError, TypeError):
            supplier_id = None

    # Low stock threshold
    raw_threshold = request.form.get('low_stock_threshold', '0')
    try:
        low_stock_threshold = float(raw_threshold)
        if low_stock_threshold < 0:
            low_stock_threshold = 0
    except (ValueError, TypeError):
        low_stock_threshold = 0

    # Allergen IDs (checkboxes)
    raw_allergen_ids = request.form.getlist('allergen_ids')
    allergen_ids = []
    for aid in raw_allergen_ids:
        try:
            allergen_ids.append(int(aid))
        except (ValueError, TypeError):
            pass

    conn.execute("BEGIN")
    ingredient_id = create_ingredient(
        conn, name, unit, unit_cost_cents, supplier_id, low_stock_threshold
    )
    set_ingredient_allergens(conn, ingredient_id, allergen_ids)
    conn.commit()

    flash('Ingredient created successfully.', 'success')
    return redirect(url_for('ingredients.detail', id=ingredient_id))


@bp.route('/<int:id>')
def detail(id):
    conn = get_db()
    ingredient = get_ingredient(conn, id)
    if ingredient is None:
        flash('Ingredient not found.', 'error')
        return redirect(url_for('ingredients.list_ingredients'))

    allergens = get_ingredient_allergens(conn, id)
    movements = get_stock_movements(conn, id)
    return render_template(
        'ingredients/detail.html',
        ingredient=ingredient,
        allergens=allergens,
        movements=movements,
    )


@bp.route('/<int:id>/edit', methods=['GET'])
def edit_form(id):
    conn = get_db()
    ingredient = get_ingredient(conn, id)
    if ingredient is None:
        flash('Ingredient not found.', 'error')
        return redirect(url_for('ingredients.list_ingredients'))

    suppliers = get_all_suppliers(conn)
    allergens = get_all_allergens(conn)
    ingredient_allergens = get_ingredient_allergens(conn, id)
    return render_template(
        'ingredients/form.html',
        ingredient=ingredient,
        suppliers=suppliers,
        allergens=allergens,
        ingredient_allergens=ingredient_allergens,
    )


@bp.route('/<int:id>/edit', methods=['POST'])
def edit(id):
    conn = get_db()
    ingredient = get_ingredient(conn, id)
    if ingredient is None:
        flash('Ingredient not found.', 'error')
        return redirect(url_for('ingredients.list_ingredients'))

    # Validate name
    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Name is required.', 'error')
        return redirect(request.url)

    # Unit
    unit = request.form.get('unit', 'g').strip()[:50]
    if not unit:
        unit = 'g'

    # Unit cost: decimal dollars -> integer cents
    raw_cost = request.form.get('unit_cost', '0')
    try:
        unit_cost_cents = int(round(float(raw_cost) * 100))
        if unit_cost_cents < 0:
            unit_cost_cents = 0
    except (ValueError, TypeError):
        unit_cost_cents = 0

    # Supplier ID (optional)
    raw_supplier = request.form.get('supplier_id', '')
    supplier_id = None
    if raw_supplier:
        try:
            supplier_id = int(raw_supplier)
        except (ValueError, TypeError):
            supplier_id = None

    # Low stock threshold
    raw_threshold = request.form.get('low_stock_threshold', '0')
    try:
        low_stock_threshold = float(raw_threshold)
        if low_stock_threshold < 0:
            low_stock_threshold = 0
    except (ValueError, TypeError):
        low_stock_threshold = 0

    # Allergen IDs (checkboxes)
    raw_allergen_ids = request.form.getlist('allergen_ids')
    allergen_ids = []
    for aid in raw_allergen_ids:
        try:
            allergen_ids.append(int(aid))
        except (ValueError, TypeError):
            pass

    conn.execute("BEGIN")
    update_ingredient(conn, id, name, unit, unit_cost_cents, supplier_id, low_stock_threshold)
    set_ingredient_allergens(conn, id, allergen_ids)
    conn.commit()

    flash('Ingredient updated successfully.', 'success')
    return redirect(url_for('ingredients.detail', id=id))


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    conn = get_db()
    ingredient = get_ingredient(conn, id)
    if ingredient is None:
        flash('Ingredient not found.', 'error')
        return redirect(url_for('ingredients.list_ingredients'))

    conn.execute("BEGIN")
    delete_ingredient(conn, id)
    conn.commit()

    flash('Ingredient deleted successfully.', 'success')
    return redirect(url_for('ingredients.list_ingredients'))
